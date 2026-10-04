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

from bot.admin.states import KEY_PENDING, get_data, pop_data

# 10 chars of urlsafe base64 is ~60 bits of entropy - plenty to stop accidental
# or replayed callback reuse.
_OP_ID_BYTES = 8
MAX_PENDING = 24


def new_operation_id() -> str:
    return secrets.token_urlsafe(_OP_ID_BYTES)


async def put(context: FSMContext, operation_id: str, payload: dict[str, Any]) -> None:
    """Store a pending operation, dropping the oldest when the buffer is full."""
    pending = await _pending(context)
    pending[operation_id] = payload
    while len(pending) > MAX_PENDING:
        pending.pop(next(iter(pending)))
    await context.update_data(**{KEY_PENDING: pending})


async def _pending(context: FSMContext) -> dict[str, Any]:
    data = await get_data(context)
    return dict(data.get(KEY_PENDING) or {})


async def get(context: FSMContext, operation_id: str) -> dict[str, Any] | None:
    payload = (await _pending(context)).get(operation_id)
    return dict(payload) if isinstance(payload, dict) else None


async def pop(context: FSMContext, operation_id: str) -> dict[str, Any] | None:
    """Take a pending operation out of the buffer - it can never run twice."""
    pending = await _pending(context)
    payload = pending.pop(operation_id, None)
    await context.update_data(**{KEY_PENDING: pending})
    return dict(payload) if isinstance(payload, dict) else None


async def count(context: FSMContext) -> int:
    """How many operations are still waiting - used by the tests."""
    return len(await _pending(context))


async def clear(context: FSMContext) -> None:
    await pop_data(context, KEY_PENDING)


__all__ = ["MAX_PENDING", "clear", "count", "get", "new_operation_id", "pop", "put"]
