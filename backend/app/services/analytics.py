"""Product analytics sink."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.analytics import AnalyticsEvent


class AnalyticsService:
    """Records product events; failures never break the user-facing flow."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def track(
        self,
        name: str,
        *,
        user_id: int | None = None,
        telegram_id: int | None = None,
        props: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        event = AnalyticsEvent(
            user_id=user_id,
            telegram_id=telegram_id,
            name=str(name),
            props=props or None,
            created_at=utcnow(),
        )
        self.db.add(event)
        self.db.flush()
        return event
