"""Admin panel: entry command, navigation, users and every per-player screen.

Registered behind :func:`bot.admin.common.guard`, so authorisation is enforced
for every single event - command, callback or text message - independently of how
the panel was opened.

Routing order is owned by :mod:`bot.admin.routing`: specific handlers always win
and the reject-everything fallback is attached last, so a valid admin callback can
never degrade into "Unknown action".
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from admin import keyboards as kb
from admin import ops
from admin.common import data_of, guard, render, render_error, require_user, toast
from admin.formatters import (
    esc,
    num,
    user_card,
    user_line,
)
from admin.players import router as players_router
from admin.routing import attach_fallback, handled_routes
from admin.states import (
    AdminStates,
    set_selected_user,
)
from admin.world import router as world_router

logger = logging.getLogger("bot.admin.router")

router = Router(name="admin")

# Actions that need an explicit confirmation before they run.
DANGEROUS_PREFIXES = (
    kb.ACT_COINS,
    kb.ACT_BALANCE,
    kb.ACT_ROLLS_RESET,
    kb.ACT_PROG_RESET,
    kb.ACT_PREMIUM_REVOKE,
    kb.ACT_BAN,
    kb.ACT_FIRST_DISCOVERY,
    kb.ACT_LIVE_ROLL,
    kb.ACT_COUNTRY,
    kb.ACT_EVENT,
    kb.ACT_SEASON,
)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
@router.message(Command("admin", "panel", "a"))
@guard
async def handle_start(message: Message, command: CommandObject) -> None:
    """``/admin`` (also ``/panel`` and ``/a``) opens the control centre.

    Non-admins get the same generic refusal as any other unauthorised command.

    The whole body is wrapped: an unexpected failure here used to be swallowed by
    aiogram's error middleware, which left the operator with a deleted command and
    no reply at all - indistinguishable from an unhandled route. Every exit from
    this handler now produces a message the operator can act on.
    """
    del command
    # Keep the operator's chat as clean as a player's: the command disappears and
    # only the panel message remains.
    from bot import delete_quietly

    await delete_quietly(message)
    try:
        await open_panel(message, answer=True)
    except Exception as exc:  # pragma: no cover - belt and braces
        logger.error("admin panel failed to open", exc_info=True)
        await message.answer(
            "⚠️ <b>Панель не открылась</b>\n\n"
            f"<code>{type(exc).__name__}</code>\n"
            "<i>Подробности в логе бота. Попробуйте ещё раз.</i>"
        )


async def open_panel(
    message: Message | CallbackQuery,
    *,
    answer: bool = False,
    actor_id: int | None = None,
) -> None:
    """Render the home dashboard, editing the current message when possible.

    ``actor_id`` is the operator who pressed the button. It is threaded explicitly
    instead of being read from the message, because the panel message itself has no
    reliable author (and none at all in a channel).
    """
    from admin.common import actor_of, get_client

    actor = actor_id if actor_id is not None else actor_of(message)
    if actor is None:
        logger.error("cannot render the panel: the acting admin is unknown")
        return
    try:
        data = await get_client().dashboard(actor)
    except Exception as exc:
        await render_error(message, exc)
        return
    from admin.formatters import home, recent_actions

    text = home(data)
    actions = recent_actions(data.get("recent_actions") or [])
    if actions:
        text = f"{text}\n\n{actions}"
    await render(message, text, kb.home_keyboard(), answer=answer)


def _telegram_id(target: Message | CallbackQuery) -> int:
    from admin.common import telegram_id

    return telegram_id(target)


# ---------------------------------------------------------------------------
# navigation
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.HOME))
@guard
async def go_home(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(None)
    await ops.clear(context)
    await open_panel(callback, actor_id=_telegram_id(callback))


@router.callback_query(F.data == kb.pack(kb.BACK))
@guard
async def go_back(callback: CallbackQuery, context: FSMContext) -> None:
    """Back is state-driven: it always returns to the screen you came from."""
    await context.set_state(None)
    await ops.clear(context)
    await open_panel(callback, actor_id=_telegram_id(callback))


@router.callback_query(F.data == kb.pack(kb.REFRESH))
@guard
async def refresh(callback: CallbackQuery, context: FSMContext) -> None:
    """Re-read whatever screen is currently open."""
    from admin.world import refresh_current_screen

    await refresh_current_screen(callback, context)


@router.callback_query(F.data == kb.pack(kb.NOOP))
@guard
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USERS))
@guard
async def users_menu(callback: CallbackQuery) -> None:
    await render(
        callback.message,
        "👤 <b>ЮЗЕРЫ</b>\n━━━━━━━━━━\n\nНайдите игрока по Telegram ID, внутреннему ID,\n@username или имени.",
        kb.users_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.USER_RECENT))
@guard
async def users_recent(callback: CallbackQuery) -> None:
    from admin.common import get_client

    try:
        data = await get_client().search_users(_telegram_id(callback), None, 1)
    except Exception as exc:
        await render_error(callback, exc)
        return
    await _render_search(callback, data, title="🕘 <b>ПОСЛЕДНИЕ ИГРОКИ</b>")


@router.callback_query(F.data == kb.pack(kb.USER_SEARCH))
@guard
async def users_search_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.search_user)
    await render(
        callback.message,
        "🔍 <b>ПОИСК ИГРОКА</b>\n━━━━━━━━━━\n\nВведите Telegram ID, внутренний ID,\n"
        "@username или имя.\n\n<i>Пример: 123456789 · @alex · Alex</i>",
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data.regexp(rf"^{kb.PREFIX}:{kb.USER_PAGE}:\d+$"))
@guard
async def users_page(callback: CallbackQuery, context: FSMContext) -> None:
    """Paginate the user search results.

    The route code is pinned to a numeric page on purpose: ``up`` is a prefix of
    ``upg`` / ``upi`` / ``upl`` / ``url`` (progression, profile, numbers, rolls), so
    a plain ``startswith`` filter would steal every one of those sub-routes.
    """
    from admin.common import get_client

    parts = kb.unpack(callback.data or "")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    query = await data_of(context, "query")
    try:
        data = await get_client().search_users(_telegram_id(callback), query, page)
    except Exception as exc:
        await render_error(callback, exc)
        return
    await _render_search(callback, data)


@router.message(AdminStates.search_user)
@guard
async def users_search_input(message: Message, context: FSMContext) -> None:
    from admin.common import get_client

    query = (message.text or "").strip()
    await context.set_state(None)
    if not query or query.startswith("/"):
        await render(message, "🔍 <b>ПОИСК</b>\n\nПустой запрос.", kb.users_keyboard(), answer=True)
        return
    await context.update_data(query=query)
    try:
        data = await get_client().search_users(_telegram_id(message), query, 1)
    except Exception as exc:
        await render_error(message, exc)
        return
    await _render_search(message, data, answer=True)


async def _render_search(
    target: CallbackQuery | Message,
    data: dict[str, Any],
    *,
    title: str = "🔍 <b>РЕЗУЛЬТАТЫ</b>",
    answer: bool = False,
) -> None:
    items = data.get("items") or []
    if not items:
        await render(
            target,
            f"{title}\n━━━━━━━━━━\n\n<i>Никого не найдено.</i>",
            kb.users_keyboard(),
            answer=answer,
        )
        return
    rows = []
    for item in items:
        label = user_line(item)
        coins = num(item.get("coins"))
        mark = "⛔" if item.get("is_banned") else ""
        rows.append((int(item["id"]), f"{label} · {coins}💰 {mark}"))
    body = [title, "━━━━━━━━━━", ""]
    for user_id, label in rows:
        body.append(f"• {esc(label)}  <code>{user_id}</code>")
    body.append(f"\n<i>стр. {data.get('page', 1)} • всего {num(data.get('total'))}</i>")
    await render(
        target,
        "\n".join(body),
        kb.search_results_keyboard(rows, page=int(data.get("page", 1)), has_more=bool(data.get("has_more"))),
        answer=answer,
    )


@router.callback_query(F.data.startswith(kb.pack(kb.USER_OPEN)))
@guard
async def user_open(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3 or not parts[2].isdigit():
        await toast(callback, "Bad request.")
        return
    await set_selected_user(context, int(parts[2]))
    await _render_user(callback, context, int(parts[2]), actor_id=_telegram_id(callback))


@router.callback_query(F.data == kb.pack(kb.USER_PLATES))
@guard
async def user_plates(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    from admin.common import get_client

    try:
        data = await get_client().plates(_telegram_id(callback), user_id=user_id, sort="recent", page=1)
    except Exception as exc:
        await render_error(callback, exc)
        return
    from admin.formatters import plate_list

    await render(callback.message, plate_list(data), kb.user_plates_keyboard())


@router.callback_query(F.data == kb.pack(kb.USER_SNAPSHOT))
@guard
async def user_snapshot(callback: CallbackQuery, context: FSMContext) -> None:
    await _render_user(callback, context)


# ---------------------------------------------------------------------------
# panel-wide sections that are not tied to one player
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.COSMETICS))
@guard
async def cosmetics_menu(callback: CallbackQuery, context: FSMContext) -> None:
    """Global cosmetic catalogue: the section behind the home screen button."""
    from admin.common import get_client

    await context.update_data(cosmetics_query=None)
    try:
        data = await get_client().cosmetics(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    from admin.formatters import cosmetics as fmt_cosmetics

    items = data.get("items") or []
    await render(
        callback.message,
        fmt_cosmetics(data, []),
        kb.cosmetics_catalogue_keyboard(items) if items else kb.cosmetics_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.COSMETIC_SEARCH))
@guard
async def cosmetics_catalogue_search(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.cosmetic_code)
    await render(
        callback.message,
        "🔍 <b>КОСМЕТИКА</b>\n━━━━━━━━━━\n\nВведите код косметики или её название.",
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.REWARDS))
@guard
async def rewards_catalogue(callback: CallbackQuery, context: FSMContext) -> None:
    """Fixed-value reward catalogue: what an operator can hand out at all."""
    from admin.common import get_client

    try:
        data = await get_client().get("/rewards/catalog", admin_telegram_id=_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    from admin.formatters import rewards as fmt_rewards

    await render(
        callback.message,
        fmt_rewards(data),
        kb.rewards_catalogue_keyboard(data.get("items") or []),
    )


# ---------------------------------------------------------------------------
# user card
# ---------------------------------------------------------------------------
async def _render_user(
    target: CallbackQuery | Message,
    context: FSMContext,
    user_id: int | None = None,
    *,
    actor_id: int | None = None,
) -> None:
    from admin.common import actor_of, get_client

    user_id = user_id or await require_user(context, target)
    if user_id is None:
        return
    actor = actor_id if actor_id is not None else actor_of(target)
    if actor is None:
        logger.error("cannot open a player card: the acting admin is unknown")
        return
    try:
        data = await get_client().user_detail(actor, user_id)
    except Exception as exc:
        await render_error(target, exc)
        return
    await render(target, user_card(data), kb.user_keyboard())


# Sub-routers are attached in a fixed, documented order and the reject-everything
# fallback goes last - see :mod:`bot.admin.routing` for why that is not optional.
router.include_router(world_router)
router.include_router(players_router)
attach_fallback(router)

__all__ = ["handled_routes", "open_panel", "router"]
