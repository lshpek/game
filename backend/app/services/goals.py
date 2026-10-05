"""Country completion sets and the single next objective.

Retention in a collector game comes from always being one find away from something. This
module turns the progression systems NUMORA already has - country completion sets, daily
missions, albums, achievements and first discoveries - into **one** concise objective, so
the player is told what to hunt next instead of being handed a dashboard.

Design rules
------------
* **One objective, not a list.** Exactly one target is returned.
* **Server-owned.** The counts come from the same authoritative rows the roll, the albums
  and the missions already use.
* **No user-facing copy.** The payload carries stable codes and numbers; the client
  renders the sentence through i18n, so no backend string is shown to a player and
  nothing is hardcoded in English.
* **Cheap.** A handful of aggregate queries, so it is safe to call on every roll.

Country completion sets
-----------------------
Every playable country is split into four sections - ``STANDARD``, ``REGIONAL``,
``RARE_FORMATS`` and ``SPECIAL`` - whose totals are derived from the live catalogue, so
they stay meaningful as a country's layouts grow instead of being a frozen hand-count.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.numora import Mission, UserMission
from app.models.plates import Album, Country, Plate, PlateTemplate, Region, UserPlate
from app.models.progression import Achievement, UserAchievement
from app.models.user import User

#: Plate types that belong to the ``SPECIAL`` section rather than ``STANDARD``.
SPECIAL_PLATE_TYPES: frozenset[str] = frozenset(
    {
        "SPECIAL",
        "HISTORICAL",
        "DIPLOMATIC_STYLE",
        "GOVERNMENT_STYLE",
        "MOTORCYCLE",
        "COMMERCIAL",
    }
)

#: The four country sections, in presentation order.
COUNTRY_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("STANDARD", "Standard", "Стандарт"),
    ("REGIONAL", "Regional", "Региональные"),
    ("RARE_FORMATS", "Rare Formats", "Редкие форматы"),
    ("SPECIAL", "Special", "Специальные"),
)

#: Rarity tiers that count towards the "rare formats" section.
RARE_TIERS: tuple[str, ...] = ("RARE", "EPIC", "LEGENDARY", "MYTHIC", "SECRET")

#: A goal is offered as the next objective once it is within this many finds.
NEAR_TERM = 3

#: How many distinct operators make a SIM collection feel covered.
OPERATOR_GOAL = 3

#: Tier -> achievement metric, for the "you have never found one of these" objective.
TIER_METRICS: tuple[tuple[str, str, str], ...] = (
    ("RARE", "RARITY_RARE", "RARITY_RARE"),
    ("EPIC", "RARITY_EPIC", "RARITY_EPIC"),
    ("LEGENDARY", "RARITY_LEGENDARY", "LEGENDARY_HUNTER"),
    ("MYTHIC", "RARITY_MYTHIC", "MYTHIC_HUNTER"),
)


@dataclass(frozen=True, slots=True)
class SectionTotals:
    """Catalogue-derived targets for one country."""

    standard: int
    special: int
    regions: int


def section_totals(db: Session, country: Country) -> SectionTotals:
    """Targets for one country's sections, derived from the live catalogue.

    Targets count *collectible formats* - the country's layouts - not every possible
    serial. A country's catalogue is the space the player is actually completing, so the
    goal is both honest and reachable; multiplying layouts by regions (or worse, by every
    SIM edition) would produce a number no one could ever see through.
    """
    rows = (
        db.execute(
            select(PlateTemplate.plate_type).where(
                PlateTemplate.country_id == country.id,
                PlateTemplate.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    standard_templates = sum(
        1 for value in rows if str(value or "").upper() not in SPECIAL_PLATE_TYPES
    )
    special_templates = len(rows) - standard_templates
    regions = int(
        db.execute(select(func.count(Region.id)).where(Region.country_id == country.id)).scalar_one()
        or 0
    )
    return SectionTotals(
        standard=max(1, standard_templates),
        special=max(1, special_templates),
        regions=regions,
    )


def country_sections(db: Session, user_id: int, country: Country) -> list[dict[str, object]]:
    """The four completion sections of one country for one player."""
    totals = section_totals(db, country)
    rows = (
        db.execute(
            select(Plate.rarity, Plate.region_code, Plate.plate_type, Plate.is_secret)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id, Plate.country_id == country.id)
        )
        .all()
    )

    standard_owned = 0
    special_owned = 0
    rare_owned = 0
    regions: set[str] = set()
    for rarity, region, plate_type, is_secret in rows:
        plate_type_code = str(plate_type or "").upper()
        if plate_type_code in SPECIAL_PLATE_TYPES:
            special_owned += 1
        else:
            standard_owned += 1
        if is_secret or str(rarity or "").upper() in RARE_TIERS:
            rare_owned += 1
        if region:
            regions.add(str(region))

    counts = {
        "STANDARD": (standard_owned, totals.standard),
        "REGIONAL": (len(regions), totals.regions or 1),
        "RARE_FORMATS": (rare_owned, max(1, totals.standard // 4)),
        "SPECIAL": (special_owned, totals.special),
    }

    sections: list[dict[str, object]] = []
    for code, name_en, name_ru in COUNTRY_SECTIONS:
        collected, target = counts[code]
        target = max(1, int(target))
        # Never show more collected than the section can hold: a player who owns more
        # than the catalogue implies still reads as "complete", not as a broken counter.
        held = int(min(collected, target))
        sections.append(
            {
                "code": code,
                "name_en": name_en,
                "name_ru": name_ru,
                "collected": held,
                "total": target,
                "remaining": max(0, target - held),
                "progress": round(min(1.0, held / target), 4),
                "completed": collected >= target,
            }
        )
    return sections


def country_completion(db: Session, user: User, country: Country) -> dict[str, object]:
    """Country completion: the four sections plus the overall total."""
    sections = country_sections(db, user.id, country)
    total = sum(int(section["total"]) for section in sections)  # type: ignore[arg-type]
    collected = sum(int(section["collected"]) for section in sections)  # type: ignore[arg-type]
    return {
        "country_code": country.code,
        "sections": sections,
        "collected": collected,
        "total": total,
        "remaining": max(0, total - collected),
        "progress": round(min(1.0, collected / total), 4) if total else 0.0,
        "completed": total > 0 and collected >= total,
    }


def _target(
    code: str,
    *,
    country: Country | None = None,
    current: int = 0,
    target: int = 0,
    remaining: int | None = None,
    **extra: object,
) -> dict[str, object]:
    """One machine-readable objective. The client renders the sentence via i18n."""
    left = max(0, int(target) - int(current)) if remaining is None else max(0, int(remaining))
    return {
        "code": code,
        "country_code": country.code if country is not None else "",
        "country_name_en": country.name_en if country is not None else "",
        "country_name_ru": country.name_ru if country is not None else "",
        "country_flag": country.flag if country is not None else "",
        "current": int(current),
        "target": int(target),
        "remaining": left,
        "progress": round(min(1.0, (int(current) / int(target)) if target else 0.0), 4),
        **extra,
    }


class GoalService:
    """Computes the single next objective for a player."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- helpers ---------------------------------------------------------
    def _hunt_country(self, user: User, country_code: str | None) -> Country | None:
        code = (country_code or user.active_country_code or "").strip().upper()
        if not code:
            return None
        return self.db.execute(
            select(Country).where(
                or_(Country.code == code, Country.iso_alpha2 == code),
                Country.is_active.is_(True),
            )
        ).scalar_one_or_none()

    def provider_count(self, country: Country) -> int:
        """How many operator brands the country may print."""
        config = country.sim_config or {}
        providers = config.get("providers")
        if isinstance(providers, list) and providers:
            return len(providers)
        from app.game.sim_cards import operators_for

        return len(operators_for(country.code))

    def operator_count(self, user_id: int, country: Country) -> int:
        """Distinct operator brands on the player's SIM cards in this country."""
        rows = (
            self.db.execute(
                select(Plate.details)
                .join(UserPlate, UserPlate.plate_id == Plate.id)
                .where(UserPlate.user_id == user_id, Plate.country_id == country.id)
            )
            .scalars()
            .all()
        )
        brands: set[str] = set()
        for details in rows:
            if isinstance(details, dict):
                code = str(details.get("operator_code") or "")
                if code:
                    brands.add(code)
        return len(brands)

    # --- public API ------------------------------------------------------
    def next_target(
        self,
        user: User,
        *,
        country_code: str | None = None,
        category: str | None = None,
    ) -> dict[str, object]:
        """One objective, chosen by how close the player already is to it."""
        country = self._hunt_country(user, country_code)
        hunting_sim = str(category or "").upper() == "SIM_CARD"

        if country is not None:
            sections = country_sections(self.db, user.id, country)
            near = [
                section
                for section in sections
                if 0 < int(section["remaining"]) <= NEAR_TERM  # type: ignore[arg-type]
            ]
            if near:
                # The section closest to completion is the most motivating one.
                best = min(near, key=lambda item: int(item["remaining"]))  # type: ignore[arg-type]
                return _target(
                    "country_set",
                    country=country,
                    current=int(best["collected"]),  # type: ignore[arg-type]
                    target=int(best["total"]),  # type: ignore[arg-type]
                    section_code=str(best["code"]),
                    section_name_en=str(best["name_en"]),
                    section_name_ru=str(best["name_ru"]),
                )

            regional = next((item for item in sections if item["code"] == "REGIONAL"), None)
            if (
                regional is not None
                and int(regional["remaining"]) > 0
                and int(regional["total"]) > int(regional["collected"])
            ):
                return _target(
                    "country_region",
                    country=country,
                    current=int(regional["collected"]),
                    target=int(regional["total"]),
                )

            if hunting_sim:
                available = self.provider_count(country)
                owned = self.operator_count(user.id, country)
                goal = min(OPERATOR_GOAL, available)
                if goal > 0 and owned < goal:
                    return _target(
                        "country_operator",
                        country=country,
                        current=owned,
                        target=goal,
                        providers_total=available,
                    )

        mission = self._near_mission(user)
        if mission is not None:
            return mission

        album = self._near_album(user)
        if album is not None:
            return album

        tier = self._missing_tier(user)
        if tier is not None:
            return tier

        if int(user.first_discoveries_count) == 0:
            return _target("first_discovery", current=0, target=1, reward_coins=300)

        return _target(
            "keep_rolling",
            country=country,
            current=int(user.total_rolls),
            target=int(user.total_rolls) + 1,
        )

    # --- individual sources ------------------------------------------------
    def _near_mission(self, user: User) -> dict[str, object] | None:
        """The daily mission closest to completion, if any is close."""
        rows = (
            self.db.execute(
                select(UserMission, Mission)
                .join(Mission, Mission.id == UserMission.mission_id)
                .where(
                    UserMission.user_id == user.id,
                    UserMission.mission_date == utcnow().date(),
                    UserMission.completed_at.is_(None),
                )
            )
            .all()
        )
        near: list[tuple[int, UserMission, Mission]] = []
        for progress, mission in rows:
            left = max(0, int(mission.target) - int(progress.progress))
            if 0 < left <= NEAR_TERM:
                near.append((left, progress, mission))
        if not near:
            return None
        left, progress, mission = min(near, key=lambda item: item[0])
        return _target(
            "mission",
            current=int(progress.progress),
            target=int(mission.target),
            remaining=left,
            mission_code=mission.code,
            mission_name_en=mission.name_en,
            mission_name_ru=mission.name_ru,
            reward_coins=int(mission.reward_coins),
        )

    def _near_album(self, user: User) -> dict[str, object] | None:
        """The album closest to completion, if any is close."""
        from app.services.albums import AlbumService

        albums = (
            self.db.execute(select(Album).where(Album.is_active.is_(True)))
            .scalars()
            .all()
        )
        if not albums:
            return None
        service = AlbumService(self.db)
        best: tuple[int, dict[str, object]] | None = None
        for album in albums:
            collected = service.collected_count(user.id, album)
            total = service.total_count(album)
            left = max(0, total - collected)
            if 0 < left <= NEAR_TERM and (best is None or left < best[0]):
                best = (
                    left,
                    _target(
                        "album",
                        current=collected,
                        target=total,
                        album_code=album.code,
                        album_name_en=album.name_en,
                        album_name_ru=album.name_ru,
                        reward_coins=int((album.config or {}).get("reward_coins", 0)),
                    ),
                )
        return best[1] if best else None

    def _missing_tier(self, user: User) -> dict[str, object] | None:
        """A tier the player has never found, with what completing it is worth."""
        owned_ids = {
            int(item)
            for item in self.db.execute(
                select(UserAchievement.achievement_id).where(UserAchievement.user_id == user.id)
            )
            .scalars()
            .all()
        }
        if not owned_ids:
            # No achievement rows yet: offer the first achievable one so the player has
            # a concrete goal from the very first session.
            rows = (
                self.db.execute(select(Achievement).where(Achievement.code == "FIRST_PLATE"))
                .scalars()
                .all()
            )
            if not rows or rows[0].id in owned_ids:
                return None
            return _target(
                "collection",
                current=int(user.plates_count),
                target=1,
                achievement_code="FIRST_PLATE",
                reward_coins=int(rows[0].reward_coins or 0),
            )

        codes = {
            str(code)
            for code in self.db.execute(
                select(Achievement.code).where(Achievement.id.in_(owned_ids))
            )
            .scalars()
            .all()
        }
        from app.game.achievements import achievement_by_code

        for tier, _metric, code in TIER_METRICS:
            if code in codes:
                continue
            definition = achievement_by_code(code)
            if definition is None:
                continue
            return _target(
                "rarity",
                current=0,
                target=max(1, definition.threshold),
                rarity=tier,
                achievement_code=code,
                reward_coins=definition.reward_coins,
            )
        return None


__all__ = [
    "COUNTRY_SECTIONS",
    "NEAR_TERM",
    "OPERATOR_GOAL",
    "RARE_TIERS",
    "SPECIAL_PLATE_TYPES",
    "TIER_METRICS",
    "GoalService",
    "country_completion",
    "country_sections",
    "section_totals",
]
