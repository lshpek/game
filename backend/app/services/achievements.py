"""Achievement evaluation.

Metrics are resolved from the user's persisted counters, so unlocking is
deterministic and replay-safe (rewards are keyed by ``achievement:{id}``).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.game.plate_rarity import RARITY_RANK
from app.models.enums import TransactionType
from app.models.payment import PremiumEntitlement
from app.models.plates import Country, Plate, PlateDiscovery, UserPlate
from app.models.progression import Achievement, UserAchievement
from app.models.social import Challenge, Referral, ShareEvent
from app.models.user import User
from app.services.economy import EconomyService

# Traits that count toward the pattern achievements.
PALINDROME_TRAITS = ("palindrome", "symmetric_plate")
REPEAT_TRAITS = ("repeated_pattern", "pair_letter", "triple_letter")


class AchievementService:
    """Unlocks achievements and pays their rewards exactly once."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.economy = EconomyService(db)

    def _count(self, model, *conditions) -> int:
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return int(self.db.execute(stmt).scalar_one() or 0)

    def _owned(self, user: User) -> list[tuple]:
        """One bounded query feeding every plate-derived metric."""
        stmt = (
            select(UserPlate.plate_id, Plate.rarity, Plate.country_id, Plate.tags, Plate.is_secret)
            .join(Plate, Plate.id == UserPlate.plate_id)
            .where(UserPlate.user_id == user.id)
        )
        return list(self.db.execute(stmt).all())

    def _rarity_count(self, rows: list[tuple], threshold_rank: int) -> int:
        rarities = {code for code, rank in RARITY_RANK.items() if rank >= threshold_rank}
        return len({row[0] for row in rows if row[1] in rarities})

    @staticmethod
    def _has_tag(tags: object, wanted: tuple[str, ...]) -> bool:
        values = tags if isinstance(tags, (list, tuple, set)) else []
        return any(tag in wanted for tag in values)  # type: ignore[union-attr]

    def metrics(self, user: User) -> dict[str, int]:
        """Current value of every metric referenced by the catalogue."""
        rows = self._owned(user)
        country_codes = {
            int(country_id): str(code)
            for country_id, code in self.db.execute(select(Country.id, Country.code)).all()
        }
        country_counts: dict[str, int] = {}
        for row in rows:
            code = country_codes.get(int(row[2]))
            if code:
                country_counts[code.lower()] = country_counts.get(code.lower(), 0) + 1

        metrics: dict[str, int] = {
            "total_rolls": int(user.total_rolls),
            "plates": len({row[0] for row in rows}),
            "packs_opened": int(user.containers_opened),
            "streak": int(user.longest_streak),
            "countries": len({row[2] for row in rows}),
            "first_discoveries": self._count(
                PlateDiscovery,
                PlateDiscovery.user_id == user.id,
                PlateDiscovery.is_first_discovery.is_(True),
            ),
            "referrals": self._count(
                Referral, Referral.referrer_id == user.id, Referral.reward_paid.is_(True)
            ),
            "challenges_completed": int(user.challenges_completed),
            "shares": self._count(ShareEvent, ShareEvent.user_id == user.id),
            "rarity_rare": self._rarity_count(rows, RARITY_RANK["RARE"]),
            "rarity_epic": self._rarity_count(rows, RARITY_RANK["EPIC"]),
            "rarity_legendary": self._rarity_count(rows, RARITY_RANK["LEGENDARY"]),
            "rarity_mythic": self._rarity_count(rows, RARITY_RANK["MYTHIC"]),
            "secret": len({row[0] for row in rows if bool(row[4])}),
            "trait_palindrome": len(
                {row[0] for row in rows if self._has_tag(row[3], PALINDROME_TRAITS)}
            ),
            "trait_repeat": len({row[0] for row in rows if self._has_tag(row[3], REPEAT_TRAITS)}),
            "trait_777": len({row[0] for row in rows if self._has_tag(row[3], ("contains_777",))}),
        }
        for code, count in country_counts.items():
            metrics[f"country_{code}"] = count
        return metrics

    def evaluate(self, user: User) -> list[UserAchievement]:
        """Check every active achievement and unlock those that qualify."""
        definitions = (
            self.db.execute(select(Achievement).where(Achievement.is_active.is_(True))).scalars().all()
        )
        if not definitions:
            return []

        metrics = self.metrics(user)
        existing = {
            row.achievement_id: row
            for row in self.db.execute(
                select(UserAchievement).where(UserAchievement.user_id == user.id)
            )
            .scalars()
            .all()
        }

        unlocked: list[UserAchievement] = []
        for definition in definitions:
            progress = int(metrics.get(definition.metric, 0))
            row = existing.get(definition.id)
            if row is None:
                row = UserAchievement(
                    user_id=user.id,
                    achievement_id=definition.id,
                    progress=progress,
                    unlocked_at=None,
                )
                self.db.add(row)
                self.db.flush()
                existing[definition.id] = row
            else:
                row.progress = max(int(row.progress), progress)

            if row.unlocked_at is None and progress >= int(definition.threshold):
                row.unlocked_at = utcnow()
                unlocked.append(row)
                if definition.reward_coins:
                    self.economy.credit(
                        user.id,
                        int(definition.reward_coins),
                        TransactionType.ACHIEVEMENT_REWARD,
                        reference_type="achievement",
                        reference_id=definition.code,
                        idempotency_key=f"achievement:{user.id}:{definition.code}",
                    )
        self.db.flush()
        return unlocked

    def list_for_user(self, user: User) -> list[dict[str, object]]:
        """Full achievement list with progress for the profile screen."""
        definitions = (
            self.db.execute(
                select(Achievement)
                .where(Achievement.is_active.is_(True))
                .order_by(Achievement.sort_order, Achievement.id)
            )
            .scalars()
            .all()
        )
        progress_rows = {
            row.achievement_id: row
            for row in self.db.execute(
                select(UserAchievement).where(UserAchievement.user_id == user.id)
            )
            .scalars()
            .all()
        }
        metrics = self.metrics(user)
        result: list[dict[str, object]] = []
        for definition in definitions:
            row = progress_rows.get(definition.id)
            progress = min(int(metrics.get(definition.metric, 0)), int(definition.threshold))
            result.append(
                {
                    "code": definition.code,
                    "name": definition.name,
                    "description": definition.description,
                    "icon": definition.icon,
                    "threshold": int(definition.threshold),
                    "progress": progress,
                    "reward_coins": int(definition.reward_coins),
                    "unlocked": bool(row and row.unlocked_at),
                    "unlocked_at": row.unlocked_at.isoformat() if row and row.unlocked_at else None,
                }
            )
        return result

    def unlocked_count(self, user_id: int) -> int:
        return self._count(UserAchievement, UserAchievement.user_id == user_id, UserAchievement.unlocked_at.isnot(None))

    def challenge_count(self, user_id: int) -> int:
        return self._count(Challenge, Challenge.challenger_id == user_id)

    def has_premium_history(self, user_id: int) -> bool:
        return self._count(PremiumEntitlement, PremiumEntitlement.user_id == user_id) > 0


def summarize(unlocked: list[UserAchievement]) -> list[dict[str, object]]:
    """Serialise freshly unlocked achievements for API responses."""
    return [
        {
            "code": row.achievement.code,
            "name": row.achievement.name,
            "description": row.achievement.description,
            "icon": row.achievement.icon,
            "reward_coins": int(row.achievement.reward_coins),
        }
        for row in unlocked
    ]
