"""The roll economy: daily bank, passive regeneration and bonus rolls.

The whole model is **server authoritative**. The client is told the three numbers it
needs to render the roll button (normal bank, bonus bank, countdown) and nothing else;
it never decides how many rolls exist, when one regenerates, or whether one may be
spent.

The model
---------
``normal bank``
    Up to :data:`RollEconomyConfig.bank_cap` rolls (20 by default). Rolls are drawn from
    it first. While it sits below the cap it regenerates passively at one roll every
    :data:`RollEconomyConfig.regen_minutes` (45 by default) and **never** exceeds the
    cap - so a player cannot bank a surplus by not playing.

``bonus bank``
    Rolls granted by missions, achievements, referrals, events, season rewards,
    collection milestones and fixed store bundles. They live *above* the normal bank
    and are never consumed by passive regeneration, so they cannot silently disappear
    just because the normal bank reached its cap.

``daily reset``
    The normal bank refills at a UTC boundary computed on the server. Existing players
    keep their spent-roll counter, their bonus bank and their collection: the reset only
    moves ``daily_rolls_used`` back to zero.

Timezone consistency
--------------------
Every timestamp is produced by :mod:`app.core.timeutils`, and the daily boundary is
UTC midnight - a single, stable rule that does not shift with the player's device
timezone or with daylight saving.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.timeutils import as_aware, days_between, next_utc_midnight, utcnow
from app.models.enums import TransactionType
from app.models.progression import DailyReward
from app.models.user import User
from app.services.economy import EconomyService

#: Fallback interval when a deployment sets an unusable value.
MIN_REGEN_MINUTES = 5


@dataclass(frozen=True, slots=True)
class RollEconomyConfig:
    """Tunables for the roll economy, resolved from settings."""

    bank_cap: int = 20
    regen_minutes: int = 45

    @property
    def regen_seconds(self) -> int:
        return max(MIN_REGEN_MINUTES, int(self.regen_minutes)) * 60


@dataclass(slots=True)
class RollState:
    """Authoritative roll balance for one player, ready to serialise."""

    #: Normal banked rolls (the regenerating pool).
    normal_remaining: int
    #: Bonus rolls granted by progression and purchases.
    bonus_rolls: int
    #: The normal bank's cap for this player (base + PRO).
    bank_cap: int
    #: Everything the player may spend right now.
    rolls_remaining: int
    #: UTC instant the normal bank refills completely.
    resets_at: str
    #: When the next passive roll lands, or ``None`` when the bank is full.
    next_roll_at: str | None
    #: Whole seconds until that roll (0 when none is pending).
    seconds_to_next_roll: int
    #: Configured regeneration interval, so the UI can label the countdown.
    regen_minutes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "rolls_remaining": self.rolls_remaining,
            "normal_rolls": self.normal_remaining,
            "bonus_rolls": self.bonus_rolls,
            "daily_allowance": self.bank_cap,
            "bank_cap": self.bank_cap,
            "resets_at": self.resets_at,
            "next_roll_at": self.next_roll_at,
            "seconds_to_next_roll": self.seconds_to_next_roll,
            "regen_minutes": self.regen_minutes,
        }


@dataclass(slots=True)
class DailyAllowance:
    """Backwards-compatible view of the daily allowance and the streak."""

    rolls_remaining: int
    daily_allowance: int
    resets_at: str
    streak: int
    can_claim: bool
    claim_reward_coins: int
    bonus_rolls: int = 0
    next_roll_at: str | None = None
    seconds_to_next_roll: int = 0
    regen_minutes: int = 45
    normal_rolls: int = 0


class DailyService:
    """Owns the daily bank, passive regeneration, streak and claim idempotency."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.economy = EconomyService(db)

    # --- configuration ---------------------------------------------------
    def config_for(self, user: User) -> RollEconomyConfig:
        """Effective economy tunables for one player.

        The cap is the base bank plus any PRO bonus, so a subscription buys
        *convenience* - more rolls to play with - and never a better collectible.
        """
        from app.services.premium import PremiumService

        premium = PremiumService(self.db, self.settings)
        cap = int(self.settings.default_daily_rolls) + premium.daily_rolls_bonus(user.id)
        return RollEconomyConfig(
            bank_cap=max(1, cap),
            regen_minutes=int(self.settings.roll_regen_minutes),
        )

    def daily_allowance(self, user: User) -> int:
        """The normal bank's cap for this player."""
        return self.config_for(user).bank_cap

    # --- reads -------------------------------------------------------------
    def normal_remaining(self, user: User) -> int:
        cap = self.daily_allowance(user)
        return max(0, cap - int(user.daily_rolls_used))

    def rolls_remaining(self, user: User) -> int:
        """Total spendable rolls: the normal bank plus the bonus bank.

        Regeneration is settled first, so every caller - the roll pipeline, the profile
        serializer, the roll button - sees the same authoritative number.
        """
        state = self.sync(user)
        return state.rolls_remaining

    def state(self, user: User, *, now: datetime | None = None) -> RollState:
        """Read-only snapshot. Call :meth:`sync` first when regeneration matters."""
        return self._state(user, now=now)

    def sync(self, user: User, *, now: datetime | None = None) -> RollState:
        """Reset the day if needed and bank every roll that has regenerated.

        Called at the start of a roll and whenever the client asks for the balance, so
        the countdown the player sees is the same number the next roll will use.
        """
        moment = now or utcnow()
        self.ensure_reset(user, now=moment)
        self._apply_regeneration(user, moment)
        return self._state(user, now=moment)

    # --- writes ------------------------------------------------------------
    def ensure_reset(self, user: User, *, now: datetime | None = None) -> bool:
        """Refill the normal bank when the UTC day rolled over.

        Only the normal bank moves: ``bonus_rolls`` and the regeneration clock are
        deliberately untouched, so nothing a player earned is ever deleted by a reset.
        """
        moment = now or utcnow()
        reset_at = as_aware(user.daily_reset_at)
        if reset_at is None:
            user.daily_reset_at = next_utc_midnight(moment)
            user.daily_rolls_used = 0
            user.roll_regen_at = None
            self.db.flush()
            return True
        if moment >= reset_at:
            user.daily_rolls_used = 0
            user.daily_reset_at = next_utc_midnight(moment)
            # A full bank needs no pending regeneration.
            user.roll_regen_at = None
            self.db.flush()
            return True
        return False

    def _apply_regeneration(self, user: User, now: datetime) -> int:
        """Bank every regenerating roll the player has earned, up to the cap."""
        config = self.config_for(user)
        cap = config.bank_cap
        normal = self.normal_remaining(user)
        if normal >= cap:
            # The bank is full: idle the clock so no surplus can accumulate.
            if user.roll_regen_at is not None:
                user.roll_regen_at = None
                self.db.flush()
            return 0

        interval = config.regen_seconds
        pending = as_aware(user.roll_regen_at)
        if pending is None:
            # The bank just fell below the cap (or the player joined): start the clock.
            user.roll_regen_at = now + timedelta(seconds=interval)
            self.db.flush()
            return 0

        granted = 0
        if now >= pending:
            # ``roll_regen_at`` is the instant the next roll becomes available, so the
            # pending slot itself is due now; every whole interval after it adds one more.
            elapsed = (now - pending).total_seconds()
            earned = int(elapsed // interval) + 1
            granted = int(min(earned, cap - normal))
            if granted > 0:
                user.daily_rolls_used = max(0, int(user.daily_rolls_used) - granted)
                normal += granted
            # Advance the clock by exactly the rolls banked, so nothing is lost when the
            # player was away and nothing is granted early when they were not.
            user.roll_regen_at = (
                None if normal >= cap else pending + timedelta(seconds=interval * granted)
            )
            self.db.flush()
        return granted

    def consume_roll(self, user: User) -> str:
        """Spend one roll. Normal bank first, then bonus. Returns the bank used.

        Settles the day rollover and any regenerated roll first, so a caller can never
        spend from - or be refused by - a stale balance.
        """
        self.sync(user)
        if self.normal_remaining(user) > 0:
            user.daily_rolls_used = int(user.daily_rolls_used) + 1
            self._start_regen_clock(user)
            self.db.flush()
            return "normal"
        if int(user.bonus_rolls) > 0:
            user.bonus_rolls = int(user.bonus_rolls) - 1
            self.db.flush()
            return "bonus"
        from app.core.errors import NoRollsAvailableError

        raise NoRollsAvailableError(
            "No rolls available.",
            details={
                "resets_at": (as_aware(user.daily_reset_at) or next_utc_midnight()).isoformat(),
                "next_roll_at": (
                    as_aware(user.roll_regen_at).isoformat() if user.roll_regen_at else None
                ),
            },
        )

    def _start_regen_clock(self, user: User) -> None:
        """Begin (or leave running) the passive clock after the bank drops below cap."""
        if self.normal_remaining(user) >= self.daily_allowance(user):
            user.roll_regen_at = None
            return
        if user.roll_regen_at is None:
            user.roll_regen_at = utcnow() + timedelta(seconds=self.config_for(user).regen_seconds)

    def grant_bonus_rolls(self, user: User, amount: int) -> int:
        """Add bonus rolls above the normal bank. Never clamped by the cap."""
        if amount <= 0:
            return int(user.bonus_rolls)
        user.bonus_rolls = int(user.bonus_rolls) + int(amount)
        self.db.flush()
        return int(user.bonus_rolls)

    def reset_daily_usage(self, user: User) -> int:
        """Refund today's spent rolls.

        Admin-only escape hatch used when a player is wrongly blocked. It only
        touches today's counter - the configured cap itself is never changed, and the
        bonus bank and the regeneration clock are left alone.
        """
        used = int(user.daily_rolls_used)
        user.daily_rolls_used = 0
        user.daily_reset_at = next_utc_midnight()
        user.roll_regen_at = None
        self.db.flush()
        return used

    # --- daily reward -------------------------------------------------------
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
        """Claim today's reward. Idempotent per UTC day via a unique constraint.

        Returns ``(reward_row, coins_granted, rolls_granted)``.
        """
        from app.core.errors import ConflictError

        if not self.can_claim(user):
            raise ConflictError("Daily reward already claimed today.", code="DAILY_ALREADY_CLAIMED")

        now = utcnow()
        streak = self.next_streak(user)
        coins = int(self.settings.daily_base_coins) + int(self.settings.daily_streak_bonus_coins) * streak
        # The daily reward tops the bank up to its cap rather than handing out extra
        # rolls on top of it, so claiming can never be farmed for a surplus.
        rolls = max(0, self.daily_allowance(user) - int(user.daily_rolls_used))

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
        # Claiming refills the normal bank for the new day.
        user.daily_rolls_used = max(0, int(user.daily_rolls_used) - rolls)
        user.daily_reset_at = next_utc_midnight(now)
        user.roll_regen_at = None
        self.db.flush()
        return reward, coins, rolls

    # --- projections -------------------------------------------------------
    def _state(self, user: User, *, now: datetime | None = None) -> RollState:
        moment = now or utcnow()
        config = self.config_for(user)
        normal = self.normal_remaining(user)
        bonus = max(0, int(user.bonus_rolls))
        resets_at = as_aware(user.daily_reset_at) or next_utc_midnight(moment)
        pending = as_aware(user.roll_regen_at) if normal < config.bank_cap else None
        seconds = 0
        if pending is not None:
            seconds = max(0, int((pending - moment).total_seconds()))
        return RollState(
            normal_remaining=normal,
            bonus_rolls=bonus,
            bank_cap=config.bank_cap,
            rolls_remaining=normal + bonus,
            resets_at=resets_at.isoformat(),
            next_roll_at=pending.isoformat() if pending is not None else None,
            seconds_to_next_roll=seconds,
            regen_minutes=config.regen_minutes,
        )

    def status(self, user: User) -> DailyAllowance:
        state = self.sync(user)
        return DailyAllowance(
            rolls_remaining=state.rolls_remaining,
            daily_allowance=state.bank_cap,
            resets_at=state.resets_at,
            streak=int(user.current_streak),
            can_claim=self.can_claim(user),
            claim_reward_coins=int(self.settings.daily_base_coins)
            + int(self.settings.daily_streak_bonus_coins) * self.next_streak(user),
            bonus_rolls=state.bonus_rolls,
            next_roll_at=state.next_roll_at,
            seconds_to_next_roll=state.seconds_to_next_roll,
            regen_minutes=state.regen_minutes,
            normal_rolls=state.normal_remaining,
        )

    def claim_history(self, user_id: int, limit: int = 30) -> list[DailyReward]:
        stmt = (
            select(DailyReward)
            .where(DailyReward.user_id == user_id)
            .order_by(DailyReward.claimed_on.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())


__all__ = [
    "MIN_REGEN_MINUTES",
    "DailyAllowance",
    "DailyService",
    "RollEconomyConfig",
    "RollState",
]
