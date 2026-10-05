"""Catalogue access: the bridge between the database and the game engine.

Lives between SQLAlchemy and :mod:`app.game.plate_generator` so the engine never
touches the ORM and the services never re-implement generation logic.

Caching is process-local and short-lived: the catalogue only changes on deploy or
via admin, so a cached snapshot avoids a per-roll join storm without adding a
distributed cache dependency.
"""

from __future__ import annotations

import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.game.countries import COUNTRIES as CATALOG_COUNTRIES
from app.game.plate_generator import GenerationContext, RegionOption, TemplateOption
from app.game.plate_visuals import serialize_visual
from app.models.plates import Country, PlateTemplate, Region

CACHE_TTL_SECONDS = 60.0
_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


class CatalogSnapshot:
    """Immutable view of the country/region/template catalogue."""

    __slots__ = ("context", "countries", "regions", "templates")

    def __init__(
        self,
        context: GenerationContext,
        countries: list[Country],
        regions: list[Region],
        templates: list[PlateTemplate],
    ) -> None:
        self.context = context
        self.countries = countries
        self.regions = regions
        self.templates = templates


def _requires_region(template: PlateTemplate) -> bool:
    return "R" in (template.pattern or "")


def build_snapshot(db: Session, rarity_weights: dict[str, float]) -> CatalogSnapshot:
    """Read the whole catalogue in three queries and map it for the engine.

    Only *playable* countries enter the generation context: locked countries are
    listed by the atlas but can never be produced by a roll, which is what makes
    "coming soon" honest instead of a silent surprise.
    """
    countries = list(
        db.execute(
            select(Country)
            .where(Country.is_active.is_(True), Country.is_playable.is_(True))
            .options(selectinload(Country.regions), selectinload(Country.templates))
            .order_by(Country.sort_order, Country.id)
        )
        .scalars()
        .unique()
        .all()
    )
    regions = list(db.execute(select(Region).order_by(Region.id)).scalars().all())
    templates = list(
        db.execute(
            select(PlateTemplate)
            .where(PlateTemplate.is_active.is_(True))
            .order_by(PlateTemplate.sort_order, PlateTemplate.id)
        )
        .scalars()
        .all()
    )

    regions_by_country: dict[str, tuple[RegionOption, ...]] = {}
    templates_by_country: dict[str, tuple[TemplateOption, ...]] = {}

    # The engine selects countries by their stable *code*, so the catalogue is
    # keyed by code too - never by the database surrogate id.
    code_by_id = {country.id: country.code for country in countries}

    for region in regions:
        code = code_by_id.get(region.country_id)
        if code is None:
            continue
        weight = float((region.config or {}).get("weight", 1.0))
        regions_by_country[code] = (
            *regions_by_country.get(code, ()),
            RegionOption(
                code=region.code,
                name_en=region.name_en,
                name_ru=region.name_ru,
                weight=weight,
            ),
        )

    for template in templates:
        code = code_by_id.get(template.country_id)
        if code is None:
            continue
        config = template.config or {}
        templates_by_country[code] = (
            *templates_by_country.get(code, ()),
            TemplateOption(
                code=template.code,
                pattern=template.pattern,
                weight=float(template.weight or 1.0),
                plate_type=template.plate_type,
                rarity_floor=template.rarity_floor,
                requires_region=_requires_region(template),
                multiplier=float(config.get("multiplier", 1.0)),
                config=dict(config),
            ),
        )

    active_codes = {c.code for c in countries}
    engine_countries = tuple(c for c in CATALOG_COUNTRIES if c.code in active_codes)

    # SIM card layouts are seeded alongside the vehicle layouts by the same
    # reconciliation pass, so the database is the single source of truth for the
    # generation pool. Adding them here as well would double their weight.
    context = GenerationContext(
        countries=engine_countries,
        regions_by_country=regions_by_country,
        templates_by_country=templates_by_country,
        rarity_weights=dict(rarity_weights),
    )
    return CatalogSnapshot(context, countries, regions, templates)


def snapshot(db: Session, rarity_weights: dict[str, float]) -> CatalogSnapshot:
    """Cached :func:`build_snapshot`."""
    now = time.monotonic()
    with _lock:
        cached = _cache.get("snapshot")
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]  # type: ignore[return-value]

    built = build_snapshot(db, rarity_weights)

    with _lock:
        _cache["snapshot"] = (time.monotonic(), built)
    return built


def invalidate() -> None:
    """Drop the cache (called by the seed and by admin tooling)."""
    with _lock:
        _cache.clear()


def country_card(country: Country) -> dict[str, object]:
    """Serialisable country payload used by the WORLD screen and the selector."""
    config = country.config or {}
    return {
        "id": country.id,
        "code": country.code,
        "iso_alpha2": country.iso_alpha2 or "",
        "name_en": country.name_en,
        "name_ru": country.name_ru,
        "flag": country.flag,
        "region_group": country.region_group,
        "currency_code": config.get("currency_code", "USD"),
        "currency_symbol": config.get("currency_symbol", "$"),
        "calling_code": country.calling_code,
        "weight": config.get("weight", 1.0),
        "visual": serialize_visual(config.get("visual", "european")),
        "sort_order": country.sort_order,
        "is_active": bool(country.is_active),
        "is_playable": bool(country.is_playable),
    }


def region_card(region: Region) -> dict[str, object]:
    return {
        "code": region.code,
        "name_en": region.name_en,
        "name_ru": region.name_ru,
        "is_active": bool(region.is_active),
    }


def template_card(template: PlateTemplate) -> dict[str, object]:
    return {
        "code": template.code,
        "pattern": template.pattern,
        "plate_type": template.plate_type,
        "rarity_floor": template.rarity_floor,
        "weight": float(template.weight),
        "is_active": bool(template.is_active),
    }


def country_by_code(db: Session, code: str) -> Country | None:
    """Resolve an ISO 3166-1 alpha-3 *or* alpha-2 code to a country row.

    Deep links and share payloads carry the two-letter form, the engine and the
    catalogue use the three-letter form; both must land on the same row.
    """
    if not code:
        return None
    text = str(code).strip().upper()
    row = db.execute(select(Country).where(Country.code == text)).scalar_one_or_none()
    if row is not None:
        return row
    return db.execute(select(Country).where(Country.iso_alpha2 == text)).scalar_one_or_none()


def playable_countries(db: Session) -> list[Country]:
    """Every country a roll may produce, in atlas order."""
    return list(
        db.execute(
            select(Country)
            .where(Country.is_active.is_(True), Country.is_playable.is_(True))
            .order_by(Country.sort_order, Country.id)
        )
        .scalars()
        .all()
    )


__all__ = [
    "CatalogSnapshot",
    "build_snapshot",
    "country_by_code",
    "country_card",
    "invalidate",
    "playable_countries",
    "region_card",
    "snapshot",
    "template_card",
]
