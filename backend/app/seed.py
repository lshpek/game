"""NUMORA seed catalogue.

Idempotent by construction: every table is looked up by its stable code and then
*updated* in place, so restarting the app never duplicates a row. Run it with
``python -m app.seed`` or let the startup bootstrap do it.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.timeutils import utcnow
from app.db.session import session_scope
from app.game.achievements import ACHIEVEMENT_DEFINITIONS
from app.game.analyzer import analyze
from app.game.containers import CONTAINER_DEFINITIONS
from app.game.countries import ALL_ALBUMS, COUNTRIES, EVENTS
from app.game.products import PRODUCT_DEFINITIONS
from app.game.rarity import LEGENDARY_NUMBERS, MYTHIC_NUMBERS, SECRET_NUMBERS, SPECIAL_NUMBER_RARITY
from app.game.seasons import SEASON_DEFINITIONS
from app.game.story import build_story
from app.game.valuation import compute_value
from app.models.container import Container
from app.models.number import Number
from app.models.numora import Cosmetic, GameEvent, Mission
from app.models.payment import Product
from app.models.plates import Album, Country, PlateTemplate, Region
from app.models.progression import Achievement, Season
from app.services import catalog as catalog_service

logger = get_logger("app.seed")

SEEDED_NUMBERS = set(SECRET_NUMBERS) | set(MYTHIC_NUMBERS) | set(LEGENDARY_NUMBERS)


def seed_countries(db: Session) -> int:
    """Countries, regions and templates from the declarative catalogue."""
    created = 0
    for definition in COUNTRIES:
        country = db.execute(
            select(Country).where(Country.code == definition.code)
        ).scalar_one_or_none()
        if country is None:
            country = Country(code=definition.code)
            db.add(country)
            created += 1

        country.name_en = definition.name_en
        country.name_ru = definition.name_ru
        country.flag = definition.flag
        country.region_group = definition.region_group
        country.sort_order = definition.sort_order
        country.is_active = True
        country.config = {
            "currency_code": definition.currency_code,
            "currency_symbol": definition.currency_symbol,
            "weight": definition.weight,
            "alphabet": definition.alphabet,
            "letter_style": definition.letter_style,
            "value_scale": definition.value_scale,
            "rarity_modifier": definition.rarity_modifier,
            "visual": definition.visual,
            "tag": definition.tag,
        }
        db.flush()

        for index, region_def in enumerate(definition.regions):
            region = db.execute(
                select(Region).where(
                    Region.country_id == country.id, Region.code == region_def.code
                )
            ).scalar_one_or_none()
            if region is None:
                region = Region(country_id=country.id, code=region_def.code)
                db.add(region)
                created += 1
            region.name_en = region_def.name_en
            region.name_ru = region_def.name_ru
            region.config = {"weight": region_def.weight, **region_def.config}
            region.sort_order = index
            region.is_active = True

        db.flush()

        for index, template_def in enumerate(definition.templates):
            template = db.execute(
                select(PlateTemplate).where(PlateTemplate.code == template_def.code)
            ).scalar_one_or_none()
            if template is None:
                template = PlateTemplate(code=template_def.code)
                db.add(template)
                created += 1
            template.country_id = country.id
            template.region_id = None
            template.pattern = template_def.pattern
            template.plate_type = template_def.plate_type
            template.rarity_floor = template_def.rarity_floor
            template.weight = template_def.weight
            template.config = dict(template_def.config)
            template.sort_order = index
            template.is_active = True

    db.flush()
    catalog_service.invalidate()
    return created


def seed_albums(db: Session) -> int:
    """Theme albums plus one country-completion album per launch country."""
    created = 0
    countries = {row.code: row for row in db.execute(select(Country)).scalars().all()}

    for definition in ALL_ALBUMS:
        album = db.execute(
            select(Album).where(Album.code == definition.code)
        ).scalar_one_or_none()
        if album is None:
            album = Album(code=definition.code)
            db.add(album)
            created += 1
        country = countries.get(definition.country_code or "")
        album.name_en = definition.name_en
        album.name_ru = definition.name_ru
        album.description_en = definition.description_en
        album.description_ru = definition.description_ru
        album.icon = definition.icon
        album.kind = definition.kind
        album.country_id = country.id if country else None
        album.sort_order = definition.sort_order
        album.is_active = True
        album.config = {
            "reward_coins": definition.reward_coins,
            "reward_title": definition.reward_title,
            "tags": list(definition.code.replace("album_", "").split("_")),
        }

    db.flush()
    return created


def seed_events(db: Session) -> int:
    """Rotating global events. The rotation itself is computed at read time."""
    created = 0
    now = utcnow()
    for index, definition in enumerate(EVENTS):
        event = db.execute(
            select(GameEvent).where(GameEvent.code == definition.code)
        ).scalar_one_or_none()
        if event is None:
            event = GameEvent(code=definition.code)
            db.add(event)
            created += 1
        event.name_en = definition.name_en
        event.name_ru = definition.name_ru
        event.flag = definition.flag
        event.country_multipliers = dict(definition.country_multipliers)
        event.reward_coins = definition.reward_coins
        event.reward_title = definition.reward_title
        event.starts_at = now
        event.ends_at = now + timedelta(days=definition.duration_days)
        event.sort_order = definition.sort_order
        # Left inactive so the deterministic rotation drives the game; an admin
        # can pin one explicitly.
        event.is_active = False
        index = index  # keep the loop variable meaningful for linters
    db.flush()
    return created


# @@NEXT@@


def seed_containers(db: Session) -> int:
    created = 0
    for definition in CONTAINER_DEFINITIONS:
        row = db.execute(select(Container).where(Container.code == definition.code)).scalar_one_or_none()
        if row is None:
            row = Container(code=definition.code)
            db.add(row)
            created += 1
        row.name = definition.name
        row.description = definition.description
        row.price = definition.price
        row.rarity_weights = dict(definition.rarity_weights)
        row.minimum_rarity = definition.minimum_rarity
        row.accent = definition.accent
        row.animation = definition.animation
        row.premium_only = definition.premium_only
        row.sort_order = definition.sort_order
        row.is_active = True
    db.flush()
    return created


def seed_achievements(db: Session) -> int:
    created = 0
    for definition in ACHIEVEMENT_DEFINITIONS:
        row = db.execute(select(Achievement).where(Achievement.code == definition.code)).scalar_one_or_none()
        if row is None:
            row = Achievement(code=definition.code)
            db.add(row)
            created += 1
        row.name = definition.name
        row.description = definition.description
        row.metric = definition.metric
        row.threshold = definition.threshold
        row.reward_coins = definition.reward_coins
        row.icon = definition.icon
        row.sort_order = definition.sort_order
        row.is_active = True
    db.flush()
    return created


def seed_seasons(db: Session) -> int:
    created = 0
    now = utcnow()
    for index, definition in enumerate(SEASON_DEFINITIONS):
        row = db.execute(select(Season).where(Season.code == definition.code)).scalar_one_or_none()
        if row is None:
            row = Season(
                code=definition.code,
                start_date=now,
                end_date=now + timedelta(days=definition.duration_days),
            )
            db.add(row)
            created += 1
        row.name = definition.name
        row.description = definition.description
        row.special_numbers = list(definition.special_numbers)
        row.rewards = dict(definition.rewards)
        row.sort_order = definition.sort_order
        row.is_active = index == 0  # exactly one active season
    db.flush()
    return created


def seed_special_numbers(db: Session) -> int:
    """Pre-register notable numbers so their rarity and story exist from day 1."""
    created = 0
    for value in sorted(SEEDED_NUMBERS):
        if db.execute(select(Number.id).where(Number.value_str == value)).scalar_one_or_none() is not None:
            continue
        analysis = analyze(value)
        db.add(
            Number(
                value_str=value,
                value_int=analysis.value,
                rarity=SPECIAL_NUMBER_RARITY.get(value, analysis.rarity).value,
                base_value=compute_value(analysis.rarity, analysis.traits, value, discovery_count=0),
                traits=list(analysis.traits),
                tags=list(analysis.tags),
                story=build_story(analysis),
                is_special=True,
                discovery_count=0,
            )
        )
        created += 1
    db.flush()
    return created


def seed_missions(db: Session) -> int:
    """Daily mission definitions."""
    from app.game.content import MISSION_DEFINITIONS

    created = 0
    for definition in MISSION_DEFINITIONS:
        row = db.execute(
            select(Mission).where(Mission.code == definition.code)
        ).scalar_one_or_none()
        if row is None:
            row = Mission(code=definition.code)
            db.add(row)
            created += 1
        row.name_en = definition.name_en
        row.name_ru = definition.name_ru
        row.description_en = definition.description_en
        row.description_ru = definition.description_ru
        row.metric = definition.metric
        row.target = definition.target
        row.reward_coins = definition.reward_coins
        row.reward_rolls = definition.reward_rolls
        row.reward_xp = definition.reward_xp
        row.icon = definition.icon
        row.sort_order = definition.sort_order
        row.is_active = True
    db.flush()
    return created


def seed_cosmetics(db: Session) -> int:
    """Cosmetic catalogue (presentation only)."""
    from app.game.content import COSMETIC_DEFINITIONS

    created = 0
    for definition in COSMETIC_DEFINITIONS:
        row = db.execute(
            select(Cosmetic).where(Cosmetic.code == definition.code)
        ).scalar_one_or_none()
        if row is None:
            row = Cosmetic(code=definition.code)
            db.add(row)
            created += 1
        row.kind = definition.kind
        row.name_en = definition.name_en
        row.name_ru = definition.name_ru
        row.description_en = definition.description_en
        row.description_ru = definition.description_ru
        row.config = dict(definition.config)
        row.price_stars = definition.price_stars
        row.price_numora = definition.price_numora
        row.rarity_code = definition.rarity_code
        row.sort_order = definition.sort_order
        row.is_active = True
    db.flush()
    return created


def seed_products(db: Session) -> int:
    """Store catalogue: NUMORA, PRO, supporter tiers and fixed bundles.

    Defined once, after the other catalogue seeders, so there is a single place that
    knows how a product row is written. The previous copy here never set
    ``category``, so every seeded product landed in the default bucket.
    """
    created = 0
    for definition in PRODUCT_DEFINITIONS:
        row = db.execute(select(Product).where(Product.code == definition.code)).scalar_one_or_none()
        if row is None:
            row = Product(code=definition.code)
            db.add(row)
            created += 1
        row.name = definition.name
        row.description = definition.description
        row.stars_price = definition.stars_price
        row.grant_type = definition.grant_type.upper()
        row.grant_payload = dict(definition.grant_payload)
        row.category = definition.category
        row.sort_order = definition.sort_order
        row.is_active = True
    db.flush()
    return created


def seed_all(db: Session) -> dict[str, int]:
    """Seed every catalogue table and return the number of new rows per table."""
    result = {
        "countries": seed_countries(db),
        "albums": seed_albums(db),
        "events": seed_events(db),
        "containers": seed_containers(db),
        "achievements": seed_achievements(db),
        "seasons": seed_seasons(db),
        "missions": seed_missions(db),
        "cosmetics": seed_cosmetics(db),
        "products": seed_products(db),
        "numbers": seed_special_numbers(db),
    }
    db.commit()
    catalog_service.invalidate()
    return result


def main() -> None:
    """CLI entry point: ``python -m app.seed``."""
    configure_logging(settings.log_level)
    with session_scope() as db:
        counts = seed_all(db)
    logger.info("Seeding complete: %s", counts)


if __name__ == "__main__":  # pragma: no cover - CLI
    main()

