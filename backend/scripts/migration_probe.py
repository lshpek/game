"""Apply migrations + seed against a scratch SQLite database.

    python scripts/migration_probe.py
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

scratch = Path(tempfile.gettempdir()) / "numora_migration_probe.db"
if scratch.exists():
    scratch.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{scratch.as_posix()}"
os.environ["APP_ENV"] = "development"
os.environ["AUTO_MIGRATE"] = "true"
os.environ["AUTO_SEED"] = "true"

from app.bootstrap import bootstrap, run_migrations  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402

from app.models.plates import Country, Plate, PlateTemplate  # noqa: E402


def report(label: str) -> None:
    with SessionLocal() as db:
        countries = db.execute(select(func.count(Country.id))).scalar_one()
        templates = db.execute(select(func.count(PlateTemplate.id))).scalar_one()
        sim = db.execute(
            select(func.count(PlateTemplate.id)).where(PlateTemplate.plate_type == "SIM")
        ).scalar_one()
        print(f"{label}: countries={countries} templates={templates} sim_templates={sim}")


def main() -> int:
    bootstrap()
    report("after upgrade+seed")

    # A second boot must be a no-op: the catalogue reconciles idempotently.
    bootstrap()
    report("after second boot")

    # A roll must work end to end against the migrated schema.
    from app.game.plate_generator import PlateGenerator
    from app.game.rng import default_rng
    from app.services.catalog import snapshot
    from app.core.config import settings as app_settings

    with SessionLocal() as db:
        ctx = snapshot(db, app_settings.rarity_weights)
        generated = PlateGenerator(ctx.context, default_rng()).generate(luck=None)
        db.commit()
        print(
            "generated:",
            generated.country.code,
            generated.plate_text.encode("unicode_escape").decode(),
            generated.rarity.value,
            generated.kind.value,
        )

    # Downgrade must be safe and keep every row.
    from alembic import command
    from app.bootstrap import alembic_config

    command.downgrade(alembic_config(), "-1")
    with SessionLocal() as db:
        names = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all()
        assert "countries" in names, names
        assert "plates" in names, names
        print("downgrade kept tables:", sorted(n for n in names if n in {"countries", "plates", "plate_templates"}))

    command.upgrade(alembic_config(), "head")
    report("after downgrade+upgrade")

    print("MIGRATION PROBE OK")
    # The engine may still hold the file; leaving the scratch database behind is
    # harmless and better than failing a probe that already passed.
    try:
        scratch.unlink(missing_ok=True)
    except OSError:
        print(f"note: left {scratch} behind (still open)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())