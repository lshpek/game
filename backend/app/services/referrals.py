"""Referral system.

Anti-abuse rules enforced server side:

* the inviter must exist as a real, non-banned user;
* self-referral is rejected;
* a user can only ever be referred once (unique constraint on ``referred_id``);
* the reward is paid only after the invitee performs a real roll;
* a per-day activation cap limits farmed accounts.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import NotFoundError, ReferralAbuseError
from app.core.timeutils import start_of_utc_day, utcnow
from app.models.enums import AnalyticsEventName, ReferralStatus, TransactionType
from app.models.social import Referral
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.services.daily import DailyService
from app.services.economy import EconomyService


@dataclass(slots=True)
class ReferralStats:
    total: int
    activated: int
    pending: int
    coins_earned: int


class ReferralService:
    """Binds invitees to inviters and pays out verified activations."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.economy = EconomyService(db)
        self.daily = DailyService(db, self.settings)
        self.analytics = AnalyticsService(db)

    # --- binding --------------------------------------------------------
    def bind(self, user: User, referrer_telegram_id: int | None, start_param: str | None = None) -> Referral | None:
        """Attach a pending referral to ``user`` if all guards pass."""
        if not referrer_telegram_id:
            return None

        referrer = self.db.execute(
            select(User).where(User.telegram_id == int(referrer_telegram_id))
        ).scalar_one_or_none()
        if referrer is None:
            raise NotFoundError("Referrer not found.", code="REFERRER_NOT_FOUND")
        if referrer.id == user.id:
            raise ReferralAbuseError("Self-referral is not allowed.")
        if referrer.is_banned:
            raise ReferralAbuseError("Referrer is not eligible.")

        existing = self.db.execute(
            select(Referral).where(Referral.referred_id == user.id)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        today_count = int(
            self.db.execute(
                select(func.count())
                .select_from(Referral)
                .where(
                    Referral.referrer_id == referrer.id,
                    Referral.status == ReferralStatus.ACTIVATED.value,
                    Referral.activated_at >= start_of_utc_day(),
                )
            ).scalar_one()
            or 0
        )
        if today_count >= int(self.settings.max_referrals_per_day):
            raise ReferralAbuseError("Daily referral activation limit reached for this inviter.")

        referral = Referral(
            referrer_id=referrer.id,
            referred_id=user.id,
            status=ReferralStatus.PENDING.value,
            start_param=start_param,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.db.add(referral)
        self.db.flush()
        self.analytics.track(
            AnalyticsEventName.REFERRAL_CLICK.value,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={"referrer_telegram_id": referrer_telegram_id},
        )
        return referral

    # --- activation -----------------------------------------------------
    def activate(self, user: User) -> Referral | None:
        """Pay out a pending referral once the invitee has rolled for real."""
        referral = self.db.execute(
            select(Referral).where(
                Referral.referred_id == user.id,
                Referral.status == ReferralStatus.PENDING.value,
            )
        ).scalar_one_or_none()
        if referral is None or referral.reward_paid:
            return None
        return self._payout(referral, user)

    def _payout(self, referral: Referral, user: User) -> Referral | None:
        referrer = self.db.get(User, referral.referrer_id)
        if referrer is None:
            return None

        coins = int(self.settings.referral_reward_coins)
        rolls = int(self.settings.referral_reward_rolls)

        referral.status = ReferralStatus.ACTIVATED.value
        referral.activated_at = utcnow()
        referral.reward_coins = coins
        referral.reward_rolls = rolls
        referral.reward_paid = True

        self.economy.credit(
            referrer.id,
            coins,
            TransactionType.REFERRAL_REWARD,
            reference_type="referral",
            reference_id=str(referral.id),
            idempotency_key=f"referral:{referral.id}",
        )
        self.daily.grant_bonus_rolls(referrer, rolls)
        referrer.referrals_count = int(referrer.referrals_count) + 1

        # The invitee gets a small welcome bonus too.
        self.daily.grant_bonus_rolls(user, max(1, rolls // 2))
        self.db.flush()

        self.analytics.track(
            AnalyticsEventName.REFERRAL_ACTIVATED.value,
            user_id=referrer.id,
            telegram_id=referrer.telegram_id,
            props={"referred_telegram_id": user.telegram_id},
        )
        return referral

    # --- reporting ------------------------------------------------------
    def stats(self, user_id: int) -> ReferralStats:
        rows = (
            self.db.execute(
                select(Referral.status, func.count(), func.coalesce(func.sum(Referral.reward_coins), 0))
                .where(Referral.referrer_id == user_id, Referral.reward_paid.is_(True))
                .group_by(Referral.status)
            )
            .all()
        )
        activated = pending = coins = 0
        for status, count, reward in rows:
            if status == ReferralStatus.ACTIVATED.value:
                activated += int(count)
                coins += int(reward or 0)
            elif status == ReferralStatus.PENDING.value:
                pending += int(count)

        total = int(
            self.db.execute(
                select(func.count()).select_from(Referral).where(Referral.referrer_id == user_id)
            ).scalar_one()
            or 0
        )
        return ReferralStats(total=total, activated=activated, pending=pending, coins_earned=coins)

    def list_referrals(self, user_id: int, limit: int = 50) -> list[dict[str, object]]:
        rows = (
            self.db.execute(
                select(Referral, User)
                .join(User, User.id == Referral.referred_id)
                .where(Referral.referrer_id == user_id)
                .order_by(Referral.id.desc())
                .limit(limit)
            )
            .all()
        )
        return [
            {
                "status": referral.status,
                "username": referred.username,
                "display_name": referred.display_name,
                "photo_url": referred.photo_url,
                "reward_coins": int(referral.reward_coins),
                "created_at": referral.created_at.isoformat(),
                "activated_at": referral.activated_at.isoformat() if referral.activated_at else None,
            }
            for referral, referred in rows
        ]
