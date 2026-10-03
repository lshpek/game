"""Generic replay protection for operations that are not ledger-backed."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.analytics import IdempotencyRecord


class IdempotencyService:
    """Stores the first response for a (user, scope, key) triple.

    A retried request with the same key returns the stored response instead of
    executing the operation again.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int, scope: str, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key == key,
        )
        record = self.db.execute(stmt).scalar_one_or_none()
        return record.response if record else None

    def remember(self, user_id: int, scope: str, key: str | None, response: dict[str, Any]) -> None:
        if not key:
            return
        self.db.add(
            IdempotencyRecord(
                user_id=user_id,
                scope=scope,
                key=key,
                response=response,
                created_at=utcnow(),
            )
        )
        self.db.flush()
