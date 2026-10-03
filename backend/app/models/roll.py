"""Roll history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.number import Number


class Roll(Base):
    """One server-authoritative roll result.

    ``idempotency_key`` makes a retried HTTP request return the original roll
    instead of granting a second reward.
    """

    __tablename__ = "rolls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    number_id: Mapped[int] = mapped_column(ForeignKey("numbers.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    natural_rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    luck_rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    coins_awarded: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_first_discovery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    number: Mapped["Number"] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_rolls_idempotency_key"),
        Index("ix_rolls_user_created", "user_id", "created_at"),
        Index("ix_rolls_rarity_created", "rarity", "created_at"),
    )


__all__ = ["Roll"]
