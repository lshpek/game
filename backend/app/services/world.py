"""WORLD: the collection atlas.

Country completion is computed from the template catalogue, not from a magic
constant: a country's total is how many distinct serials its active templates
can produce. That keeps ``42 / 150`` honest as countries gain templates,
without anyone maintaining a counter by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.game.plate_rarity import RARITY_RANK, rarity_rank
from app.models.plates import Country, Plate, PlateTemplate, Region, UserPlate
from app.models.user import User
from app.services.catalog import country_card, region_card, snapshot

# Combinatorics above this are capped so the displayed number stays readable.
TOTAL_CAP = 100_000


@dataclass(slots=True)
class CountryProgress:
    country: Country
    collected: int
    total: int
    best_rarity: str | None
    regions_collected: int
    regions_total: int

    @property
    def percent(self) -> float:
        return 0.0 if self.total <= 0 else round(min(1.0, self.collected / self.total), 4)

    def to_dict(self) -> dict[str, object]:
        card = country_card(self.country)
        card.update(
            {
                "collected": self.collected,
                "total": self.total,
                "progress": self.percent,
                "percent": round(self.percent * 100, 1),
                "best_rarity": self.best_rarity,
                "regions_collected": self.regions_collected,
                "regions_total": self.regions_total,
                "completed": self.total > 0 and self.collected >= self.total,
            }
        )
        return card


def estimate_country_total(templates: list[PlateTemplate]) -> int:
    """How many distinct plates a country's templates can produce.

    Product of per-template slot counts; the result is capped so the WORLD
    screen never shows an unreadable number.
    """
    total = 1
    for template in templates:
        pattern = template.pattern or ""
        letters = sum(1 for ch in pattern if ch in "LA")
        digits = sum(1 for ch in pattern if ch in "DXF")
        slots = 1
        if letters:
            slots *= 26**letters
        if digits:
            slots *= 10**digits
        total *= max(1, slots)
    return max(1, min(TOTAL_CAP, total))


class WorldService:
    """Country and region progress for one player."""

    def __init__(self, db: Session, rarity_weights: dict[str, float] | None = None) -> None:
        self.db = db
        self._weights = rarity_weights or {}
        self._snapshot = None

    def _catalog(self):
        if self._snapshot is None:
            self._snapshot = snapshot(self.db, self._weights)
        return self._snapshot

    def _collected_by_country(self, user_id: int) -> dict[int, int]:
        rows = self.db.execute(
            select(Plate.country_id, func.count(func.distinct(UserPlate.plate_id)))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id)
            .group_by(Plate.country_id)
        ).all()
        return {int(country_id): int(count) for country_id, count in rows}

    def _collected_by_region(self, user_id: int) -> dict[int, int]:
        rows = self.db.execute(
            select(Plate.region_id, func.count(func.distinct(UserPlate.plate_id)))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id, Plate.region_id.isnot(None))
            .group_by(Plate.region_id)
        ).all()
        return {int(region_id): int(count) for region_id, count in rows}

    def _best_rarity(self, user_id: int) -> dict[int, str]:
        rows = (
            self.db.execute(
                select(Plate.country_id, Plate.rarity)
                .join(UserPlate, UserPlate.plate_id == Plate.id)
                .where(UserPlate.user_id == user_id)
            )
            .tuples()
            .all()
        )
        best: dict[int, str] = {}
        for country_id, rarity in rows:
            code = int(country_id)
            if code not in best or rarity_rank(rarity) > rarity_rank(best[code]):
                best[code] = rarity
        return best

    def overview(self, user: User) -> dict[str, object]:
        """Every country with progress, ordered for the atlas screen."""
        catalog = self._catalog()
        collected = self._collected_by_country(user.id)
        regions = self._collected_by_region(user.id)
        best = self._best_rarity(user.id)

        templates_by_country: dict[int, list[PlateTemplate]] = {}
        for template in catalog.templates:
            templates_by_country.setdefault(template.country_id, []).append(template)
        regions_by_country: dict[int, list[Region]] = {}
        for region in catalog.regions:
            regions_by_country.setdefault(region.country_id, []).append(region)

        entries: list[dict[str, object]] = []
        for country in catalog.countries:
            country_regions = regions_by_country.get(country.id, [])
            entries.append(
                CountryProgress(
                    country=country,
                    collected=collected.get(country.id, 0),
                    total=estimate_country_total(templates_by_country.get(country.id, [])),
                    best_rarity=best.get(country.id),
                    regions_collected=sum(1 for r in country_regions if regions.get(r.id, 0) > 0),
                    regions_total=len(country_regions),
                ).to_dict()
            )

        entries.sort(key=lambda item: (str(item.get("region_group")), int(item.get("sort_order", 0))))

        total_plates = sum(int(e["collected"]) for e in entries)
        total_slots = sum(int(e["total"]) for e in entries)
        return {
            "countries": entries,
            "total_collected": total_plates,
            "total_plates": total_slots,
            "progress": 0.0 if total_slots <= 0 else round(min(1.0, total_plates / total_slots), 4),
            "rarity_rank": dict(RARITY_RANK),
        }

    def country_detail(self, user: User, country_code: str) -> dict[str, object]:
        """Country detail: regions, templates and the player's progress."""
        catalog = self._catalog()
        country = next((c for c in catalog.countries if c.code == country_code.upper()), None)
        if country is None:
            raise NotFoundError("Country not found.", code="COUNTRY_NOT_FOUND")

        country_templates = [t for t in catalog.templates if t.country_id == country.id]
        country_regions = [r for r in catalog.regions if r.country_id == country.id]
        collected = self._collected_by_country(user.id).get(country.id, 0)
        region_progress = self._collected_by_region(user.id)
        total = estimate_country_total(country_templates)

        return {
            **country_card(country),
            "collected": collected,
            "total": total,
            "progress": 0.0 if total <= 0 else round(min(1.0, collected / total), 4),
            "percent": round((collected / total) * 100, 1) if total else 0.0,
            "best_rarity": self._best_rarity(user.id).get(country.id),
            "completed": total > 0 and collected >= total,
            "regions": [
                {
                    **region_card(region),
                    "collected": region_progress.get(region.id, 0),
                    "plate_type_count": len(country_templates),
                }
                for region in sorted(country_regions, key=lambda r: r.sort_order)
            ],
            "templates": [
                {
                    "code": template.code,
                    "pattern": template.pattern,
                    "plate_type": template.plate_type,
                    "rarity_floor": template.rarity_floor,
                }
                for template in sorted(country_templates, key=lambda t: t.sort_order)
            ],
        }


__all__ = ["CountryProgress", "WorldService", "estimate_country_total"]