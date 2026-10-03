"""Number catalogue, ownership and first-discovery records."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from app.models.user import User


class Number(Base, TimestampMixin):
    """Catalogue entry for one of the 10 000 possible numbers.

    Created lazily the first time a number is rolled, so unknown numbers have no
    row and ``discovery_count`` starts at zero by definition.
    """

    __tablename__ = "numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    value_str: Mapped[str] = mapped_column(String(4), unique=True, index=True, nullable=False)
    value_int: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    base_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    traits: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    story: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_special: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovery_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    first_discovered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    first_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_numbers_rarity_value", "rarity", "value_int"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Number {self.value_str} {self.rarity}>"


class UserNumber(Base, TimestampMixin):
    """Ownership record. Duplicates increment ``duplicate_count``."""

    __tablename__ = "user_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    number_id: Mapped[int] = mapped_column(ForeignKey("numbers.id", ondelete="CASCADE"), index=True, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    first_acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="numbers")
    number: Mapped[Number] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "number_id", name="uq_user_numbers_user_number"),
        Index("ix_user_numbers_user_acquired", "user_id", "first_acquired_at"),
    )


class Discovery(Base):
    """Every roll that "found" a number - powers the discovery counter."""

    __tablename__ = "discoveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number_id: Mapped[int] = mapped_column(ForeignKey("numbers.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    is_first_discovery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="ROLL", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_discoveries_number_created", "number_id", "created_at"),)


__all__ = ["Discovery", "Number", "UserNumber"]
