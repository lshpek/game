"""Admin audit log.

Every mutation issued from the internal control surfaces (today: the Telegram
admin panel) appends one immutable row here. The table is append-only: rows are
never updated except to fill in ``result``/``after_json`` for an operation that
was claimed but not yet finished, and they are never deleted.

The log is deliberately free of secrets - it stores ids, action codes, amounts,
reasons and small before/after snapshots of *game* state only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutils import utcnow
from app.db.base import Base


class AdminAuditLog(Base):
    """One administrative action, successful or not."""

    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- who -------------------------------------------------------------
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    admin_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # --- whom ------------------------------------------------------------
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # --- what ------------------------------------------------------------
    action: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(24), index=True, default="MISC", nullable=False)
    amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # --- operational -----------------------------------------------------
    # Unique per operation: replaying a callback with the same id can never
    # grant twice, because the second insert collides.
    operation_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    result: Mapped[str] = mapped_column(String(16), default="OK", index=True, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_admin_audit_admin_created", "admin_telegram_id", "created_at"),
        Index("ix_admin_audit_target_created", "target_user_id", "created_at"),
        Index("ix_admin_audit_action_created", "action", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<AdminAuditLog {self.id} {self.action} by {self.admin_telegram_id}>"


__all__ = ["AdminAuditLog"]
