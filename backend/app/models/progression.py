"""Progression models: achievements, seasons and daily rewards."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
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


class Achievement(Base, TimestampMixin):
    """Catalogue of unlockable achievements."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon: Mapped[str] = mapped_column(String(32), default="star", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserAchievement(Base):
    """Unlock state and progress per user."""

    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    achievement: Mapped[Achievement] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievements_user_achievement"),
    )


class Season(Base, TimestampMixin):
    """A timed content season."""

    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    special_numbers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rewards: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DailyReward(Base):
    """One row per claimed UTC day - the unique constraint is the idempotency."""

    __tablename__ = "daily_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    claimed_on: Mapped[date] = mapped_column(Date, nullable=False)
    rolls_granted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins_granted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "claimed_on", name="uq_daily_rewards_user_claimed_on"),
        Index("ix_daily_rewards_user_created", "user_id", "created_at"),
    )


__all__ = ["Achievement", "DailyReward", "Season", "UserAchievement"]
