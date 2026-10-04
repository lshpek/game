"""Server-authoritative plate roll engine.

One request -> one transaction:

    authenticate (done by the router)
      -> lock the player
      -> re-check idempotency
      -> ensure daily allowance / consume a roll
      -> server RNG: country -> region -> template -> serial
      -> pattern analysis + rarity + valuation (in the engine)
      -> persist the plate, register the discovery
      -> grant ownership, update collection and progression
      -> award any free NUMORA
      -> missions, achievements, analytics
      -> commit

Nothing here trusts the client: not the country, not the serial, not the rarity,
not the value and not the reward.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.locks import user_lock
from app.core.timeutils import utcnow
from app.game.collectibles import CollectibleCategory
from app.game.plate_generator import PlateGenerator
from app.game.plate_rarity import RARITY_RANK, Rarity, pity_weights, rarity_rank
from app.game.plate_valuation import duplicate_sale_value
from app.game.rng import Rng, default_rng, weighted_choice
from app.models.enums import AnalyticsEventName, RollSource, TransactionType
from app.models.numora import PlateRoll
from app.models.plates import Plate, UserPlate
from app.models.user import User
from app.services.achievements import AchievementService, summarize
from app.services.albums import AlbumService
from app.services.analytics import AnalyticsService
from app.services.catalog import snapshot
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.events import EventService
from app.services.missions import MissionService
from app.services.plates import PlateService
from app.services.premium import PremiumService
from app.services.progression import ProgressionService

RARE_RANK = RARITY_RANK[Rarity.RARE.value]
EPIC_RANK = RARITY_RANK[Rarity.EPIC.value]
LEGENDARY_RANK = RARITY_RANK[Rarity.LEGENDARY.value]

# Occasional free NUMORA drop, scaled by rarity. Keeps the loop rewarding even
# when a player rolls a duplicate.
NUMORA_DROP_CHANCE = 0.3
NUMORA_DROP_MIN = 2
NUMORA_DROP_MAX = 18
NUMORA_DROP_RARITY_STEP = 0.9

# Guaranteed consolation when a player has had a very long unlucky streak.
BAD_LUCK_THRESHOLD = 40
BAD_LUCK_NUMORA = 120


@dataclass(slots=True)
class PlateRollOutcome:
    """Everything the client needs to render one roll result."""

    roll: PlateRoll
    plate: Plate
    user_plate: UserPlate | None
    is_duplicate: bool
    is_first_discovery: bool
    is_new_country: bool
    is_new_region: bool
    numora_awarded: int
    balance: int
    rolls_remaining: int
    sale_value: int
    collector_level: int
    missions_completed: list[dict[str, object]] = field(default_factory=list)
    albums_completed: list[dict[str, object]] = field(default_factory=list)
    unlocked_achievements: list[dict[str, object]] = field(default_factory=list)
    replayed: bool = False
    event: dict[str, object] | None = None
    share_start_param: str = ""


class PlateRollService:
    """Executes plate rolls with locking, idempotency and pity protection."""

    def __init__(
        self,
        db: Session,
        config: Settings | None = None,
        rng: Rng | None = None,
    ) -> None:
        self.db = db
        self.settings = config or settings
        self.rng = rng or default_rng()
        self.economy = EconomyService(db)
        self.plates = PlateService(db)
        self.daily = DailyService(db, self.settings)
        self.premium = PremiumService(db, self.settings)
        self.achievements = AchievementService(db)
        self.analytics = AnalyticsService(db)
        self.progression = ProgressionService(db)
        self.missions = MissionService(db, self.economy)
        self.albums = AlbumService(db, self.economy)
        self.events = EventService(db)

    # --- helpers --------------------------------------------------------
    def _existing_roll(self, user_id: int, idempotency_key: str | None) -> PlateRoll | None:
        if not idempotency_key:
            return None
        return self.db.execute(
            select(PlateRoll).where(
                PlateRoll.user_id == user_id, PlateRoll.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()

    def _luck_rarity(self, user: User) -> Rarity:
        """Roll the luck tier, softened by bad-luck protection."""
        weights = pity_weights(
            self.settings.rarity_weights,
            rare_streak=int(user.pity_rare_streak),
            epic_streak=int(user.pity_epic_streak),
            legendary_streak=int(user.pity_legendary_streak),
        )
        return Rarity(weighted_choice(weights, self.rng))

    def _numora_drop(self, rank: int) -> int:
        if self.rng.random() > NUMORA_DROP_CHANCE:
            return 0
        base = self.rng.randint(NUMORA_DROP_MIN, NUMORA_DROP_MAX)
        return round(base * (1.0 + NUMORA_DROP_RARITY_STEP * rank))

    def _update_pity(self, user: User, rank: int) -> None:
        """Advance or reset the bad-luck counters."""
        if rank >= LEGENDARY_RANK:
            user.pity_legendary_streak = 0
        else:
            user.pity_legendary_streak = int(user.pity_legendary_streak) + 1

        if rank >= EPIC_RANK:
            user.pity_epic_streak = 0
        else:
            user.pity_epic_streak = int(user.pity_epic_streak) + 1

        if rank >= RARE_RANK:
            user.pity_rare_streak = 0
        else:
            user.pity_rare_streak = int(user.pity_rare_streak) + 1

    def _event_context(self):
        event = self.events.active()
        return event, event.multipliers

    def history(self, user_id: int, limit: int = 20, offset: int = 0) -> list[PlateRoll]:
        stmt = (
            select(PlateRoll)
            .where(PlateRoll.user_id == user_id)
            .order_by(PlateRoll.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def _build_outcome(
        self,
        user: User,
        roll: PlateRoll,
        *,
        grants=None,
        is_first_discovery: bool = False,
        numora_awarded: int = 0,
        missions: list[dict[str, object]] | None = None,
        albums: list[dict[str, object]] | None = None,
        achievements: list[dict[str, object]] | None = None,
        event: dict[str, object] | None = None,
        replayed: bool = False,
    ) -> PlateRollOutcome:
        plate = self.plates.require_plate(roll.plate_id)
        user_plate = self.plates.get_user_plate(user.id, plate.id)
        return PlateRollOutcome(
            roll=roll,
            plate=plate,
            user_plate=user_plate,
            is_duplicate=bool(roll.is_duplicate),
            is_first_discovery=is_first_discovery,
            is_new_country=bool(getattr(grants, "is_new_country", False)),
            is_new_region=bool(getattr(grants, "is_new_region", False)),
            numora_awarded=numora_awarded,
            balance=self.economy.balance(user.id),
            rolls_remaining=self.daily.rolls_remaining(user),
            sale_value=duplicate_sale_value(int(plate.dealer_value)),
            collector_level=int(user.collector_level),
            missions_completed=missions or [],
            albums_completed=albums or [],
            unlocked_achievements=achievements or [],
            replayed=replayed,
            event=event,
            share_start_param=f"plate_{plate.id}",
        )

    def perform_roll(
        self,
        user: User,
        *,
        source: RollSource = RollSource.DAILY,
        idempotency_key: str | None = None,
        bypass_allowance: bool = False,
        category: CollectibleCategory | None = None,
        country_code: str | None = None,
    ) -> PlateRollOutcome:
        """The single entry point for producing a collectible.

        ``category`` and ``country_code`` only narrow the *eligible pool* that the
        generator draws from. They cannot influence the number itself, its rarity,
        its value or the reward - all of that stays server-side, which is what keeps
        a hunt filter from becoming a cheat or a forgery vector.
        """
        with user_lock(user.id):
            existing = self._existing_roll(user.id, idempotency_key)
            if existing is not None:
                return self._build_outcome(user, existing, replayed=True)

            if not bypass_allowance:
                self.daily.ensure_reset(user)
                self.daily.consume_roll(user)

            now = utcnow()
            event, multipliers = self._event_context()

            catalog = snapshot(self.db, self.settings.rarity_weights)
            context = catalog.context
            # Events re-weight the country table inside the engine.
            context.event_multipliers = multipliers

            luck = self._luck_rarity(user)
            generated = PlateGenerator(context, self.rng).generate(
                luck=luck,
                category=category,
                country_code=country_code,
            )

            plate, _created = self.plates.materialize(generated)
            grant = self.plates.grant(plate, user)
            is_first = self.plates.record_discovery(plate, user, source=source.value)

            rank = rarity_rank(plate.rarity)
            self._update_pity(user, rank)

            # Free NUMORA: rarer finds pay more, duplicates still pay something.
            numora_awarded = self._numora_drop(rank)
            if int(user.pity_rare_streak) >= BAD_LUCK_THRESHOLD:
                numora_awarded += BAD_LUCK_NUMORA

            roll = PlateRoll(
                user_id=user.id,
                plate_id=plate.id,
                source=source.value,
                rarity=plate.rarity,
                natural_rarity=generated.natural_rarity.value,
                luck_rarity=generated.luck_rarity.value,
                rarity_score=int(plate.rarity_score),
                dealer_value=int(plate.dealer_value),
                collector_value=int(plate.collector_value),
                numora_awarded=numora_awarded,
                is_duplicate=bool(grant.is_duplicate),
                is_first_discovery=is_first,
                idempotency_key=idempotency_key,
                created_at=now,
            )
            self.db.add(roll)
            self.db.flush()

            if numora_awarded > 0:
                self.economy.credit(
                    user.id,
                    numora_awarded,
                    TransactionType.ROLL_REWARD,
                    reference_type="plate_roll",
                    reference_id=str(roll.id),
                    idempotency_key=f"plate_roll_reward:{roll.id}",
                    meta={"rarity": plate.rarity},
                )

            self._update_user(user, plate, rank, now)

            self.progression.add_roll_xp(
                user,
                new_plate=not grant.is_duplicate,
                new_country=grant.is_new_country,
                new_region=grant.is_new_region,
                first_discovery=is_first,
                rare=rank >= RARE_RANK,
            )
            self.progression.recompute_counters(user)

            missions_done = self.missions.record(user, self._mission_events(generated, grant, rank))
            albums_done = self.albums.evaluate(user)
            unlocked = self.achievements.evaluate(user)

            self._track_events(user, plate, roll, is_first, rank)

            self.db.commit()
            self.db.refresh(roll)

            return self._build_outcome(
                user,
                roll,
                grants=grant,
                is_first_discovery=is_first,
                numora_awarded=numora_awarded,
                missions=[item.to_dict() for item in missions_done],
                albums=albums_done,
                achievements=summarize(unlocked),
                event=event.to_dict(),
            )

    def _update_user(self, user: User, plate: Plate, rank: int, now) -> None:
        """Update the cached per-user counters inside the same transaction."""
        user.total_rolls = int(user.total_rolls) + 1
        user.last_roll_at = now

        if int(plate.collector_value) > int(user.best_collector_value):
            user.best_collector_value = int(plate.collector_value)
            user.best_plate_id = plate.id
        if rank >= rarity_rank(user.best_rarity or Rarity.COMMON.value):
            user.best_value = int(plate.dealer_value)
            user.best_rarity = plate.rarity
        self.db.flush()

    def _mission_events(self, generated, grant, rank: int) -> dict[str, int]:
        """Translate what happened into mission counters."""
        traits = set(generated.analysis.traits)
        return {
            "rolls": 1,
            "rare_found": 1 if rank >= RARE_RANK else 0,
            "new_country": 1 if grant.is_new_country else 0,
            "duplicate": 1 if grant.is_duplicate else 0,
            "repeated_pattern": 1
            if traits & {"repeated_pattern", "pair_letter", "triple_letter"}
            else 0,
            "find_777": 1 if "contains_777" in traits else 0,
            "find_palindrome": 1 if traits & {"palindrome", "symmetric_plate"} else 0,
            "country_plate": 1 if generated.country.code == "JPN" else 0,
        }

    def _track_events(
        self,
        user: User,
        plate: Plate,
        roll: PlateRoll,
        is_first: bool,
        rank: int,
    ) -> None:
        """Analytics for one roll. No secrets, no PII beyond internal ids."""
        props = {
            "plate_id": plate.id,
            "country": plate.country_code,
            "region": plate.region_code,
            "rarity": plate.rarity,
            "score": int(plate.rarity_score),
            "template": plate.template.code if plate.template else "",
            "collector_value": int(plate.collector_value),
            "dealer_value": int(plate.dealer_value),
            "duplicate": bool(roll.is_duplicate),
        }

        def _track(name) -> None:
            self.analytics.track(
                name.value if hasattr(name, "value") else str(name),
                user_id=user.id,
                telegram_id=user.telegram_id,
                props=props,
            )

        _track(AnalyticsEventName.ROLL_COMPLETED)
        if is_first:
            _track(AnalyticsEventName.FIRST_DISCOVERY)
        if rank >= RARE_RANK:
            _track(AnalyticsEventName.RARE_FOUND)
        _track(
            AnalyticsEventName.PLATE_DUPLICATE
            if roll.is_duplicate
            else AnalyticsEventName.PLATE_COLLECTED
        )

        if int(user.total_rolls) == 1:
            self.analytics.track(
                AnalyticsEventName.FIRST_ROLL.value,
                user_id=user.id,
                telegram_id=user.telegram_id,
            )


__all__ = ["PlateRollOutcome", "PlateRollService"]
