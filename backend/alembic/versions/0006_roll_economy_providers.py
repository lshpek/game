"""roll economy: passive regeneration clock, SIM provider catalogue

Brings the roll economy to the documented model and gives the SIM line a real provider
catalogue, without touching a single existing collectible.

What this migration adds
------------------------
``users.roll_regen_at``
    When the next passive roll becomes available. ``NULL`` means the normal bank is
    full, so regeneration is idle. Existing players are unaffected: the bank simply
    refills to its (new, larger) cap, and no already earned roll is removed.

``sim_providers``
    The mobile operator catalogue a country's SIM cards may print. Stable code, country,
    brand, local name, weight and the two *game* modifiers. Seeded idempotently by the
    catalogue seed the backend runs on every boot.

``plate_templates.config.provider_*``
    Generated in code - the seed writes them - so a SIM template always knows which
    provider and which game modifiers produced it.

Data fix
--------
None. Nothing is deleted, renumbered or rewritten: existing plates, ownership rows,
discoveries, ledger entries, missions and achievements are untouched. SIM templates
belonging to the retired fictional operator set are deactivated by the seed (their rows
stay, so old cards keep rendering), while new rolls use the real provider catalogue.

Safety
------
Every added column is nullable; the new table is additive. An older application revision
running against the upgraded schema keeps working.


Revision ID: 0006_roll_economy_providers
Revises: 0005_global_world
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_roll_economy_providers"
down_revision: Union[str, None] = "0005_global_world"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- passive regeneration clock -------------------------------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("roll_regen_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.create_index(batch.f("ix_users_roll_regen_at"), ["roll_regen_at"], unique=False)

    # --- the SIM provider catalogue -------------------------------------
    op.create_table(
        "sim_providers",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("brand", sa.String(length=48), nullable=False),
        sa.Column("local_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("rarity_modifier", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("value_modifier", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("visual", sa.String(length=24), nullable=False, server_default="neutral"),
        sa.Column("accent", sa.String(length=16), nullable=False, server_default="#c9a227"),
        sa.Column("is_real_brand", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sim_providers")),
        sa.UniqueConstraint("code", name=op.f("uq_sim_providers_code")),
    )
    with op.batch_alter_table("sim_providers") as batch:
        batch.create_index(batch.f("ix_sim_providers_code"), ["code"], unique=True)
        batch.create_index(batch.f("ix_sim_providers_country_code"), ["country_code"], unique=False)
        batch.create_index(batch.f("ix_sim_providers_is_active"), ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_table("sim_providers")

    with op.batch_alter_table("users") as batch:
        batch.drop_index(batch.f("ix_users_roll_regen_at"))
        batch.drop_column("roll_regen_at")

    # Collectible data is never touched by a downgrade: SIM plates stay SIM and the
    # provider catalogue is rebuilt by the seed on the next boot.