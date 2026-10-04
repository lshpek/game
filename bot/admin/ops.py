"""Pending-operation registry behind the confirm buttons.

Every dangerous action becomes an *operation* first: an unpredictable id plus the
payload it will send. The id is the only thing that travels in ``callback_data``
(``a:cf:<id>`` / ``a:cx:<id>``) - never the amount, the reason or the target - so
nothing sensitive is exposed to anyone who can read a callback, and a stale
button cannot be replayed onto a different payload.

Each operation is consumed exactly once: confirming pops it, cancelling pops it,
and an execution failure pops it too. Combined with the backend's unique
``operation_id`` index, a Telegram double-tap can never grant twice.
"""

from __future__ import annotations

import secrets
from typing import Any

from aiogram.fsm.context import FSMContext

from bot.admin.states import KEY_PENDING

# 10 chars of urlsafe base64 is ~60 bits of entropy - plenty to stop accidental
# or replayed callback reuse.
_OP_ID_BYTES = 8
MAX_PENDING = 24


def new_operation_id() -> str:
    return secrets.token_urlsafe(_OP_ID_BYTES)


async def put(context: FSMContext, operation_id: str, payload: dict[str, Any]) -> None:
    """Store a pending operation, dropping the oldest when the buffer is full."""
    data = context.data or {}
    pending = dict(data.get(KEY_PENDING) or {})
    pending[operation_id] = payload
    while len(pending) > MAX_PENDING:
        pending.pop(next(iter(pending)))
    await context.update_data(**{KEY_PENDING: pending})


async def get(context: FSMContext, operation_id: str) -> dict[str, Any] | None:
    pending = (context.data or {}).get(KEY_PENDING) or {}
    payload = pending.get(operation_id)
    return dict(payload) if isinstance(payload, dict) else None


async def pop(context: FSMContext, operation_id: str) -> dict[str, Any] | None:
    """Take a pending operation out of the buffer - it can never run twice."""
    pending = dict((context.data or {}).get(KEY_PENDING) or {})
    payload = pending.pop(operation_id, None)
    await context.update_data(**{KEY_PENDING: pending})
    return dict(payload) if isinstance(payload, dict) else None


async def clear(context: FSMContext) -> None:
    await context.pop_data(KEY_PENDING, None)


__all__ = ["MAX_PENDING", "get", "new_operation_id", "pop", "put", "clear"]