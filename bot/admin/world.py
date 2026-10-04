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

from admin import keyboards as kb
from admin.common import (
    data_of,
    get_client,
    guard,
    render,
    render_error,
    require_user,
    toast,
)
from admin.formatters import (
    analytics as fmt_analytics,
)
from admin.formatters import (
    audit as fmt_audit,
)
from admin.formatters import (
    confirm,
    esc,
    num,
    plate_card,
)
from admin.formatters import (
    countries as fmt_countries,
)
from admin.formatters import (
    events as fmt_events,
)
from admin.formatters import (
    plate_list as fmt_plate_list,
)
from admin.formatters import (
    ranks as fmt_ranks,
)
from admin.formatters import (
    system as fmt_system,
)
from admin.formatters import (
    test_roll as fmt_test_roll,
)
from admin.formatters import (
    transactions as fmt_transactions,
)
from admin.states import (
    KEY_CATEGORY,
    KEY_COUNTRY,
    KEY_MODE,
    KEY_PRESET,
    KEY_QUERY,
    KEY_RARITY,
    KEY_REGION,
    KEY_SCREEN,
    KEY_SORT,
    KEY_TRAIT,
    AdminStates,
    selected_user_id,
    set_selected_user,
)

logger = logging.getLogger("bot.admin.world")

router = Router(name="admin-world")

DEFAULT_MODE = "SIMULATION"


# ---------------------------------------------------------------------------
# generic routing helpers
# ---------------------------------------------------------------------------
async def _screen(context: FSMContext, name: str) -> None:
    """Remember which screen is open so ``Refresh`` knows what to re-read."""
    await context.update_data(**{KEY_SCREEN: name})


def _telegram_id(target: Message | CallbackQuery) -> int:
    return int(target.from_user.id)


async def refresh_current_screen(target: CallbackQuery, context: FSMContext) -> None:
    """Re-render whichever screen the admin is looking at."""
    screen = await data_of(context, KEY_SCREEN, kb.HOME)
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
        from admin.router import open_panel

        await open_panel(target.message)
        return
    await handler(target, context)


async def _refresh_user_section(target: CallbackQuery, context: FSMContext) -> None:
    from admin.router import _render_user

    await _render_user(target, context)


# ---------------------------------------------------------------------------
# test lab
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.TESTLAB))
@guard
async def lab_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.TESTLAB)
    mode = await data_of(context, KEY_MODE, DEFAULT_MODE)
    user_id = await selected_user_id(context)
    await render(
        callback.message,
        await _lab_header(mode, user_id, context),
        kb.lab_keyboard(mode=str(mode), has_user=user_id is not None),
    )


async def _lab_header(mode: str, user_id: int | None, context: FSMContext) -> str:
    country = await data_of(context, KEY_COUNTRY)
    rarity = await data_of(context, KEY_RARITY)
    preset = await data_of(context, KEY_PRESET)
    trait = await data_of(context, KEY_TRAIT)
    category = await data_of(context, KEY_CATEGORY)
    region = await data_of(context, KEY_REGION)
    rows = [
        "🧪 <b>TEST LAB</b>",
        "━━━━━━━━━━",
        f"режим: {'🟡 СИМУЛЯЦИЯ' if mode == 'SIMULATION' else '🔴 LIVE ADMIN TEST'}",
        f"игрок: {'<code>' + str(user_id) + '</code>' if user_id else '<i>не выбран</i>'}",
    ]
    if category:
        rows.append(f"категория: {esc(category)}")
    if preset:
        rows.append(f"пресет: {esc(preset)}")
    if country:
        rows.append(f"страна: {esc(country)}")
    if region:
        rows.append(f"регион: {esc(region)}")
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


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_MODE)))
@guard
async def lab_mode(callback: CallbackQuery, context: FSMContext) -> None:
    # The toggle button carries the target mode, so the route is prefix-matched.
    # Matching it exactly made the LIVE/SIM button dead: "a:tm:live" was answered
    # with "Unknown action".
    parts = kb.unpack(callback.data or "")
    mode = "LIVE" if len(parts) > 2 and parts[2] == "live" else "SIMULATION"
    await context.update_data(**{KEY_MODE: mode})
    await toast(callback, "LIVE" if mode == "LIVE" else "SIMULATION")
    await lab_menu(callback, context)


@router.callback_query(F.data == kb.pack(kb.LAB_CATEGORY))
@guard
async def lab_category_menu(callback: CallbackQuery, context: FSMContext) -> None:
    """Category comes from the backend catalogue so a new category needs no bot change."""
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    categories = [(str(item["code"]), str(item.get("label") or item["code"])) for item in (catalog.get("categories") or [])]
    if not categories:
        await toast(callback, "Catalogue is empty.")
        return
    await render(
        callback.message,
        "📂 <b>КАТЕГОРИЯ</b>\n━━━━━━━━━━\n\nКатегория коллекционного номера.",
        kb.lab_category_keyboard(categories, current=await data_of(context, KEY_CATEGORY)),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_CATEGORY)))
@guard
async def lab_category_pick(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    value = parts[2] if len(parts) > 2 else ""
    await context.update_data(
        **{KEY_CATEGORY: None if value == "*" else value.upper(), KEY_PRESET: None}
    )
    await toast(callback, f"Категория: {value}")
    await lab_menu(callback, context)


@router.callback_query(F.data == kb.pack(kb.LAB_TRAIT))
@guard
async def lab_trait_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    traits = [str(value) for value in (catalog.get("traits") or [])]
    if not traits:
        await toast(callback, "No traits in the catalogue.")
        return
    await render(
        callback.message,
        "🧬 <b>TRAIT</b>\n━━━━━━━━━━\n\nБудет сгенерирован номер с этим признаком.",
        kb.lab_trait_keyboard(traits, current=await data_of(context, KEY_TRAIT)),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_TRAIT)))
@guard
async def lab_trait_pick(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    value = parts[2] if len(parts) > 2 else ""
    await context.update_data(**{KEY_TRAIT: None if value == "*" else value.upper(), KEY_PRESET: None})
    await toast(callback, f"Trait: {value}")
    await lab_menu(callback, context)


@router.callback_query(F.data == kb.pack(kb.LAB_REGION))
@guard
async def lab_region_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    regions = [(str(item["code"]), str(item.get("label") or item["code"])) for item in (catalog.get("regions") or [])]
    if not regions:
        await toast(callback, "No regions in the catalogue.")
        return
    await render(
        callback.message,
        "🗺 <b>РЕГИОН</b>\n━━━━━━━━━━\n\nРегион выбранной страны.",
        kb.lab_region_keyboard(regions),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_REGION)))
@guard
async def lab_region_pick(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3:
        await lab_region_menu(callback, context)
        return
    await context.update_data(**{KEY_REGION: parts[2].upper(), "region_code": parts[2].upper(), KEY_PRESET: None})
    await toast(callback, f"Регион: {parts[2].upper()}")
    await lab_menu(callback, context)


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_SEARCH)))
@guard
async def lab_search_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) > 2 and parts[2] == "clear":
        # Tapping the active query chip clears the filter and shows every country.
        await context.update_data(country_query=None)
        await _render_country_picker(callback, context, None)
        return
    await context.set_state(AdminStates.search_user)
    await context.update_data(**{KEY_SCREEN: "lab-country-search"})
    await render(
        callback.message,
        "🔍 <b>ПОИСК СТРАНЫ</b>\n━━━━━━━━━━\n\nВведите код или часть названия: <i>ru, rus,россия</i>",
        kb.prompt_keyboard(),
    )


@router.message(AdminStates.search_user, F.text)
@guard
async def lab_search_input(message: Message, context: FSMContext) -> None:
    if await data_of(context, KEY_SCREEN) != "lab-country-search":
        return
    query = (message.text or "").strip()[:24]
    await context.set_state(None)
    await context.update_data(country_query=query)
    await _render_country_picker(message, context, query)


@router.callback_query(F.data.startswith(kb.pack(kb.LAB_SEARCH_PAGE)))
@guard
async def lab_search_page(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    query = parts[3] if len(parts) > 3 and parts[3] not in ("", "*") else None
    await _render_country_picker(callback, context, query, page)


@router.callback_query(F.data == kb.pack(kb.LAB_COUNTRY))
@guard
async def lab_country_menu(callback: CallbackQuery, context: FSMContext) -> None:
    """Countries are loaded from the backend catalogue, never hardcoded here.

    They are paged and searchable - a hard 40-row cap used to make most of the
    catalogue unreachable from the panel.
    """
    await _render_country_picker(callback, context, await data_of(context, "country_query"))


COUNTRY_PAGE_SIZE = 24


async def _render_country_picker(
    target: CallbackQuery | Message,
    context: FSMContext,
    query: str | None,
    page: int = 1,
) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(target))
    except Exception as exc:
        await render_error(target, exc)
        return
    raw = catalog.get("countries") or []
    category = await data_of(context, KEY_CATEGORY)
    if category:
        raw = [
            item
            for item in raw
            if str((item.get("config") or {}).get("category") or "").upper() == str(category).upper()
        ]
    needle = (query or "").strip().lower()
    if needle:
        raw = [
            item
            for item in raw
            if needle in str(item.get("code", "")).lower()
            or needle in str(item.get("name_en", "")).lower()
            or needle in str(item.get("name_ru", "")).lower()
            or needle in str(item.get("flag", "")).lower()
        ]
    if not raw:
        await render(
            target,
            "🌍 <b>СТРАНА</b>\n━━━━━━━━━━\n\n<i>Ничего не найдено.</i>"
            + (f"\n\nзапрос: {esc(query or '')}" if query else ""),
            kb.country_keyboard((), query=query),
        )
        return
    pages = max(1, -(-len(raw) // COUNTRY_PAGE_SIZE))
    page = max(1, min(page, pages))
    window = raw[(page - 1) * COUNTRY_PAGE_SIZE : page * COUNTRY_PAGE_SIZE]
    codes = [(str(item.get("code")), str(item.get("flag") or "")) for item in window]
    header = "🌍 <b>СТРАНА</b>\n━━━━━━━━━━\n\nВыберите страну для генерации."
    if query:
        header += f"\n\n🔎 {esc(query)} • найдено {len(raw)}"
    await render(target, header, kb.country_keyboard(codes, page=page, pages=pages, query=query))


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
    except Exception as exc:
        await render_error(callback, exc)
        return
    rarities = [str(value) for value in (catalog.get("rarities") or [])]
    await render(
        callback.message,
        "💎 <b>РЕДКОСТЬ</b>\n━━━━━━━━━━\n\nБудет сгенерирован номер этой редкости.\n<i>веса RNG не меняются</i>",
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
    except Exception as exc:
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
    await context.update_data(**{KEY_PRESET: parts[2], KEY_COUNTRY: None, KEY_RARITY: None, KEY_TRAIT: None})
    await toast(callback, f"Пресет: {parts[2]}")
    await lab_menu(callback, context)


async def _lab_request(context: FSMContext) -> dict[str, Any]:
    return {
        "country_code": await data_of(context, KEY_COUNTRY),
        "rarity": await data_of(context, KEY_RARITY),
        "preset": await data_of(context, KEY_PRESET),
        "require_trait": await data_of(context, KEY_TRAIT),
    }


@router.callback_query(F.data == kb.pack(kb.LAB_SIMULATE))
@guard
async def lab_simulate(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.TESTLAB)
    try:
        payload = await get_client().post(
            "/testlab/simulate",
            admin_telegram_id=_telegram_id(callback),
            json=await _lab_request(context),
        )
    except Exception as exc:
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        fmt_test_roll(payload, mode="SIMULATION"),
        kb.lab_keyboard(mode=str(await data_of(context, KEY_MODE, DEFAULT_MODE)), has_user=False),
    )


@router.callback_query(F.data == kb.pack(kb.LAB_LIVE))
@guard
async def lab_live_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    request = await _lab_request(context)
    # Stage the action type; ``players.reason_input`` is the one and only reason
    # dispatcher, so the reason is captured there and turned into the pending
    # operation here.
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_LIVE_ROLL, user_id=user_id)
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
    await context.update_data(plate_text=text[:32])
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_FORCE_PLATE)
    await message.answer("✅ Текст принят. Введите причину.", reply_markup=kb.prompt_keyboard())


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
        "🔍 <b>ПОИСК НОМЕРА</b>\n━━━━━━━━━━\n\n"
        "Введите текст номера (<code>A777AA 77</code>), его номер в каталоге\n"
        "(<code>#1234</code>), страну (<code>RUS</code>) или фильтр\n"
        "(<code>MYTHIC</code>, <code>PHONE</code>).\n"
        "<i>Точный ID больше не поглощает текстовый запрос</i>",
        kb.prompt_keyboard(),
    )


@router.message(AdminStates.search_user, F.text)
@guard
async def plate_search_input(message: Message, context: FSMContext) -> None:
    if await data_of(context, KEY_SCREEN) != "plate-search":
        return
    raw = (message.text or "").strip()[:48]
    await context.set_state(None)
    if not raw:
        await render(message, "🔍 <b>ПОИСК</b>\n\nПустой запрос.", kb.plates_keyboard())
        return
    # A bare "#1234" is an explicit catalogue id; anything else is a text query,
    # so "777" or "RUS" are no longer silently reinterpreted as ids.
    explicit_id = raw.lstrip("#")
    if explicit_id.isdigit() and raw.startswith("#"):
        await context.update_data(plate_id=int(explicit_id))
        await render(message, f"🔍 Открываю номер <code>{esc(explicit_id)}</code>…", kb.plates_keyboard())
        await plate_open_by_id(message, context, int(explicit_id))
        return
    await context.update_data(plate_id=None, **{KEY_QUERY: raw}, **(await _search_filters(context)))
    await render(message, f"🔍 Ищу <code>{esc(raw)}</code>…", None, answer=True)
    await _render_plate_list(message, context, 1)


async def _search_filters(context: FSMContext) -> dict[str, Any]:
    """Whatever the operator had filtered when a new query is typed."""
    return {
        KEY_SORT: await data_of(context, KEY_SORT, "recent"),
        KEY_COUNTRY: await data_of(context, KEY_COUNTRY),
        KEY_CATEGORY: await data_of(context, KEY_CATEGORY),
        KEY_RARITY: await data_of(context, KEY_RARITY),
    }


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_SORT)))
@guard
async def plate_sort(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    sort = parts[2] if len(parts) > 2 else "recent"
    await context.update_data(**{KEY_SORT: sort, KEY_QUERY: None})
    await _render_plate_list(callback, context, 1)


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_COUNTRY_FILTER)))
@guard
async def plate_country_filter(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    value = parts[2] if len(parts) > 2 else "*"
    await context.update_data(**{KEY_COUNTRY: None if value == "*" else value.upper()})
    await _render_plate_list(callback, context, 1)


@router.callback_query(F.data == kb.pack(kb.PLATE_COUNTRY_FILTER))
@guard
async def plate_country_filter_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        data = await get_client().countries(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    codes = [
        (str(item.get("code")), str(item.get("flag") or ""))
        for item in (data.get("items") or [])
        if item.get("code")
    ]
    if not codes:
        await toast(callback, "No countries in the catalogue.")
        return
    await render(
        callback.message,
        "🌍 <b>ФИЛЬТР СТРАНЫ</b>\n━━━━━━━━━━\n\n<i>«Все страны» снимает фильтр.</i>",
        kb.country_filter_keyboard(codes, current=await data_of(context, KEY_COUNTRY)),
    )


@router.callback_query(F.data == kb.pack(kb.PLATE_CATEGORY_FILTER))
@guard
async def plate_category_filter_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    categories = [
        (str(item["code"]), str(item.get("label") or item["code"])) for item in (catalog.get("categories") or [])
    ]
    if not categories:
        await toast(callback, "No categories in the catalogue.")
        return
    await render(
        callback.message,
        "📂 <b>ФИЛЬТР КАТЕГОРИИ</b>\n━━━━━━━━━━\n\n<i>«Все категории» снимает фильтр.</i>",
        kb.category_filter_keyboard(categories, current=await data_of(context, KEY_CATEGORY)),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_CATEGORY_FILTER)))
@guard
async def plate_category_filter(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    value = parts[2] if len(parts) > 2 else "*"
    await context.update_data(**{KEY_CATEGORY: None if value == "*" else value.upper()})
    await _render_plate_list(callback, context, 1)


@router.callback_query(F.data == kb.pack(kb.PLATE_RARITY_FILTER))
@guard
async def plate_rarity_filter_menu(callback: CallbackQuery, context: FSMContext) -> None:
    try:
        catalog = await get_client().catalog(_telegram_id(callback))
    except Exception as exc:
        await render_error(callback, exc)
        return
    rarities = [str(value) for value in (catalog.get("rarities") or [])]
    if not rarities:
        await toast(callback, "No rarities in the catalogue.")
        return
    await render(
        callback.message,
        "💎 <b>ФИЛЬТР РЕДКОСТИ</b>\n━━━━━━━━━━\n\n<i>«Любая редкость» снимает фильтр.</i>",
        kb.rarity_filter_keyboard(rarities, current=await data_of(context, KEY_RARITY)),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_RARITY_FILTER)))
@guard
async def plate_rarity_filter(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    value = parts[2] if len(parts) > 2 else "*"
    await context.update_data(**{KEY_RARITY: None if value == "*" else value.upper()})
    await _render_plate_list(callback, context, 1)


@router.callback_query(F.data == kb.pack(kb.PLATE_CLEAR))
@guard
async def plate_clear_filters(callback: CallbackQuery, context: FSMContext) -> None:
    await context.update_data(
        **{
            KEY_QUERY: None,
            KEY_COUNTRY: None,
            KEY_CATEGORY: None,
            KEY_RARITY: None,
            KEY_SORT: "recent",
        }
    )
    await toast(callback, "Фильтры сброшены")
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
    params: dict[str, Any] = {"sort": await data_of(context, KEY_SORT, "recent"), "page": page}
    query = await data_of(context, KEY_QUERY)
    if query:
        params["query"] = query
    for key, name in ((KEY_COUNTRY, "country_code"), (KEY_CATEGORY, "category"), (KEY_RARITY, "rarity")):
        value = await data_of(context, key)
        if value:
            params[name] = value
    try:
        data = await get_client().plates(_telegram_id(target), **params)
    except Exception as exc:
        await render_error(target, exc)
        return
    active = [
        f"{label}: <code>{esc(str(await data_of(context, key)))}</code>"
        for key, label in (
            (KEY_COUNTRY, "🌍"),
            (KEY_CATEGORY, "📂"),
            (KEY_RARITY, "💎"),
        )
        if await data_of(context, key)
    ]
    await render(
        target,
        fmt_plate_list(data, filters=active),
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
    await plate_open_by_id(callback, context, int(parts[2]))


async def plate_open_by_id(
    target: CallbackQuery | Message,
    context: FSMContext,
    plate_id: int,
) -> None:
    try:
        data = await get_client().plate(_telegram_id(target), plate_id)
    except Exception as exc:
        await render_error(target, exc)
        return
    await render(target, plate_card(data), kb.plate_keyboard(plate_id))


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_GRANT)))
@guard
async def plate_grant_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    plate_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else await data_of(context, "plate_id")
    if not plate_id:
        await toast(callback, "Bad plate id.")
        return
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_PLATE_GRANT, plate_id=int(plate_id), user_id=user_id)
    await render(
        callback.message,
        confirm(
            "🎁 ВЫДАТЬ НОМЕР",
            [
                f"игрок: {await _player_label(callback, context, user_id)}",
                f"номер: <code>{plate_id}</code>",
                "<i>повторная выдача безопасна</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.PLATE_FIRST)))
@guard
async def plate_first_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    plate_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else await data_of(context, "plate_id")
    if not plate_id:
        await toast(callback, "Bad plate id.")
        return
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(
        kind=kb.ACT_FIRST_DISCOVERY, plate_id=int(plate_id), user_id=user_id, override_first=False
    )
    await render(
        callback.message,
        confirm(
            "🥇 ПЕРВАЯ НАХОДКА",
            [
                f"игрок: {await _player_label(callback, context, user_id)}",
                f"номер: <code>{plate_id}</code>",
                "<i>перенос первой находки возможен только с override</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


async def _player_label(target: CallbackQuery | Message, context: FSMContext, user_id: int) -> str:
    from admin.players import _user_label

    return await _user_label(target, context, user_id)


# ---------------------------------------------------------------------------
# ranks
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.RANKS))
@guard
async def ranks_menu(callback: CallbackQuery, context: FSMContext) -> None:
    await _screen(context, kb.RANKS)
    category = await data_of(context, "rank_category", "COLLECTION")
    period = await data_of(context, "rank_period", "daily")
    try:
        data = await get_client().ranks(_telegram_id(callback), category, period)
    except Exception as exc:
        await render_error(callback, exc)
        return
    entries = [
        (int(entry["user_id"]), (entry.get("username") and f"@{entry['username']}") or entry.get("display_name") or "")
        for entry in (data.get("entries") or [])
    ]
    # Every row is a button that opens the real player card; the card's Back button
    # returns here, so #1 → card → #2 → card is a one-tap loop.
    keyboard = kb.ranks_keyboard(
        data.get("categories") or ["COLLECTION"],
        data.get("periods") or ["daily"],
        entries,
    )
    await render(callback.message, _ranks_with_open(data, entries), keyboard)


def _ranks_with_open(data: dict[str, Any], entries: list[tuple[int, str]]) -> str:
    base = fmt_ranks(data)
    if entries:
        base += "\n\n<i>Нажмите на игрока, чтобы открыть его карточку.</i>"
    return base


@router.callback_query(F.data.startswith(kb.pack(kb.RANK_OPEN)))
@guard
async def rank_open_player(callback: CallbackQuery, context: FSMContext) -> None:
    """Open a ranked player's card, remembering the ranking as the way back."""
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3 or not parts[2].isdigit():
        await toast(callback, "Bad request.")
        return
    user_id = int(parts[2])
    await context.update_data(rank_category=await data_of(context, "rank_category", "COLLECTION"))
    await context.update_data(rank_period=await data_of(context, "rank_period", "daily"))
    await set_selected_user(context, user_id)
    from admin.router import _render_user

    await _render_user(callback, context, user_id)


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
    except Exception as exc:
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
    except Exception as exc:
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
    except Exception as exc:
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
    except Exception as exc:
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
    except Exception as exc:
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
    scope = await data_of(context, "audit_scope", "all")
    if scope == "mine":
        # The *current actor* - never "the first configured admin id". With more
        # than one operator that used to show admin #1's log to everyone.
        params["admin_telegram_id"] = _telegram_id(target)
    user_id = await selected_user_id(context)
    if scope == "user" and user_id is not None:
        params["target_user_id"] = user_id
    try:
        data = await get_client().audit(_telegram_id(target), **params)
    except Exception as exc:
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
    except Exception as exc:
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
    except Exception as exc:
        await render_error(callback, exc)
        return
    await render(
        callback.message,
        fmt_transactions(data),
        kb.ledger_keyboard(offset=offset, has_more=bool(data.get("has_more"))),
    )


__all__ = ["refresh_current_screen", "router"]
