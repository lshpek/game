"""WORLD screen queries: atlas, country detail and global progress.

Kept separate from the API layer so the same numbers back the player screen, the
admin panel and the share card. Every query is aggregated in SQL: with the full
ISO 3166-1 list in the database, per-country Python loops would be a performance
problem on every request.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.game.plate_traits import trait_labels
from app.game.plate_visuals import serialize_visual
from app.models.plates import Album, Country, Plate, PlateTemplate, Region, UserPlate
from app.models.user import User
from app.services import catalog

DEFAULT_PAGE_SIZE = 60
MAX_PAGE_SIZE = 250


class WorldService:
    """Read-only views over the country catalogue and the player's progress."""

    def __init__(self, db: Session, rarity_weights: dict[str, float] | None = None) -> None:
        self.db = db
        self.rarity_weights = rarity_weights or settings.rarity_weights

    # --- helpers -----------------------------------------------------------
    def country(self, code: str) -> Country | None:
        """Resolve an ISO 3166-1 alpha-3 or alpha-2 code."""
        return catalog.country_by_code(self.db, code)

    def _collected_counts(self, user_id: int) -> dict[str, int]:
        rows = self.db.execute(
            select(Plate.country_code, func.count(func.distinct(Plate.id)))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id)
            .group_by(Plate.country_code)
        ).all()
        return {code: int(count) for code, count in rows}

    def _region_counts(self, user_id: int) -> dict[str, int]:
        rows = self.db.execute(
            select(Plate.country_code, func.count(func.distinct(Plate.region_code)))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id, Plate.region_code.isnot(None))
            .group_by(Plate.country_code)
        ).all()
        return {code: int(count) for code, count in rows}

    def totals(self) -> dict[str, int]:
        """Global collectible counts, without building any per-country payloads.

        Only playable countries are counted: a locked country has no layouts, so
        including it would inflate the global target and make every player's
        progress look worse than it is.
        """
        total = int(
            self.db.execute(
                select(func.count(PlateTemplate.id))
                .join(Country, Country.id == PlateTemplate.country_id)
                .where(
                    PlateTemplate.is_active.is_(True),
                    Country.is_active.is_(True),
                    Country.is_playable.is_(True),
                )
            ).scalar_one()
            or 0
        )
        discovered = int(
            self.db.execute(
                select(func.count(func.distinct(Plate.id)))
                .join(Country, Country.id == Plate.country_id)
                .where(Country.is_playable.is_(True))
            ).scalar_one()
            or 0
        )
        return {
            "total_templates": total,
            "discovered": discovered,
            "playable_countries": int(
                self.db.execute(
                    select(func.count(Country.id)).where(
                        Country.is_active.is_(True), Country.is_playable.is_(True)
                    )
                ).scalar_one()
                or 0
            ),
            "locked_countries": int(
                self.db.execute(
                    select(func.count(Country.id)).where(
                        Country.is_active.is_(True), Country.is_playable.is_(False)
                    )
                ).scalar_one()
                or 0
            ),
        }

    def _estimate_total(self, templates: int, slots: int) -> int:
        """Distinct serials a country can produce.

        Deliberately an *estimate*: exact combinatorics depend on alphabet size and
        repetition rules, and the number only has to make a progress bar honest.
        """
        if not templates:
            return 0
        return max(1, min(templates * max(1, slots), 100_000))

    def estimate_country_total(self, country_code: str) -> int:
        """Total collectibles a country can hold (0 for a locked country)."""
        row = self.country(country_code)
        if row is None or not row.is_playable:
            return 0
        templates = list(
            self.db.execute(
                select(PlateTemplate).where(
                    PlateTemplate.country_id == row.id, PlateTemplate.is_active.is_(True)
                )
            )
            .scalars()
            .all()
        )
        if not templates:
            return 0
        # ~20k serials per layout keeps the estimate comparable across countries
        # while staying cheap to compute.
        return self._estimate_total(len(templates), slots=3)

    # --- atlas -------------------------------------------------------------
    def overview(
        self,
        user: User,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> dict:
        """One page of the atlas plus global progress."""
        limit = max(1, min(int(limit or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
        offset = max(0, int(offset or 0))

        collected = self._collected_counts(user.id)
        regions_collected = self._region_counts(user.id)

        total_rows = int(
            self.db.execute(
                select(func.count(Country.id)).where(Country.is_active.is_(True))
            ).scalar_one()
            or 0
        )
        page = list(
            self.db.execute(
                select(Country)
                .where(Country.is_active.is_(True))
                .order_by(Country.sort_order, Country.id)
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )

        # Slot counts per country in one grouped query for the whole page.
        slot_rows = self.db.execute(
            select(PlateTemplate.country_id, func.count(PlateTemplate.id))
            .where(
                PlateTemplate.is_active.is_(True),
                PlateTemplate.country_id.in_([row.id for row in page] or [0]),
            )
            .group_by(PlateTemplate.country_id)
        ).all()
        slots = {int(cid): int(count) for cid, count in slot_rows}

        region_rows = self.db.execute(
            select(Region.country_id, func.count(Region.id))
            .where(Region.is_active.is_(True), Region.country_id.in_([row.id for row in page] or [0]))
            .group_by(Region.country_id)
        ).all()
        regions_total = {int(cid): int(count) for cid, count in region_rows}

        globals_ = self.totals()
        entries: list[dict] = []
        for row in page:
            has = collected.get(row.code, 0)
            total = self._estimate_total(slots.get(row.id, 0), slots=3) if row.is_playable else 0
            regions_have = regions_collected.get(row.code, 0)
            regions_have_count = regions_total.get(row.id, 0)
            entries.append(
                self.country_card(
                    row,
                    collected=has,
                    total=total,
                    regions_collected=regions_have,
                    regions_total=regions_have_count,
                    is_active=bool(user.active_country_code == row.code),
                )
            )

        total_collected = int(
            self.db.execute(
                select(func.count(UserPlate.plate_id)).where(UserPlate.user_id == user.id)
            ).scalar_one()
            or 0
        )
        target = globals_["total_templates"]

        return {
            "countries": entries,
            "total_collected": total_collected,
            "total_plates": target,
            "progress": round(total_collected / target, 4) if target else 0.0,
            "offset": offset,
            "limit": limit,
            "countries_total": total_rows,
            "playable_total": globals_["playable_countries"],
            "locked_total": globals_["locked_countries"],
        }

    def country_card(
        self,
        row: Country,
        *,
        collected: int = 0,
        total: int = 0,
        regions_collected: int = 0,
        regions_total: int = 0,
        is_active: bool = False,
    ) -> dict:
        """One atlas entry."""
        cfg = row.config or {}
        return {
            "code": row.code,
            "iso_alpha2": row.iso_alpha2 or "",
            "name_en": row.name_en,
            "name_ru": row.name_ru,
            "flag": row.flag,
            "region_group": row.region_group,
            "currency_code": cfg.get("currency_code", "USD"),
            "currency_symbol": cfg.get("currency_symbol", "$"),
            "calling_code": row.calling_code,
            "visual": serialize_visual(cfg.get("visual", "european")),
            "collected": collected,
            "total": total,
            "progress": round(collected / total, 4) if total else 0.0,
            "percent": int(collected / total * 100) if total else 0,
            "best_rarity": None,
            "regions_collected": regions_collected,
            "regions_total": regions_total,
            "completed": bool(total and collected >= total),
            "sort_order": row.sort_order,
            "is_active": is_active,
            "is_playable": bool(row.is_playable),
        }

    # --- one country -------------------------------------------------------
    def country_detail(self, user: User, code: str) -> dict:
        row = self.country(code)
        if row is None or not row.is_active:
            raise NotFoundError("Country not found.", code="COUNTRY_NOT_FOUND")

        collected = self._collected_counts(user.id).get(row.code, 0)
        total = self.estimate_country_total(row.code)
        cfg = row.config or {}

        regions = self.db.execute(
            select(Region).where(
                Region.country_id == row.id, Region.is_active.is_(True)
            ).order_by(Region.sort_order)
        ).scalars().all()

        # Per-region counts in one grouped query, so a country with 20 regions costs
        # the same as one with 2 - and so the detail screen can actually show which
        # regions are still missing instead of a column of zeroes.
        region_have: dict[str, int] = {}
        if regions:
            rows = self.db.execute(
                select(Plate.region_code, func.count(func.distinct(Plate.id)))
                .join(UserPlate, UserPlate.plate_id == Plate.id)
                .where(
                    UserPlate.user_id == user.id,
                    Plate.country_id == row.id,
                    Plate.region_code.isnot(None),
                )
                .group_by(Plate.region_code)
            ).all()
            region_have = {str(code): int(count) for code, count in rows}
        regions_collected = sum(1 for value in region_have.values() if value > 0)
        regions_total = len(regions)

        best = self.db.execute(
            select(Plate.rarity, func.count(Plate.id))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user.id, Plate.country_id == row.id)
            .group_by(Plate.rarity)
        ).all()
        from app.game.plate_rarity import RARITY_RANK

        best_rarity = next(
            (code for code, _count in sorted(best, key=lambda item: -RARITY_RANK.get(item[0], 0))),
            None,
        )

        templates = self.db.execute(
            select(PlateTemplate).where(
                PlateTemplate.country_id == row.id, PlateTemplate.is_active.is_(True)
            ).order_by(PlateTemplate.sort_order)
        ).scalars().all()

        return {
            "code": row.code,
            "iso_alpha2": row.iso_alpha2 or "",
            "name_en": row.name_en,
            "name_ru": row.name_ru,
            "flag": row.flag,
            "region_group": row.region_group,
            "currency_code": cfg.get("currency_code", "USD"),
            "currency_symbol": cfg.get("currency_symbol", "$"),
            "calling_code": row.calling_code,
            "visual": serialize_visual(cfg.get("visual", "european")),
            "is_playable": bool(row.is_playable),
            "collected": collected,
            "total": total,
            "progress": round(collected / total, 4) if total else 0.0,
            "percent": int(collected / total * 100) if total else 0,
            "best_rarity": best_rarity,
            "completed": bool(total and collected >= total),
            "regions_collected": regions_collected,
            "regions_total": regions_total,
            "regions": [
                {
                    "code": region.code,
                    "name_en": region.name_en,
                    "name_ru": region.name_ru,
                    "collected": region_have.get(region.code, 0),
                }
                for region in regions
            ],
            "templates": [
                {
                    "code": template.code,
                    "pattern": template.pattern,
                    "plate_type": template.plate_type,
                    "rarity_floor": template.rarity_floor,
                    "weight": float(template.weight),
                }
                for template in templates
            ],
        }

    # --- economy context ---------------------------------------------------
    def economy_context(self, user: User) -> dict:
        """Everything the collection header shows, as aggregate numbers only."""
        totals = self.totals()
        collected = int(
            self.db.execute(
                select(func.count(UserPlate.plate_id)).where(UserPlate.user_id == user.id)
            ).scalar_one()
            or 0
        )
        value = int(
            self.db.execute(
                select(func.coalesce(func.sum(Plate.dealer_value), 0))
                .join(UserPlate, UserPlate.plate_id == Plate.id)
                .where(UserPlate.user_id == user.id)
            ).scalar_one()
            or 0
        )
        target = totals["total_templates"]
        return {
            "total_collected": collected,
            "total_plates": target,
            "progress": round(collected / target, 4) if target else 0.0,
            "total_dealer_value": value,
            "playable_total": totals["playable_countries"],
            "locked_total": totals["locked_countries"],
        }

    # --- collections -------------------------------------------------------
    def albums(self) -> list[dict]:
        rows = self.db.execute(select(Album).where(Album.is_active.is_(True))).scalars().all()
        return [
            {
                "code": row.code,
                "name_en": row.name_en,
                "name_ru": row.name_ru,
                "description_en": row.description_en,
                "description_ru": row.description_ru,
                "icon": row.icon,
                "kind": row.kind,
                "country_id": row.country_id,
                "sort_order": row.sort_order,
                "reward_coins": int((row.config or {}).get("reward_coins", 0)),
                "reward_title": (row.config or {}).get("reward_title"),
            }
            for row in rows
        ]

    def collectible_today(self, user: User) -> list[dict]:
        rows = self.db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user.id)
            .order_by(UserPlate.last_acquired_at.desc())
            .limit(8)
        ).scalars().all()
        return [
            {
                "id": row.id,
                "plate_text": row.plate_text,
                "rarity": row.rarity,
                "reason_labels": trait_labels(list(row.traits or [])[:4]),
                "country_code": row.country_code,
                "currency_symbol": row.currency_symbol,
                "collector_value": int(row.collector_value),
            }
            for row in rows
        ]

    def leaderboard_scope(self, user: User) -> dict:
        """What a leaderboard row for this player should contain."""
        rows = self.db.execute(
            select(
                func.count(UserPlate.plate_id),
                func.coalesce(func.sum(Plate.dealer_value), 0),
                func.count(func.distinct(Plate.country_code)),
            )
            .join(Plate, Plate.id == UserPlate.plate_id)
            .where(UserPlate.user_id == user.id)
        ).one()
        return {
            "plates": int(rows[0] or 0),
            "value": int(rows[1] or 0),
            "countries": int(rows[2] or 0),
        }


__all__ = ["DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "WorldService"]
