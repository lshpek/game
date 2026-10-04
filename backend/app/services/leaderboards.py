"""Leaderboards that reward collecting, never wallet balance.

Every board is a single aggregate query over indexed columns, so no N+1 fan-out
occurs and a board stays cheap at any table size.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.timeutils import start_of_utc_day, start_of_utc_week
from app.game.plate_rarity import RARITY_RANK
from app.models.numora import PlateRoll
from app.models.plates import Plate, PlateDiscovery, UserPlate
from app.models.user import User

MAX_LIMIT = 100

# Rank of a rarity, used to find each player's best find.
RARITY_CASE = case(RARITY_RANK, value=Plate.rarity, else_=0)


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


def _entry(row, *, score: int, metric: str) -> dict[str, object]:
    return {
        "user_id": row.user_id,
        "display_name": _display(row.username, row.first_name, row.last_name),
        "username": row.username,
        "photo_url": row.photo_url,
        "score": score,
        "metric": metric,
    }


class PlateLeaderboardService:
    """Computes the collection, rarity and discovery boards."""

    IDENTITY_COLUMNS = (User.username, User.first_name, User.last_name, User.photo_url)

    def __init__(self, db: Session) -> None:
        self.db = db

    def _period(self, period: str) -> LeaderboardPeriod:
        return periods().get(period, periods()["daily"])

    def _owned_aggregate(self):
        return (
            select(
                UserPlate.user_id.label("user_id"),
                func.count(func.distinct(UserPlate.plate_id)).label("plates"),
                func.count(func.distinct(Plate.country_id)).label("countries"),
                func.coalesce(func.max(RARITY_CASE), 0).label("rarity_rank"),
                *self.IDENTITY_COLUMNS
            )
            .join(Plate, Plate.id == UserPlate.plate_id)
            .join(User, User.id == UserPlate.user_id)
            .group_by(UserPlate.user_id, *self.IDENTITY_COLUMNS)
        )

    def _discovery_aggregate(self, since: datetime | None):
        stmt = (
            select(
                PlateDiscovery.user_id.label("user_id"),
                func.count(PlateDiscovery.id).label("discoveries"),
                *self.IDENTITY_COLUMNS
            )
            .join(User, User.id == PlateDiscovery.user_id)
            .where(PlateDiscovery.is_first_discovery.is_(True))
            .group_by(PlateDiscovery.user_id, *self.IDENTITY_COLUMNS)
        )
        if since is not None:
            stmt = stmt.where(PlateDiscovery.created_at >= since)
        return stmt

    def _roll_aggregate(self, since: datetime | None):
        stmt = (
            select(
                PlateRoll.user_id.label("user_id"),
                func.count(PlateRoll.id).label("rolls"),
                *self.IDENTITY_COLUMNS
            )
            .join(User, User.id == PlateRoll.user_id)
            .group_by(PlateRoll.user_id, *self.IDENTITY_COLUMNS)
        )
        if since is not None:
            stmt = stmt.where(PlateRoll.created_at >= since)
        return stmt

    # --- boards ---------------------------------------------------------
    def board(self, category: str, since: datetime | None, limit: int) -> list[dict[str, object]]:
        key = category.upper()

        if key == "COUNTRIES":
            stmt = self._owned_aggregate().order_by(
                func.count(func.distinct(Plate.country_id)).desc()
            )
            return [
                _entry(row, score=int(row.countries or 0), metric="COUNTRIES")
                for row in self.db.execute(stmt.limit(limit))
            ]

        if key == "FIRST_DISCOVERIES":
            stmt = self._discovery_aggregate(since).order_by(func.count(PlateDiscovery.id).desc())
            return [
                _entry(row, score=int(row.discoveries or 0), metric="FIRST_DISCOVERIES")
                for row in self.db.execute(stmt.limit(limit))
            ]

        if key in ("RARITY", "SEASON", "VALUE"):
            stmt = self._owned_aggregate().order_by(
                func.max(RARITY_CASE).desc(),
                func.max(Plate.rarity_score).desc(),
                func.max(Plate.collector_value).desc(),
            )
            return [
                _entry(row, score=int(row.rarity_rank or 0), metric=key)
                for row in self.db.execute(stmt.limit(limit))
            ]

        if key == "ROLLS":
            stmt = self._roll_aggregate(since).order_by(func.count(PlateRoll.id).desc())
            return [
                _entry(row, score=int(row.rolls or 0), metric="ROLLS")
                for row in self.db.execute(stmt.limit(limit))
            ]

        # Default: most collected plates.
        stmt = self._owned_aggregate().order_by(
            func.count(func.distinct(UserPlate.plate_id)).desc()
        )
        return [
            _entry(row, score=int(row.plates or 0), metric="COLLECTION")
            for row in self.db.execute(stmt.limit(limit))
        ]

    def leaderboard(
        self, *, category: str = "COLLECTION", period: str = "daily", limit: int = 20
    ) -> dict[str, object]:
        window = self._period(period)
        bounded = max(1, min(int(limit), MAX_LIMIT))
        return {
            "category": category.upper(),
            "period": window.key,
            "label": window.label,
            "entries": self.board(category, window.since, bounded),
        }

    def all_boards(self, *, limit: int = 20) -> dict[str, dict[str, object]]:
        categories = ("COLLECTION", "COUNTRIES", "FIRST_DISCOVERIES", "RARITY", "ROLLS")
        return {
            period: {
                category: self.leaderboard(category=category, period=period, limit=limit)
                for category in categories
            }
            for period in periods()
        }

    def rank_of(self, user_id: int, *, category: str = "COLLECTION", period: str = "daily") -> int | None:
        data = self.leaderboard(category=category, period=period, limit=MAX_LIMIT)
        for index, entry in enumerate(data["entries"], start=1):  # type: ignore[union-attr]
            if entry["user_id"] == user_id:  # type: ignore[index]
                return index
        return None


__all__ = ["MAX_LIMIT", "LeaderboardPeriod", "PlateLeaderboardService", "periods"]
