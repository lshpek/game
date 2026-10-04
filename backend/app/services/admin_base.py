"""Shared plumbing for the admin control services.

``AdminServiceBase`` owns everything both the read and the write halves need:
the collaborator services, the audit claim/finish cycle, and the state snapshot
written to the audit log. Splitting the concrete service into a read mixin and
an action mixin keeps each file reviewable while callers still see one
``AdminService`` API.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import NotFoundError
from app.core.locks import user_lock
from app.core.logging import get_logger
from app.core.security import hash_secret
from app.core.timeutils import as_aware
from app.models.enums import AdminAction, AdminCategory
from app.models.user import User
from app.services.achievements import AchievementService
from app.services.admin_audit import AdminAuditService, duration_ms, snapshot
from app.services.cosmetics import CosmeticService
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.events import EventService
from app.services.leaderboards import PlateLeaderboardService
from app.services.missions import MissionService
from app.services.plates import PlateService
from app.services.premium import PremiumService
from app.services.progression import ProgressionService
from app.services.seasons import SeasonService
from app.services.test_lab import TestLabService

logger = get_logger("app.services.admin")

# Shared lock id for operations that are not scoped to a single player.
GLOBAL_LOCK_ID = 0

ANALYTICS_PERIODS: dict[str, int | None] = {
    "today": 0,
    "7d": 7,
    "30d": 30,
    "all": None,
}


@dataclass(slots=True)
class AdminActor:
    """The verified administrator behind a request."""

    telegram_id: int
    user_id: int | None = None


class AdminServiceBase:
    """Collaborators, audit plumbing and shared state helpers."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.audit = AdminAuditService(db)
        self.economy = EconomyService(db)
        self.plates = PlateService(db)
        self.progression = ProgressionService(db)
        self.premium = PremiumService(db, self.settings)
        self.daily = DailyService(db, self.settings)
        self.missions = MissionService(db, self.economy)
        self.cosmetics = CosmeticService(db)
        self.achievements = AchievementService(db)
        self.season_service = SeasonService(db)
        self.event_service = EventService(db)
        self.leaderboards = PlateLeaderboardService(db)
        self.test_lab = TestLabService(db, self.settings)

    # ------------------------------------------------------------------
    # mutation plumbing
    # ------------------------------------------------------------------
    def _mutate(
        self,
        actor: AdminActor,
        *,
        action: AdminAction | str,
        category: AdminCategory | str,
        operation_id: str,
        work: Callable[[], dict[str, Any]],
        target_user: User | None = None,
        target_user_id: int | None = None,
        amount: int | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
        lock_id: int | None = None,
    ) -> dict[str, Any]:
        """Run one audited, idempotent mutation.

        ``work`` performs the mutation and returns the JSON-serialisable result
        that is stored on the audit row and returned to the caller. It is invoked
        at most once per ``operation_id``.
        """
        target_id = target_user_id if target_user_id is not None else (target_user.id if target_user else None)
        lock_key = lock_id if lock_id is not None else (target_id if target_id is not None else GLOBAL_LOCK_ID)
        start = time.perf_counter()

        with user_lock(lock_key, "admin"):
            row, is_new = self.audit.claim(
                action=str(action),
                category=str(category),
                admin_telegram_id=actor.telegram_id,
                admin_user_id=actor.user_id,
                target_user_id=target_id,
                target_telegram_id=int(target_user.telegram_id) if target_user else None,
                amount=amount,
                reason=reason,
                metadata=metadata,
                operation_id=operation_id,
                request_id=request_id,
            )
            if not is_new:
                # The exact same operation already ran - return its result.
                logger.info(
                    "admin_action_replayed",
                    extra={"action": str(action), "telegram_id": actor.telegram_id, "user_id": target_id},
                )
                return {"replayed": True, "audit_id": row.id, **(row.after_json or {})}

            logger.info(
                "admin_action_started",
                extra={"action": str(action), "telegram_id": actor.telegram_id, "user_id": target_id},
            )
            before = self._user_state(target_user) if target_user is not None else None
            try:
                result = work()
            except Exception:
                self.db.rollback()
                logger.error(
                    "admin_action_failed",
                    extra={"action": str(action), "telegram_id": actor.telegram_id, "user_id": target_id},
                    exc_info=True,
                )
                raise

            if before is not None:
                row.before_json = before
            # The stored ``after`` mixes the operation's own result with a fresh
            # snapshot of the player, so the audit row shows a real diff.
            after = result if target_user is None else {**result, **self._user_state(target_user)}
            self.audit.finish(row, after=after, amount=amount, duration_ms=duration_ms(start))
            self.db.commit()
            self.db.refresh(row)
            logger.info(
                "admin_action_completed",
                extra={
                    "action": str(action),
                    "telegram_id": actor.telegram_id,
                    "user_id": target_id,
                    "status_code": 0,
                    "duration_ms": duration_ms(start),
                },
            )
            return {"replayed": False, "audit_id": row.id, **result}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def require_user(self, user_id: int) -> User:
        user = self.db.get(User, int(user_id))
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        return user

    def _is_protected_admin(self, user: User) -> bool:
        return int(user.telegram_id) in {int(value) for value in self.settings.admin_telegram_ids}

    @staticmethod
    def user_label(user: User) -> str:
        return f"@{user.username}" if user.username else user.display_name

    def _user_state(self, user: User) -> dict[str, Any]:
        """Small, whitelist-friendly snapshot for the audit log."""
        entitlement = self.premium.active_entitlement(user.id)
        expires = as_aware(entitlement.expires_at) if entitlement else None
        return snapshot(
            {
                "coins": self.economy.balance(user.id),
                "bonus_rolls": int(user.bonus_rolls),
                "daily_rolls_used": int(user.daily_rolls_used),
                "collection_xp": int(user.collection_xp),
                "collector_level": int(user.collector_level),
                "current_streak": int(user.current_streak),
                "longest_streak": int(user.longest_streak),
                "plates_count": int(user.plates_count),
                "countries_count": int(user.countries_count),
                "first_discoveries_count": int(user.first_discoveries_count),
                "total_rolls": int(user.total_rolls),
                "is_banned": bool(user.is_banned),
                "premium_tier": entitlement.tier if entitlement else None,
                "premium_expires_at": expires.isoformat() if expires else None,
            }
        )


def _name_conditions(query: str | None) -> list[Any]:
    """Username / first-name / last-name / id search, one token per token.

    Tokens are ANDed so ``"alex sm"`` finds "Alex Smit" without needing a
    database-specific string-concat operator.
    """
    cleaned = (query or "").strip().lstrip("@")
    if not cleaned:
        return []

    if cleaned.isdigit():
        numeric = int(cleaned)
        return [or_(User.telegram_id == numeric, User.id == numeric)]

    conditions = []
    for token in cleaned.split()[:4]:
        pattern = f"%{token}%"
        conditions.append(
            or_(
                User.username.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
        )
    return conditions


def collection_amount(value: int) -> int:
    """Plate grants record the NUMORA a collectible is worth, not a coin delta."""
    return int(value)


def _flow_sum(db: Session, column, time_column, since, *, incoming: bool) -> int:
    """Absolute SUM of a signed column over a window (issued / spent NUMORA)."""
    conditions = [column > 0] if incoming else [column < 0]
    if since is not None:
        conditions.append(time_column >= since)
    value = int(db.execute(select(func.coalesce(func.sum(column), 0)).where(*conditions)).scalar_one() or 0)
    return abs(value)


def _short(message: str, limit: int = 160) -> str:
    """One-line error preview. Never a stack trace, never a secret."""
    cleaned = " ".join(str(message or "").split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


def _fingerprint(secret: str) -> str:
    """Non-reversible fingerprint so an operator can verify a token is set."""
    if not secret or secret == "CHANGE_ME":
        return "-"
    return hash_secret(secret)[:12]
