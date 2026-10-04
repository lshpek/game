"""Inline keyboards and compact ``callback_data`` for the admin panel.

Telegram allows 64 bytes of ``callback_data`` per button, so every payload here
uses short codes (``a:<route>[:<arg>]``). Two rules are enforced throughout:

* **no mutation data ever travels in a callback** - only a route code, an opaque
  argument (an id, a page number, a mode) or a pending operation id;
* every submenu has a ``Back`` button, and ``Home``/``Refresh`` are available from
  every major section.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PREFIX = "a"
CB_LEN = 64

# Section routes.
HOME = "h"
USERS = "u"
ECONOMY = "e"
TESTLAB = "t"
PLATES = "p"
RANKS = "r"
REWARDS = "rw"
COSMETICS = "c"
COUNTRIES = "n"
EVENTS = "v"
ANALYTICS = "a"
AUDIT = "l"
SYSTEM = "s"
LEDGER = "g"

BACK = "b"
REFRESH = "f"
NOOP = "-"

# User sub-routes.
USER_SEARCH = "us"
USER_RECENT = "ur"
USER_OPEN = "uo"
USER_PAGE = "up"
USER_ECONOMY = "ue"
USER_PROGRESSION = "upg"
USER_MISSIONS = "um"
USER_ACHIEVEMENTS = "ua"
USER_PREMIUM = "uv"
USER_COSMETICS = "uc"
USER_REWARDS = "urw"
USER_ROLLS = "url"
USER_BAN = "ub"
USER_SNAPSHOT = "usn"
USER_PLATES = "upl"
USER_PROFILE = "upi"

# Economy sub-routes.
COIN_PRESET = "cp"
COIN_CUSTOM = "cc"
COIN_SUBTRACT = "csb"
COIN_BALANCE = "cb"
COIN_REASON = "cr"
ROLL_PRESET = "rlp"
ROLL_CUSTOM = "rlc"

# Test lab sub-routes.
LAB_SIMULATE = "ts"
LAB_LIVE = "tl"
LAB_COUNTRY = "tc"
LAB_RARITY = "tr"
LAB_PRESET = "tp"
LAB_TEXT = "tt"
LAB_MODE = "tm"

# Plate sub-routes.
PLATE_SEARCH = "ps"
PLATE_SORT = "po"
PLATE_OPEN = "pp"
PLATE_PAGE = "pq"
PLATE_GRANT = "pg"
PLATE_FIRST = "pf"

# Confirmation routes.
CONFIRM = "cf"
CANCEL = "cx"

# Ranks / analytics / audit sub-routes.
RANK_CATEGORY = "rc"
RANK_PERIOD = "rp"
RANK_OPEN = "rx"
ANALYTICS_PERIOD = "ap"
AUDIT_SCOPE = "ls"
AUDIT_PAGE = "lp"

# Number-browser filters and paging. The ``f*`` family is used because ``pg``/``pf``
# are already prefix-matched by the plate grant routes.
PLATE_COUNTRY_FILTER = "fco"
PLATE_CATEGORY_FILTER = "fca"
PLATE_RARITY_FILTER = "fra"
PLATE_CLEAR = "fcl"
USER_PLATES_PAGE = "upl2"

# Test-lab additions. The ``lab*`` family is new so nothing collides with the
# existing ``tc``/``tr``/``tp``/``ts``/``tl``/``tt``/``tm`` prefix routes.
LAB_CATEGORY = "lab1"
LAB_REGION = "lab2"
LAB_SEARCH = "lab3"
LAB_SEARCH_PAGE = "lab4"
LAB_TRAIT = "lab5"

# World sub-routes.
COUNTRY_TOGGLE = "nt"
EVENT_TOGGLE = "vt"

# Mutation intent for the confirm dispatcher.
ACT_COINS = "coins"
ACT_BALANCE = "balance"
ACT_ROLLS = "rolls"
ACT_ROLLS_RESET = "rolls_reset"
ACT_XP = "xp"
ACT_LEVEL = "level"
ACT_STREAK = "streak"
ACT_PROG_RESET = "prog_reset"
ACT_MISSION = "mission"
ACT_ACHIEVEMENT = "achievement"
ACT_COSMETIC = "cosmetic"
ACT_TITLE = "title"
ACT_PREMIUM = "premium"
ACT_PREMIUM_REVOKE = "premium_revoke"
ACT_BAN = "ban"
ACT_UNBAN = "unban"
ACT_PLATE = "plate"
ACT_PLATE_GRANT = "plate_grant"
ACT_FIRST_DISCOVERY = "first_discovery"
ACT_LIVE_ROLL = "live_roll"
ACT_FORCE_PLATE = "force_plate"
ACT_COUNTRY = "country"
ACT_EVENT = "event"
ACT_SEASON = "season"
ACT_REWARD = "reward"
ACT_EQUIP = "equip"
ACT_UNEQUIP = "unequip"

#: Actions that stage through :func:`bot.admin.players.reason_input` and execute
#: from the same module. Kept next to the route constants so a new staged action
#: has exactly one obvious home.
PANEL_ACTIONS: tuple[str, ...] = (
    ACT_COINS,
    ACT_BALANCE,
    ACT_ROLLS,
    ACT_ROLLS_RESET,
    ACT_XP,
    ACT_LEVEL,
    ACT_STREAK,
    ACT_PROG_RESET,
    ACT_MISSION,
    ACT_ACHIEVEMENT,
    ACT_COSMETIC,
    ACT_TITLE,
    ACT_PREMIUM,
    ACT_PREMIUM_REVOKE,
    ACT_BAN,
    ACT_UNBAN,
    ACT_REWARD,
    ACT_PLATE_GRANT,
    ACT_FIRST_DISCOVERY,
    ACT_LIVE_ROLL,
    ACT_FORCE_PLATE,
    ACT_COUNTRY,
    ACT_EVENT,
    ACT_SEASON,
)

# Inline routes used by the per-entity keyboards below.
XP_PRESET = "x1"
STREAK_VALUE = "x2"
PREMIUM_PRESET = "pv"
COSMETIC_GRANT = "cg"
COSMETIC_EQUIP = "ce"
COSMETIC_UNEQUIP = "cu"
COSMETIC_SEARCH = "cq"
REWARD_KIND = "rw1"
MISSION_PROGRESS = "m1"
MISSION_COMPLETE = "m2"
MISSION_RESET = "m3"
ACHIEVEMENT_GRANT = "ag"


def pack(*parts: Any) -> str:
    """Build a ``callback_data`` string, staying inside Telegram's 64 bytes."""
    data = PREFIX + ":" + ":".join(str(part) for part in parts if part not in (None, ""))
    if len(data.encode("utf-8")) > CB_LEN:
        # Truncate the argument tail; callers keep arguments short by design.
        data = data.encode("utf-8")[:CB_LEN].decode("utf-8", errors="ignore")
    return data


def unpack(data: str) -> list[str]:
    if not data.startswith(f"{PREFIX}:"):
        return []
    return data.split(":")


def button(text: str, *parts: Any, danger: bool = False) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=pack(*parts))


def confirm_keyboard(operation_id: str, *, confirm_text: str = "✅ Confirm") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(confirm_text, CONFIRM, operation_id, danger=True),
                button("❌ Отмена", CANCEL, operation_id),
            ]
        ]
    )


def cancel_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[button("❌ Отмена", CANCEL, NOOP)]])


def rows(*keyboard_rows: Sequence[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    """Build an inline keyboard, dropping empty rows.

    Every argument must be a *sequence* of buttons. A bare button is rejected
    loudly: ``(button(...))`` in Python is just the button, and ``list(button)``
    yields ``(field, value)`` pairs - a markup object full of tuples that only
    fails later, inside aiogram, when the message is actually sent. Three shipped
    keyboards had exactly that typo and rendered an unusable screen.
    """
    normalised: list[list[InlineKeyboardButton]] = []
    for row in keyboard_rows:
        if isinstance(row, InlineKeyboardButton):
            raise TypeError(
                "a keyboard row must be a sequence of buttons; write (button(...),) for a single one"
            )
        built = [item for item in row if item is not None]
        if built:
            normalised.append(built)
    return InlineKeyboardMarkup(inline_keyboard=normalised)


def back_row(*extra: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return [*(extra or []), button("⬅️ Назад", BACK)]


def home_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("👤 Юзеры", USERS),
            button("💰 Экономика", ECONOMY),
        ),
        (
            button("🧪 Test Lab", TESTLAB),
            button("🪪 Номера", PLATES),
        ),
        (
            button("🏆 Топ", RANKS),
            button("🎁 Награды", REWARDS),
        ),
        (
            button("🎨 Косметика", COSMETICS),
            button("🌍 Страны", COUNTRIES),
        ),
        (
            button("🎯 Ивенты", EVENTS),
            button("📊 Аналитика", ANALYTICS),
        ),
        (
            button("🧾 Журнал", AUDIT),
            button("🛠 Система", SYSTEM),
        ),
        (button("🔄 Обновить", REFRESH),),
    )


def prompt_keyboard() -> InlineKeyboardMarkup:
    return rows((button("⬅️ Назад", BACK), button("❌ Отмена", CANCEL, NOOP)))


# ---------------------------------------------------------------------------
# section keyboards
# ---------------------------------------------------------------------------
def users_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("🔍 Найти игрока", USER_SEARCH),
            button("🕘 Недавние", USER_RECENT),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", BACK)),
    )


def search_results_keyboard(items: Iterable[tuple[int, str]], *, page: int, has_more: bool) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [[button(label, USER_OPEN, user_id) for user_id, label in items]]
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(button("◀️", USER_PAGE, page - 1))
    if has_more:
        nav.append(button("▶️", USER_PAGE, page + 1))
    keyboard.append([*nav, button("⬅️ Назад", USERS)])
    return rows(*keyboard)


def user_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("💰 Экономика", USER_ECONOMY),
            button("🎰 Роллы", USER_ROLLS),
        ),
        (
            button("🪪 Номера", USER_PLATES),
            button("🏆 Прогрессия", USER_PROGRESSION),
        ),
        (
            button("🎯 Задания", USER_MISSIONS),
            button("🏅 Достижения", USER_ACHIEVEMENTS),
        ),
        (
            button("🎁 Награды", USER_REWARDS),
            button("🎨 Косметика", USER_COSMETICS),
        ),
        (
            button("⭐ PRO", USER_PREMIUM),
            button("⛔ Бан", USER_BAN),
        ),
        (
            button("📋 Снапшот", USER_SNAPSHOT),
            button("🔄 Обновить", REFRESH),
        ),
        (button("⬅️ Назад", USERS), button("🏠 Главная", HOME)),
    )


def economy_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("+100", COIN_PRESET, 100), button("+1 000", COIN_PRESET, 1000)),
        (
            button("+10 000", COIN_PRESET, 10000),
            button("+100 000", COIN_PRESET, 100000),
        ),
        (
            button("➕ Своя сумма", COIN_CUSTOM),
            button("➖ Вычесть", COIN_SUBTRACT),
        ),
        (
            button("🎯 Точный баланс", COIN_BALANCE),
            button("📒 Леджер", LEDGER),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)),
    )


def rolls_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("+1", ROLL_PRESET, 1), button("+5", ROLL_PRESET, 5)),
        (button("+10", ROLL_PRESET, 10), button("+50", ROLL_PRESET, 50)),
        (button("+100", ROLL_PRESET, 100), button("➕ Своё", ROLL_CUSTOM)),
        (
            button("♻️ Сбросить сегодня", COIN_PRESET, "reset", danger=True),
            button("🔄 Обновить", REFRESH),
        ),
        (button("⬅️ Назад", USER_OPEN), button("🏠 Главная", HOME)),
    )


def progression_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("✨ +100", XP_PRESET, 100), button("✨ +500", XP_PRESET, 500)),
        (button("✨ +1 000", XP_PRESET, 1000), button("✨ Своё", XP_PRESET, "custom")),
        (
            button("🎯 Точный XP", XP_PRESET, "exact"),
            button("🏆 Уровень", XP_PRESET, "level"),
        ),
        (
            button("🔥 Стрик", XP_PRESET, "streak"),
            button("♻️ Сбросить прогресс", XP_PRESET, "reset", danger=True),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_OPEN)),
    )


def streak_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("1", STREAK_VALUE, 1),
            button("3", STREAK_VALUE, 3),
            button("7", STREAK_VALUE, 7),
        ),
        (
            button("14", STREAK_VALUE, 14),
            button("30", STREAK_VALUE, 30),
            button("♻️ Сброс", STREAK_VALUE, "reset", danger=True),
        ),
        (button("⬅️ Назад", USER_PROGRESSION),),
    )


def missions_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("🎯 Задания", USER_MISSIONS), button("🔄 Обновить", REFRESH)),
        (button("⬅️ Назад", USER_OPEN), button("🏠 Главная", HOME)),
    )


def achievements_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("🏅 Достижения", USER_ACHIEVEMENTS), button("🔄 Обновить", REFRESH)),
        (button("⬅️ Назад", USER_OPEN), button("🏠 Главная", HOME)),
    )


def premium_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("1 день", PREMIUM_PRESET, 1), button("7 дней", PREMIUM_PRESET, 7)),
        (button("30 дней", PREMIUM_PRESET, 30), button("90 дней", PREMIUM_PRESET, 90)),
        (
            button("365 дней", PREMIUM_PRESET, 365),
            button("➕ Своё", PREMIUM_PRESET, "custom"),
        ),
        (button("⛔ Отозвать", PREMIUM_PRESET, "revoke", danger=True),),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_OPEN)),
    )


def cosmetics_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("🎁 Выдать", COSMETIC_GRANT),
            button("👕 Надеть", COSMETIC_EQUIP),
        ),
        (
            button("🥋 Снять", COSMETIC_UNEQUIP),
            button("🔍 Найти", COSMETIC_SEARCH),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_OPEN)),
    )


def rewards_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("💰 NUMORA", REWARD_KIND, "coins"),
            button("🎰 Роллы", REWARD_KIND, "rolls"),
        ),
        (
            button("✨ XP", REWARD_KIND, "xp"),
            button("⭐ PRO 30д", REWARD_KIND, "premium"),
        ),
        (
            button("🎨 Косметика", REWARD_KIND, "cosmetic"),
            button("🏷 Титул", REWARD_KIND, "title"),
        ),
        (button("🎫 Сезон-пасс", REWARD_KIND, "season_pass"),),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_OPEN)),
    )


def lab_keyboard(*, mode: str, has_user: bool) -> InlineKeyboardMarkup:
    toggle = button(
        "🔴 Переключить на LIVE" if mode == "SIMULATION" else "🟡 Переключить на SIM",
        LAB_MODE,
        "live" if mode == "SIMULATION" else "sim",
    )
    return rows(
        (
            button("🎲 Симулировать", LAB_SIMULATE),
            button("🔴 LIVE тест", LAB_LIVE, danger=True),
        ),
        (
            button("🌍 Страна", LAB_COUNTRY),
            button("📂 Категория", LAB_CATEGORY),
        ),
        (
            button("🗺 Регион", LAB_REGION),
            button("💎 Редкость", LAB_RARITY),
        ),
        (
            button("⚡ Пресет", LAB_PRESET),
            button("🧬 Trait", LAB_TRAIT),
        ),
        (
            button("🔍 Найти страну", LAB_SEARCH),
            button("🔤 Номер вручную", LAB_TEXT),
        ),
        (toggle,),
        (
            button("🔄 Обновить", REFRESH),
            button("⬅️ Назад", HOME),
        ),
    )


def lab_category_keyboard(categories: Sequence[tuple[str, str]], *, current: str | None) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [[button("📂 Любая категория", LAB_CATEGORY, "*")]]
    line = [
        button(f"{'✅ ' if current == value else ''}{label}", LAB_CATEGORY, value, danger=True)
        for value, label in categories
    ]
    half = (len(line) + 1) // 2
    keyboard.append(line[:half])
    if line[half:]:
        keyboard.append(line[half:])
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", TESTLAB)])
    return rows(*keyboard)


def lab_trait_keyboard(traits: Sequence[str], *, current: str | None) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [[button("🧬 Любой trait", LAB_TRAIT, "*")]]
    line = [
        button(f"{'✅ ' if current == value else ''}{value}", LAB_TRAIT, value, danger=True) for value in traits[:24]
    ]
    half = (len(line) + 1) // 2
    if line[:half]:
        keyboard.append(line[:half])
    if line[half:]:
        keyboard.append(line[half:])
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", TESTLAB)])
    return rows(*keyboard)


def lab_region_keyboard(regions: Sequence[tuple[str, str]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for code, label in regions:
        line.append(button(f"{label}"[:28], LAB_REGION, code, danger=True))
        if len(line) == 3:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", TESTLAB)])
    return rows(*keyboard)


def user_plates_keyboard(
    user_id: int | None = None,
    *,
    page: int = 1,
    has_more: bool = False,
) -> InlineKeyboardMarkup:
    """A player's own numbers. Back always returns to the player card."""
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(button("◀️", USER_PLATES_PAGE, page - 1))
    if has_more:
        nav.append(button("▶️", USER_PLATES_PAGE, page + 1))
    rows_out: list[Sequence[InlineKeyboardButton]] = []
    if nav:
        rows_out.append(nav)
    if user_id is not None:
        rows_out.append((button("🎁 Выдать ещё", PLATE_GRANT, user_id),))
    rows_out.append(
        [button("🔄 Обновить", REFRESH), button("⬅️ К карточке", USER_OPEN, user_id if user_id else 0)]
    )
    return rows(*rows_out)


def country_keyboard(
    codes: Sequence[tuple[str, str] | tuple[str, str, bool]],
    *,
    page: int = 1,
    pages: int = 1,
    query: str | None = None,
) -> InlineKeyboardMarkup:
    """Country picker for the test lab.

    Countries are paged instead of silently truncated, so the 41st country is
    reachable; ``pages`` drives the pager and ``query`` is echoed back. A third tuple
    element marks a country as locked (coming soon): it stays visible so an operator
    can see the full catalogue, but the lock makes its state unambiguous.
    """
    keyboard: list[list[InlineKeyboardButton]] = []
    if query:
        keyboard.append([button(f"🔎 «{query[:16]}»", LAB_SEARCH, "clear")])
    line: list[InlineKeyboardButton] = []
    for entry in codes:
        code, flag = entry[0], entry[1]
        playable = entry[2] if len(entry) > 2 else True
        label = f"{'🔒 ' if not playable else ''}{flag} {code}"
        line.append(button(label, LAB_COUNTRY, code, danger=bool(playable)))
        if len(line) == 4:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 1:
            nav.append(button("◀️", LAB_SEARCH_PAGE, page - 1, query or ""))
        nav.append(button(f"{page}/{pages}", NOOP))
        if page < pages:
            nav.append(button("▶️", LAB_SEARCH_PAGE, page + 1, query or ""))
        keyboard.append(nav)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", TESTLAB)])
    return rows(*keyboard)


def rarity_keyboard(rarities: Sequence[str]) -> InlineKeyboardMarkup:
    line = [button(value.title(), LAB_RARITY, value, danger=True) for value in rarities]
    half = (len(line) + 1) // 2
    return rows(line[:half], line[half:], [button("⬅️ Назад", TESTLAB)])


def preset_keyboard(presets: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    line = [
        button(
            f"{item.get('emoji', '⚡')} {item.get('label')}",
            LAB_PRESET,
            item.get("code"),
            danger=True,
        )
        for item in presets
    ]
    half = (len(line) + 1) // 2
    return rows(line[:half], line[half:], [button("⬅️ Назад", TESTLAB)])


def plates_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("🔍 Поиск", PLATE_SEARCH),
            button("🆕 Недавние", PLATE_SORT, "recent"),
        ),
        (
            button("💎 Редчайшие", PLATE_SORT, "rarest"),
            button("💰 Макс. цена", PLATE_SORT, "value"),
        ),
        (
            button("👥 Больше находок", PLATE_SORT, "discoveries"),
            button("🕶 Секретные", PLATE_SORT, "secret"),
        ),
        (
            button("🌍 Страна", PLATE_COUNTRY_FILTER),
            button("📂 Категория", PLATE_CATEGORY_FILTER),
        ),
        (
            button("💎 Редкость", PLATE_RARITY_FILTER),
            button("🧹 Сбросить", PLATE_CLEAR, danger=True),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)),
    )


def country_filter_keyboard(codes: Sequence[tuple[str, str]], *, current: str | None) -> InlineKeyboardMarkup:
    """Country filter for the number browser. ``None`` means "no filter"."""
    keyboard: list[list[InlineKeyboardButton]] = [
        [button("🌐 Все страны", PLATE_COUNTRY_FILTER, "*")]
    ]
    line: list[InlineKeyboardButton] = []
    for country_code, flag in codes:
        mark = "✅" if current == country_code else ""
        line.append(button(f"{mark}{flag} {country_code}", PLATE_COUNTRY_FILTER, country_code))
        if len(line) == 4:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", PLATES)])
    return rows(*keyboard)


def category_filter_keyboard(categories: Sequence[tuple[str, str]], *, current: str | None) -> InlineKeyboardMarkup:
    line = [
        button(f"{'✅ ' if current == value else ''}{label}", PLATE_CATEGORY_FILTER, value)
        for value, label in categories
    ]
    half = (len(line) + 1) // 2
    keyboard: list[list[InlineKeyboardButton]] = [[button("📂 Все категории", PLATE_CATEGORY_FILTER, "*")]]
    if line[:half]:
        keyboard.append(line[:half])
    if line[half:]:
        keyboard.append(line[half:])
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", PLATES)])
    return rows(*keyboard)


def rarity_filter_keyboard(rarities: Sequence[str], *, current: str | None) -> InlineKeyboardMarkup:
    line = [
        button(f"{'✅ ' if current == value.upper() else ''}{value.title()}", PLATE_RARITY_FILTER, value.upper())
        for value in rarities
    ]
    half = (len(line) + 1) // 2
    keyboard: list[list[InlineKeyboardButton]] = [[button("💎 Любая редкость", PLATE_RARITY_FILTER, "*")]]
    if line[:half]:
        keyboard.append(line[:half])
    if line[half:]:
        keyboard.append(line[half:])
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", PLATES)])
    return rows(*keyboard)


def plate_list_keyboard(*, page: int, has_more: bool, sort: str | None = None) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(button("◀️", PLATE_PAGE, page - 1, sort))
    if has_more:
        nav.append(button("▶️", PLATE_PAGE, page + 1, sort))
    return rows(nav, [button("⬅️ Назад", PLATES)])


def plate_keyboard(plate_id: int | None = None) -> InlineKeyboardMarkup:
    args = (plate_id,) if plate_id is not None else ()
    return rows(
        (
            button("🎁 Выдать", PLATE_GRANT, *args),
            button("🥇 Первая находка", PLATE_FIRST, *args, danger=True),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", PLATES)),
    )


def ranks_keyboard(
    categories: Sequence[str],
    periods: Sequence[str],
    entries: Sequence[tuple[int, str]] = (),
) -> InlineKeyboardMarkup:
    """Ranking filters plus one button per row entry.

    Each entry opens the real player card, and the card's Back button returns to
    the ranking, so an operator can go #1 → card → #2 → card without hunting.
    """
    cat_line = [button(value[:3].title(), RANK_CATEGORY, value) for value in categories]
    per_line = [button(value, RANK_PERIOD, value) for value in periods]
    half = (len(cat_line) + 1) // 2
    rows_out: list[Sequence[InlineKeyboardButton]] = []
    if cat_line[:half]:
        rows_out.append(cat_line[:half])
    if cat_line[half:]:
        rows_out.append(cat_line[half:])
    rows_out.append(per_line)
    for user_id, label in entries:
        rows_out.append((button(f"{label}"[:28], RANK_OPEN, user_id),))
    rows_out.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)])
    return rows(*rows_out)


def cosmetics_catalogue_keyboard(items: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Catalogue-wide cosmetic list: pick one to stage a grant."""
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for item in items[:24]:
        line.append(button(str(item.get("code"))[:12], COSMETIC_GRANT, item.get("code")))
        if len(line) == 3:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append(
        [
            button("🔍 Найти", COSMETIC_SEARCH),
            button("🔄 Обновить", REFRESH),
            button("⬅️ Назад", HOME),
        ]
    )
    return rows(*keyboard)


def rewards_catalogue_keyboard(items: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Fixed-value rewards; ``grant_<code>`` routes to the quick-grant menu."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for item in items[:16]:
        keyboard.append(
            [
                button(f"{item.get('emoji', '🎁')} {str(item.get('label'))[:22]}", REWARD_KIND, item.get("code")),
            ]
        )
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)])
    return rows(*keyboard)


def countries_keyboard(countries: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for item in countries:
        flag = "🟢" if item.get("is_active") else "⚪"
        line.append(button(f"{flag}{item.get('code')}", COUNTRY_TOGGLE, item.get("id"), danger=True))
        if len(line) == 5:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)])
    return rows(*keyboard)


def events_keyboard(events: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for item in events:
        mark = "🟢" if item.get("is_active") else "⚪"
        line.append(button(f"{mark}{item.get('code')}", EVENT_TOGGLE, item.get("id"), danger=True))
        if len(line) == 4:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)])
    return rows(*keyboard)


def analytics_keyboard(
    periods: Sequence[str] = ("today", "7d", "30d", "all"),
) -> InlineKeyboardMarkup:
    labels = {"today": "Сегодня", "7d": "7 дней", "30d": "30 дней", "all": "Всё"}
    return rows(
        [button(labels.get(value, value), ANALYTICS_PERIOD, value) for value in periods],
        [button("⬅️ Назад", HOME)],
    )


def audit_keyboard(*, page: int, has_more: bool) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(button("◀️", AUDIT_PAGE, page - 1))
    if has_more:
        nav.append(button("▶️", AUDIT_PAGE, page + 1))
    return rows(
        (
            button("🕘 Все", AUDIT_SCOPE, "all"),
            button("👮 Мои", AUDIT_SCOPE, "mine"),
        ),
        nav,
        [button("⬅️ Назад", HOME)],
    )


def system_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("📒 Транзакции", LEDGER),
            button("🧾 Ошибки", SYSTEM, "errors"),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)),
    )


def ledger_keyboard(*, offset: int, has_more: bool) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(button("◀️", LEDGER, max(0, offset - 20)))
    if has_more:
        nav.append(button("▶️", LEDGER, offset + 20))
    return rows(nav, [button("⬅️ Назад", SYSTEM)])


def ban_keyboard(is_banned: bool, is_protected: bool) -> InlineKeyboardMarkup:
    if is_protected:
        return rows(
            (button("🛡 Защищённый админ", NOOP),),
            [button("⬅️ Назад", USER_OPEN)],
        )
    label = "✅ Разбанить" if is_banned else "⛔ Забанить"
    action = ACT_UNBAN if is_banned else ACT_BAN
    return rows(
        (button(label, USER_BAN, action, danger=True),),
        [button("⬅️ Назад", USER_OPEN)],
    )


def missions_item_keyboard(codes: Sequence[str], page: int = 1) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for code in codes:
        keyboard.append(
            [
                button(f"+1 {code[:8]}", MISSION_PROGRESS, code, 1),
                button(f"+5 {code[:8]}", MISSION_PROGRESS, code, 5),
            ]
        )
        keyboard.append(
            [
                button(f"✅ Завершить {code[:8]}", MISSION_COMPLETE, code),
                button(f"♻️ {code[:8]}", MISSION_RESET, code, danger=True),
            ]
        )
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_MISSIONS)])
    return rows(*keyboard)


def achievements_item_keyboard(
    codes: Sequence[tuple[str, bool]],
) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for code, unlocked in codes:
        mark = "✅" if unlocked else "▫️"
        line.append(button(f"{mark} {code}", ACHIEVEMENT_GRANT, code))
        if len(line) == 3:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_ACHIEVEMENTS)])
    return rows(*keyboard)


def cosmetics_item_keyboard(items: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for item in items[:12]:
        line.append(button(str(item.get("code"))[:14], COSMETIC_GRANT, item.get("code")))
        if len(line) == 3:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_COSMETICS)])
    return rows(*keyboard)


def user_result_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("💰 Экономика", USER_ECONOMY),
            button("🪪 Номера", USER_PLATES),
        ),
        (button("🏆 Прогрессия", USER_PROGRESSION), button("🔄 Обновить", REFRESH)),
        (button("⬅️ К списку", USERS), button("🏠 Главная", HOME)),
    )


def prefix_routes() -> dict[str, str]:
    """Route codes matched with ``startswith`` instead of exact equality.

    Any *shorter* route code that shares one of these prefixes would be stolen by
    the broader filter, so the panel's route table is validated against this in
    ``bot/tests/test_admin_routing.py``. ``USER_PAGE`` is deliberately absent: it is
    pinned to ``a:up:<digits>`` by a regular expression precisely because ``up`` is a
    prefix of ``upg``/``upi``/``upl``/``url``.
    """
    return {
        USER_OPEN: f"{PREFIX}:{USER_OPEN}:",
        USER_PLATES_PAGE: f"{PREFIX}:{USER_PLATES_PAGE}:",
        COIN_PRESET: f"{PREFIX}:{COIN_PRESET}:",
        ROLL_PRESET: f"{PREFIX}:{ROLL_PRESET}:",
        LAB_MODE: f"{PREFIX}:{LAB_MODE}:",
        LAB_CATEGORY: f"{PREFIX}:{LAB_CATEGORY}:",
        LAB_REGION: f"{PREFIX}:{LAB_REGION}:",
        LAB_RARITY: f"{PREFIX}:{LAB_RARITY}:",
        LAB_PRESET: f"{PREFIX}:{LAB_PRESET}:",
        LAB_TRAIT: f"{PREFIX}:{LAB_TRAIT}:",
        LAB_SEARCH: f"{PREFIX}:{LAB_SEARCH}:",
        LAB_SEARCH_PAGE: f"{PREFIX}:{LAB_SEARCH_PAGE}:",
        PLATE_SORT: f"{PREFIX}:{PLATE_SORT}:",
        PLATE_PAGE: f"{PREFIX}:{PLATE_PAGE}:",
        PLATE_OPEN: f"{PREFIX}:{PLATE_OPEN}:",
        PLATE_GRANT: f"{PREFIX}:{PLATE_GRANT}:",
        PLATE_FIRST: f"{PREFIX}:{PLATE_FIRST}:",
        PLATE_COUNTRY_FILTER: f"{PREFIX}:{PLATE_COUNTRY_FILTER}:",
        PLATE_CATEGORY_FILTER: f"{PREFIX}:{PLATE_CATEGORY_FILTER}:",
        PLATE_RARITY_FILTER: f"{PREFIX}:{PLATE_RARITY_FILTER}:",
        RANK_CATEGORY: f"{PREFIX}:{RANK_CATEGORY}:",
        RANK_PERIOD: f"{PREFIX}:{RANK_PERIOD}:",
        RANK_OPEN: f"{PREFIX}:{RANK_OPEN}:",
        ANALYTICS_PERIOD: f"{PREFIX}:{ANALYTICS_PERIOD}:",
        AUDIT_SCOPE: f"{PREFIX}:{AUDIT_SCOPE}:",
        AUDIT_PAGE: f"{PREFIX}:{AUDIT_PAGE}:",
        COUNTRY_TOGGLE: f"{PREFIX}:{COUNTRY_TOGGLE}:",
        EVENT_TOGGLE: f"{PREFIX}:{EVENT_TOGGLE}:",
        SYSTEM: f"{PREFIX}:{SYSTEM}",
        LEDGER: f"{PREFIX}:{LEDGER}",
        MISSION_PROGRESS: f"{PREFIX}:{MISSION_PROGRESS}:",
        MISSION_COMPLETE: f"{PREFIX}:{MISSION_COMPLETE}:",
        MISSION_RESET: f"{PREFIX}:{MISSION_RESET}:",
        ACHIEVEMENT_GRANT: f"{PREFIX}:{ACHIEVEMENT_GRANT}:",
        COSMETIC_GRANT: f"{PREFIX}:{COSMETIC_GRANT}:",
        COSMETIC_EQUIP: f"{PREFIX}:{COSMETIC_EQUIP}:",
        COSMETIC_UNEQUIP: f"{PREFIX}:{COSMETIC_UNEQUIP}:",
        REWARD_KIND: f"{PREFIX}:{REWARD_KIND}:",
        XP_PRESET: f"{PREFIX}:{XP_PRESET}:",
        STREAK_VALUE: f"{PREFIX}:{STREAK_VALUE}:",
        PREMIUM_PRESET: f"{PREFIX}:{PREMIUM_PRESET}:",
        USER_BAN: f"{PREFIX}:{USER_BAN}:",
        CONFIRM: f"{PREFIX}:{CONFIRM}:",
        CANCEL: f"{PREFIX}:{CANCEL}",
    }


def exact_routes() -> frozenset[str]:
    """Route codes answered by an equality check only.

    Anything in here must never appear in a button as ``a:<code>:<argument>``: an
    equality filter would not match it and the button would answer "Unknown action".
    The test-lab pickers that do carry a value are deliberately *absent* and
    belong in :func:`prefix_routes` instead.
    """
    return frozenset(
        {
            HOME,
            BACK,
            REFRESH,
            NOOP,
            USERS,
            ECONOMY,
            TESTLAB,
            PLATES,
            RANKS,
            REWARDS,
            COSMETICS,
            COUNTRIES,
            EVENTS,
            ANALYTICS,
            AUDIT,
            USER_SEARCH,
            USER_RECENT,
            USER_SNAPSHOT,
            USER_ECONOMY,
            USER_PROGRESSION,
            USER_MISSIONS,
            USER_ACHIEVEMENTS,
            USER_PREMIUM,
            USER_COSMETICS,
            USER_REWARDS,
            USER_ROLLS,
            USER_PLATES,
            USER_PROFILE,
            COIN_BALANCE,
            COIN_CUSTOM,
            COIN_SUBTRACT,
            ROLL_CUSTOM,
            PLATE_SEARCH,
            COSMETIC_SEARCH,
        }
    )


__all__ = [name for name in dir() if not name.startswith("_")]
