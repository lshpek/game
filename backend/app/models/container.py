"""Container catalogue and opening history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Container(Base, TimestampMixin):
    """A purchasable box. Results are always resolved server side."""

    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    rarity_weights: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    minimum_rarity: Mapped[str] = mapped_column(String(16), default="COMMON", nullable=False)
    accent: Mapped[str] = mapped_column(String(16), default="#38bdf8", nullable=False)
    animation: Mapped[str] = mapped_column(String(16), default="shake", nullable=False)
    premium_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ContainerOpening(Base):
    """Audit row for a container purchase and its result."""

    __tablename__ = "container_openings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    container_id: Mapped[int] = mapped_column(ForeignKey("containers.id", ondelete="CASCADE"), nullable=False)
    number_id: Mapped[int] = mapped_column(ForeignKey("numbers.id", ondelete="CASCADE"), nullable=False)
    price_paid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    container: Mapped[Container] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_container_openings_idempotency_key"),
        Index("ix_openings_user_created", "user_id", "created_at"),
    )


__all__ = ["Container", "ContainerOpening"]
