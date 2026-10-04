"""Admin panel: test lab, plate browser, ranks, world config and reporting.

Kept separate from :mod:`bot.admin.router` so both files stay readable. Shares the
same guard, rendering helpers and confirmation flow.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.admin import keyboards as kb
from bot.admin import ops
from bot.admin.common import (
    data_of,
    get_client,
    guard,
    render,
    render_error,
    require_user,
    stage,
    toast,
)
from bot.admin.formatters import (
    analytics as fmt_analytics,
)
from bot.admin.formatters import (
    audit as fmt_audit,
)
from bot.admin.formatters import (
    confirm,
)
from bot.admin.formatters import (
    countries as fmt_countries,
)
from bot.admin.formatters import (
    events as fmt_events,
)
from bot.admin.formatters import (
    plate_card,
)
from bot.admin.formatters import (
    plate_list as fmt_plate_list,
)
from bot.admin.formatters import (
    ranks as fmt_ranks,
)
from bot.admin.formatters import (
    result_ok,
)
from bot.admin.formatters import (
    system as fmt_system,
)
from bot.admin.formatters import (
    test_roll as fmt_test_roll,
)
from bot.admin.formatters import (
    transactions as fmt_transactions,
)
from bot.admin.formatters import esc, num
from bot.admin.states import (
    KEY_COUNTRY,
    KEY_MODE,
    KEY_PAGE,
    KEY_PRESET,
    KEY_QUERY,
    KEY_RARITY,
    KEY_SCREEN,
    KEY_SORT,
    KEY_TRAIT,
    AdminStates,
    clear_flow_data,
    selected_user_id,
)

logger = logging.getLogger("bot.admin.world")

router = Router(name="admin-world")

DEFAULT_MODE = "SIMULATION"


# ---------------------------------------------------------------------------
# generic routing helpers
# ---------------------------------------------------------------------------
def _screen(context: FSMContext, name: str) -> None:
    await context.update_data(**{KEY_SCREEN: name})


def _telegram_id(target: Message | CallbackQuery) -> int:
    return int(target.from_user.id)


async def refresh_current_screen(target: CallbackQuery, context: FSMContext) -> None:
    """Re-render whichever screen the admin is looking at."""
    screen = data_of(context, KEY_SCREEN, kb.HOME)
    handlers = {
        kb.TESTLAB: lab_menu,
        kb.PLATES: plates_menu,
        kb.RANKS: ranks_menu,
        kb.COUNTRIES: countries_menu,
        kb.EVENTS: events_menu,
        kb.ANALYTICS: analytics_menu,
        kb.AUDIT: audit_menu,
        kb.SYSTEM: system_menu,
        kb.LEDGER: ledger_menu,
        kb.ECONOMY: _refresh_user_section,
    }
    handler = handlers.get(str(screen))
    if handler is None:
        from bot.admin.router import open_panel

        await open_panel(target.message)
        return
    await handler(target, context)


async def _refresh_user_section(target: CallbackQuery, context: FSMContext) -> None:
    from bot.admin.router import _render_user

    await _render_user(target, context)


# ---------------------------------------------------------------------------
# test lab
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.TESTLAB))
@guard
async def lab_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.TESTLAB)
    mode = data_of(context, KEY_MODE, DEFAULT_MODE)
    user_id = await selected_user_id(context)
    await render(
        callback.message,
        _lab_header(mode, user_id, context),
        kb.lab_keyboard(mode=str(mode), has_user=user_id is not None),
    )


def _lab_header(mode: str, user_id: int | None, context: FSMContext) -> str:
    country = data_of(context, KEY_COUNTRY)
    rarity = data_of(context, KEY_RARITY)
    preset = data_of(context, KEY_PRESET)
    trait = data_of(context, KEY_TRAIT)
    rows = [
        "🧪 <b>TEST LAB</b>",
        "━━━━━━━━━━",
        f"режим: {'🟡 СИМУЛЯЦИЯ' if mode == 'SIMULATION' else '🔴 LIVE ADMIN TEST'}",
        f"игрок: {'<code>' + str(user_id) + '</code>' if user_id else '<i>не выбран</i>'}",
    ]
    if preset:
        rows.append(f"пресет: {esc(preset)}")
    if country:
        rows.append(f"страна: {esc(country)}")
    if rarity:
        rows.append(f"редкость: {esc(rarity)}")
    if trait:
        rows.append(f"trait: {esc(trait)}")
    rows.extend(
        [
            "",
            "<i>Симуляция ничего не меняет.\nLIVE — создаёт и выдаёт номер игроку.</i>",
        ]
    )
    return "\n".join(rows)


@router.callback_query(F.data == kb.pack(kb.LAB_MODE))
@guard
async def lab_mode(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    mode = "LIVE" if len(parts) > 2 and parts[2] == "live" else "SIMULATION"
    await context.update_data(**{KEY_MODE: mode})
    await toast(callback, "LIVE" if mode == "LIVE" else "SIMULATION")
    await lab_menu(callback, context)


@router.callback_query(F.data == kb.pack(kb.LAB_COUNTRY))
@guard
async def lab_country_menu(callback: CallbackQuery, context: FSMContext) -> None:
    """Countries are loaded from the backend catalogue, never hardcoded here."""
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    countries = catalog.get("countries") or []
    if not countries:
        await toast(callback, "Catalogue is empty.")
        return
    codes = [(str(item.get("code")), str(item.get("flag") or "")) for item in countries[:40]]
    await render(
        callback.message,
        "🌍 <b>СТРАНА</b>\n━━━━━━━━━━\n\nВыберите страну для генерации.",
        kb.country_keyboard(codes),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_COUNTRY)))
@guard
async def lab_country_pick(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3:
        await lab_country_menu(callback, context)
        return
    await context.update_data(**{KEY_COUNTRY: parts[2].upper(), KEY_PRESET: None})
    await toast(callback, f"Страна: {parts[2].upper()}")
    await lab_menu(callback, context)


@router.callback_query(F.data == kb.pack(kb.LAB_RARITY))
@guard
async def lab_rarity_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    rarities = [str(value) for value in (catalog.get("rarities") or [])]
    await render(
        callback.message,
        "💎 <b>РЕДКОСТЬ</b>\n━━━━━━━━━━\n\nБудет сгенерирован номер этой редкости.\n"
        "<i>веса RNG не меняются</i>",
        kb.rarity_keyboard(rarities),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_RARITY)))
@guard
async def lab_rarity_pick(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3:
        await lab_rarity_menu(callback, context)
        return
    await context.update_data(**{KEY_RARITY: parts[2].upper(), KEY_PRESET: None})
    await toast(callback, f"Редкость: {parts[2].upper()}")
    await lab_menu(callback, context)


@router.callback_query(F.data == kb.pack(kb.LAB_PRESET))
@guard
async def lab_preset_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        "⚡ <b>ПРЕСЕТЫ</b>\n━━━━━━━━━━\n\nПовторяемые тестовые сценарии.",
        kb.preset_keyboard(catalog.get("presets") or []),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_PRESET)))
@guard
async def lab_preset_pick(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3:
        await lab_preset_menu(callback, context)
        return
    await context.update_data(
        **{KEY_PRESET: parts[2], KEY_COUNTRY: None, KEY_RARITY: None, KEY_TRAIT: None}
    )
    await toast(callback, f"Пресет: {parts[2]}")
    await lab_menu(callback, context)


def _lab_request(context: FSMContext) -> dict[str, Any]:
    return {
        "country_code": data_of(context, KEY_COUNTRY),
        "rarity": data_of(context, KEY_RARITY),
        "preset": data_of(context, KEY_PRESET),
        "require_trait": data_of(context, KEY_TRAIT),
    }


@router.callback_query(F.data == kb.pack(kb.LAB_SIMULATE))
@guard
async def lab_simulate(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.TESTLAB)
    try:
        payload = await get_client().post(
            "/testlab/simulate",
            admin_telegram_id=_telegram_id(callback),
            json=_lab_request(context),
        )
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        fmt_test_roll(payload, mode="SIMULATION"),
        kb.lab_keyboard(mode=str(data_of(context, KEY_MODE, DEFAULT_MODE)), has_user=False),
    )


@router.callback_query(F.data == kb.pack(kb.LAB_LIVE))
@guard
async def lab_live_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    request = _lab_request(context)
    await context.set_state(AdminStates.reason)
    await context.update_data(**{KEY_MODE: "LIVE"})
    rows = [
        f"игрок: <code>{user_id}</code>",
        f"страна: {esc(request.get('country_code') or 'любая')}",
        f"редкость: {esc(request.get('rarity') or 'любая')}",
        f"пресет: {esc(request.get('preset') or '—')}",
        "",
        "<i>Будет создан и выдан реальный номер.</i>",
        "📝 причина: <i>укажите сейчас</i>",
    ]
    await render(
        callback.message,
        confirm("🔴 LIVE ТЕСТ-РОЛЛ", rows),
        kb.prompt_keyboard(),
    )


@router.message(AdminStates.reason, F.text)
@guard
async def world_reason_capture(message: Message, context: FSMContext) -> None:
    """Catch reason input for the world/test-lab flows.

    The main router consumes ``AdminStates.reason`` first for player mutations;
    this handler only sees messages that reached it, i.e. the LIVE test roll.
    """
    del context
    await message.answer("⚠️ Неизвестное действие.", reply_markup=kb.prompt_keyboard())


@router.callback_query(F.data == kb.pack(kb.LAB_TEXT))
@guard
async def lab_text_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.plate_text)
    await render(
        callback.message,
        "🔤 <b>НОМЕР СВОИМИ РУКАМИ</b>\n━━━━━━━━━━\n\n"
        "Введите номер: <code>A777AA 77</code>, <code>7ABC777</code>, <code>AB12 CDE</code>\n"
        "<i>Юникод и разные страны поддерживаются</i>",
        kb.prompt_keyboard(),
    )


@router.message(AdminStates.plate_text)
@guard
async def lab_text_input(message: Message, context: FSMContext) -> None:
    text = (message.text or "").strip()
    await context.set_state(AdminStates.reason)
    await context.update_data(plate_text=text[:32])
    await message.answer(
        "✅ Текст принят. Введите причину.", reply_markup=kb.prompt_keyboard()
    )


# ---------------------------------------------------------------------------
# plate browser
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.PLATES))
@guard
async def plates_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.PLATES)
    await render(
        callback.message,
        "🪪 <b>НОМЕРА</b>\n━━━━━━━━━━\n\nПоиск, сортировки и выдача номеров игрокам.",
        kb.plates_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.PLATE_SEARCH))
@guard
async def plate_search_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.search_user)
    await context.update_data(**{KEY_SCREEN: "plate-search"})
    await render(
        callback.message,
        "🔍 <b>ПОИСК НОМЕРА</b>\n━━━━━━━━━━\n\nВведите текст номера или его Plate ID.",
        kb.prompt_keyboard(),
    )


@router.message(AdminStates.search_user, F.text)
@guard
async def plate_search_input(message: Message, context: FSMContext) -> None:
    if data_of(context, KEY_SCREEN) != "plate-search":
        return
    query = (message.text or "").strip()[:32]
    await context.set_state(None)
    await render(message, f"🔍 Ищу <code>{esc(query)}</code>…", None, answer=True)
    try:
        data = await get_client().plates(_telegram_id(message), query=query, sort="recent", page=1)
    except Exception as exc:  # noqa: BLE001
        await render_error(message, exc)
        return
    await render(message, fmt_plate_list(data), kb.plate_list_keyboard(
        page=int(data.get("page", 1)), has_more=bool(data.get("has_more"))
    ))


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_SORT)))
@guard
async def plate_sort(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    sort = parts[2] if len(parts) > 2 else "recent"
    await context.update_data(**{KEY_SORT: sort, KEY_QUERY: None})
    await _render_plate_list(callback, context, 1)


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_PAGE)))
@guard
async def plate_page(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    await _render_plate_list(callback, context, page)


async def _render_plate_list(
    target: CallbackQuery | Message,
    context: FSMContext,
    page: int,
) -> None:
    params: dict[str, Any] = {"sort": data_of(context, KEY_SORT, "recent"), "page": page}
    query = data_of(context, KEY_QUERY)
    if query:
        params["query"] = query
    try:
        data = await get_client().plates(_telegram_id(target), **params)
    except Exception as exc:  # noqa: BLE001
        await render_error(target, exc)
        return
    await render(
        target,
        fmt_plate_list(data),
        kb.plate_list_keyboard(page=page, has_more=bool(data.get("has_more")), sort=params["sort"]),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_OPEN)))
@guard
async def plate_open(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3 or not parts[2].isdigit():
        await toast(callback, "Bad plate id.")
        return
    await context.update_data(plate_id=int(parts[2]))
    try:
        data = await get_client().plate(_telegram_id(callback), int(parts[2]))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(callback.message, plate_card(data), kb.plate_keyboard())


# ---------------------------------------------------------------------------
# ranks
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.RANKS))
@guard
async def ranks_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.RANKS)
    category = data_of(context, "rank_category", "COLLECTION")
    period = data_of(context, "rank_period", "daily")
    try:
        data = await get_client().ranks(_telegram_id(callback), category, period)
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    entries = [
        (int(entry["user_id"]), entry.get("username") and f"@{entry['username']}" or entry.get("display_name") or "")
        for entry in (data.get("entries") or [])
    ]
    keyboard = kb.ranks_keyboard(
        data.get("categories") or ["COLLECTION"], data.get("periods") or ["daily"]
    )
    await render(callback.message, _ranks_with_open(data, entries), keyboard)


def _ranks_with_open(data: dict[str, Any], entries: list[tuple[int, str]]) -> str:
    base = fmt_ranks(data)
    base += "\n\n<i>Выберите игрока, чтобы открыть его карточку.</i>"
    del entries
    return base


@router.callback_query(F.data.startswith(kb.pack(kb.RANK_CATEGORY)))
@guard
async def rank_category(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    await context.update_data(rank_category=parts[2] if len(parts) > 2 else "COLLECTION")
    await ranks_menu(callback, context)


@router.callback_query(F.data.startswith(kb.pack(kb.RANK_PERIOD)))
@guard
async def rank_period(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    await context.update_data(rank_period=parts[2] if len(parts) > 2 else "daily")
    await ranks_menu(callback, context)


# ---------------------------------------------------------------------------
# world
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.COUNTRIES))
@guard
async def countries_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.COUNTRIES)
    try:
        data = await get_client().countries(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        fmt_countries(data),
        kb.countries_keyboard(data.get("items") or []),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.COUNTRY_TOGGLE)))
@guard
async def country_toggle(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3 or not parts[2].isdigit():
        await toast(callback, "Bad country.")
        return
    country_id = int(parts[2])
    try:
        data = await get_client().countries(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    current = next((item for item in (data.get("items") or []) if int(item["id"]) == country_id), None)
    if current is None:
        await toast(callback, "Country not found.")
        return
    activate = not bool(current.get("is_active"))
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_COUNTRY, country_id=country_id, activate=activate)
    await render(
        callback.message,
        confirm(
            ("🟢 АКТИВИРОВАТЬ" if activate else "⚪ ДЕАКТИВИРОВАТЬ") + f" {current.get('code')}",
            [
                f"страна: {current.get('flag', '')} {esc(str(current.get('code')))}",
                f"номеров: {num(current.get('plates'))}",
                "<i>страна пропадёт/появится в генерации</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.EVENTS))
@guard
async def events_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.EVENTS)
    try:
        data = await get_client().events(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(callback.message, fmt_events(data), kb.events_keyboard(data.get("items") or []))


@router.callback_query(F.data.startswith(kb.pack(kb.EVENT_TOGGLE)))
@guard
async def event_toggle(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3 or not parts[2].isdigit():
        await toast(callback, "Bad event.")
        return
    event_id = int(parts[2])
    try:
        data = await get_client().events(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    current = next((item for item in (data.get("items") or []) if int(item["id"]) == event_id), None)
    if current is None:
        await toast(callback, "Event not found.")
        return
    activate = not bool(current.get("is_active"))
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_EVENT, event_id=event_id, activate=activate)
    await render(
        callback.message,
        confirm(
            ("🟢 АКТИВИРОВАТЬ" if activate else "⚪ ДЕАКТИВИРОВАТЬ") + f" {current.get('code')}",
            [
                f"ивент: {esc(str(current.get('code')))}",
                f"до: {esc(str(current.get('ends_at')))}",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


# ---------------------------------------------------------------------------
# analytics / audit / system / ledger
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.ANALYTICS))
@guard
async def analytics_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.ANALYTICS)
    await render(
        callback.message,
        "📊 <b>АНАЛИТИКА</b>\n━━━━━━━━━━\n\nВыберите период.",
        kb.analytics_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.ANALYTICS_PERIOD)))
@guard
async def analytics_period(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    period = parts[2] if len(parts) > 2 else "today"
    await _screen(context, kb.ANALYTICS)
    try:
        data = await get_client().analytics(_telegram_id(callback), period)
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        fmt_analytics(data),
        kb.analytics_keyboard(("today", "7d", "30d", "all")),
    )


@router.callback_query(F.data == kb.pack(kb.AUDIT))
@guard
async def audit_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.AUDIT)
    await _render_audit(callback, context, 1)


@router.callback_query(F.data.startswith(kb.pack(kb.AUDIT_SCOPE)))
@guard
async def audit_scope(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    scope = parts[2] if len(parts) > 2 else "all"
    await context.update_data(audit_scope=scope)
    await _render_audit(callback, context, 1)


@router.callback_query(F.data.startswith(kb.pack(kb.AUDIT_PAGE)))
@guard
async def audit_page(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    await _render_audit(callback, context, page)


async def _render_audit(
    target: CallbackQuery | Message,
    context: FSMContext,
    page: int,
) -> None:
    params: dict[str, Any] = {"page": page}
    scope = data_of(context, "audit_scope", "all")
    if scope == "mine":
        from bot.admin.common import config

        if config.admin_ids:
            params["admin_telegram_id"] = min(config.admin_ids)
    user_id = await selected_user_id(context)
    if scope == "user" and user_id is not None:
        params["target_user_id"] = user_id
    try:
        data = await get_client().audit(_telegram_id(target), **params)
    except Exception as exc:  # noqa: BLE001
        await render_error(target, exc)
        return
    await render(
        target,
        fmt_audit(data),
        kb.audit_keyboard(page=page, has_more=bool(data.get("has_more"))),
    )


@router.callback_query(F.data == kb.pack(kb.SYSTEM))
@guard
async def system_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.SYSTEM)
    try:
        data = await get_client().system(_telegram_id(callback))
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    bot_username = os_environ("TELEGRAM_BOT_USERNAME")
    mini_app = os_environ("MINI_APP_SHORT_NAME")
    await render(callback.message, fmt_system(data, bot_username=bot_username, mini_app=mini_app), kb.system_keyboard())


@router.callback_query(F.data.startswith(kb.pack(kb.SYSTEM)))
@guard
async def system_submenu(callback: CallbackQuery, context: FSMContext) -> None:
    await system_menu(callback, context)


def os_environ(name: str) -> str:
    import os

    return (os.getenv(name) or "").lstrip("@")


@router.callback_query(F.data.startswith(kb.pack(kb.LEDGER)))
@guard
async def ledger_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.LEDGER)
    parts = kb.unpack(callback.data or "")
    offset = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    params: dict[str, Any] = {"limit": 20, "offset": offset}
    user_id = await selected_user_id(context)
    if user_id is not None:
        params["user_id"] = user_id
    try:
        data = await get_client().transactions(_telegram_id(callback), **params)
    except Exception as exc:  # noqa: BLE001
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        fmt_transactions(data),
        kb.ledger_keyboard(offset=offset, has_more=bool(data.get("has_more"))),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.HOME))
@guard
async def world_home(callback: CallbackQuery) -> None:
    """Home is handled by the main router; swallow duplicates here."""
    del callback


__all__ = ["refresh_current_screen", "router"]
