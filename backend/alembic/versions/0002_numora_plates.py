"""numora plate engine: countries, plates, cosmetics, missions, events

Creates the whole plate domain (it has never been migrated - the models existed
without a revision), fixes the incorrect global uniqueness on
``plates.normalized_text`` by scoping it to ``(country_id, normalized_text)``,
and adds the collector progression / pity columns.

No existing table is dropped and no legacy row is deleted: the 4-digit ``numbers``
tables are untouched so existing players keep their collection.

Revision ID: 0002_numora_plates
Revises: b830b9d498eb
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_numora_plates"
down_revision: Union[str, None] = "b830b9d498eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TS = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    # --- countries ---------------------------------------------------------
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name_en", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=64), nullable=False),
        sa.Column("flag", sa.String(length=8), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("region_group", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_countries")),
    )
    with op.batch_alter_table("countries") as batch:
        batch.create_index(batch.f("ix_countries_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_countries_region_group"), ["region_group"], unique=False)
        batch.create_index(batch.f("ix_countries_is_active"), ["is_active"], unique=False)

    # --- regions -----------------------------------------------------------
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name_en", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regions")),
        sa.UniqueConstraint("country_id", "code", name="uq_regions_country_code"),
    )
    with op.batch_alter_table("regions") as batch:
        batch.create_index(batch.f("ix_regions_country_id"), ["country_id"], unique=False)

    # --- plate templates ---------------------------------------------------
    op.create_table(
        "plate_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("pattern", sa.String(length=96), nullable=False),
        sa.Column("plate_type", sa.String(length=24), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("rarity_floor", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plate_templates")),
    )
    with op.batch_alter_table("plate_templates") as batch:
        batch.create_index(batch.f("ix_plate_templates_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_plate_templates_country_id"), ["country_id"], unique=False)
        batch.create_index(batch.f("ix_plate_templates_region_id"), ["region_id"], unique=False)
        batch.create_index(batch.f("ix_plate_templates_plate_type"), ["plate_type"], unique=False)
        batch.create_index(batch.f("ix_plate_templates_is_active"), ["is_active"], unique=False)

    # --- plates -----------------------------------------------------------
    # Uniqueness is (country_id, normalized_text): the same textual plate may
    # legitimately exist in different countries.
    op.create_table(
        "plates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("plate_text", sa.String(length=32), nullable=False),
        sa.Column("normalized_text", sa.String(length=48), nullable=False),
        sa.Column("display_segments", sa.JSON(), nullable=False),
        sa.Column("numeric_parts", sa.JSON(), nullable=False),
        sa.Column("letter_parts", sa.JSON(), nullable=False),
        sa.Column("plate_type", sa.String(length=24), nullable=False),
        sa.Column("rarity", sa.String(length=16), nullable=False),
        sa.Column("rarity_score", sa.Integer(), nullable=False),
        sa.Column("collector_value", sa.BigInteger(), nullable=False),
        sa.Column("dealer_value", sa.BigInteger(), nullable=False),
        sa.Column("coin_value", sa.BigInteger(), nullable=False),
        sa.Column("story", sa.Text(), nullable=False),
        sa.Column("story_ru", sa.Text(), nullable=False),
        sa.Column("traits", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("visual_style", sa.String(length=32), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("region_code", sa.String(length=16), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("currency_symbol", sa.String(length=8), nullable=False),
        sa.Column("season_code", sa.String(length=32), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False),
        sa.Column("discovery_count", sa.Integer(), nullable=False),
        sa.Column("first_discovered_by_id", sa.Integer(), nullable=True),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["plate_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["first_discovered_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plates")),
        sa.UniqueConstraint("country_id", "normalized_text", name="uq_plates_country_normalized"),
    )
    with op.batch_alter_table("plates") as batch:
        for name, cols in (
            ("ix_plates_plate_text", ["plate_text"]),
            ("ix_plates_normalized_text", ["normalized_text"]),
            ("ix_plates_plate_type", ["plate_type"]),
            ("ix_plates_rarity", ["rarity"]),
            ("ix_plates_rarity_score", ["rarity_score"]),
            ("ix_plates_dealer_value", ["dealer_value"]),
            ("ix_plates_season_code", ["season_code"]),
            ("ix_plates_is_secret", ["is_secret"]),
            ("ix_plates_country_id", ["country_id"]),
            ("ix_plates_region_id", ["region_id"]),
            ("ix_plates_country_rarity", ["country_id", "rarity"]),
            ("ix_plates_country_region", ["country_id", "region_id"]),
            ("ix_plates_rarity_value", ["rarity", "collector_value"]),
            ("ix_plates_discovery_count", ["discovery_count"]),
        ):
            batch.create_index(name, cols, unique=False)

    # --- user plates ------------------------------------------------------
    op.create_table(
        "user_plates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plate_id", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("coins_earned", sa.BigInteger(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.Column("copies_sold", sa.Integer(), nullable=False),
        sa.Column("first_acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plate_id"], ["plates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_plates")),
        sa.UniqueConstraint("user_id", "plate_id", name="uq_user_plates_user_plate"),
    )
    with op.batch_alter_table("user_plates") as batch:
        batch.create_index(batch.f("ix_user_plates_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_user_plates_plate_id"), ["plate_id"], unique=False)
        batch.create_index(batch.f("ix_user_plates_is_favorite"), ["is_favorite"], unique=False)
        batch.create_index(batch.f("ix_user_plates_user_acquired"), ["user_id", "first_acquired_at"])

    # --- discoveries, albums, plate challenges --------------------------
    op.create_table(
        "plate_discoveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plate_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_first_discovery", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plate_id"], ["plates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plate_discoveries")),
    )
    with op.batch_alter_table("plate_discoveries") as batch:
        batch.create_index(batch.f("ix_plate_discoveries_plate_id"), ["plate_id"], unique=False)
        batch.create_index(batch.f("ix_plate_discoveries_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_plate_discoveries_plate_created"), ["plate_id", "created_at"])

    op.create_table(
        "albums",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("name_en", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=64), nullable=False),
        sa.Column("description_en", sa.String(length=256), nullable=False),
        sa.Column("description_ru", sa.String(length=256), nullable=False),
        sa.Column("icon", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_albums")),
    )
    with op.batch_alter_table("albums") as batch:
        batch.create_index(batch.f("ix_albums_code"), ["code"], unique=True)

    op.create_table(
        "plate_albums",
        sa.Column("plate_id", sa.Integer(), nullable=False),
        sa.Column("album_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["album_id"], ["albums.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plate_id"], ["plates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plate_id", "album_id"),
    )
    with op.batch_alter_table("plate_albums") as batch:
        batch.create_index(batch.f("ix_plate_albums_album_id"), ["album_id"], unique=False)

    op.create_table(
        "plate_challenges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("challenger_id", sa.Integer(), nullable=False),
        sa.Column("opponent_id", sa.Integer(), nullable=True),
        sa.Column("challenger_plate_id", sa.Integer(), nullable=False),
        sa.Column("opponent_plate_id", sa.Integer(), nullable=True),
        sa.Column("challenger_score", sa.Integer(), nullable=False),
        sa.Column("opponent_score", sa.Integer(), nullable=True),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reward_coins", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["challenger_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opponent_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["challenger_plate_id"], ["plates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opponent_plate_id"], ["plates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plate_challenges")),
    )
    with op.batch_alter_table("plate_challenges") as batch:
        batch.create_index(batch.f("ix_plate_challenges_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_plate_challenges_challenger_id"), ["challenger_id"], unique=False)
        batch.create_index(batch.f("ix_plate_challenges_opponent_id"), ["opponent_id"], unique=False)
        batch.create_index(batch.f("ix_plate_challenges_status"), ["status"], unique=False)

    op.create_table(
        "plate_rolls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plate_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("rarity", sa.String(length=16), nullable=False),
        sa.Column("natural_rarity", sa.String(length=16), nullable=False),
        sa.Column("luck_rarity", sa.String(length=16), nullable=False),
        sa.Column("rarity_score", sa.Integer(), nullable=False),
        sa.Column("dealer_value", sa.BigInteger(), nullable=False),
        sa.Column("collector_value", sa.BigInteger(), nullable=False),
        sa.Column("numora_awarded", sa.BigInteger(), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("is_first_discovery", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plate_id"], ["plates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plate_rolls")),
        sa.UniqueConstraint("idempotency_key", name="uq_plate_rolls_idempotency_key"),
    )
    with op.batch_alter_table("plate_rolls") as batch:
        batch.create_index(batch.f("ix_plate_rolls_user_created"), ["user_id", "created_at"])
        batch.create_index(batch.f("ix_plate_rolls_rarity_created"), ["rarity", "created_at"])

    # --- cosmetics, events, missions, progress --------------------------
    op.create_table(
        "cosmetics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name_en", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=64), nullable=False),
        sa.Column("description_en", sa.String(length=256), nullable=False),
        sa.Column("description_ru", sa.String(length=256), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("price_stars", sa.Integer(), nullable=False),
        sa.Column("price_numora", sa.BigInteger(), nullable=False),
        sa.Column("rarity_code", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cosmetics")),
    )
    with op.batch_alter_table("cosmetics") as batch:
        batch.create_index(batch.f("ix_cosmetics_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_cosmetics_kind"), ["kind"], unique=False)
        batch.create_index(batch.f("ix_cosmetics_is_active"), ["is_active"], unique=False)

    op.create_table(
        "user_cosmetics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cosmetic_id", sa.Integer(), nullable=False),
        sa.Column("equipped", sa.Boolean(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cosmetic_id"], ["cosmetics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_cosmetics")),
        sa.UniqueConstraint("user_id", "cosmetic_id", name="uq_user_cosmetics_user_cosmetic"),
    )
    with op.batch_alter_table("user_cosmetics") as batch:
        batch.create_index(batch.f("ix_user_cosmetics_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_user_cosmetics_equipped"), ["equipped"], unique=False)
        batch.create_index(batch.f("ix_user_cosmetics_user_equipped"), ["user_id", "equipped"])

    op.create_table(
        "game_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_en", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=64), nullable=False),
        sa.Column("flag", sa.String(length=8), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country_multipliers", sa.JSON(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("reward_title", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_events")),
    )
    with op.batch_alter_table("game_events") as batch:
        batch.create_index(batch.f("ix_game_events_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_game_events_is_active"), ["is_active"], unique=False)

    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("name_en", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=64), nullable=False),
        sa.Column("description_en", sa.String(length=128), nullable=False),
        sa.Column("description_ru", sa.String(length=128), nullable=False),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("reward_rolls", sa.Integer(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_missions")),
    )
    with op.batch_alter_table("missions") as batch:
        batch.create_index(batch.f("ix_missions_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_missions_is_active"), ["is_active"], unique=False)

    op.create_table(
        "user_missions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("mission_date", sa.Date(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_paid", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_missions")),
        sa.UniqueConstraint("user_id", "mission_id", "mission_date", name="uq_user_missions_day"),
    )
    with op.batch_alter_table("user_missions") as batch:
        batch.create_index(batch.f("ix_user_missions_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_user_missions_user_date"), ["user_id", "mission_date"])

    op.create_table(
        "album_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("album_id", sa.Integer(), nullable=False),
        sa.Column("collected", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_paid", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["album_id"], ["albums.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_album_progress")),
        sa.UniqueConstraint("user_id", "album_id", name="uq_album_progress_user_album"),
    )
    with op.batch_alter_table("album_progress") as batch:
        batch.create_index(batch.f("ix_album_progress_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_album_progress_completed_at"), ["completed_at"], unique=False)

    op.create_table(
        "season_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("season_code", sa.String(length=48), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("claimed_tiers", sa.JSON(), nullable=False),
        sa.Column("has_pass", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_season_progress")),
        sa.UniqueConstraint("user_id", "season_code", name="uq_season_progress_user_season"),
    )
    with op.batch_alter_table("season_progress") as batch:
        batch.create_index(batch.f("ix_season_progress_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_season_progress_season_code"), ["season_code"], unique=False)

    op.create_table(
        "cosmetic_titles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("equipped", sa.Boolean(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cosmetic_titles")),
    )
    with op.batch_alter_table("cosmetic_titles") as batch:
        batch.create_index(batch.f("ix_cosmetic_titles_user_id"), ["user_id"], unique=False)
        batch.create_index(batch.f("ix_cosmetic_titles_equipped"), ["equipped"], unique=False)

    # --- users: collector progression, pity state, display ----------------
    with op.batch_alter_table("users") as batch:
        for col in (
            sa.Column("collection_xp", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("collector_level", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("plates_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("countries_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("regions_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("first_discoveries_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicates_sold_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("best_plate_id", sa.Integer(), nullable=True),
            sa.Column("best_collector_value", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("equipped_title", sa.String(length=64), nullable=True),
            sa.Column("equipped_cosmetic_code", sa.String(length=48), nullable=True),
            sa.Column("season_pass_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("pity_rare_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pity_epic_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pity_legendary_streak", sa.Integer(), nullable=False, server_default="0"),
        ):
            batch.add_column(col)
        batch.create_foreign_key(
            "fk_users_best_plate_id", "users", ["best_plate_id"], ["plates", "id"], ondelete="SET NULL"
        )
        batch.create_index("ix_users_collector_level", ["collector_level"])
        batch.create_index("ix_users_plates_count", ["plates_count"])
        batch.create_index("ix_users_first_discoveries_count", ["first_discoveries_count"])

    # --- store catalogue grouping ----------------------------------------
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column("category", sa.String(length=24), nullable=False, server_default="PRO")
        )
        batch.create_index("ix_products_category", ["category"], unique=False)

    # --- supporter entitlements ------------------------------------------
    op.create_table(
        "supporter_entitlements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supporter_entitlements")),
    )
    with op.batch_alter_table("supporter_entitlements") as batch:
        batch.create_index(batch.f("ix_supporter_entitlements_user_id"), ["user_id"], unique=False)
        batch.create_index("ix_supporter_entitlements_user_active", ["user_id", "is_active"])


def downgrade() -> None:
    # The legacy 4-digit number domain is deliberately preserved: this migration
    # only removes what it created.
    op.drop_table("supporter_entitlements")

    with op.batch_alter_table("products") as batch:
        batch.drop_index("ix_products_category")
        batch.drop_column("category")

    with op.batch_alter_table("users") as batch:
        for name in (
            "ix_users_first_discoveries_count",
            "ix_users_plates_count",
            "ix_users_collector_level",
        ):
            batch.drop_index(name)
        batch.drop_constraint("fk_users_best_plate_id", type_="foreignkey")
        for name in (
            "pity_legendary_streak",
            "pity_epic_streak",
            "pity_rare_streak",
            "season_pass_active",
            "equipped_cosmetic_code",
            "equipped_title",
            "best_collector_value",
            "best_plate_id",
            "duplicates_sold_count",
            "first_discoveries_count",
            "regions_count",
            "countries_count",
            "plates_count",
            "collector_level",
            "collection_xp",
        ):
            batch.drop_column(name)

    for table in (
        "cosmetic_titles",
        "season_progress",
        "album_progress",
        "user_missions",
        "missions",
        "game_events",
        "user_cosmetics",
        "cosmetics",
        "plate_rolls",
        "plate_challenges",
        "plate_albums",
        "albums",
        "plate_discoveries",
        "user_plates",
        "plates",
        "plate_templates",
        "regions",
        "countries",
    ):
        op.drop_table(table)
