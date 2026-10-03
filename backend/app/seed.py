"""Database seeding.

Loaded once on startup (or via ``python -m app.seed``). All seed data is
idempotent: existing rows are updated, never duplicated.
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
from app.game.products import PRODUCT_DEFINITIONS
from app.game.rarity import LEGENDARY_NUMBERS, MYTHIC_NUMBERS, SECRET_NUMBERS, SPECIAL_NUMBER_RARITY
from app.game.seasons import SEASON_DEFINITIONS
from app.game.story import build_story
from app.game.valuation import compute_value
from app.models.container import Container
from app.models.number import Number
from app.models.payment import Product
from app.models.progression import Achievement, Season

logger = get_logger("app.seed")

SEEDED_NUMBERS = set(SECRET_NUMBERS) | set(MYTHIC_NUMBERS) | set(LEGENDARY_NUMBERS)


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


def seed_products(db: Session) -> int:
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
        row.sort_order = definition.sort_order
        row.is_active = True
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


def seed_all(db: Session) -> dict[str, int]:
    """Seed every catalogue table and return the number of new rows per table."""
    result = {
        "containers": seed_containers(db),
        "achievements": seed_achievements(db),
        "seasons": seed_seasons(db),
        "products": seed_products(db),
        "numbers": seed_special_numbers(db),
    }
    db.commit()
    return result


def main() -> None:
    """CLI entry point: ``python -m app.seed``."""
    configure_logging(settings.log_level)
    with session_scope() as db:
        counts = seed_all(db)
    logger.info("Seeding complete: %s", counts)


if __name__ == "__main__":  # pragma: no cover - CLI
    main()

