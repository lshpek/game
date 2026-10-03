"""Analytics events and generic idempotency records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsEvent(Base):
    """Lightweight product analytics sink (no third party, no PII beyond ids)."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    props: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    __table_args__ = (Index("ix_analytics_name_created", "name", "created_at"),)


class IdempotencyRecord(Base):
    """Replay protection for non-ledger operations (e.g. challenge creation)."""

    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    response: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_user_scope_key"),
    )


__all__ = ["AnalyticsEvent", "IdempotencyRecord"]
