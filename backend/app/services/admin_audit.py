"""Admin audit log persistence.

The service is intentionally tiny: append a row, find one by its operation id,
and page through the newest entries. All mutation logic lives in
:mod:`app.services.admin`, which claims an operation *before* touching game state
so a replayed Telegram callback can never grant twice.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timeutils import as_aware, utcnow
from app.models.admin import AdminAuditLog
from app.models.enums import AdminCategory

# Snapshot fields kept in ``before_json`` / ``after_json``. Only small, flat,
# non-sensitive game state is allowed here.
SNAPSHOT_KEYS = (
    "coins",
    "bonus_rolls",
    "daily_rolls_used",
    "collection_xp",
    "collector_level",
    "current_streak",
    "longest_streak",
    "plates_count",
    "countries_count",
    "first_discoveries_count",
    "total_rolls",
    "is_banned",
    "premium_tier",
    "premium_expires_at",
    "plate_id",
    "plates_count_after",
)


def snapshot(values: dict[str, Any]) -> dict[str, Any]:
    """Keep only the whitelisted, JSON-safe subset of a state snapshot."""
    result: dict[str, Any] = {}
    for key in SNAPSHOT_KEYS:
        if key not in values:
            continue
        value = values[key]
        if value is None or isinstance(value, (int, float, bool, str)):
            result[key] = value
    return result


class AdminAuditService:
    """Append-only writer/reader for :class:`AdminAuditLog`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- writes ---------------------------------------------------------
    def claim(
        self,
        *,
        action: str,
        category: AdminCategory | str,
        admin_telegram_id: int,
        operation_id: str | None = None,
        admin_user_id: int | None = None,
        target_user_id: int | None = None,
        target_telegram_id: int | None = None,
        amount: int | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> tuple[AdminAuditLog, bool]:
        """Insert a ``PENDING`` row; return ``(row, is_new)``.

        The unique ``operation_id`` index is what makes the whole panel safe
        against duplicated Telegram callbacks: the second insert loses the race
        and is reported as ``(existing_row, False)`` instead of executing
        anything.
        """
        if operation_id:
            existing = self.by_operation(operation_id)
            if existing is not None:
                return existing, False

        row = AdminAuditLog(
            action=str(action),
            category=str(category),
            admin_telegram_id=int(admin_telegram_id),
            admin_user_id=admin_user_id,
            target_user_id=target_user_id,
            target_telegram_id=target_telegram_id,
            amount=amount,
            reason=(reason or "")[:255] or None,
            metadata_json=metadata or None,
            operation_id=operation_id,
            request_id=request_id,
            result="PENDING",
            created_at=utcnow(),
        )
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
        except IntegrityError:
            # ``begin_nested`` already rolled the savepoint back; the outer
            # transaction stays usable.
            if operation_id:
                found = self.by_operation(operation_id)
                if found is not None:
                    return found, False
            raise
        return row, True

    def by_operation(self, operation_id: str) -> AdminAuditLog | None:
        return self.db.execute(
            select(AdminAuditLog).where(AdminAuditLog.operation_id == operation_id)
        ).scalar_one_or_none()

    def finish(
        self,
        row: AdminAuditLog,
        *,
        after: dict[str, Any] | None = None,
        amount: int | None = None,
        result: str = "OK",
        duration_ms: int | None = None,
    ) -> AdminAuditLog:
        """Mark a claimed operation as finished and store its outcome."""
        row.after_json = snapshot(after) if after else None
        if amount is not None:
            row.amount = int(amount)
        row.result = result
        row.duration_ms = duration_ms
        self.db.flush()
        return row

    def record(
        self,
        *,
        action: str,
        category: AdminCategory | str,
        admin_telegram_id: int,
        after: dict[str, Any] | None = None,
        before: dict[str, Any] | None = None,
        amount: int | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        admin_user_id: int | None = None,
        target_user_id: int | None = None,
        target_telegram_id: int | None = None,
        operation_id: str | None = None,
        request_id: str | None = None,
        duration_ms: int | None = None,
    ) -> AdminAuditLog:
        """One-shot helper for non-idempotent bookkeeping entries."""
        row = AdminAuditLog(
            action=str(action),
            category=str(category),
            admin_telegram_id=int(admin_telegram_id),
            admin_user_id=admin_user_id,
            target_user_id=target_user_id,
            target_telegram_id=target_telegram_id,
            amount=amount,
            reason=(reason or "")[:255] or None,
            before_json=snapshot(before) if before else None,
            after_json=snapshot(after) if after else None,
            metadata_json=metadata or None,
            operation_id=operation_id,
            request_id=request_id,
            result="OK",
            duration_ms=duration_ms,
            created_at=utcnow(),
        )
        self.db.add(row)
        self.db.flush()
        return row

    # --- reads ----------------------------------------------------------
    def recent(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        admin_telegram_id: int | None = None,
        target_user_id: int | None = None,
        action: str | None = None,
        category: str | None = None,
    ) -> list[AdminAuditLog]:
        stmt = select(AdminAuditLog)
        if admin_telegram_id is not None:
            stmt = stmt.where(AdminAuditLog.admin_telegram_id == admin_telegram_id)
        if target_user_id is not None:
            stmt = stmt.where(AdminAuditLog.target_user_id == target_user_id)
        if action:
            stmt = stmt.where(AdminAuditLog.action == action.upper())
        if category:
            stmt = stmt.where(AdminAuditLog.category == category.upper())
        rows = self.db.execute(
            stmt.order_by(AdminAuditLog.id.desc()).limit(max(1, min(limit, 50))).offset(max(0, offset))
        ).scalars()
        return list(rows)

    def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(AdminAuditLog)
        for column, value in filters.items():
            if value is None:
                continue
            stmt = stmt.where(getattr(AdminAuditLog, column) == value)
        return int(self.db.execute(stmt).scalar_one() or 0)

    def failed_count(self, since=None) -> int:
        stmt = select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.result != "OK")
        if since is not None:
            stmt = stmt.where(AdminAuditLog.created_at >= since)
        return int(self.db.execute(stmt).scalar_one() or 0)

    def serialize(self, row: AdminAuditLog) -> dict[str, object]:
        created = as_aware(row.created_at)
        return {
            "id": row.id,
            "admin_telegram_id": int(row.admin_telegram_id),
            "admin_user_id": row.admin_user_id,
            "target_user_id": row.target_user_id,
            "target_telegram_id": row.target_telegram_id,
            "action": row.action,
            "category": row.category,
            "amount": int(row.amount) if row.amount is not None else None,
            "reason": row.reason or "",
            "before": row.before_json or {},
            "after": row.after_json or {},
            "metadata": row.metadata_json or {},
            "operation_id": row.operation_id,
            "request_id": row.request_id,
            "result": row.result,
            "duration_ms": row.duration_ms,
            "created_at": created.isoformat() if created else None,
        }


def duration_ms(start: float) -> int:
    """Milliseconds elapsed since ``start = time.perf_counter()``."""
    return round((time.perf_counter() - start) * 1000)


__all__ = ["SNAPSHOT_KEYS", "AdminAuditService", "duration_ms", "snapshot"]
