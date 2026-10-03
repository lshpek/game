"""Leaderboards.

Queries are aggregate-only and bounded by ``limit`` with supporting indexes
(``rolls.user_id/created_at``, ``rolls.rarity/created_at``,
``user_numbers.user_id/first_acquired_at``) so no N+1 fan-out occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.timeutils import start_of_utc_day, start_of_utc_week
from app.game.rarity import RARITY_RANK
from app.models.enums import LeaderboardCategory
from app.models.number import UserNumber
from app.models.roll import Roll
from app.models.user import User

RARITY_CASE = case(RARITY_RANK, value=Roll.rarity, else_=0)
MAX_LIMIT = 100


@dataclass(slots=True)
class LeaderboardPeriod:
    key: str
    label: str
    since: datetime | None


def periods() -> dict[str, LeaderboardPeriod]:
    return {
        "daily": LeaderboardPeriod("daily", "Today", start_of_utc_day()),
        "weekly": LeaderboardPeriod("weekly", "This week", start_of_utc_week()),
        "alltime": LeaderboardPeriod("alltime", "All time", None),
    }


def _display(username: str | None, first_name: str | None, last_name: str | None) -> str:
    full = f"{first_name or ''} {last_name or ''}".strip()
    return full or (f"@{username}" if username else "Player")


def _entry(row, *, score: int, rolls: int = 0) -> dict[str, object]:
    return {
        "user_id": row.user_id,
        "display_name": _display(row.username, row.first_name, row.last_name),
        "username": row.username,
        "photo_url": row.photo_url,
        "score": score,
        "rolls": rolls,
    }


class LeaderboardService:
    """Computes daily, weekly and all-time rankings."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _period(self, period: str) -> LeaderboardPeriod:
        return periods().get(period, periods()["daily"])

    def _rolls_query(self, since: datetime | None):
        stmt = (
            select(
                Roll.user_id.label("user_id"),
                func.count(Roll.id).label("rolls"),
                func.coalesce(func.sum(Roll.value), 0).label("value"),
                func.coalesce(func.max(RARITY_CASE), 0).label("rarity_rank"),
                User.username,
                User.first_name,
                User.last_name,
                User.photo_url,
            )
            .join(User, User.id == Roll.user_id)
            .group_by(Roll.user_id, User.username, User.first_name, User.last_name, User.photo_url)
        )
        if since is not None:
            stmt = stmt.where(Roll.created_at >= since)
        return stmt

    def _value_leaderboard(self, since: datetime | None, limit: int) -> list[dict[str, object]]:
        stmt = self._rolls_query(since).order_by(func.sum(Roll.value).desc()).limit(limit)
        return [_entry(row, score=int(row.value or 0), rolls=int(row.rolls)) for row in self.db.execute(stmt)]

    def _rarest_leaderboard(self, since: datetime | None, limit: int) -> list[dict[str, object]]:
        stmt = (
            self._rolls_query(since)
            .order_by(func.max(RARITY_CASE).desc(), func.sum(Roll.value).desc())
            .limit(limit)
        )
        return [_entry(row, score=int(row.rarity_rank or 0), rolls=int(row.rolls)) for row in self.db.execute(stmt)]

    def _rolls_leaderboard(self, since: datetime | None, limit: int) -> list[dict[str, object]]:
        stmt = self._rolls_query(since).order_by(func.count(Roll.id).desc()).limit(limit)
        return [_entry(row, score=int(row.rolls), rolls=int(row.rolls)) for row in self.db.execute(stmt)]

    def _collection_leaderboard(self, since: datetime | None, limit: int) -> list[dict[str, object]]:
        owned = func.count(func.distinct(UserNumber.number_id))
        stmt = (
            select(
                UserNumber.user_id.label("user_id"),
                owned.label("owned"),
                User.username,
                User.first_name,
                User.last_name,
                User.photo_url,
            )
            .join(User, User.id == UserNumber.user_id)
            .group_by(UserNumber.user_id, User.username, User.first_name, User.last_name, User.photo_url)
            .order_by(owned.desc())
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(UserNumber.first_acquired_at >= since)
        return [_entry(row, score=int(row.owned)) for row in self.db.execute(stmt)]

    def leaderboard(
        self,
        *,
        category: str = "VALUE",
        period: str = "daily",
        limit: int = 20,
    ) -> dict[str, object]:
        try:
            resolved = LeaderboardCategory(str(category).upper())
        except ValueError:
            resolved = LeaderboardCategory.VALUE

        window = self._period(period)
        bounded = max(1, min(int(limit), MAX_LIMIT))

        builders = {
            LeaderboardCategory.VALUE: self._value_leaderboard,
            LeaderboardCategory.RARITY: self._rarest_leaderboard,
            LeaderboardCategory.COLLECTION: self._collection_leaderboard,
            LeaderboardCategory.ROLLS: self._rolls_leaderboard,
        }
        entries = builders[resolved](window.since, bounded)
        return {
            "category": resolved.value,
            "period": window.key,
            "label": window.label,
            "entries": entries,
        }

    def all_boards(self, *, limit: int = 20) -> dict[str, dict[str, object]]:
        """Every board for one period - used by the ranking screen."""
        return {
            period: {
                category: self.leaderboard(category=category, period=period, limit=limit)
                for category in ("VALUE", "RARITY", "COLLECTION", "ROLLS")
            }
            for period in periods()
        }

    def rank_of(self, user_id: int, *, category: str = "VALUE", period: str = "daily") -> int | None:
        """Position of one user inside the visible board (bounded query)."""
        data = self.leaderboard(category=category, period=period, limit=MAX_LIMIT)
        for index, entry in enumerate(data["entries"], start=1):  # type: ignore[union-attr]
            if entry["user_id"] == user_id:  # type: ignore[index]
                return index
        return None
