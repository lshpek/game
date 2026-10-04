"""Rotating global events.

An event re-weights country selection for a bounded window. The rotation is
derived deterministically from the current time and the catalogue order, so every
process agrees on which event is live without any scheduling job.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutils import as_aware, utcnow
from app.game.countries import EVENTS
from app.models.numora import GameEvent

# The rotation repeats every CYCLE_DAYS days; each event occupies its own slice.
CYCLE_DAYS = 21


@dataclass(slots=True)
class ActiveEvent:
    """The event currently in force (or a neutral placeholder)."""

    code: str
    name_en: str
    name_ru: str
    flag: str
    country_multipliers: dict[str, float]
    ends_at: object
    reward_coins: int
    reward_title: str | None
    is_event: bool

    @property
    def multipliers(self) -> dict[str, float]:
        return dict(self.country_multipliers)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name_en": self.name_en,
            "name_ru": self.name_ru,
            "flag": self.flag,
            "country_multipliers": dict(self.country_multipliers),
            "ends_at": self.ends_at.isoformat() if hasattr(self.ends_at, "isoformat") else None,
            "reward_coins": self.reward_coins,
            "reward_title": self.reward_title,
            "is_event": self.is_event,
        }


NEUTRAL_EVENT = ActiveEvent(
    code="none",
    name_en="WORLD OPEN",
    name_ru="МИР ОТКРЫТ",
    flag="\U0001F30D",
    country_multipliers={},
    ends_at=None,
    reward_coins=0,
    reward_title=None,
    is_event=False,
)


def rotation_index(now=None) -> int:
    """Deterministic index into the event rotation."""
    now = now or utcnow()
    epoch_day = now.date().toordinal()
    return (epoch_day // 7) % max(1, len(EVENTS))


def current_event(now=None) -> ActiveEvent:
    """The event live right now, computed from the catalogue rotation."""
    now = now or utcnow()
    definition = EVENTS[rotation_index(now)]
    # Each event occupies a full week slice of the cycle.
    cycle_start = now - timedelta(
        days=(now.date().toordinal() % CYCLE_DAYS),
    )
    slot_start = cycle_start.replace(hour=0, minute=0, second=0, microsecond=0)
    slot_end = slot_start + timedelta(days=7)
    return ActiveEvent(
        code=definition.code,
        name_en=definition.name_en,
        name_ru=definition.name_ru,
        flag=definition.flag,
        country_multipliers=dict(definition.country_multipliers),
        ends_at=slot_end,
        reward_coins=definition.reward_coins,
        reward_title=definition.reward_title,
        is_event=True,
    )


class EventService:
    """Reads persisted events, falling back to the computed rotation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def persisted_active(self) -> GameEvent | None:
        return self.db.execute(
            select(GameEvent).where(GameEvent.is_active.is_(True)).order_by(GameEvent.sort_order).limit(1)
        ).scalar_one_or_none()

    def active(self) -> ActiveEvent:
        """Admin overrides win; otherwise the rotation drives the game."""
        row = self.persisted_active()
        if row is not None:
            return ActiveEvent(
                code=row.code,
                name_en=row.name_en,
                name_ru=row.name_ru,
                flag=row.flag,
                country_multipliers=dict(row.country_multipliers or {}),
                ends_at=as_aware(row.ends_at),
                reward_coins=int(row.reward_coins),
                reward_title=row.reward_title,
                is_event=True,
            )
        return current_event()

    def multipliers(self) -> dict[str, float]:
        return self.active().multipliers

    def serialize(self, event: ActiveEvent | None = None) -> dict[str, object]:
        return (event or self.active()).to_dict()


__all__ = [
    "CYCLE_DAYS",
    "NEUTRAL_EVENT",
    "ActiveEvent",
    "EventService",
    "current_event",
    "rotation_index",
]
