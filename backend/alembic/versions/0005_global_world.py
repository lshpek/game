"""global world: ISO 3166-1 countries, playable flag, SIM details, active country

Extends the country system from the twelve launch countries to the complete
ISO 3166-1 list (250 countries and territories) and gives SIM cards a first-class
place in the schema.

What this migration adds
------------------------
``countries.iso_alpha2``
    ISO 3166-1 alpha-2 code. ``countries.code`` was already the alpha-3 identifier,
    so the pair now matches the standard exactly and deep links can carry either form.

``countries.is_playable``
    Separate from ``is_active``. Every ISO country is active (listed by the atlas),
    but only countries with complete generation and presentation data can be rolled.
    A locked country is released by flipping this flag - no schema change.

``countries.sim_config``
    SIM/number presentation configuration: calling code, printed groupings, fictional
    operators and editions. Written for locked countries too, so a future unlock only
    needs layouts.

``plates.details``
    Kind-specific payload. SIM cards carry ``operator``, ``series``, ``edition`` and
    the synthetic number printed on the card. Empty for vehicle plates.

``users.active_country_code``
    The player's selected world, authoritative on the server. ``NULL`` means "the
    whole world", which is exactly the previous default behaviour.

Data fix
--------
``PHONE`` plates and templates - the removed ``PHONE_NUMBER`` collectible - are folded
into ``SIM_CARD``. A ``PHONE`` row already *is* a physical card with a synthetic number
printed on it, so re-labelling keeps every discovery, ownership and first-discoverer
row intact. Nothing is deleted.

Safety
------
No table is dropped, no row is deleted, no production data is reset. Every added
column is nullable or carries a server default, so an older application revision
running against the upgraded schema keeps working.


Revision ID: 0005_global_world
Revises: 0004_payment_integrity
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_global_world"
down_revision: Union[str, None] = "0004_payment_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON_EMPTY = sa.text("'{}'")


def upgrade() -> None:
    # --- countries: ISO identifiers, playability, SIM configuration ---------
    with op.batch_alter_table("countries") as batch:
        batch.add_column(sa.Column("iso_alpha2", sa.String(length=2), nullable=True))
        batch.add_column(
            sa.Column(
                "is_playable",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch.add_column(
            sa.Column(
                "sim_config",
                sa.JSON(),
                nullable=False,
                server_default=_JSON_EMPTY,
            )
        )
    with op.batch_alter_table("countries") as batch:
        batch.create_index(batch.f("ix_countries_iso_alpha2"), ["iso_alpha2"], unique=True)
        batch.create_index(batch.f("ix_countries_is_playable"), ["is_playable"], unique=False)

    # Widen the display columns: ISO official names are longer than 64 characters.
    with op.batch_alter_table("countries") as batch:
        batch.alter_column("name_en", type_=sa.String(length=96), existing_type=sa.String(length=64))
        batch.alter_column("name_ru", type_=sa.String(length=96), existing_type=sa.String(length=64))
        batch.alter_column("flag", type_=sa.String(length=16), existing_type=sa.String(length=8))
        batch.alter_column(
            "region_group", type_=sa.String(length=24), existing_type=sa.String(length=16)
        )

    # --- plates: kind-specific payload ------------------------------------
    with op.batch_alter_table("plates") as batch:
        batch.add_column(
            sa.Column("details", sa.JSON(), nullable=False, server_default=_JSON_EMPTY)
        )

    # --- users: the authoritative active country ---------------------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("active_country_code", sa.String(length=3), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.create_index(
            batch.f("ix_users_active_country_code"), ["active_country_code"], unique=False
        )

    _fold_phone_into_sim()


def _fold_phone_into_sim() -> None:
    """Re-label the removed ``PHONE_NUMBER`` collectible as a SIM card.

    ``PHONE`` rows and templates keep their ids, so ownership, discoveries, albums and
    first-discoverer links are preserved exactly. The country rows themselves are
    filled by the idempotent catalogue seed the backend runs on every boot, which is
    how an existing database receives the rest of the ISO 3166-1 list.
    """
    op.execute(
        sa.text("UPDATE plate_templates SET plate_type = 'SIM' WHERE plate_type = 'PHONE'")
    )
    op.execute(sa.text("UPDATE plates SET plate_type = 'SIM' WHERE plate_type = 'PHONE'"))
    op.execute(
        sa.text(
            "UPDATE plates SET tags = '[\"sim\", \"synthetic\"]' "
            "WHERE plate_type = 'SIM' AND (tags IS NULL OR tags = '[]')"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index(batch.f("ix_users_active_country_code"))
        batch.drop_column("active_country_code")

    with op.batch_alter_table("plates") as batch:
        batch.drop_column("details")

    with op.batch_alter_table("countries") as batch:
        batch.alter_column(
            "region_group", type_=sa.String(length=16), existing_type=sa.String(length=24)
        )
        batch.alter_column("flag", type_=sa.String(length=8), existing_type=sa.String(length=16))
        batch.alter_column("name_ru", type_=sa.String(length=64), existing_type=sa.String(length=96))
        batch.alter_column("name_en", type_=sa.String(length=64), existing_type=sa.String(length=96))
        batch.drop_index(batch.f("ix_countries_is_playable"))
        batch.drop_index(batch.f("ix_countries_iso_alpha2"))
        batch.drop_column("sim_config")
        batch.drop_column("is_playable")
        batch.drop_column("iso_alpha2")

    # SIM rows stay SIM on the way down: the previous revision can represent them
    # (it rendered a number on a card), so no collectible data is lost by a downgrade.