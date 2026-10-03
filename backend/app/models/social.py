"""Social models: referrals, challenges and share events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import ChallengeStatus, ReferralStatus


class Referral(Base, TimestampMixin):
    """Link between an inviter and an invitee.

    A referral row is created as ``PENDING`` when the invitee first opens the
    Mini App and only becomes ``ACTIVATED`` (and paid) after the invitee
    completes a real roll.
    """

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    referred_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default=ReferralStatus.PENDING.value, index=True, nullable=False)
    start_param: Mapped[str | None] = mapped_column(String(64))
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_rolls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_referrals_referrer_status", "referrer_id", "status"),)


class Challenge(Base, TimestampMixin):
    """A friend duel created from a deep link."""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    challenger_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    opponent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    challenger_number_id: Mapped[int] = mapped_column(ForeignKey("numbers.id", ondelete="CASCADE"), nullable=False)
    opponent_number_id: Mapped[int | None] = mapped_column(ForeignKey("numbers.id", ondelete="SET NULL"))
    challenger_rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    challenger_value: Mapped[int] = mapped_column(Integer, nullable=False)
    opponent_rarity: Mapped[str | None] = mapped_column(String(16))
    opponent_value: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=ChallengeStatus.PENDING.value, index=True, nullable=False)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_challenges_opponent_status", "opponent_id", "status"),)


class ShareEvent(Base):
    """Analytics: how often players share their results."""

    __tablename__ = "share_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    number_id: Mapped[int | None] = mapped_column(ForeignKey("numbers.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(32), default="telegram", nullable=False)
    start_param: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


__all__ = ["Challenge", "Referral", "ShareEvent"]
