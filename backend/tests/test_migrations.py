"""Migration safety.

The acceptance bar for a schema change is not "it runs" but "running it against a
populated database loses nothing". These tests exercise migration 0005's data fix
directly against the live test database, because the one thing a from-scratch upgrade
cannot prove is that an *existing* player's rows survive it.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import select

from app.core.config import BACKEND_DIR
from app.models.plates import Country, Plate, PlateTemplate, UserPlate
from app.models.user import User

MIGRATIONS = Path(BACKEND_DIR) / "alembic" / "versions"
HEAD_REVISION = "0005_global_world"


def load_revision(name: str):
    """Import a revision module by file name, the way Alembic does."""
    path = MIGRATIONS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRevisionGraph:
    @pytest.fixture
    def _script(self) -> ScriptDirectory:
        return ScriptDirectory(str(Path(BACKEND_DIR) / "alembic"))

    def test_0005_is_the_single_head(self, _script):
        assert _script.get_heads() == [HEAD_REVISION]

    def test_the_chain_is_linear(self, _script):
        revisions = {rev.revision for rev in _script.walk_revisions()}
        assert HEAD_REVISION in revisions
        for revision in _script.walk_revisions():
            down = revision.down_revision
            # Alembic stores a single parent as a bare string, a branch as a tuple.
            parents = () if down is None else (down if isinstance(down, tuple) else (down,))
            for parent in parents:
                assert parent in revisions, (revision.revision, parent)


class TestPhoneFoldIntoSim:
    """``PHONE`` rows are re-labelled as SIM cards, keeping every id."""

    @pytest.fixture
    def fold(self, db, monkeypatch):
        """Run the migration's data fix against the test database."""
        module = load_revision(HEAD_REVISION)
        context = MigrationContext.configure(db.connection())
        monkeypatch.setattr(module, "op", Operations(context))

        def _run() -> None:
            module._fold_phone_into_sim()
            # The migration writes through its own connection, so the identity map
            # still holds the pre-migration objects.
            db.expire_all()

        return _run

    def _legacy_phone(self, db) -> tuple[int, int]:
        country = db.execute(select(Country).where(Country.code == "RUS")).scalar_one()
        template = db.execute(
            select(PlateTemplate).where(
                PlateTemplate.plate_type == "SIM", PlateTemplate.country_id == country.id
            ).limit(1)
        ).scalars().first()
        assert template is not None
        # The fixture database has no players yet; this test is about rows, not users.
        user = User(telegram_id=999_555_001, first_name="Legacy")
        db.add(user)
        db.flush()
        plate = Plate(
            country_id=country.id,
            template_id=template.id,
            plate_text="+7 900 000 00 01",
            normalized_text="79000000001",
            display_segments=["+7", "900", "000", "00", "01"],
            letter_parts=[],
            numeric_parts=["7", "900", "000", "00", "01"],
            plate_type="PHONE",
            details={},
            rarity="COMMON",
            rarity_score=10,
            traits=["phone_digits"],
            tags=["phone"],
            story="",
            collector_value=100,
            dealer_value=10,
            currency_code="RUB",
            currency_symbol="₽",
            region_code=None,
            season_code=None,
            is_secret=False,
            discovery_count=1,
        )
        db.add(plate)
        db.flush()
        db.add(
            UserPlate(
                user_id=user.id,
                plate_id=plate.id,
                duplicate_count=0,
                first_acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
                last_acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        db.flush()
        return plate.id, user.id

    def test_a_phone_row_becomes_a_sim_card_without_losing_its_id(self, db, fold):
        plate_id, user_id = self._legacy_phone(db)

        fold()

        plate = db.execute(select(Plate).where(Plate.id == plate_id)).scalar_one()
        assert plate.plate_type == "SIM"
        # Identity, ownership and discovery survive: nothing was deleted or recreated.
        assert plate.normalized_text == "79000000001"
        owned = db.execute(
            select(UserPlate).where(UserPlate.plate_id == plate_id)
        ).scalar_one()
        assert owned.user_id == user_id
        assert plate.discovery_count == 1

    def test_phone_templates_become_sim_templates(self, db, fold):
        country = db.execute(select(Country).where(Country.code == "USA")).scalar_one()
        template = db.execute(
            select(PlateTemplate).where(PlateTemplate.country_id == country.id).limit(1)
        ).scalars().first()
        assert template is not None
        template.plate_type = "PHONE"
        db.flush()
        template_id = template.id

        fold()

        assert db.execute(select(PlateTemplate).where(PlateTemplate.id == template_id)).scalar_one().plate_type == "SIM"

    def test_the_fold_is_idempotent(self, db, fold):
        plate_id, _user_id = self._legacy_phone(db)

        fold()
        first = db.execute(select(Plate).where(Plate.id == plate_id)).scalar_one()
        fold()
        second = db.execute(select(Plate).where(Plate.id == plate_id)).scalar_one()

        assert first.plate_type == second.plate_type == "SIM"
        assert "sim" in second.tags
        assert "synthetic" in second.tags

    def test_nothing_is_deleted(self, db, fold):
        before_plates = db.query(Plate).count()
        before_templates = db.query(PlateTemplate).count()
        plate_id, _user_id = self._legacy_phone(db)

        fold()

        assert db.query(Plate).count() == before_plates + 1
        assert db.query(PlateTemplate).count() == before_templates

    def test_the_tag_rewrite_is_dialect_aware(self, db):
        """``tags`` is a JSON column and the two databases disagree about SQL.

        PostgreSQL has no ``LIKE`` for ``json`` and needs an explicit cast in both
        directions; getting this wrong is a statement that passes on SQLite and
        crash-loops the production backend on every restart.
        """
        module = load_revision(HEAD_REVISION)
        postgres = [
            statement
            for name in dir(module)
            if name.startswith("_retag")
            for statement in str(getattr(module, name)).split('"')
        ]
        assert postgres, "the migration no longer has a dialect-specific tag rewrite"

        source = Path(MIGRATIONS / f"{HEAD_REVISION}.py").read_text(encoding="utf-8")
        postgres_branch = source.split('if dialect == "postgresql":')[1]
        assert "::text" in postgres_branch
        assert "::json" in postgres_branch
        # The other branch must not use Postgres-only syntax.
        other = source.split('return\n', 1)[1]
        assert "::" not in other