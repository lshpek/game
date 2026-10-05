"""Server-authoritative roll engine.

The client never decides anything: it asks for a roll, the server locks the
player, consumes a roll, generates the number with its own RNG, persists the
result and writes the ledger entry - all inside one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.locks import user_lock
from app.core.timeutils import utcnow
from app.game.analyzer import analyze, combine_with_luck
from app.game.rarity import RARITY_RANK, Rarity, max_rarity, rarity_rank
from app.game.rng import Rng, default_rng, random_number, roll_rarity
from app.game.valuation import compute_value, duplicate_conversion_reward
from app.models.enums import AnalyticsEventName, RollSource, TransactionType
from app.models.number import Number
from app.models.roll import Roll
from app.models.user import User
from app.services.achievements import AchievementService, summarize
from app.services.analytics import AnalyticsService
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.numbers import NumberService
from app.services.premium import PremiumService

RARE_RANK_THRESHOLD = RARITY_RANK[Rarity.RARE.value]
COIN_DROP_RARITY_STEP = 0.75


@dataclass(slots=True)
class RollOutcome:
    """Everything the client needs to render a roll result."""

    roll: Roll
    number: Number
    is_duplicate: bool
    is_first_discovery: bool
    coins_awarded: int
    value: int
    balance: int
    rolls_remaining: int
    conversion_value: int
    unlocked_achievements: list[dict[str, object]] = field(default_factory=list)
    replayed: bool = False


class RollService:
    """Executes rolls with locking and idempotency."""

    def __init__(self, db: Session, config: Settings | None = None, rng: Rng | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.rng = rng or default_rng()
        self.economy = EconomyService(db)
        self.numbers = NumberService(db)
        self.daily = DailyService(db, self.settings)
        self.premium = PremiumService(db, self.settings)
        self.achievements = AchievementService(db)
        self.analytics = AnalyticsService(db)

    # --- helpers --------------------------------------------------------
    def _existing_roll(self, user_id: int, idempotency_key: str | None) -> Roll | None:
        if not idempotency_key:
            return None
        return self.db.execute(
            select(Roll).where(Roll.user_id == user_id, Roll.idempotency_key == idempotency_key)
        ).scalar_one_or_none()

    def _coin_drop(self, rank: int) -> int:
        """Occasional COINS drop, scaled by rarity rank."""
        if self.rng.random() > float(self.settings.roll_coin_reward_chance):
            return 0
        base = self.rng.randint(int(self.settings.roll_coin_reward_min), int(self.settings.roll_coin_reward_max))
        return round(base * (1.0 + COIN_DROP_RARITY_STEP * rank))

    def _build_outcome(
        self,
        user: User,
        roll: Roll,
        number: Number,
        *,
        unlocked: list[dict[str, object]] | None = None,
        replayed: bool = False,
    ) -> RollOutcome:
        return RollOutcome(
            roll=roll,
            number=number,
            is_duplicate=bool(roll.is_duplicate),
            is_first_discovery=bool(roll.is_first_discovery),
            coins_awarded=int(roll.coins_awarded),
            value=int(roll.value),
            balance=self.economy.balance(user.id),
            rolls_remaining=self.daily.rolls_remaining(user),
            conversion_value=duplicate_conversion_reward(int(roll.value)),
            unlocked_achievements=unlocked or [],
            replayed=replayed,
        )

    # --- main flow ------------------------------------------------------
    def perform_roll(
        self,
        user: User,
        *,
        source: RollSource = RollSource.DAILY,
        idempotency_key: str | None = None,
    ) -> RollOutcome:
        """Consume one roll and persist the result atomically."""
        replay = self._existing_roll(user.id, idempotency_key)
        if replay is not None:
            return self._build_outcome(user, replay, self.db.get(Number, replay.number_id), replayed=True)  # type: ignore[arg-type]

        with user_lock(user.id, "roll"):
            # Re-check inside the lock: a concurrent request may have won the race.
            replay = self._existing_roll(user.id, idempotency_key)
            if replay is not None:
                return self._build_outcome(user, replay, self.db.get(Number, replay.number_id), replayed=True)  # type: ignore[arg-type]

            now = utcnow()
            self.daily.sync(user)
            wallet = self.economy.get_wallet(user.id, for_update=True)
            self.daily.consume_roll(user)

            raw = random_number(self.rng)
            analysis = analyze(raw)
            luck = roll_rarity(self.settings.rarity_weights, self.rng)
            final_rarity = combine_with_luck(analysis.rarity, luck)

            number, created = self.numbers.get_or_create(raw)
            number.rarity = max_rarity(number.rarity, final_rarity).value

            value = compute_value(
                final_rarity.value, list(number.traits or []), number.value_str, number.discovery_count
            )
            grant = self.numbers.grant(user, number, value=value)
            is_first_discovery = self.numbers.record_discovery(number, user.id, source=source.value)
            _ = created

            coins_awarded = 0 if grant.is_duplicate else self._coin_drop(rarity_rank(final_rarity))

            roll = Roll(
                user_id=user.id,
                number_id=number.id,
                source=source.value,
                rarity=final_rarity.value,
                natural_rarity=analysis.rarity.value,
                luck_rarity=luck.value,
                value=value,
                coins_awarded=coins_awarded,
                is_duplicate=grant.is_duplicate,
                is_first_discovery=is_first_discovery,
                idempotency_key=idempotency_key,
                created_at=now,
            )
            self.db.add(roll)
            self.db.flush()

            if coins_awarded > 0:
                self.economy.credit(
                    user.id,
                    coins_awarded,
                    TransactionType.ROLL_REWARD,
                    reference_type="roll",
                    reference_id=str(roll.id),
                    idempotency_key=f"roll_reward:{roll.id}",
                    wallet=wallet,
                )

            user.total_rolls = int(user.total_rolls) + 1
            user.last_roll_at = now
            if value > int(user.best_value):
                user.best_value = value
                user.best_rarity = final_rarity.value
            self.db.flush()

            unlocked = self.achievements.evaluate(user)

            self.analytics.track(
                AnalyticsEventName.ROLL.value,
                user_id=user.id,
                telegram_id=user.telegram_id,
                props={"number": number.value_str, "rarity": final_rarity.value, "value": value},
            )
            if int(user.total_rolls) == 1:
                self.analytics.track(
                    AnalyticsEventName.FIRST_ROLL.value, user_id=user.id, telegram_id=user.telegram_id
                )
            if rarity_rank(final_rarity) >= RARE_RANK_THRESHOLD:
                self.analytics.track(
                    AnalyticsEventName.RARE_FOUND.value,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    props={"rarity": final_rarity.value, "number": number.value_str},
                )

            self.db.commit()
            self.db.refresh(roll)
            return self._build_outcome(user, roll, number, unlocked=summarize(unlocked))

    def history(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Roll]:
        stmt = (
            select(Roll)
            .where(Roll.user_id == user_id)
            .order_by(Roll.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).unique().scalars().all())
