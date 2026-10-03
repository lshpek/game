"""Achievement evaluation.

Metrics are resolved from the user's persisted counters, so unlocking is
deterministic and replay-safe (rewards are keyed by ``achievement:{id}``).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.game.rarity import RARITY_RANK, Rarity
from app.models.enums import TransactionType
from app.models.number import Discovery, Number, UserNumber
from app.models.payment import PremiumEntitlement
from app.models.progression import Achievement, UserAchievement
from app.models.social import Challenge, Referral, ShareEvent
from app.models.user import User
from app.services.economy import EconomyService


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

    def _rarity_count(self, user: User, threshold_rank: int) -> int:
        rarities = [code for code, rank in RARITY_RANK.items() if rank >= threshold_rank]
        stmt = (
            select(func.count(func.distinct(UserNumber.number_id)))
            .join(Number, Number.id == UserNumber.number_id)
            .where(UserNumber.user_id == user.id, Number.rarity.in_(rarities))
        )
        return int(self.db.execute(stmt).scalar_one() or 0)

    def _secret_first_count(self, user: User) -> int:
        """First-ever discoveries of *Secret* numbers only."""
        stmt = (
            select(func.count())
            .select_from(Discovery)
            .join(Number, Number.id == Discovery.number_id)
            .where(
                Discovery.user_id == user.id,
                Discovery.is_first_discovery.is_(True),
                Number.rarity == Rarity.SECRET.value,
            )
        )
        return int(self.db.execute(stmt).scalar_one() or 0)

    def metrics(self, user: User) -> dict[str, int]:
        """Current value of every metric referenced by the catalogue."""
        return {
            "total_rolls": int(user.total_rolls),
            "unique_numbers": int(user.unique_numbers_count),
            "containers_opened": int(user.containers_opened),
            "streak": int(user.longest_streak),
            "referrals": self._count(
                Referral, Referral.referrer_id == user.id, Referral.reward_paid.is_(True)
            ),
            "challenges_completed": int(user.challenges_completed),
            "shares": self._count(ShareEvent, ShareEvent.user_id == user.id),
            "rarity_rare": self._rarity_count(user, RARITY_RANK[Rarity.RARE.value]),
            "rarity_epic": self._rarity_count(user, RARITY_RANK[Rarity.EPIC.value]),
            "rarity_legendary": self._rarity_count(user, RARITY_RANK[Rarity.LEGENDARY.value]),
            "rarity_mythic": self._rarity_count(user, RARITY_RANK[Rarity.MYTHIC.value]),
            "secret_first_discovery": self._secret_first_count(user),
        }

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
