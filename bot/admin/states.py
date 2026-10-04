"""FSM states and per-admin context keys for the admin panel.

aiogram keys its storage by ``(bot_id, chat_id, user_id)``, so two admins working
in the same chat keep independent panels: separate selected player, separate
search text, separate pending operations. Nothing here is shared.
"""

from __future__ import annotations

from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Short text-input steps of the panel."""

    search_user = State()
    coin_amount = State()
    coin_reason = State()
    balance_target = State()
    roll_count = State()
    xp_amount = State()
    xp_exact = State()
    streak_value = State()
    level_value = State()
    premium_days = State()
    plate_text = State()
    mission_progress = State()
    cosmetic_code = State()
    achievement_code = State()
    reason = State()


# Keys inside ``context.data`` (never inside ``callback_data``).
KEY_SELECTED_USER = "user_id"
KEY_PENDING = "pending"
KEY_SCREEN = "screen"
KEY_REASON = "reason"
KEY_AMOUNT = "amount"
KEY_KIND = "kind"
KEY_MODE = "mode"
KEY_COUNTRY = "country"
KEY_CATEGORY = "category"
KEY_REGION = "region"
KEY_RARITY = "rarity"
KEY_PRESET = "preset"
KEY_TRAIT = "trait"
KEY_QUERY = "query"
KEY_PAGE = "page"
KEY_SORT = "sort"

#: How long a staged operation and its FSM flow stay valid. A pending mutation is
#: short-lived on purpose: an operator who walks away must not be able to confirm a
#: grant half an hour later against a balance that has moved on.
FLOW_TTL_SECONDS = 900


async def get_data(context: FSMContext) -> dict[str, Any]:
    """Snapshot of the admin's flow data.

    aiogram exposes FSM data only through ``get_data()``; this wrapper keeps the
    call sites short and returns a mutable copy.
    """
    return dict(await context.get_data() or {})


async def pop_data(context: FSMContext, key: str) -> None:
    """Delete one key from the flow data."""
    data = await get_data(context)
    if key in data:
        data.pop(key, None)
        await context.set_data(data)


async def selected_user_id(context: FSMContext) -> int | None:
    value = (await get_data(context)).get(KEY_SELECTED_USER)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def set_selected_user(context: FSMContext, user_id: int | None) -> None:
    if user_id is None:
        await pop_data(context, KEY_SELECTED_USER)
    else:
        await context.update_data(**{KEY_SELECTED_USER: user_id})


async def clear_flow_data(context: FSMContext, *, keep_user: bool = True) -> None:
    """Drop obsolete state after a selection, optionally keeping the target."""
    keep = {KEY_SELECTED_USER} if keep_user else set()
    data = await get_data(context)
    for key in list(data.keys()):
        if key not in keep and key != KEY_PENDING:
            data.pop(key, None)
    await context.set_data(data)


__all__ = [
    "FLOW_TTL_SECONDS",
    "KEY_AMOUNT",
    "KEY_CATEGORY",
    "KEY_COUNTRY",
    "KEY_KIND",
    "KEY_MODE",
    "KEY_PAGE",
    "KEY_PENDING",
    "KEY_PRESET",
    "KEY_QUERY",
    "KEY_RARITY",
    "KEY_REASON",
    "KEY_REGION",
    "KEY_SCREEN",
    "KEY_SELECTED_USER",
    "KEY_SORT",
    "KEY_TRAIT",
    "AdminStates",
    "clear_flow_data",
    "get_data",
    "pop_data",
    "selected_user_id",
    "set_selected_user",
]
