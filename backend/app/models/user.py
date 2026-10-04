"""User, wallet and ledger models.

The wallet balance is never mutated directly by game logic: every change flows
through ``app.services.economy`` which writes an auditable ledger row.
"""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import TransactionType, UserRole

if TYPE_CHECKING:
    from app.models.number import UserNumber


class User(Base, TimestampMixin):
    """A Telegram user plus their cached aggregate statistics."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    last_name: Mapped[str] = mapped_column(String(128), default="")
    language_code: Mapped[str | None] = mapped_column(String(16))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    is_telegram_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default=UserRole.USER.value, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Cached counters - updated inside the same transaction as the action.
    total_rolls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    containers_opened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_numbers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    challenges_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referrals_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    best_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    best_rarity: Mapped[str] = mapped_column(String(16), default="", nullable=False)

    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_roll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Collector progression and first-discovery statistics.
    collection_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    collector_level: Mapped[int] = mapped_column(Integer, default=1, index=True, nullable=False)
    plates_count: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)
    countries_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    regions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_discoveries_count: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)
    duplicates_sold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_plate_id: Mapped[int | None] = mapped_column(
        ForeignKey("plates.id", ondelete="SET NULL", use_alter=True)
    )
    best_collector_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    equipped_title: Mapped[str | None] = mapped_column(String(64))
    equipped_cosmetic_code: Mapped[str | None] = mapped_column(String(48))
    season_pass_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Bad-luck protection state - server owned, never client editable.
    pity_rare_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pity_epic_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pity_legendary_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Daily roll allowance (server authority; never trusts client time).
    daily_rolls_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bonus_rolls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    numbers: Mapped[list["UserNumber"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_users_best_value", "best_value"),
        Index("ix_users_unique_numbers", "unique_numbers_count"),
        Index("ix_users_total_rolls", "total_rolls"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or (f"@{self.username}" if self.username else f"id{self.telegram_id}")


class Wallet(Base, TimestampMixin):
    """Current COINS balance and lifetime totals."""

    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_spent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="wallet")


class WalletTransaction(Base):
    """Immutable ledger entry - the audit trail for every balance change."""

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(32))
    reference_id: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_wallet_transactions_idempotency_key"),
        Index("ix_wallet_tx_user_type_created", "user_id", "type", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<WalletTransaction {self.id} {self.type} {self.amount:+d} -> {self.balance_after}>"


__all__ = ["TransactionType", "User", "UserRole", "Wallet", "WalletTransaction"]
