"""NUMORA extras: cosmetics, missions, global events and collector progression.

These tables back the presentation layer (cosmetics), the retention layer
(missions) and the live feel of the game (rotating events). None of them can
influence rarity, valuation or the ledger - they are presentation and pacing
only.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Cosmetic(Base, TimestampMixin):
    """A purchasable or unlockable cosmetic."""

    __tablename__ = "cosmetics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(64), nullable=False)
    description_en: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    description_ru: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    # Presentation payload the client renders (colours, gradients, preview info).
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    price_stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_numora: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rarity_code: Mapped[str] = mapped_column(String(16), default="COMMON", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cosmetic {self.code}>"


class UserCosmetic(Base):
    """Ownership of one cosmetic, plus whether it is currently equipped."""

    __tablename__ = "user_cosmetics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    cosmetic_id: Mapped[int] = mapped_column(ForeignKey("cosmetics.id", ondelete="CASCADE"), nullable=False)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cosmetic: Mapped[Cosmetic] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "cosmetic_id", name="uq_user_cosmetics_user_cosmetic"),
        Index("ix_user_cosmetics_user_equipped", "user_id", "equipped"),
    )


class GameEvent(Base, TimestampMixin):
    """A rotating global event with configurable country weight modifiers."""

    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(64), nullable=False)
    flag: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # ``{country_code: multiplier}`` - configuration, not frontend logic.
    country_multipliers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_title: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)


class Mission(Base):
    """A daily mission definition."""

    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(64), nullable=False)
    description_en: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    description_ru: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    metric: Mapped[str] = mapped_column(String(48), nullable=False)
    target: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_rolls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon: Mapped[str] = mapped_column(String(32), default="target", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class UserMission(Base):
    """Per-user mission progress for one UTC day."""

    __tablename__ = "user_missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    mission_date: Mapped[date] = mapped_column(Date, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reward_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mission: Mapped[Mission] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "mission_id", "mission_date", name="uq_user_missions_day"),
        Index("ix_user_missions_user_date", "user_id", "mission_date"),
    )


class AlbumProgress(Base):
    """Completion of one album by one user."""

    __tablename__ = "album_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    album_id: Mapped[int] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"), nullable=False)
    collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reward_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "album_id", name="uq_album_progress_user_album"),
    )


class SeasonProgress(Base):
    """Season XP and reward-track state for one user."""

    __tablename__ = "season_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    season_code: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_tiers: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    has_pass: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "season_code", name="uq_season_progress_user_season"),
    )


class CosmeticTitle(Base):
    """A title unlocked through an achievement, album or purchase."""

    __tablename__ = "cosmetic_titles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(48), default="", nullable=False)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SupporterEntitlement(Base, TimestampMixin):
    """Server-side supporter tier granted by a Stars purchase.

    Purely a supporter badge/title - never a gameplay power-up, so supporting
    NUMORA can never become a required paywall.
    """

    __tablename__ = "supporter_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="PURCHASE", nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_supporter_entitlements_user_active", "user_id", "is_active"),)


class PlateRoll(Base):
    """Roll history for plates (the authoritative record of a roll)."""

    __tablename__ = "plate_rolls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plate_id: Mapped[int] = mapped_column(ForeignKey("plates.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    natural_rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    luck_rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    rarity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dealer_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    collector_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    numora_awarded: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_first_discovery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    plate: Mapped[object] = relationship("Plate", lazy="joined")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_plate_rolls_idempotency_key"),
        Index("ix_plate_rolls_user_created", "user_id", "created_at"),
        Index("ix_plate_rolls_rarity_created", "rarity", "created_at"),
    )


__all__ = [
    "AlbumProgress",
    "Cosmetic",
    "CosmeticTitle",
    "GameEvent",
    "Mission",
    "PlateRoll",
    "SeasonProgress",
    "SupporterEntitlement",
    "UserCosmetic",
    "UserMission",
]
