"""Collector level and collection XP.

XP is earned by collecting, never bought - the level ladder is a display of
progress, not a paywall. All values live here so tuning never needs a code
change elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.plates import Plate, UserPlate
from app.models.user import User

# XP awarded per event. Tuned so early levels arrive quickly and later ones
# require sustained collecting.
XP_PER_NEW_PLATE = 8
XP_PER_NEW_COUNTRY = 120
XP_PER_NEW_REGION = 35
XP_PER_ALBUM = 250
XP_PER_FIRST_DISCOVERY = 60
XP_PER_CHALLENGE_WIN = 90
XP_PER_STREAK_DAY = 20
XP_PER_RARE_FIND = 15

LEVEL_TITLES: tuple[tuple[int, str, str], ...] = (
    (1, "Rookie", "Новичок"),
    (5, "Collector", "Коллекционер"),
    (10, "Hunter", "Охотник"),
    (20, "World Collector", "Коллекционер мира"),
    (50, "Plate Addict", "Заядог для номеров"),
    (100, "NUMORA Legend", "Легенда NUMORA"),
)


@dataclass(slots=True)
class CollectorLevel:
    level: int
    title_en: str
    title_ru: str
    xp: int
    xp_into_level: int
    xp_for_level: int
    progress: float

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "title_en": self.title_en,
            "title_ru": self.title_ru,
            "xp": self.xp,
            "xp_into_level": self.xp_into_level,
            "xp_for_level": self.xp_for_level,
            "progress": self.progress,
        }


def level_for_xp(xp: int) -> int:
    """Cumulative XP required to reach each level.

    Level ``n`` needs ``120 * (n-1) ** 1.55`` XP in total - fast early, slow late.
    """
    target = 1
    while target < 999:
        required = int(120 * ((target) ** 1.55))
        if xp < required:
            return target
        target += 1
    return target  # pragma: no cover


def xp_for_level(level: int) -> int:
    return int(120 * max(0, level) ** 1.55)


def title_for_level(level: int) -> tuple[str, str]:
    current = (1, LEVEL_TITLES[0][1], LEVEL_TITLES[0][2])
    for threshold, en, ru in LEVEL_TITLES:
        if level >= threshold:
            current = (threshold, en, ru)
    return current[1], current[2]


class ProgressionService:
    """Adds collection XP and keeps the cached counters correct."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add_xp(self, user: User, amount: int) -> int:
        """Add XP and recompute the level. Returns the new level."""
        if amount <= 0:
            return int(user.collector_level)
        user.collection_xp = int(user.collection_xp) + int(amount)
        user.collector_level = level_for_xp(int(user.collection_xp))
        self.db.flush()
        return int(user.collector_level)

    def add_roll_xp(self, user: User, *, new_plate: bool, new_country: bool, new_region: bool, first_discovery: bool, rare: bool) -> int:
        """XP for one roll, assembled from what actually happened."""
        xp = 0
        if new_plate:
            xp += XP_PER_NEW_PLATE
        if new_country:
            xp += XP_PER_NEW_COUNTRY
        if new_region:
            xp += XP_PER_NEW_REGION
        if first_discovery:
            xp += XP_PER_FIRST_DISCOVERY
        if rare:
            xp += XP_PER_RARE_FIND
        return self.add_xp(user, xp) if xp else int(user.collector_level)

    def recompute_counters(self, user: User) -> None:
        """Recount plate/country/region totals from the ownership table."""
        plates = int(
            self.db.execute(
                select(func.count(func.distinct(UserPlate.plate_id))).where(UserPlate.user_id == user.id)
            ).scalar_one()
            or 0
        )
        countries = int(
            self.db.execute(
                select(func.count(func.distinct(Plate.country_id)))
                .join(UserPlate, UserPlate.plate_id == Plate.id)
                .where(UserPlate.user_id == user.id)
            ).scalar_one()
            or 0
        )
        regions = int(
            self.db.execute(
                select(func.count(func.distinct(Plate.region_id)))
                .join(UserPlate, UserPlate.plate_id == Plate.id)
                .where(UserPlate.user_id == user.id, Plate.region_id.isnot(None))
            ).scalar_one()
            or 0
        )
        user.plates_count = plates
        user.countries_count = countries
        user.regions_count = regions
        self.db.flush()

    def current_level(self, user: User) -> CollectorLevel:
        xp = int(user.collection_xp)
        level = level_for_xp(xp)
        base = xp_for_level(level - 1)
        needed = xp_for_level(level) - base
        into = xp - base
        title_en, title_ru = title_for_level(level)
        progress = 0.0 if needed <= 0 else max(0.0, min(1.0, into / needed))
        return CollectorLevel(
            level=level,
            title_en=title_en,
            title_ru=title_ru,
            xp=xp,
            xp_into_level=max(0, into),
            xp_for_level=max(0, needed),
            progress=round(progress, 4),
        )


__all__ = [
    "LEVEL_TITLES",
    "CollectorLevel",
    "ProgressionService",
    "level_for_xp",
    "title_for_level",
    "xp_for_level",
]
