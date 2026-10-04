"""Inline keyboards and compact ``callback_data`` for the admin panel.

Telegram allows 64 bytes of ``callback_data`` per button, so every payload here
uses short codes (``a:<route>[:<arg>]``). Two rules are enforced throughout:

* **no mutation data ever travels in a callback** - only a route code, an opaque
  argument (an id, a page number, a mode) or a pending operation id;
* every submenu has a ``Back`` button, and ``Home``/``Refresh`` are available from
  every major section.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

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
PLATE_COUNTRY = "pc"

# Confirmation routes.
CONFIRM = "cf"
CANCEL = "cx"

# Ranks / analytics / audit sub-routes.
RANK_CATEGORY = "rc"
RANK_PERIOD = "rp"
ANALYTICS_PERIOD = "ap"
AUDIT_SCOPE = "ls"
AUDIT_PAGE = "lp"

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
ACT_FIRST_DISCOVERY = "first_discovery"
ACT_LIVE_ROLL = "live_roll"
ACT_FORCE_PLATE = "force_plate"
ACT_COUNTRY = "country"
ACT_EVENT = "event"
ACT_SEASON = "season"
ACT_REWARD = "reward"
ACT_EQUIP = "equip"
ACT_UNEQUIP = "unequip"

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
        inline_keyboard=[[
            button(confirm_text, CONFIRM, operation_id, danger=True),
            button("❌ Отмена", CANCEL, operation_id),
        ]]
    )


def cancel_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[button("❌ Отмена", CANCEL, NOOP)]])


def rows(*keyboard_rows: Sequence[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(row) for row in keyboard_rows if row])


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


def search_results_keyboard(
    items: Iterable[tuple[int, str]], *, page: int, has_more: bool
) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [button(label, USER_OPEN, user_id) for user_id, label in items]
    ]
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
        (button("+10 000", COIN_PRESET, 10000), button("+100 000", COIN_PRESET, 100000)),
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
        (button("🎯 Точный XP", XP_PRESET, "exact"), button("🏆 Уровень", XP_PRESET, "level")),
        (
            button("🔥 Стрик", XP_PRESET, "streak"),
            button("♻️ Сбросить прогресс", XP_PRESET, "reset", danger=True),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_OPEN)),
    )


def streak_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (button("1", STREAK_VALUE, 1), button("3", STREAK_VALUE, 3), button("7", STREAK_VALUE, 7)),
        (
            button("14", STREAK_VALUE, 14),
            button("30", STREAK_VALUE, 30),
            button("♻️ Сброс", STREAK_VALUE, "reset", danger=True),
        ),
        (button("⬅️ Назад", USER_PROGRESSION)),
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
        (button("365 дней", PREMIUM_PRESET, 365), button("➕ Своё", PREMIUM_PRESET, "custom")),
        (button("⛔ Отозвать", PREMIUM_PRESET, "revoke", danger=True)),
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
        (button("🎫 Сезон-пасс", REWARD_KIND, "season_pass")),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", USER_OPEN)),
    )


def lab_keyboard(*, mode: str, has_user: bool) -> InlineKeyboardMarkup:
    toggle = button(
        "🔴 Переключить на LIVE" if mode == "SIMULATION" else "🟡 Переключить на SIM",
        LAB_MODE,
        "live" if mode == "SIMULATION" else "sim",
    )
    return rows(
        (button("🎲 Симулировать", LAB_SIMULATE), button("🔴 LIVE тест", LAB_LIVE, danger=True)),
        (
            button("🌍 Страна", LAB_COUNTRY),
            button("💎 Редкость", LAB_RARITY),
        ),
        (
            button("⚡ Пресет", LAB_PRESET),
            button("🔤 Текст номера", LAB_TEXT),
        ),
        (toggle,),
        (
            button("🔄 Обновить", REFRESH),
            button("⬅️ Назад", HOME),
        ),
    )


def country_keyboard(codes: Sequence[tuple[str, str]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for code, flag in codes:
        line.append(button(f"{flag} {code}", LAB_COUNTRY, code, danger=True))
        if len(line) == 4:
            keyboard.append(line)
            line = []
    if line:
        keyboard.append(line)
    keyboard.append([button("⬅️ Назад", TESTLAB)])
    return rows(*keyboard)


def rarity_keyboard(rarities: Sequence[str]) -> InlineKeyboardMarkup:
    line = [button(value.title(), LAB_RARITY, value, danger=True) for value in rarities]
    half = (len(line) + 1) // 2
    return rows(line[:half], line[half:], [button("⬅️ Назад", TESTLAB)])


def preset_keyboard(presets: Sequence[dict[str, Any]]) -> InlineKeyboardMarkup:
    line = [
        button(f"{item.get('emoji', '⚡')} {item.get('label')}", LAB_PRESET, item.get("code"), danger=True)
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
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", HOME)),
    )


def plate_list_keyboard(*, page: int, has_more: bool, sort: str | None = None) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(button("◀️", PLATE_PAGE, page - 1, sort))
    if has_more:
        nav.append(button("▶️", PLATE_PAGE, page + 1, sort))
    return rows(nav, [button("⬅️ Назад", PLATES)])


def plate_keyboard() -> InlineKeyboardMarkup:
    return rows(
        (
            button("🎁 Выдать", PLATE_GRANT),
            button("🥇 Первая находка", PLATE_FIRST, danger=True),
        ),
        (button("🔄 Обновить", REFRESH), button("⬅️ Назад", PLATES)),
    )


def ranks_keyboard(categories: Sequence[str], periods: Sequence[str]) -> InlineKeyboardMarkup:
    cat_line = [button(value[:3].title(), RANK_CATEGORY, value) for value in categories]
    per_line = [button(value, RANK_PERIOD, value) for value in periods]
    half = (len(cat_line) + 1) // 2
    return rows(cat_line[:half], cat_line[half:], per_line, [button("⬅️ Назад", RANKS)])


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


def analytics_keyboard(periods: Sequence[str] = ("today", "7d", "30d", "all")) -> InlineKeyboardMarkup:
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


def achievements_item_keyboard(codes: Sequence[tuple[str, bool]]) -> InlineKeyboardMarkup:
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


def quick_actions_keyboard() -> InlineKeyboardMarkup:
    """The one-tap LiveOps row from requirement 51."""
    return rows(
        (
            button("+100 💰", COIN_PRESET, 100),
            button("+1K 💰", COIN_PRESET, 1000),
        ),
        (
            button("+10K 💰", COIN_PRESET, 10000),
            button("+10 🎰", ROLL_PRESET, 10),
        ),
        (
            button("+500 ✨", XP_PRESET, 500),
            button("PRO 30д ⭐", PREMIUM_PRESET, 30),
        ),
        (button("⬅️ Назад", HOME),),
    )


__all__ = [name for name in dir() if not name.startswith("_")]