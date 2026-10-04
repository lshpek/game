"""Screen text for the admin panel.

Russian, compact, and built for reading on a phone: short sections, one value per
line, ids in ``code`` spans so they can be copied straight out of Telegram.

Pure functions only - no I/O, no business rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

HR = "━━━━━━━━━━━━━━━━━━"
SMALL = "──────────"

EMOJI = {
    "home": "🎛",
    "users": "👤",
    "economy": "💰",
    "testlab": "🧪",
    "plates": "🪪",
    "ranks": "🏆",
    "rewards": "🎁",
    "cosmetics": "🎨",
    "countries": "🌍",
    "events": "🎯",
    "analytics": "📊",
    "audit": "🧾",
    "system": "🛠",
    "rolls": "🎰",
    "missions": "🎯",
    "premium": "⭐",
    "ban": "⛔",
    "ledger": "📒",
}

RARITY_RU = {
    "COMMON": "Обычный",
    "UNCOMMON": "Необычный",
    "RARE": "Редкий",
    "EPIC": "Эпический",
    "LEGENDARY": "Легендарный",
    "MYTHIC": "Мифический",
    "SECRET": "Секретный",
}

PERIOD_RU = {"today": "сегодня", "7d": "7 дней", "30d": "30 дней", "all": "за всё время"}


def esc(value: Any) -> str:
    """HTML-escape any value before it reaches Telegram's HTML parse mode."""
    text = str(value if value is not None else "")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(value: Any) -> str:
    """Thousands-separated integer, with ``-`` for anything unusable."""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "-"


def signed(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "-"
    return f"+{num(number)}" if number >= 0 else f"-{num(abs(number))}"


def code(value: Any) -> str:
    text = str(value if value not in (None, "") else "-")
    return f"<code>{esc(text)}</code>"


def rarity(value: Any) -> str:
    text = str(value or "-").upper()
    return RARITY_RU.get(text, text)


def dt(value: Any, *, with_time: bool = True) -> str:
    """Render an ISO timestamp or datetime as ``YYYY-MM-DD HH:MM``."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return esc(value)
    else:
        return "-"
    return moment.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def ago(value: Any) -> str:
    """Compact relative time ("2 ч назад")."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return "-"
    else:
        return "-"
    now = datetime.now(moment.tzinfo)
    seconds = int((now - moment).total_seconds())
    if seconds < 0:
        return "только что"
    if seconds < 60:
        return "только что"
    if seconds < 3600:
        return f"{seconds // 60} мин назад"
    if seconds < 86_400:
        return f"{seconds // 3600} ч назад"
    return f"{seconds // 86_400} дн назад"


def username_of(user: dict[str, Any]) -> str:
    name = user.get("username")
    return f"@{name}" if name else (user.get("display_name") or "без имени")


def user_line(user: dict[str, Any]) -> str:
    return f"{esc(user.get('display_name') or 'игрок')} {esc('@' + user['username']) if user.get('username') else ''}".strip()


def truncate(text: str, limit: int = 3400) -> str:
    """Keep a screen under Telegram's 4096-character message limit."""
    if len(text) <= limit:
        return text
    return text[: limit - 30].rstrip() + "\n<i>…обрезано</i>"


def lines(items: Iterable[str]) -> str:
    return "\n".join(item for item in items if item)


# ---------------------------------------------------------------------------
# screens
# ---------------------------------------------------------------------------
def home(data: dict[str, Any]) -> str:
    users = data.get("users", {})
    rolls = data.get("rolls", {})
    collection = data.get("collection", {})
    economy = data.get("economy", {})
    money = data.get("monetization", {})
    season = data.get("season", {})
    system = data.get("system", {})

    return lines(
        [
            "<b>NUMORA ADMIN CONTROL</b>",
            HR,
            f"{EMOJI['users']} <b>Юзеры</b>",
            f"• всего: {num(users.get('total'))}",
            f"• новых сегодня: {num(users.get('new_today'))}",
            f"• активных сегодня: {num(users.get('active_today'))}",
            "",
            f"{EMOJI['rolls']} <b>Роллы</b>",
            f"• всего: {num(rolls.get('total'))}",
            f"• сегодня: {num(rolls.get('today'))}",
            "",
            f"{EMOJI['plates']} <b>Коллекция</b>",
            f"• номеров найдено: {num(collection.get('plates'))}",
            f"• стран: {num(collection.get('countries'))}",
            f"• первых находок: {num(collection.get('first_discoveries'))}",
            "",
            f"{EMOJI['economy']} <b>Экономика</b>",
            f"• в обращении: {num(economy.get('circulation'))} NUMORA",
            f"• выпущено сегодня: {num(economy.get('issued_today'))}",
            f"• потрачено сегодня: {num(economy.get('spent_today'))}",
            "",
            f"⭐ <b>Монетизация</b>",
            f"• оплат: {num(money.get('paid_purchases'))}",
            f"• Stars: {num(money.get('stars_revenue'))}",
            f"• активных PRO: {num(money.get('pro_active'))}",
            "",
            f"🎯 <b>Сезон</b>",
            f"• {code(season.get('code') or 'нет')} "
            f"{'🟢 активен' if season.get('is_active') else '⚪ не активен'}",
            f"• ивент: {code(season.get('event_code') or 'нет')}",
            "",
            "⚠️ <b>Система</b>",
            f"• API: {system.get('api', '?')} • DB: {system.get('database', '?')}",
            f"• ошибок в буфере: {num(system.get('errors_recent'))}",
            f"• проваленных операций: {num(system.get('errors_failed_operations'))}",
            "",
            f"<i>обновлено {dt(data.get('generated_at'))}</i>",
        ]
    )


def recent_actions(actions: Iterable[dict[str, Any]]) -> str:
    rows = list(actions)[:5]
    if not rows:
        return ""
    body = [f"<b>🕘 Последние действия</b>"]
    for item in rows:
        amount = item.get("amount")
        amount_text = f" {signed(amount)}" if amount is not None else ""
        body.append(
            f"• {dt(item.get('created_at'), with_time=False)} {esc(item.get('action'))}"
            f"{amount_text} → {esc(item.get('target_label') or '-')}"
        )
    return "\n".join(body)


def user_card(data: dict[str, Any]) -> str:
    level = data.get("collector_level", {})
    premium = data.get("premium", {})
    best = data.get("best_plate") or {}
    rarest = data.get("rarest_plate") or {}
    ban = "⛔ <b>забанен</b>" if data.get("is_banned") else "не забанен"

    rows = [
        f"{EMOJI['users']} <b>ИГРОК</b>",
        HR,
        f"{esc(data.get('display_name') or 'игрок')}"
        + (f" {esc('@' + data['username'])}" if data.get("username") else ""),
        f"TG ID: {code(data.get('telegram_id'))}",
        f"DB ID: {code(data.get('id'))}",
        "",
        f"{EMOJI['economy']} NUMORA: <b>{num(data.get('coins'))}</b>",
        f"заработано: {num(data.get('total_earned'))} • потрачено: {num(data.get('total_spent'))}",
        f"{EMOJI['rolls']} роллов: {num(data.get('total_rolls'))}"
        f" • бонус: {num(data.get('bonus_rolls'))}",
        f"сегодня использовано: {num(data.get('daily_rolls_used'))}"
        f" / осталось {num(data.get('rolls_remaining'))}",
        f"{EMOJI['ranks']} уровень: <b>{num(level.get('level'))}</b> — {esc(level.get('title_ru') or '')}",
        f"✨ XP: {num(level.get('xp'))} / {num(level.get('xp_for_level'))}",
        f"🔥 стрик: {num(data.get('current_streak'))} (рекорд {num(data.get('longest_streak'))})",
        f"{EMOJI['plates']} номеров: {num(data.get('plates_count'))}"
        f" • стран: {num(data.get('countries_count'))}"
        f" • регионов: {num(data.get('regions_count'))}",
        f"🥇 первых находок: {num(data.get('first_discoveries_count'))}",
    ]

    if best:
        rows.append(
            f"💎 лучший номер: {code(best.get('plate_text'))} "
            f"[{esc(rarity(best.get('rarity')))}] {num(best.get('collector_value'))}"
        )
    if rarest and rarest.get("id") != best.get("id"):
        rows.append(
            f"🌟 самый редкий: {code(rarest.get('plate_text'))} "
            f"[{esc(rarity(rarest.get('rarity')))}]"
        )

    rows.extend(
        [
            f"⭐ PRO: {'активен до ' + dt(premium.get('expires_at')) if premium.get('active') else 'нет'}",
            f"🎫 сезон-пасс: {'да' if data.get('season_pass_active') else 'нет'}",
            f"🏷 титул: {esc(data.get('equipped_title') or '—')}",
            f"🎨 косметика: {esc(', '.join(data.get('equipped_cosmetics') or []) or '—')}",
            f"👥 рефералов: {num(data.get('referrals_count'))}"
            f" • шеров: {num(data.get('shares_count'))}"
            f" • челленджей: {num(data.get('challenges_completed'))}",
            f"🕒 активность: {ago(data.get('last_activity_at'))}",
            f"📅 регистрация: {dt(data.get('created_at'), with_time=False)}",
            "",
            f"🔒 бан: {ban}",
        ]
    )
    if data.get("is_protected_admin"):
        rows.append("🛡 этот игрок — администратор (бан недоступен)")
    return "\n".join(rows)


def economy(data: dict[str, Any]) -> str:
    transactions = data.get("transactions") or []
    body = [
        f"{EMOJI['economy']} <b>ЭКОНОМИКА</b>",
        SMALL,
        f"игрок: {code('@' + data['username']) if data.get('username') else code(data.get('user_id'))}",
        f"баланс: <b>{num(data.get('coins'))} NUMORA</b>",
        f"заработано: {num(data.get('total_earned'))}",
        f"потрачено: {num(data.get('total_spent'))}",
        "",
    ]
    if transactions:
        body.append(f"<b>Последние операции</b>")
        for item in transactions[:10]:
            body.append(
                f"• {dt(item.get('created_at'))} {signed(item.get('amount'))}"
                f" → {num(item.get('balance_after'))} "
                f"<i>{esc(item.get('type'))}</i>"
            )
    else:
        body.append("<i>операций пока нет</i>")
    return "\n".join(body)


def progression(data: dict[str, Any], missions_board: dict[str, Any] | None = None) -> str:
    level = data.get("collector_level", {})
    missions = missions_board or {}
    items = missions.get("items") or []
    completed = sum(1 for item in items if item.get("completed"))
    paid = sum(1 for item in items if item.get("reward_paid"))
    return "\n".join(
        [
            f"{EMOJI['ranks']} <b>ПРОГРЕССИЯ</b>",
            SMALL,
            f"уровень: <b>{num(level.get('level'))}</b> — {esc(level.get('title_ru') or '')}",
            f"✨ XP: {num(level.get('xp'))} (в уровень: {num(level.get('xp_into_level'))}"
            f" / {num(level.get('xp_for_level'))})",
            f"🔥 стрик: {num(data.get('current_streak'))}"
            f" • рекорд: {num(data.get('longest_streak'))}",
            f"{EMOJI['countries']} стран: {num(data.get('countries_count'))}"
            f" • регионов: {num(data.get('regions_count'))}",
            f"{EMOJI['plates']} номеров: {num(data.get('plates_count'))}",
            f"🥇 первых находок: {num(data.get('first_discoveries_count'))}",
            f"{EMOJI['economy']} баланс: {num(data.get('coins'))} NUMORA",
            f"{EMOJI['missions']} заданий: {num(completed)}/{num(len(items))}"
            f" • наград выдано: {num(paid)}",
        ]
    )


def missions(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    body = [f"{EMOJI['missions']} <b>ЗАДАНИЯ</b> <i>(сегодня)</i>", SMALL]
    for item in items:
        marks = []
        if item.get("completed"):
            marks.append("✅")
        if item.get("reward_paid"):
            marks.append("💰")
        rewards = []
        if item.get("reward_coins"):
            rewards.append(f"{num(item['reward_coins'])} NUMORA")
        if item.get("reward_rolls"):
            rewards.append(f"{num(item['reward_rolls'])} роллов")
        if item.get("reward_xp"):
            rewards.append(f"{num(item['reward_xp'])} XP")
        body.append(
            f"{''.join(marks) or '▫️'} {code(item.get('code'))}"
            f" — {esc(item.get('name_ru') or '')}\n"
            f"    {num(item.get('progress'))}/{num(item.get('target'))}"
            f" • {', '.join(rewards) or 'без награды'}"
        )
    if not items:
        body.append("<i>заданий нет</i>")
    return "\n".join(body)


def achievements(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    body = [
        f"{EMOJI['ranks']} <b>ДОСТИЖЕНИЯ</b>",
        SMALL,
        f"получено: {num(data.get('unlocked_count'))} / {num(len(items))}",
    ]
    for item in items:
        mark = "✅" if item.get("unlocked") else "▫️"
        body.append(f"{mark} {code(item.get('code'))} {esc(item.get('name') or '')}")
    return "\n".join(body)


def premium(data: dict[str, Any]) -> str:
    perks = data.get("perks") or {}
    perk_lines = [
        f"• {esc(name)}: {esc(value)}" for name, value in perks.items()
    ] or ["<i>нет данных</i>"]
    return "\n".join(
        [
            f"⭐ <b>PREMIUM</b>",
            SMALL,
            f"статус: {'🟢 активен' if data.get('active') else '⚪ нет'}",
            f"уровень: {code(data.get('tier') or '—')}",
            f"начало: {dt(data.get('starts_at'))}",
            f"истекает: {dt(data.get('expires_at'))}",
            f"+{num(data.get('daily_rolls_bonus'))} роллов в день"
            f" • ×{data.get('duplicate_multiplier')} за дубли",
            "",
            "<b>Бонусы</b>",
            *perk_lines,
        ]
    )


def cosmetics(catalogue: dict[str, Any], owned: Iterable[str] = ()) -> str:
    owned_codes = set(owned or ())
    items = catalogue.get("items") or []
    body = [f"{EMOJI['cosmetics']} <b>КОСМЕТИКА</b>", SMALL]
    for item in items[:20]:
        mark = "✅" if item.get("code") in owned_codes else "▫️"
        price = []
        if item.get("price_stars"):
            price.append(f"⭐{num(item['price_stars'])}")
        if item.get("price_numora"):
            price.append(f"{num(item['price_numora'])} NUMORA")
        body.append(
            f"{mark} {code(item.get('code'))} <i>{esc(item.get('kind'))}</i>"
            f" — {esc(item.get('name_ru') or item.get('name_en') or '')}"
            f" {'· ' + '/'.join(price) if price else ''}"
        )
    if not items:
        body.append("<i>каталог пуст</i>")
    body.append(f"<i>показано {min(len(items), 20)} из {len(items)}</i>")
    return "\n".join(body)


def plate_card(data: dict[str, Any], *, with_history: bool = True) -> str:
    discoverer = data.get("first_discoverer") or {}
    discoverer_label = (
        f"@{discoverer['username']}"
        if discoverer.get("username")
        else (discoverer.get("display_name") or "—")
    )
    body = [
        f"{EMOJI['plates']} <b>НОМЕР</b>",
        SMALL,
        f"Plate ID: {code(data.get('id'))}",
        f"{esc(data.get('country_flag') or '')} {code(data.get('country_code'))}"
        f" • регион {code(data.get('region_code') or '—')}",
        f"шаблон: {code(data.get('template_code') or '—')} ({code(data.get('template_pattern') or '—')})",
        f"текст: <b>{esc(data.get('plate_text'))}</b>",
        f"нормализованный: {code(data.get('normalized_text'))}",
        f"редкость: <b>{esc(rarity(data.get('rarity')))}</b>"
        f" • score: {num(data.get('rarity_score'))}",
        f"коллекционная: {num(data.get('collector_value'))}"
        f" • скупщик: {num(data.get('dealer_value'))}",
        f"находок: {num(data.get('discovery_count'))}",
        f"первый: {esc(discoverer_label)}"
        f" • {dt(data.get('first_discovered_at'), with_time=False)}",
        f"сезон: {code(data.get('season_code') or '—')}"
        f" • секретный: {'да' if data.get('is_secret') else 'нет'}",
        f"traits: {esc(', '.join(data.get('traits') or []) or '—')}",
        f"tags: {esc(', '.join(data.get('tags') or []) or '—')}",
    ]
    if with_history:
        owners = data.get("owners") or []
        if owners:
            body.append("")
            body.append("<b>Владельцы</b>")
            for owner in owners[:5]:
                body.append(
                    f"• {esc(owner.get('username') and '@' + owner['username'] or owner.get('display_name'))}"
                    f" — дублей {num(owner.get('duplicate_count'))}"
                    f" • {dt(owner.get('acquired_at'), with_time=False)}"
                )
        history = data.get("history") or []
        if history:
            body.append("<b>История находок</b>")
            for row in history[:5]:
                flag = "🥇 " if row.get("is_first_discovery") else "• "
                body.append(
                    f"{flag}{esc(row.get('username') and '@' + row['username'] or row.get('display_name'))}"
                    f" — {dt(row.get('created_at'))} ({esc(row.get('source') or '—')})"
                )
    return "\n".join(body)


def plate_list(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    body = [f"{EMOJI['plates']} <b>НОМЕРА</b> <i>{esc(data.get('sort'))}</i>", SMALL]
    for item in items:
        owner_count = item.get("owner_count") or 0
        body.append(
            f"{esc(item.get('country_flag') or '')} {code(item.get('plate_text'))}"
            f" {code(item.get('id'))} [{esc(rarity(item.get('rarity')))}]"
            f" • {num(item.get('collector_value'))}"
            f" • 👥{num(owner_count)}"
        )
    if not items:
        body.append("<i>ничего не найдено</i>")
    body.append(f"<i>стр. {num(data.get('page'))} • всего {num(data.get('total'))}</i>")
    return "\n".join(body)


def test_roll(payload: dict[str, Any], *, mode: str, user_label: str = "") -> str:
    plate = payload.get("plate", {})
    header = f"🧪 <b>ТЕСТ-РОЛЛ</b>"
    body = [header, SMALL]
    if user_label:
        body.append(f"игрок: {esc(user_label)}")
    body.append(f"режим: {'🟡 СИМУЛЯЦИЯ' if mode == 'SIMULATION' else '🔴 LIVE ADMIN TEST'}")
    body.append(f"🇺 {esc(plate.get('country_flag') or '')} {code(plate.get('country_code'))}")
    body.append(f"редкость: <b>{esc(rarity(plate.get('rarity')))}</b>")
    body.append(f"текст: <b>{esc(plate.get('plate_text'))}</b>")
    body.append(f"score: {num(plate.get('rarity_score'))}")
    body.append(f"коллекционная: {num(plate.get('collector_value'))}"
                f" • скупщик: {num(plate.get('dealer_value'))}")
    traits = plate.get("traits") or []
    body.append(f"traits: {esc(', '.join(traits) or '—')}")
    if mode == "LIVE":
        body.append(f"Plate ID: {code(payload.get('plate_id') or '—')}")
        body.append(f"владелец: {'получил новый номер' if not payload.get('is_duplicate') else 'дубль'}")
        if payload.get("is_first_discovery"):
            body.append("🥇 <b>первая находка мира</b>")
        if payload.get("audit_id"):
            body.append(f"Audit ID: {code(payload.get('audit_id'))}")
    else:
        body.append("<i>симуляция: без изменений в игре</i>")
        if payload.get("audit_id"):
            body.append(f"Audit ID: {code(payload.get('audit_id'))}")
    return "\n".join(body)


def ranks(data: dict[str, Any]) -> str:
    entries = data.get("entries") or []
    body = [
        f"{EMOJI['ranks']} <b>ТОП: {esc(data.get('label') or data.get('category'))}</b>",
        f"<i>{esc(PERIOD_RU.get(data.get('period'), data.get('period') or ''))}</i>",
        SMALL,
    ]
    for index, entry in enumerate(entries, start=1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(index, f"{index}.")
        username = entry.get("username")
        label = f"@{username}" if username else (entry.get("display_name") or str(entry.get("user_id")))
        body.append(
            f"{medal} {esc(label)} <code>{esc(entry.get('user_id'))}</code>"
            f" — {num(entry.get('value'))}"
        )
    if not entries:
        body.append("<i>пусто</i>")
    return "\n".join(body)


def countries(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    body = [f"{EMOJI['countries']} <b>СТРАНЫ</b>", SMALL]
    for item in items:
        mark = "🟢" if item.get("is_active") else "⚪"
        body.append(
            f"{mark} {esc(item.get('flag') or '')} {code(item.get('code'))}"
            f" {esc(item.get('name_ru') or item.get('name_en') or '')}"
            f" • {num(item.get('plates'))} номеров"
            f" • {num(item.get('discoveries'))} находок"
            f" • {num(item.get('templates'))}шт/р"
        )
    return "\n".join(body)


def events(data: dict[str, Any]) -> str:
    active = data.get("active") or {}
    body = [
        f"{EMOJI['events']} <b>ИВЕНТЫ</b>",
        SMALL,
        f"активный: {code(active.get('code') or 'нет')}"
        f" {esc(active.get('name_ru') or '')}",
        f"до: {dt(active.get('ends_at'))}",
    ]
    multipliers = active.get("country_multipliers") or {}
    if multipliers:
        body.append("модификаторы стран: " + ", ".join(f"{k}×{v}" for k, v in list(multipliers.items())[:8]))
    body.append("")
    for item in data.get("items") or []:
        mark = "🟢" if item.get("is_active") else "⚪"
        body.append(
            f"{mark} {code(item.get('code'))} {esc(item.get('flag') or '')}"
            f" {esc(item.get('name_ru') or item.get('name_en') or '')}"
            f" • {dt(item.get('starts_at'), with_time=False)} → {dt(item.get('ends_at'), with_time=False)}"
        )
    return "\n".join(body)


def analytics(data: dict[str, Any]) -> str:
    period = data.get("period", "today")
    users = data.get("users", {})
    rolls = data.get("rolls", {})
    economy = data.get("economy", {})
    money = data.get("monetization", {})
    social = data.get("social", {})
    body = [
        f"{EMOJI['analytics']} <b>АНАЛИТИКА</b> <i>{esc(PERIOD_RU.get(period, period))}</i>",
        SMALL,
        f"👤 юзеров всего: {num(users.get('total'))} • новых: {num(users.get('new'))}"
        f" • активных: {num(users.get('active'))}",
        f"🎰 роллов: {num(rolls.get('total'))} • уникальных номеров: {num(rolls.get('unique_plates'))}",
        f"🥇 первых находок: {num(rolls.get('first_discoveries'))}",
        f"💎 Rare+: {num(rolls.get('rare_plus'))} • Legendary+: {num(rolls.get('legendary_plus'))}"
        f" • Mythic: {num(rolls.get('mythic'))} • Secret: {num(rolls.get('secret'))}",
        f"{EMOJI['economy']} выпущено: {num(economy.get('issued'))}"
        f" • потрачено: {num(economy.get('spent'))}"
        f" • в обращении: {num(economy.get('circulation'))}",
        f"⭐ оплат: {num(money.get('purchases'))} • Stars: {num(money.get('stars_revenue'))}",
        f"👥 рефералов: {num(social.get('referrals'))} • шеров: {num(social.get('shares'))}"
        f" • челленджей: {num(social.get('challenges'))}",
        "",
        "<b>Редкости</b>",
    ]
    distribution = data.get("rarity_distribution") or {}
    for key, value in sorted(distribution.items(), key=lambda item: -int(item[1])):
        body.append(f"• {esc(rarity(key))}: {num(value)}")
    countries = data.get("country_distribution") or []
    if countries:
        body.append("")
        body.append("<b>Страны</b>")
        for item in countries[:8]:
            body.append(f"• {esc(item.get('flag') or '')} {code(item.get('code'))} — {num(item.get('rolls'))}")
    for title, key in (
        ("Топ-коллекционеры", "top_collectors"),
        ("Топ первооткрывателей", "top_first_discoverers"),
        ("Топ роллеров", "top_rollers"),
    ):
        rows = data.get(key) or []
        if not rows:
            continue
        body.append("")
        body.append(f"<b>{title}</b>")
        for index, row in enumerate(rows[:5], start=1):
            username = row.get("username")
            label = f"@{username}" if username else (row.get("display_name") or row.get("user_id"))
            body.append(f"{index}. {esc(label)} — {num(row.get('score'))}")
    return "\n".join(body)


def audit(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    body = [f"{EMOJI['audit']} <b>ЖУРНАЛ АДМИНОВ</b>", SMALL]
    for item in items:
        amount = item.get("amount")
        body.append(
            f"🕒 {dt(item.get('created_at'))}\n"
            f"👮 {esc(item.get('admin_label'))} → 🎯 {esc(item.get('target_label') or '-')}\n"
            f"⚙ {esc(item.get('action'))}"
            + (f" • 💰 {signed(amount)}" if amount is not None else "")
            + (f"\n📝 {esc(item.get('reason'))}" if item.get("reason") else "")
            + f"\n<code>#{esc(item.get('id'))}</code>"
        )
    if not items:
        body.append("<i>записей нет</i>")
    body.append(f"<i>стр. {num(data.get('page'))} • всего {num(data.get('total'))}</i>")
    return "\n".join(body)


def system(data: dict[str, Any], *, bot_username: str = "", mini_app: str = "") -> str:
    errors = data.get("recent_errors") or []
    body = [
        f"{EMOJI['system']} <b>СИСТЕМА</b>",
        SMALL,
        f"API: {data.get('api_health')} • DB: {data.get('database_health')}",
        f"версия: {code(data.get('version'))} • окружение: {code(data.get('environment'))}",
        f"rate limit: {'включён' if data.get('rate_limit_enabled') else 'выключен'}"
        f" ({num(data.get('rate_limit_window'))}с)",
        f"активный сезон: {code(data.get('active_season') or '—')}",
        f"бот: @{esc(bot_username or '—')} • mini app: {esc(mini_app or '—')}",
        f"ошибок в буфере: {num(data.get('error_buffer_count'))}"
        f" • проваленных операций: {num(data.get('failed_operations'))}",
        f"админов настроено: {num(data.get('admin_ids_configured'))}",
        f"service token: {'настроен' if data.get('service_token_set') else 'НЕ НАСТРОЕН'}"
        f" (отпечаток {code(data.get('token_fingerprint'))})",
        f"драйвер БД: {code(data.get('database_driver'))}",
    ]
    if errors:
        body.append("")
        body.append("<b>Последние ошибки</b>")
        for item in errors:
            body.append(
                f"• {esc(item.get('ts'))} {esc(item.get('logger'))}\n"
                f"  {esc(item.get('message'))}"
            )
    return "\n".join(body)


def transactions(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    body = [f"{EMOJI['ledger']} <b>ТРАНЗАКЦИИ</b> <i>(append-only)</i>", SMALL]
    for item in items:
        label = f"@{item['username']}" if item.get("username") else str(item.get("user_id"))
        body.append(
            f"#{esc(item.get('id'))} {esc(label)}\n"
            f"  {esc(item.get('type'))} {signed(item.get('amount'))}"
            f" → баланс {num(item.get('balance_after'))}\n"
            f"  {esc(item.get('reference_type') or '')}:{esc(item.get('reference_id') or '—')}"
            f" • {dt(item.get('created_at'))}"
        )
    if not items:
        body.append("<i>пусто</i>")
    body.append(f"<i>показано {len(items)} • всего {num(data.get('total'))}</i>")
    return "\n".join(body)


# ---------------------------------------------------------------------------
# confirmations
# ---------------------------------------------------------------------------
def confirm(title: str, rows: Iterable[str]) -> str:
    body = [f"⚠️ <b>ПОДТВЕРЖДЕНИЕ</b>", f"<b>{esc(title)}</b>", SMALL]
    body.extend(rows)
    body.append("")
    body.append("<i>операция попадёт в журнал админов</i>")
    return "\n".join(body)


def result_ok(title: str, rows: Iterable[str]) -> str:
    body = [f"✅ <b>{esc(title)}</b>", SMALL]
    body.extend(rows)
    return "\n".join(body)


__all__ = [name for name in dir() if not name.startswith("_")]