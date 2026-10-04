"""Startup bootstrap: run migrations and seed the catalogue if needed.

Keeps ``uvicorn app.main:app --reload`` a one-command experience while still
using Alembic as the single source of schema truth.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import BACKEND_DIR, settings
from app.core.logging import get_logger
from app.db.session import SessionLocal, engine
from app.models.container import Container

logger = get_logger(__name__)


def alembic_config() -> Config:
    config = Config(str(Path(BACKEND_DIR) / "alembic.ini"))
    config.set_main_option("script_location", str(Path(BACKEND_DIR) / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def run_migrations() -> None:
    """Upgrade the database to head."""
    command.upgrade(alembic_config(), "head")


def catalogue_is_empty(db: Session) -> bool:
    return db.execute(select(Container.id).limit(1)).scalar_one_or_none() is None


def tables_exist() -> bool:
    return bool(inspect(engine).get_table_names())


def bootstrap() -> None:
    """Idempotent startup routine."""
    if settings.auto_migrate:
        run_migrations()
    elif not tables_exist():
        logger.warning("Database has no tables and AUTO_MIGRATE is disabled.")
        return

    if not settings.auto_seed:
        return

    with SessionLocal() as db:
        first_boot = catalogue_is_empty(db)
        # The catalogue is *configuration* that ships with the code, so it is
        # reconciled on every boot: a release that adds countries, layouts or albums
        # must reach an existing database, and every seed is an idempotent upsert by
        # stable code. Nothing is ever deleted or reset.
        from app.seed import seed_all

        counts = seed_all(db)
        if first_boot:
            logger.info("Seed data created: %s", counts)
        else:
            logger.info("Catalogue reconciled: %s", counts)
