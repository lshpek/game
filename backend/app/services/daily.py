"""Daily roll allowance and daily reward claiming.

Rolls regenerate on a UTC boundary decided by the server; the client clock is
never consulted.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.timeutils import as_aware, days_between, next_utc_midnight, utcnow
from app.models.enums import TransactionType
from app.models.progression import DailyReward
from app.models.user import User
from app.services.economy import EconomyService


@dataclass(slots=True)
class DailyAllowance:
    rolls_remaining: int
    daily_allowance: int
    resets_at: str
    streak: int
    can_claim: bool
    claim_reward_coins: int


class DailyService:
    """Owns the daily reset, streak progression and claim idempotency."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.economy = EconomyService(db)

    def daily_allowance(self, user: User) -> int:
        from app.services.premium import PremiumService

        premium = PremiumService(self.db, self.settings)
        return int(self.settings.default_daily_rolls) + premium.daily_rolls_bonus(user.id)

    def rolls_remaining(self, user: User) -> int:
        return max(0, self.daily_allowance(user) - int(user.daily_rolls_used)) + int(user.bonus_rolls)

    def ensure_reset(self, user: User) -> bool:
        """Reset the daily counter when the UTC day rolled over."""
        now = utcnow()
        reset_at = as_aware(user.daily_reset_at)
        if reset_at is None:
            user.daily_reset_at = next_utc_midnight(now)
            user.daily_rolls_used = 0
            self.db.flush()
            return True
        if now >= reset_at:
            user.daily_rolls_used = 0
            user.daily_reset_at = next_utc_midnight(now)
            self.db.flush()
            return True
        return False

    def consume_roll(self, user: User) -> None:
        """Spend one roll: daily allowance first, then bonus stock."""
        if int(user.daily_rolls_used) < self.daily_allowance(user):
            user.daily_rolls_used = int(user.daily_rolls_used) + 1
        elif int(user.bonus_rolls) > 0:
            user.bonus_rolls = int(user.bonus_rolls) - 1
        else:
            from app.core.errors import NoRollsAvailableError

            raise NoRollsAvailableError("No rolls available.")
        self.db.flush()

    def grant_bonus_rolls(self, user: User, amount: int) -> None:
        user.bonus_rolls = int(user.bonus_rolls) + max(0, amount)
        self.db.flush()

    def can_claim(self, user: User) -> bool:
        claimed_at = as_aware(user.last_daily_claim_at)
        if claimed_at is None:
            return True
        return days_between(utcnow(), claimed_at) >= 1

    def next_streak(self, user: User) -> int:
        """Streak value if the player claims today (0 or >1 day gaps reset it)."""
        claimed_at = as_aware(user.last_daily_claim_at)
        if claimed_at is None:
            return 1
        gap = days_between(utcnow(), claimed_at)
        if gap == 0:
            return max(1, int(user.current_streak or 0))
        if gap == 1:
            return int(user.current_streak or 0) + 1
        return 1

    def claim(self, user: User) -> tuple[DailyReward, int, int]:
        """Claim today's reward. Idempotent per UTC day via unique constraint.

        Returns ``(reward_row, coins_granted, rolls_granted)``.
        """
        from app.core.errors import ConflictError

        if not self.can_claim(user):
            raise ConflictError("Daily reward already claimed today.", code="DAILY_ALREADY_CLAIMED")

        now = utcnow()
        streak = self.next_streak(user)
        coins = int(self.settings.daily_base_coins) + int(self.settings.daily_streak_bonus_coins) * streak
        rolls = self.daily_allowance(user)

        reward = DailyReward(
            user_id=user.id,
            claimed_on=now.date(),
            rolls_granted=rolls,
            coins_granted=coins,
            streak=streak,
            created_at=now,
        )
        self.db.add(reward)
        self.db.flush()

        if coins > 0:
            self.economy.credit(
                user.id,
                coins,
                TransactionType.DAILY_REWARD,
                reference_type="daily_reward",
                reference_id=str(reward.id),
                idempotency_key=f"daily:{user.id}:{now.date().isoformat()}",
            )

        user.last_daily_claim_at = now
        user.current_streak = streak
        user.longest_streak = max(int(user.longest_streak), streak)
        # Claiming refills the daily allowance for the new day.
        user.daily_rolls_used = 0
        user.daily_reset_at = next_utc_midnight(now)
        self.db.flush()
        return reward, coins, rolls

    def status(self, user: User) -> DailyAllowance:
        self.ensure_reset(user)
        resets_at = as_aware(user.daily_reset_at) or next_utc_midnight()
        return DailyAllowance(
            rolls_remaining=self.rolls_remaining(user),
            daily_allowance=self.daily_allowance(user),
            resets_at=resets_at.isoformat(),
            streak=int(user.current_streak),
            can_claim=self.can_claim(user),
            claim_reward_coins=int(self.settings.daily_base_coins)
            + int(self.settings.daily_streak_bonus_coins) * self.next_streak(user),
        )

    def claim_history(self, user_id: int, limit: int = 30) -> list[DailyReward]:
        stmt = (
            select(DailyReward)
            .where(DailyReward.user_id == user_id)
            .order_by(DailyReward.claimed_on.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
