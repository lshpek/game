"""payment and idempotency integrity for the collectible universe

Four fixes, all of them about money never being lost and never being granted
twice. No row is deleted and no wallet balance is rewritten.

1. ``admin_audit_logs.result_json`` stores the operation's own response. A replay
   of the same ``operation_id`` used to answer with the whitelisted ``after``
   snapshot, so a retried request returned a *different shape* from the original -
   the caller could not tell a replay from a fresh grant.

2. ``payments.invoice_payload`` gets an index. It is the lookup key for every
   Telegram webhook, so without it each payment confirmation was a sequential
   scan that got slower with every sale.

3. The global ``uq_payments_idempotency_key`` becomes ``(user_id,
   idempotency_key)``. The key is supplied by the client and looked up *per user*,
   so a global constraint meant two unrelated players who happened to send the
   same key collided into an ``IntegrityError`` - a 500 on a legitimate purchase.
   Existing duplicate keys are de-duplicated to the oldest row before the new
   constraint is added, so the migration cannot fail on production data.

4. ``payments.idempotency_key`` becomes NULL when it repeats within a user, which
   is what "this key has already been used" means for a column with a unique
   index. Duplicates keep the charge; they simply stop reserving the key.

Revision ID: 0004_payment_integrity
Revises: 0003_admin_audit_log
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_payment_integrity"
down_revision: Union[str, None] = "0003_admin_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 0) the audit row now stores the operation's own response, so a replayed
    #    request is answered with the same payload the first call produced
    #    instead of a whitelisted state snapshot.
    with op.batch_alter_table("admin_audit_logs") as batch:
        batch.add_column(sa.Column("result_json", sa.JSON(), nullable=True))

    # 1) index the webhook lookup key
    with op.batch_alter_table("payments") as batch:
        batch.create_index("ix_payments_invoice_payload", ["invoice_payload"], unique=False)

    # 2) free keys that repeat inside one user, keeping the earliest payment
    #    (the one that actually consumed the key) untouched.
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                UPDATE payments AS loser
                   SET idempotency_key = NULL
                  FROM payments AS winner
                 WHERE loser.user_id = winner.user_id
                   AND loser.idempotency_key IS NOT NULL
                   AND loser.idempotency_key = winner.idempotency_key
                   AND loser.id > winner.id
                """
            )
        )
    else:
        # SQLite has no UPDATE ... FROM; the correlated subquery is equivalent and
        # keeps this migration runnable in the test suite.
        bind.execute(
            sa.text(
                """
                UPDATE payments
                   SET idempotency_key = NULL
                 WHERE idempotency_key IS NOT NULL
                   AND EXISTS (
                        SELECT 1
                          FROM payments AS winner
                         WHERE winner.user_id = payments.user_id
                           AND winner.idempotency_key = payments.idempotency_key
                           AND winner.id < payments.id
                   )
                """
            )
        )

    # 3) scope uniqueness to the user the key actually belongs to
    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("uq_payments_idempotency_key", type_="unique")
        batch.create_unique_constraint(
            "uq_payments_user_idempotency_key", ["user_id", "idempotency_key"]
        )
        batch.create_index("ix_payments_user_status", ["user_id", "status"], unique=False)
        batch.create_index("ix_payments_provider_status", ["provider", "status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("admin_audit_logs") as batch:
        batch.drop_column("result_json")

    with op.batch_alter_table("payments") as batch:
        batch.drop_index("ix_payments_provider_status")
        batch.drop_index("ix_payments_user_status")
        batch.drop_constraint("uq_payments_user_idempotency_key", type_="unique")
        # A global unique constraint cannot be restored while per-user duplicates
        # exist, so those keys are cleared first.
        bind = op.get_bind()
        bind.execute(
            sa.text(
                """
                UPDATE payments
                   SET idempotency_key = NULL
                 WHERE idempotency_key IS NOT NULL
                   AND EXISTS (
                        SELECT 1
                          FROM payments AS other
                         WHERE other.idempotency_key = payments.idempotency_key
                           AND other.id <> payments.id
                   )
                """
            )
        )
        batch.create_unique_constraint("uq_payments_idempotency_key", ["idempotency_key"])
        batch.drop_index("ix_payments_invoice_payload")