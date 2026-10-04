"""admin audit log for the internal control surfaces

Adds a single append-only table, ``admin_audit_logs``, plus its indexes. No
existing table is touched: no user row, no ``wallet_transactions`` row and no
collection row is rewritten or removed, so this revision is safe to apply to a
live PostgreSQL production database.

The table only references ``users.id`` with ``ON DELETE SET NULL``, so deleting a
player keeps the audit trail intact instead of cascading it away.

Revision ID: 0003_admin_audit_log
Revises: 0002_numora_plates
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_admin_audit_log"
down_revision: Union[str, None] = "0002_numora_plates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TS = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("operation_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=48), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_audit_logs")),
    )

    with op.batch_alter_table("admin_audit_logs") as batch:
        batch.create_index(batch.f("ix_admin_audit_logs_action"), ["action"], unique=False)
        batch.create_index(batch.f("ix_admin_audit_logs_admin_telegram_id"), ["admin_telegram_id"], unique=False)
        batch.create_index(batch.f("ix_admin_audit_logs_category"), ["category"], unique=False)
        batch.create_index(batch.f("ix_admin_audit_logs_created_at"), ["created_at"], unique=False)
        batch.create_index(batch.f("ix_admin_audit_logs_operation_id"), ["operation_id"], unique=True)
        batch.create_index(batch.f("ix_admin_audit_logs_result"), ["result"], unique=False)
        batch.create_index(batch.f("ix_admin_audit_logs_target_user_id"), ["target_user_id"], unique=False)
        batch.create_index(
            batch.f("ix_admin_audit_admin_created"), ["admin_telegram_id", "created_at"], unique=False
        )
        batch.create_index(
            batch.f("ix_admin_audit_target_created"), ["target_user_id", "created_at"], unique=False
        )
        batch.create_index(
            batch.f("ix_admin_audit_action_created"), ["action", "created_at"], unique=False
        )


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
