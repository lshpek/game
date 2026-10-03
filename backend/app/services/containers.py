"""Container catalogue access and server-side box opening."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import ContainerUnavailableError, NotFoundError
from app.core.locks import user_lock
from app.core.timeutils import utcnow
from app.game.analyzer import analyze, combine_with_luck
from app.game.rarity import RARITY_RANK, Rarity, max_rarity
from app.game.rng import Rng, default_rng, random_number, roll_rarity
from app.game.valuation import compute_value, duplicate_conversion_reward
from app.models.container import Container, ContainerOpening
from app.models.enums import AnalyticsEventName, TransactionType
from app.models.number import Number
from app.models.user import User
from app.services.achievements import AchievementService, summarize
from app.services.analytics import AnalyticsService
from app.services.economy import EconomyService
from app.services.numbers import NumberService
from app.services.premium import PremiumService


@dataclass(slots=True)
class OpeningOutcome:
    opening: ContainerOpening
    container: Container
    number: Number
    is_duplicate: bool
    value: int
    balance: int
    conversion_value: int
    unlocked_achievements: list[dict[str, object]] = field(default_factory=list)
    replayed: bool = False


class ContainerService:
    """Lists boxes, validates purchases and resolves loot server side."""

    def __init__(self, db: Session, config: Settings | None = None, rng: Rng | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.rng = rng or default_rng()
        self.economy = EconomyService(db)
        self.numbers = NumberService(db)
        self.premium = PremiumService(db, self.settings)
        self.achievements = AchievementService(db)
        self.analytics = AnalyticsService(db)

    # --- catalogue ------------------------------------------------------
    def list_containers(self, user: User | None = None) -> list[dict[str, object]]:
        rows = (
            self.db.execute(
                select(Container)
                .where(Container.is_active.is_(True))
                .order_by(Container.sort_order, Container.id)
            )
            .scalars()
            .all()
        )
        unlocked = self.premium.unlocked_containers(user.id) if user else set()
        has_premium = bool(user and self.premium.is_premium(user.id))
        balance = self.economy.balance(user.id) if user else 0

        result: list[dict[str, object]] = []
        for row in rows:
            locked = bool(row.premium_only) and not has_premium
            result.append(
                {
                    "code": row.code,
                    "name": row.name,
                    "description": row.description,
                    "price": int(row.price),
                    "minimum_rarity": row.minimum_rarity,
                    "rarity_weights": dict(row.rarity_weights or {}),
                    "accent": row.accent,
                    "animation": row.animation,
                    "premium_only": bool(row.premium_only),
                    "locked": locked,
                    "affordable": balance >= int(row.price),
                    "granted_by_premium": row.code in unlocked,
                }
            )
        return result

    def get_container(self, code: str) -> Container:
        row = self.db.execute(
            select(Container).where(Container.code == code, Container.is_active.is_(True))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Container not found.", code="CONTAINER_NOT_FOUND")
        return row

    @staticmethod
    def rarity_rank(value: str) -> int:
        return RARITY_RANK.get(value, 0)

    # --- opening --------------------------------------------------------
    def open_container(self, user: User, code: str, *, idempotency_key: str | None = None) -> OpeningOutcome:
        container = self.get_container(code)

        if container.premium_only and not self.premium.is_premium(user.id):
            raise ContainerUnavailableError("This container requires a Pro subscription.")

        if idempotency_key:
            existing = self.db.execute(
                select(ContainerOpening).where(
                    ContainerOpening.user_id == user.id,
                    ContainerOpening.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if existing is not None:
                number = self.db.get(Number, existing.number_id)
                return OpeningOutcome(
                    opening=existing,
                    container=container,
                    number=number,  # type: ignore[arg-type]
                    is_duplicate=bool(existing.is_duplicate),
                    value=int(existing.value),
                    balance=self.economy.balance(user.id),
                    conversion_value=duplicate_conversion_reward(int(existing.value)),
                    replayed=True,
                )

        with user_lock(user.id, "container"):
            # Re-check after acquiring the lock (concurrent retry with same key).
            if idempotency_key:
                existing = self.db.execute(
                    select(ContainerOpening).where(
                        ContainerOpening.user_id == user.id,
                        ContainerOpening.idempotency_key == idempotency_key,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    number = self.db.get(Number, existing.number_id)
                    return OpeningOutcome(
                        existing,
                        container,
                        number,  # type: ignore[arg-type]
                        bool(existing.is_duplicate),
                        int(existing.value),
                        self.economy.balance(user.id),
                        duplicate_conversion_reward(int(existing.value)),
                        replayed=True,
                    )

            wallet = self.economy.get_wallet(user.id, for_update=True)
            self.economy.debit(
                user.id,
                int(container.price),
                TransactionType.CONTAINER_PURCHASE,
                reference_type="container",
                reference_id=container.code,
                idempotency_key=f"container_purchase:{user.id}:{idempotency_key}" if idempotency_key else None,
                meta={"container": container.code},
                wallet=wallet,
            )

            raw = random_number(self.rng)
            analysis = analyze(raw)
            luck = roll_rarity(dict(container.rarity_weights or {}), self.rng)
            floor = Rarity(container.minimum_rarity or Rarity.COMMON.value)
            final_rarity = combine_with_luck(combine_with_luck(analysis.rarity, luck), floor)

            number, _created = self.numbers.get_or_create(raw)
            number.rarity = max_rarity(number.rarity, final_rarity).value
            value = compute_value(
                final_rarity.value, list(number.traits or []), number.value_str, number.discovery_count
            )
            grant = self.numbers.grant(user, number, value=value)
            self.numbers.record_discovery(number, user.id, source="CONTAINER")

            opening = ContainerOpening(
                user_id=user.id,
                container_id=container.id,
                number_id=number.id,
                price_paid=int(container.price),
                rarity=final_rarity.value,
                value=value,
                is_duplicate=grant.is_duplicate,
                idempotency_key=idempotency_key,
                created_at=utcnow(),
            )
            self.db.add(opening)
            self.db.flush()

            user.containers_opened = int(user.containers_opened) + 1
            if value > int(user.best_value):
                user.best_value = value
                user.best_rarity = final_rarity.value
            self.db.flush()

            unlocked = self.achievements.evaluate(user)
            self.analytics.track(
                AnalyticsEventName.CONTAINER_OPEN.value,
                user_id=user.id,
                telegram_id=user.telegram_id,
                props={"container": container.code, "rarity": final_rarity.value, "number": number.value_str},
            )
            self.db.commit()
            self.db.refresh(opening)

            return OpeningOutcome(
                opening=opening,
                container=container,
                number=number,
                is_duplicate=grant.is_duplicate,
                value=value,
                balance=self.economy.balance(user.id),
                conversion_value=duplicate_conversion_reward(value),
                unlocked_achievements=summarize(unlocked),
            )

    def history(self, user_id: int, limit: int = 20) -> list[ContainerOpening]:
        stmt = (
            select(ContainerOpening)
            .where(ContainerOpening.user_id == user_id)
            .order_by(ContainerOpening.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).unique().scalars().all())
