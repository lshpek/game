"""Time helpers.

All persistence uses timezone-aware UTC datetimes so that SQLite and
PostgreSQL behave identically.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(UTC)


def utc_today() -> date:
    return utcnow().date()


def as_aware(value: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes coming back from SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def next_utc_midnight(moment: datetime | None = None) -> datetime:
    """First instant of the following UTC day."""
    current = as_aware(moment) or utcnow()
    tomorrow = current.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=UTC)


def start_of_utc_day(moment: datetime | None = None) -> datetime:
    current = as_aware(moment) or utcnow()
    return datetime.combine(current.date(), time.min, tzinfo=UTC)


def start_of_utc_week(moment: datetime | None = None) -> datetime:
    """Monday 00:00 UTC of the current ISO week."""
    current = as_aware(moment) or utcnow()
    start = current.date() - timedelta(days=current.weekday())
    return datetime.combine(start, time.min, tzinfo=UTC)


def days_between(later: datetime, earlier: datetime) -> int:
    return (as_aware(later).date() - as_aware(earlier).date()).days  # type: ignore[union-attr]
