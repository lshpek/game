"""Premium entitlements - always evaluated server side."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.timeutils import as_aware, utcnow
from app.game.products import premium_tier_config
from app.models.enums import EntitlementTier
from app.models.payment import PremiumEntitlement


class PremiumService:
    """Reads the active entitlement row and exposes its perks."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings

    def active_entitlement(self, user_id: int) -> PremiumEntitlement | None:
        now = utcnow()
        rows = (
            self.db.execute(
                select(PremiumEntitlement)
                .where(
                    PremiumEntitlement.user_id == user_id,
                    PremiumEntitlement.is_active.is_(True),
                )
                .order_by(PremiumEntitlement.expires_at.desc())
            )
            .scalars()
            .all()
        )
        for row in rows:
            expires = as_aware(row.expires_at)
            if expires is None or expires > now:
                return row
        return None

    def active_tier(self, user_id: int) -> str | None:
        entitlement = self.active_entitlement(user_id)
        return entitlement.tier if entitlement else None

    def is_premium(self, user_id: int) -> bool:
        return self.active_entitlement(user_id) is not None

    def _tier_config(self, user_id: int) -> dict[str, object]:
        tier = self.active_tier(user_id)
        return premium_tier_config(tier) if tier else {}

    def daily_rolls_bonus(self, user_id: int) -> int:
        return int(self._tier_config(user_id).get("daily_rolls_bonus", 0) or 0)

    def duplicate_coin_multiplier(self, user_id: int) -> float:
        return float(self._tier_config(user_id).get("duplicate_coin_multiplier", 1.0) or 1.0)

    def unlocked_containers(self, user_id: int) -> set[str]:
        value = self._tier_config(user_id).get("unlocked_containers", [])
        return set(value) if isinstance(value, list) else set()

    def perks(self, user_id: int) -> list[str]:
        value = self._tier_config(user_id).get("perks", [])
        return list(value) if isinstance(value, list) else []

    # --- writes --------------------------------------------------------
    def grant(
        self,
        user_id: int,
        *,
        tier: str = EntitlementTier.PRO.value,
        days: int = 30,
        source: str = "PURCHASE",
        payment_id: int | None = None,
    ) -> PremiumEntitlement:
        """Extend (or start) a premium entitlement."""
        now = utcnow()
        current = self.active_entitlement(user_id)
        starts_at = now
        base = as_aware(current.expires_at) if current and current.tier == tier else None
        starts_at = base if base and base > now else now

        entitlement = PremiumEntitlement(
            user_id=user_id,
            tier=tier.upper(),
            source=source,
            payment_id=payment_id,
            starts_at=now,
            expires_at=starts_at + timedelta(days=max(1, days)),
            is_active=True,
        )
        self.db.add(entitlement)
        self.db.flush()
        return entitlement

    def revoke(self, user_id: int, *, payment_id: int | None = None) -> int:
        """Deactivate entitlements (used by refunds). Returns rows affected."""
        query = select(PremiumEntitlement).where(
            PremiumEntitlement.user_id == user_id,
            PremiumEntitlement.is_active.is_(True),
        )
        if payment_id is not None:
            query = query.where(PremiumEntitlement.payment_id == payment_id)
        rows = self.db.execute(query).scalars().all()
        for row in rows:
            row.is_active = False
        self.db.flush()
        return len(rows)

    def expires_at(self, user_id: int):
        entitlement = self.active_entitlement(user_id)
        return as_aware(entitlement.expires_at) if entitlement else None
