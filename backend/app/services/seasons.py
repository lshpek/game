"""Season lifecycle helpers."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.timeutils import as_aware, utcnow
from app.models.progression import Season


class SeasonService:
    """Reads seasons and exposes the active one."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def active(self) -> Season | None:
        return self.db.execute(
            select(Season).where(Season.is_active.is_(True)).order_by(Season.sort_order).limit(1)
        ).scalar_one_or_none()

    def list_all(self) -> list[Season]:
        return list(
            self.db.execute(select(Season).order_by(Season.sort_order, Season.id)).scalars().all()
        )

    def get(self, code: str) -> Season:
        row = self.db.execute(select(Season).where(Season.code == code)).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Season not found.", code="SEASON_NOT_FOUND")
        return row

    def activate(self, code: str) -> Season:
        """Make exactly one season active (admin action)."""
        target = self.get(code)
        for season in self.list_all():
            season.is_active = season.id == target.id
        self.db.flush()
        return target

    def deactivate_all(self) -> None:
        for season in self.list_all():
            season.is_active = False
        self.db.flush()

    def extend(self, code: str, days: int) -> Season:
        season = self.get(code)
        season.end_date = season.end_date + timedelta(days=max(1, days))
        self.db.flush()
        return season

    def serialize(self, season: Season) -> dict[str, object]:
        now = utcnow()
        start = as_aware(season.start_date)
        end = as_aware(season.end_date)
        return {
            "code": season.code,
            "name": season.name,
            "description": season.description,
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "is_active": bool(season.is_active),
            "is_over": bool(end and end < now),
            "special_numbers": list(season.special_numbers or []),
            "rewards": dict(season.rewards or {}),
        }
