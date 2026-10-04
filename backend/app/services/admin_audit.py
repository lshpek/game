"""Admin audit log persistence.

The service is intentionally tiny: append a row, find one by its operation id,
and page through the newest entries. All mutation logic lives in
:mod:`app.services.admin`, which claims an operation *before* touching game state
so a replayed Telegram callback can never grant twice.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.timeutils import as_aware, utcnow
from app.models.admin import AdminAuditLog
from app.models.enums import AdminCategory

logger = get_logger("app.services.admin_audit")

#: A claim in this state may be retried under the same ``operation_id``; every
#: other outcome (``OK``, ``PENDING``) is final and replays instead.
RETRYABLE_RESULT = "FAILED"

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


def failure_metadata(error: BaseException, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Audit metadata for a failed operation.

    Only the exception *type* and a short message are stored. A stack trace, a SQL
    string or a request body could carry a token or a phone number into a log that
    operators (and exports) read, so ``repr`` is deliberately not used.
    """
    payload: dict[str, Any] = {"error_type": type(error).__name__}
    message = " ".join(str(error).split())
    if message:
        payload["error_message"] = message[:200]
    if extra:
        payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


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

        The claim is **committed immediately** rather than left for the caller's
        transaction. That matters: the mutation is rolled back when it fails, and a
        released ``SAVEPOINT`` is not reliably undone by a session rollback (SQLite
        keeps the row). Committing the claim makes the id genuinely durable - the
        evidence survives the rollback, and :meth:`mark_failed` only has to update
        the existing row instead of re-inserting one that would collide with it.
        """
        if operation_id:
            existing = self.by_operation(operation_id)
            if existing is not None:
                if existing.result != RETRYABLE_RESULT:
                    return existing, False
                # The previous attempt failed, so this is a retry, not a replay.
                # Re-opening the claim is safe because every mutation carries its
                # own ``admin:<operation_id>`` ledger idempotency key: a partial
                # first attempt cannot be paid out twice. The failure diagnostics
                # are kept so the history stays readable.
                previous = existing.metadata_json or {}
                existing.result = "PENDING"
                existing.metadata_json = {
                    **previous,
                    "retries": int(previous.get("retries") or 0) + 1,
                    "last_failure": {
                        key: previous[key]
                        for key in ("error_type", "error_message")
                        if key in previous
                    },
                }
                existing.duration_ms = None
                self.db.commit()
                return existing, True

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
        self.db.commit()
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
        metadata: dict[str, Any] | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> AdminAuditLog:
        """Mark a claimed operation as finished and store its outcome.

        ``metadata`` **merges** into whatever the claim stored, so a failure can add
        its diagnostics without discarding the original request context.
        ``result_json`` stores the operation's own response, which is what a replay
        of the same ``operation_id`` returns verbatim.
        """
        row.after_json = snapshot(after) if after else None
        if amount is not None:
            row.amount = int(amount)
        row.result = result
        row.duration_ms = duration_ms
        if metadata:
            row.metadata_json = {**(row.metadata_json or {}), **metadata}
        if result_json is not None:
            row.result_json = result_json
        self.db.flush()
        return row

    def mark_failed(
        self,
        row: AdminAuditLog,
        error: BaseException,
        *,
        duration_ms: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AdminAuditLog | None:
        """Record a failed operation against the durable claim row.

        The caller's transaction is rolled back first - the mutation must leave no
        trace - and this then marks the claim ``FAILED`` in its own transaction,
        keeping the operation id, the actor, the target, the reason and the original
        timestamp. The row is *updated*, not re-inserted: the id is already taken
        (that uniqueness is what stopped the mutation from running twice), and the
        failure simply becomes its recorded outcome.

        Every field is read *before* the rollback. Afterwards the instance is
        detached and any attribute access would raise ``DetachedInstanceError``
        instead of writing the failure the operator needs.

        Returns the persisted row, or ``None`` when persistence itself failed - in
        which case the original exception is the one that matters.
        """
        claim = {
            "action": row.action,
            "category": row.category,
            "admin_telegram_id": int(row.admin_telegram_id),
            "admin_user_id": row.admin_user_id,
            "target_user_id": row.target_user_id,
            "target_telegram_id": row.target_telegram_id,
            "amount": row.amount,
            "reason": row.reason,
            "operation_id": row.operation_id,
            "request_id": row.request_id,
            "created_at": row.created_at,
        }
        diagnostics = failure_metadata(
            error, {"original_operation_id": claim["operation_id"], **(extra or {})}
        )
        # Discard the half-applied mutation before touching the audit row.
        self.db.rollback()
        try:
            persisted = self.by_operation(claim["operation_id"]) if claim["operation_id"] else None
            if persisted is None:
                # The claim is genuinely gone; keep the evidence anyway.
                persisted = self.record(
                    **claim,
                    metadata=diagnostics,
                    duration_ms=duration_ms,
                    result="FAILED",
                )
            else:
                persisted.result = "FAILED"
                persisted.metadata_json = {**(persisted.metadata_json or {}), **diagnostics}
                if duration_ms is not None:
                    persisted.duration_ms = duration_ms
                self.db.flush()
            self.db.commit()
            return persisted
        except SQLAlchemyError:
            self.db.rollback()
            logger.error(
                "admin_audit_failure_not_persisted",
                extra={"action": claim["action"], "operation_id": claim["operation_id"]},
                exc_info=True,
            )
            return None

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
        result: str = "OK",
        created_at: datetime | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> AdminAuditLog:
        """One-shot helper for non-idempotent bookkeeping entries.

        ``result`` is a parameter so a failure row and a success row are written
        through exactly the same code path.
        """
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
            result=result,
            duration_ms=duration_ms,
            created_at=created_at or utcnow(),
            result_json=result_json,
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
        result: str | None = None,
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
        if result:
            stmt = stmt.where(AdminAuditLog.result == result.upper())
        rows = self.db.execute(
            stmt.order_by(AdminAuditLog.id.desc()).limit(max(1, min(limit, 50))).offset(max(0, offset))
        ).scalars()
        return list(rows)

    def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(AdminAuditLog)
        for column, value in filters.items():
            if value is None:
                continue
            value = value.upper() if column in {"action", "category", "result"} else value
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
            "result_data": row.result_json or {},
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


__all__ = [
    "RETRYABLE_RESULT",
    "SNAPSHOT_KEYS",
    "AdminAuditService",
    "duration_ms",
    "failure_metadata",
    "snapshot",
]
