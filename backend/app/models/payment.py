"""Payments (Telegram Stars / mock) and premium entitlements."""

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import PaymentProvider, PaymentStatus


class Product(Base, TimestampMixin):
    """Purchasable product exposed to the client."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stars_price: Mapped[int] = mapped_column(Integer, nullable=False)
    grant_type: Mapped[str] = mapped_column(String(16), nullable=False)
    grant_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Payment(Base, TimestampMixin):
    """Payment record with idempotent, refund-ready processing."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(24), default=PaymentProvider.MOCK.value, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), index=True)
    product_code: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="XTR", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.PENDING.value, index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    invoice_payload: Mapped[str | None] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refunded_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_payments_provider_external_id"),
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
    )


class PremiumEntitlement(Base, TimestampMixin):
    """Server-side premium entitlement. The client only ever reads it."""

    __tablename__ = "premium_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="PURCHASE", nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_entitlements_user_active", "user_id", "is_active"),)


__all__ = ["Payment", "PremiumEntitlement", "Product"]
