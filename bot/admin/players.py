"""Admin panel: per-player screens and the confirmation dispatcher.

Everything that mutates one player lives here: economy, rolls, progression,
streaks, missions, achievements, premium, cosmetics, rewards, bans - plus the
generic "enter a reason" step and the dispatcher that executes a staged
operation exactly once.

Mutation payloads never travel in ``callback_data``: each action is staged as a
pending operation (see :mod:`bot.admin.ops`), shown with a confirmation screen,
and executed on confirm. The operation id doubles as the backend's idempotency
key, so a duplicated Telegram callback can never grant twice.
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
    telegram_id,
    toast,
)
from bot.admin.formatters import (
    achievements as fmt_achievements,
)
from bot.admin.formatters import (
    confirm,
    esc,
    num,
    result_ok,
    user_line,
)
from bot.admin.formatters import (
    cosmetics as fmt_cosmetics,
)
from bot.admin.formatters import (
    economy as fmt_economy,
)
from bot.admin.formatters import (
    missions as fmt_missions,
)
from bot.admin.formatters import (
    premium as fmt_premium,
)
from bot.admin.formatters import (
    progression as fmt_progression,
)
from bot.admin.states import (
    KEY_AMOUNT,
    KEY_KIND,
    AdminStates,
    clear_flow_data,
    selected_user_id,
)

logger = logging.getLogger("bot.admin.players")

router = Router(name="admin-players")


# ---------------------------------------------------------------------------
# economy
# ---------------------------------------------------------------------------
async def _render_economy(target: CallbackQuery | Message, user_id: int) -> None:
    """Balance, lifetime totals and the ledger tail for one player."""
    try:
        data = await get_client().user_economy(telegram_id(target), user_id)
    except Exception as exc:
        await render_error(target, exc)
        return
    await render(target, fmt_economy(data), kb.economy_keyboard())


async def _render_user(target: CallbackQuery | Message, context: FSMContext, user_id: int | None = None) -> None:
    """Re-use the shared player card renderer from the main router."""
    from bot.admin.router import _render_user as render_user_card

    await render_user_card(target, context, user_id)


# ---------------------------------------------------------------------------
# economy
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.ECONOMY))
@guard
async def economy_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await _render_economy(callback, user_id)


@router.callback_query(F.data == kb.pack(kb.COIN_BALANCE))
@guard
async def balance_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    try:
        data = await get_client().user_economy(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    await context.set_state(AdminStates.balance_target)
    await render(
        callback.message,
        f"🎯 <b>ТОЧНЫЙ БАЛАНС</b>\n━━━━━━━━━━\n\n"
        f"текущий: <b>{num(data.get('coins'))} NUMORA</b>\n\n"
        "Введите новый баланс.\n<i>дельта будет посчитана и показана перед применением</i>",
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.COIN_PRESET)))
@guard
async def coin_preset(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    arg = parts[2] if len(parts) > 2 else "0"
    if arg == "reset":
        await _stage_reset_rolls(callback, context)
        return
    if not str(arg).lstrip("-").isdigit():
        await toast(callback, "Bad amount.")
        return
    amount = int(arg)
    await _stage_coins(callback, context, amount)


async def _current_balance(target: CallbackQuery | Message, user_id: int) -> int | None:
    try:
        data = await get_client().user_economy(telegram_id(target), user_id)
    except Exception as exc:
        await render_error(target, exc)
        return None
    return int(data.get("coins") or 0)


async def _stage_coins(callback: CallbackQuery, context: FSMContext, amount: int) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    balance = await _current_balance(callback, user_id)
    if balance is None:
        return
    new_balance = balance + amount
    rows = [
        f"игрок: {await _user_label(callback, context, user_id)}",
        f"текущий баланс: <b>{num(balance)} NUMORA</b>",
        "",
        f"изменение: <b>{'+' if amount >= 0 else ''}{num(amount)} NUMORA</b>",
        f"новый баланс: <b>{num(new_balance)} NUMORA</b>",
        "",
        "📝 причина: <i>укажите после нажатия «Далее»</i>",
    ]
    await context.set_state(AdminStates.coin_reason)
    await context.update_data(amount=amount)

    await render(
        callback.message,
        confirm(
            "НАЧИСЛЕНИЕ NUMORA" if amount >= 0 else "СПИСАНИЕ NUMORA",
            rows,
        ),
        kb.prompt_keyboard(),
    )


async def _stage_balance(callback: CallbackQuery, context: FSMContext, target_balance: int) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    balance = await _current_balance(callback, user_id)
    if balance is None:
        return
    if target_balance < 0:
        await toast(callback, "Balance cannot be negative.")
        return
    delta = target_balance - balance
    if delta == 0:
        await toast(callback, "Balance already equals the target.")
        return
    rows = [
        f"игрок: {await _user_label(callback, context, user_id)}",
        f"текущий баланс: <b>{num(balance)} NUMORA</b>",
        f"целевой баланс: <b>{num(target_balance)} NUMORA</b>",
        f"дельта: <b>{'+' if delta >= 0 else ''}{num(delta)} NUMORA</b>",
        "",
        "📝 причина: <i>укажите после нажатия «Далее»</i>",
    ]
    await context.set_state(AdminStates.coin_reason)
    await context.update_data(amount=target_balance, kind=kb.ACT_BALANCE)

    await render(callback.message, confirm("УСТАНОВИТЬ БАЛАНС", rows), kb.prompt_keyboard())


async def _user_label(target: CallbackQuery | Message, context: FSMContext, user_id: int) -> str:
    try:
        data = await get_client().user_detail(telegram_id(target), user_id)
    except Exception:  # a missing label must not block the action
        return f"<code>{user_id}</code>"
    return esc(user_line(data))


@router.message(AdminStates.balance_target)
@guard
async def balance_input(message: Message, context: FSMContext) -> None:
    text = (message.text or "").strip().replace(" ", "").replace("_", "").replace(" ", "")
    if not text.lstrip("-").isdigit():
        await render(message, "⚠️ Нужно целое число.\n\n<i>Повторите ввод.</i>", kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.coin_reason)
    await context.update_data(amount=int(text), kind=kb.ACT_BALANCE)
    await message.answer(
        "✅ Цель принята. Теперь введите причину изменения.",
        reply_markup=kb.prompt_keyboard(),
    )


@router.message(AdminStates.coin_amount)
@guard
async def coin_amount_input(message: Message, context: FSMContext) -> None:
    text = _clean_number(message.text)
    if text is None:
        await message.answer("⚠️ Нужно целое число. Например: 5000", reply_markup=kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.coin_reason)
    await context.update_data(amount=text)
    await message.answer("✅ Сумма принята. Теперь введите причину.", reply_markup=kb.prompt_keyboard())


def _clean_number(raw: str | None) -> int | None:
    text = (raw or "").strip().replace(" ", "").replace("_", "").replace(",", "")
    if text.startswith("+"):
        text = text[1:]
    if text.startswith("-"):
        body = text[1:]
        return -int(body) if body.isdigit() else None
    return int(text) if text.isdigit() else None


@router.callback_query(F.data == kb.pack(kb.COIN_CUSTOM))
@guard
async def coin_custom_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.coin_amount)
    await context.update_data(kind=kb.ACT_COINS)
    await render(
        callback.message,
        "➕ <b>НАЧИСЛЕНИЕ</b>\n━━━━━━━━━━\n\nВведите сумму NUMORA.\n<i>Пример: 2500</i>",
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.COIN_SUBTRACT))
@guard
async def coin_subtract_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.coin_amount)
    await context.update_data(kind=kb.ACT_COINS, sign=-1)
    await render(
        callback.message,
        "➖ <b>СПИСАНИЕ</b>\n━━━━━━━━━━\n\nВведите сумму NUMORA для списания.\n<i>Пример: 500</i>",
        kb.prompt_keyboard(),
    )


@router.message(AdminStates.coin_reason)
@guard
async def coin_reason_input(message: Message, context: FSMContext) -> None:
    reason = (message.text or "").strip()[:240]
    if not reason or reason.startswith("/"):
        await message.answer("⚠️ Нужна причина (минимум 1 символ).", reply_markup=kb.prompt_keyboard())
        return
    amount = await data_of(context, KEY_AMOUNT)
    kind = await data_of(context, KEY_KIND, kb.ACT_COINS)
    if kind == kb.ACT_BALANCE:
        amount = int(amount or 0)
    else:
        sign = await data_of(context, "sign", 1)
        amount = int(amount or 0) * (1 if sign == 1 else -1)
    await _stage_economy(message, context, kind, amount, reason)


async def _stage_economy(
    target: CallbackQuery | Message,
    context: FSMContext,
    kind: str,
    amount: int,
    reason: str,
) -> None:
    user_id = await require_user(context, target)
    if user_id is None:
        return
    balance = await _current_balance(target, user_id)
    if balance is None:
        return
    if kind == kb.ACT_BALANCE:
        delta = amount - balance
        title = "УСТАНОВИТЬ БАЛАНС"
        new_balance = amount
    else:
        delta = amount
        new_balance = balance + amount
        title = "НАЧИСЛИТЬ NUMORA" if amount >= 0 else "СПИСАТЬ NUMORA"
    if delta == 0:
        await render(target, "⚠️ Изменение равно нулю.", None)
        return

    operation_id = await stage(
        context,
        kind,
        {"user_id": user_id, "amount": amount, "delta": delta, "reason": reason},
        title,
        [
            f"игрок: {await _user_label(target, context, user_id)}",
            f"текущий баланс: <b>{num(balance)} NUMORA</b>",
            f"изменение: <b>{'+' if delta >= 0 else ''}{num(delta)} NUMORA</b>",
            f"новый баланс: <b>{num(new_balance)} NUMORA</b>",
            "",
            f"📝 причина: {esc(reason)}",
        ],
    )

    await render(target, confirm(title, []), kb.confirm_keyboard(operation_id))


# ---------------------------------------------------------------------------
# rolls
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_ROLLS))
@guard
async def rolls_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await _render_user(callback, context, user_id)
    await render(
        callback.message,
        "🎰 <b>РОЛЛЫ</b>\n━━━━━━━━━━\n\nБонусные роллы выдаются сверх дневного лимита.\n"
        "<i>Дневной лимит не меняется.</i>",
        kb.rolls_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.ROLL_PRESET)))
@guard
async def roll_preset(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3 or not parts[2].isdigit():
        await context.set_state(AdminStates.roll_count)
        await render(
            callback.message,
            "➕ <b>РОЛЛЫ</b>\n━━━━━━━━━━\n\nВведите количество роллов.",
            kb.prompt_keyboard(),
        )
        return
    await _stage_rolls(callback, context, int(parts[2]))


@router.message(AdminStates.roll_count)
@guard
async def roll_count_input(message: Message, context: FSMContext) -> None:
    value = _clean_number(message.text)
    if value is None or value <= 0:
        await message.answer("⚠️ Нужно положительное целое число.", reply_markup=kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(amount=value, kind=kb.ACT_ROLLS)
    await message.answer("✅ Количество принято. Введите причину.", reply_markup=kb.prompt_keyboard())


async def _stage_rolls(target: CallbackQuery | Message, context: FSMContext, amount: int) -> None:
    user_id = await require_user(context, target)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(amount=amount, kind=kb.ACT_ROLLS, user_id=user_id)

    await render(
        target,
        confirm(
            f"ВЫДАТЬ {num(amount)} РОЛЛОВ",
            [
                f"игрок: {await _user_label(target, context, user_id)}",
                "Бонусные роллы выдаются сверх дневного лимита.",
                "<i>дневной лимит не изменяется</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


async def _stage_reset_rolls(target: CallbackQuery | Message, context: FSMContext) -> None:
    user_id = await require_user(context, target)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_ROLLS_RESET, user_id=user_id)

    await render(
        target,
        confirm(
            "⚠️ СБРОСИТЬ РОЛЛЫ СЕГОДНЯ",
            [
                f"игрок: {await _user_label(target, context, user_id)}",
                "Вернёт использованные сегодня роллы.",
                "<i>бонусные роллы и лимит не меняются</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


# ---------------------------------------------------------------------------
# progression
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_PROGRESSION))
@guard
async def progression_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await _render_progression(callback, context, user_id)


async def _render_progression(
    target: CallbackQuery | Message,
    context: FSMContext,
    user_id: int,
) -> None:
    client = get_client()
    try:
        detail = await client.user_detail(telegram_id(target), user_id)
        board = await client.user_missions(telegram_id(target), user_id)
    except Exception as exc:
        await render_error(target, exc)
        return
    await render(target, fmt_progression(detail, board), kb.progression_keyboard())


@router.callback_query(F.data.startswith(kb.pack(kb.XP_PRESET)))
@guard
async def xp_preset(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    arg = parts[2] if len(parts) > 2 else ""
    if arg == "streak":
        await render(
            callback.message,
            "🔥 <b>СТРИК</b>\n━━━━━━━━━━\n\nВыберите значение или сбросьте стрик.",
            kb.streak_keyboard(),
        )
        return
    if arg in ("custom", "exact"):
        state = AdminStates.xp_amount if arg == "custom" else AdminStates.xp_exact
        await context.set_state(state)
        await render(
            callback.message,
            "✨ <b>XP</b>\n━━━━━━━━━━\n\nВведите количество XP.",
            kb.prompt_keyboard(),
        )
        return
    if arg == "level":
        await context.set_state(AdminStates.level_value)
        await render(
            callback.message,
            "🏆 <b>УРОВЕНЬ</b>\n━━━━━━━━━━\n\nВведите уровень коллекционера.",
            kb.prompt_keyboard(),
        )
        return
    if arg == "reset":
        await _stage_simple(
            callback,
            context,
            kb.ACT_PROG_RESET,
            "⚠️ СБРОСИТЬ ПРОГРЕССИЮ",
            [
                f"игрок: {await _user_label(callback, context, await require_user(context, callback))}",
                "Уровень → 1, XP → 0, стрик → 0.",
                "<i>коллекция и номера не меняются</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        )
        return
    if not str(arg).isdigit():
        await toast(callback, "Bad amount.")
        return
    await _stage_xp(callback, context, int(arg))


async def _stage_xp(target: CallbackQuery | Message, context: FSMContext, amount: int) -> None:
    user_id = await require_user(context, target)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_XP, amount=amount, user_id=user_id)

    await render(
        target,
        confirm(
            f"{'НАЧИСЛИТЬ' if amount >= 0 else 'СНЯТЬ'} {num(abs(amount))} XP",
            [
                f"игрок: {await _user_label(target, context, user_id)}",
                f"изменение XP: <b>{'+' if amount >= 0 else ''}{num(amount)}</b>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.STREAK_VALUE)))
@guard
async def streak_value(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    arg = parts[2] if len(parts) > 2 else ""
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    if arg == "reset":
        await _stage_simple(
            callback,
            context,
            kb.ACT_STREAK,
            "⚠️ СБРОСИТЬ СТРИК",
            [
                f"игрок: {await _user_label(callback, context, user_id)}",
                "Текущий стрик и рекорд → 0.",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        )
        return
    if not arg.isdigit():
        await toast(callback, "Bad value.")
        return
    await _stage_simple(
        callback,
        context,
        kb.ACT_STREAK,
        f"СТРИК = {arg}",
        [
            f"игрок: {await _user_label(callback, context, user_id)}",
            f"новый стрик: <b>{arg}</b> (рекорд обновится автоматически)",
            "",
            "📝 причина: <i>укажите сейчас</i>",
        ],
        payload={"current": int(arg)},
    )


async def _stage_simple(
    target: CallbackQuery | Message,
    context: FSMContext,
    action: str,
    title: str,
    rows: list[str],
    *,
    payload: dict[str, Any] | None = None,
) -> None:
    user_id = await require_user(context, target)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=action, user_id=user_id)
    await stage(context, action, {"user_id": user_id, **(payload or {})}, title, rows)

    operation_id = await stage(
        context,
        action,
        {"user_id": user_id, **(payload or {})},
        title,
        rows,
    )
    del operation_id
    await render(target, confirm(title, rows), kb.prompt_keyboard())


@router.message(AdminStates.xp_amount)
@guard
async def xp_amount_input(message: Message, context: FSMContext) -> None:
    value = _clean_number(message.text)
    if value is None or value == 0:
        await message.answer("⚠️ Нужно целое число (можно со знаком минус).", reply_markup=kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_XP, amount=value)
    await message.answer("✅ XP принято. Введите причину.", reply_markup=kb.prompt_keyboard())


@router.message(AdminStates.xp_exact)
@guard
async def xp_exact_input(message: Message, context: FSMContext) -> None:
    value = _clean_number(message.text)
    if value is None or value < 0:
        await message.answer("⚠️ Нужно неотрицательное целое число.", reply_markup=kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_XP, amount=value, exact=True)
    await message.answer("✅ XP принято. Введите причину.", reply_markup=kb.prompt_keyboard())


@router.message(AdminStates.level_value)
@guard
async def level_input(message: Message, context: FSMContext) -> None:
    value = _clean_number(message.text)
    if value is None or value <= 0:
        await message.answer("⚠️ Нужно положительное целое число.", reply_markup=kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_LEVEL, amount=value)
    await message.answer("✅ Уровень принят. Введите причину.", reply_markup=kb.prompt_keyboard())


# ---------------------------------------------------------------------------
# missions
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_MISSIONS))
@guard
async def missions_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    try:
        data = await get_client().user_missions(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    codes = [str(item.get("code")) for item in (data.get("items") or [])]
    await render(
        callback.message,
        fmt_missions(data),
        kb.missions_item_keyboard(codes) if codes else kb.missions_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.MISSION_PROGRESS)))
@guard
async def mission_progress(callback: CallbackQuery, context: FSMContext) -> None:
    await _mission_stage(callback, context, "progress")


@router.callback_query(F.data.startswith(kb.pack(kb.MISSION_COMPLETE)))
@guard
async def mission_complete(callback: CallbackQuery, context: FSMContext) -> None:
    await _mission_stage(callback, context, "complete", dangerous=True)


@router.callback_query(F.data.startswith(kb.pack(kb.MISSION_RESET)))
@guard
async def mission_reset(callback: CallbackQuery, context: FSMContext) -> None:
    await _mission_stage(callback, context, "reset", dangerous=True)


async def _mission_stage(
    target: CallbackQuery | Message,
    context: FSMContext,
    action: str,
    *,
    dangerous: bool = False,
) -> None:
    parts = kb.unpack(getattr(target, "data", "") or "")
    if len(parts) < 3:
        await toast(target, "Bad request.")  # type: ignore[arg-type]
        return
    code = parts[2]
    amount = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
    user_id = await require_user(context, target)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_MISSION)
    title = {
        "progress": f"ПРОГРЕСС {code}",
        "complete": f"✅ ЗАВЕРШИТЬ {code}",
        "reset": f"⚠️ СБРОС {code}",
    }[action]
    rows = [
        f"игрок: {await _user_label(target, context, user_id)}",
        f"задание: {code}",
        f"действие: {action}" + (f" (+{amount})" if action == "progress" else ""),
    ]
    if dangerous:
        rows.append("<i>награда выплачивается только один раз</i>")
    rows.append("")
    rows.append("📝 причина: <i>укажите сейчас</i>")

    await render(target, confirm(title, rows), kb.prompt_keyboard())


# ---------------------------------------------------------------------------
# achievements
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_ACHIEVEMENTS))
@guard
async def achievements_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    try:
        data = await get_client().user_achievements(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    pairs = [(str(item.get("code")), bool(item.get("unlocked"))) for item in (data.get("items") or [])]
    await render(
        callback.message,
        fmt_achievements(data),
        kb.achievements_item_keyboard(pairs) if pairs else kb.achievements_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.ACHIEVEMENT_GRANT)))
@guard
async def achievement_grant(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3:
        await toast(callback, "Bad request.")
        return
    code = parts[2]
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_ACHIEVEMENT, amount=code)

    await render(
        callback.message,
        confirm(
            f"ВЫДАТЬ ДОСТИЖЕНИЕ {code}",
            [
                f"игрок: {await _user_label(callback, context, user_id)}",
                f"достижение: {code}",
                "<i>повторная выдача безопасна</i>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


# ---------------------------------------------------------------------------
# premium
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_PREMIUM))
@guard
async def premium_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    try:
        data = await get_client().user_premium(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    await render(callback.message, fmt_premium(data), kb.premium_keyboard())


@router.callback_query(F.data.startswith(kb.pack(kb.PREMIUM_PRESET)))
@guard
async def premium_preset(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    arg = parts[2] if len(parts) > 2 else ""
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    if arg == "custom":
        await context.set_state(AdminStates.premium_days)
        await render(
            callback.message,
            "⭐ <b>PRO</b>\n━━━━━━━━━━\n\nВведите количество дней.",
            kb.prompt_keyboard(),
        )
        return
    if arg == "revoke":
        await _stage_simple(
            callback,
            context,
            kb.ACT_PREMIUM_REVOKE,
            "⚠️ ОТОЗВАТЬ PRO",
            [
                f"игрок: {await _user_label(callback, context, user_id)}",
                "PRO будет отозван немедленно.",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        )
        return
    if not arg.isdigit():
        await toast(callback, "Bad duration.")
        return
    await _stage_simple(
        callback,
        context,
        kb.ACT_PREMIUM,
        f"ВЫДАТЬ PRO {arg} ДН",
        [
            f"игрок: {await _user_label(callback, context, user_id)}",
            f"срок: <b>{arg} дней</b>",
            "",
            "📝 причина: <i>укажите сейчас</i>",
        ],
        payload={"days": int(arg)},
    )


@router.message(AdminStates.premium_days)
@guard
async def premium_days_input(message: Message, context: FSMContext) -> None:
    value = _clean_number(message.text)
    if value is None or value <= 0:
        await message.answer("⚠️ Нужно положительное целое число.", reply_markup=kb.prompt_keyboard())
        return
    user_id = await selected_user_id(context)
    if user_id is None:
        await message.answer("⚠️ Сначала выберите игрока.", reply_markup=kb.prompt_keyboard())
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_PREMIUM, amount=value)
    try:
        detail = await get_client().user_detail(telegram_id(message), user_id)
    except Exception as exc:
        await render_error(message, exc)
        return

    await render(
        message,
        confirm(
            f"ВЫДАТЬ PRO {num(value)} ДН",
            [
                f"игрок: {esc(user_line(detail))}",
                f"срок: <b>{num(value)} дней</b>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
        answer=True,
    )


# ---------------------------------------------------------------------------
# cosmetics / rewards
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_COSMETICS))
@guard
async def cosmetics_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    try:
        client = get_client()
        catalogue = await client.cosmetics(telegram_id(callback))
        detail = await client.user_detail(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    owned = detail.get("equipped_cosmetics") or []
    await render(
        callback.message,
        fmt_cosmetics(catalogue, owned),
        kb.cosmetics_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.COSMETIC_SEARCH))
@guard
async def cosmetics_search_prompt(callback: CallbackQuery, context: FSMContext) -> None:
    await context.set_state(AdminStates.cosmetic_code)
    await render(
        callback.message,
        "🔍 <b>КОСМЕТИКА</b>\n━━━━━━━━━━\n\nВведите код косметики или её название.",
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.COSMETIC_GRANT)))
@guard
async def cosmetic_grant(callback: CallbackQuery, context: FSMContext) -> None:
    await _cosmetics_stage(callback, context, "grant")


@router.callback_query(F.data.startswith(kb.pack(kb.COSMETIC_EQUIP)))
@guard
async def cosmetic_equip(callback: CallbackQuery, context: FSMContext) -> None:
    await _cosmetics_stage(callback, context, "equip")


@router.callback_query(F.data.startswith(kb.pack(kb.COSMETIC_UNEQUIP)))
@guard
async def cosmetic_unequip(callback: CallbackQuery, context: FSMContext) -> None:
    await _cosmetics_stage(callback, context, "unequip")


async def _cosmetics_stage(target: CallbackQuery | Message, context: FSMContext, action: str) -> None:
    parts = kb.unpack(getattr(target, "data", "") or "")
    code = parts[2] if len(parts) > 2 else ""
    if not code:
        await context.set_state(AdminStates.cosmetic_code)
        await render(target, "🔍 Введите код косметики.", kb.prompt_keyboard())
        return
    user_id = await require_user(context, target)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=kb.ACT_COSMETIC, amount=code, action=action)
    titles = {"grant": "ВЫДАТЬ", "equip": "НАДЕТЬ", "unequip": "СНЯТЬ"}

    await render(
        target,
        confirm(
            f"{titles[action]} КОСМЕТИКУ",
            [
                f"игрок: {await _user_label(target, context, user_id)}",
                f"код: <code>{esc(code)}</code>",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


@router.callback_query(F.data == kb.pack(kb.USER_REWARDS))
@guard
async def rewards_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await _render_user(callback, context, user_id)
    await render(
        callback.message,
        "🎁 <b>БЫСТРЫЕ НАГРАДЫ</b>\n━━━━━━━━━━\n\nВыберите тип награды.",
        kb.rewards_keyboard(),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.REWARD_KIND)))
@guard
async def reward_kind(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    kind = parts[2] if len(parts) > 2 else ""
    presets = {
        "coins": (100, "🎁 ВЫДАТЬ 100 NUMORA"),
        "rolls": (5, "🎁 ВЫДАТЬ 5 РОЛЛОВ"),
        "xp": (500, "✨ ВЫДАТЬ 500 XP"),
        "premium": (30, "⭐ ВЫДАТЬ PRO 30 ДН"),
    }
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    if kind in presets:
        amount, title = presets[kind]
        await _stage_simple(
            callback,
            context,
            kb.ACT_REWARD,
            title,
            [
                f"игрок: {await _user_label(callback, context, user_id)}",
                f"награда: <b>{kind}</b> × {num(amount)}",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
            payload={"reward_kind": kind, "amount": amount},
        )
        return
    if kind == "cosmetic":
        await _cosmetics_stage(callback, context, "grant")
        return
    if kind == "title":
        await context.set_state(AdminStates.reason)
        await context.update_data(kind=kb.ACT_TITLE, amount="")
        await render(
            callback.message,
            "🏷 <b>ТИТУЛ</b>\n━━━━━━━━━━\n\nВведите текст титула.",
            kb.prompt_keyboard(),
        )
        return
    if kind == "season_pass":
        await _stage_simple(
            callback,
            context,
            kb.ACT_REWARD,
            "🎫 ВЫДАТЬ СЕЗОН-ПАСС",
            [
                f"игрок: {await _user_label(callback, context, user_id)}",
                "Активный сезон.",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
            payload={"reward_kind": "season_pass", "amount": 0},
        )
        return
    await toast(callback, "Unknown reward.")


# ---------------------------------------------------------------------------
# ban
# ---------------------------------------------------------------------------
@router.callback_query(F.data == kb.pack(kb.USER_BAN))
@guard
async def ban_menu(callback: CallbackQuery, context: FSMContext) -> None:
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    try:
        detail = await get_client().user_detail(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    state = "забанен" if detail.get("is_banned") else "активен"
    await render(
        callback.message,
        f"⛔ <b>МОДЕРАЦИЯ</b>\n━━━━━━━━━━\n\n"
        f"игрок: {esc(user_line(detail))}\n"
        f"TG ID: {esc(str(detail.get('telegram_id')))}\n"
        f"статус: <b>{state}</b>",
        kb.ban_keyboard(
            bool(detail.get("is_banned")),
            bool(detail.get("is_protected_admin")),
        ),
    )


@router.callback_query(F.data.startswith(kb.pack(kb.USER_BAN)))
@guard
async def ban_toggle(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    action = parts[2] if len(parts) > 2 else kb.ACT_BAN
    if action not in (kb.ACT_BAN, kb.ACT_UNBAN):
        return
    user_id = await require_user(context, callback)
    if user_id is None:
        return
    await context.set_state(AdminStates.reason)
    await context.update_data(kind=action)
    banning = action == kb.ACT_BAN
    try:
        detail = await get_client().user_detail(telegram_id(callback), user_id)
    except Exception as exc:
        await render_error(callback, exc)
        return
    if detail.get("is_protected_admin"):
        await toast(callback, "Configured admins are protected.")
        return

    await render(
        callback.message,
        confirm(
            "⚠️ ЗАБАНИТЬ ИГРОКА" if banning else "✅ РАЗБАНИТЬ ИГРОКА",
            [
                f"игрок: {esc(user_line(detail))}",
                f"TG ID: {esc(str(detail.get('telegram_id')))}",
                "",
                "Бан блокирует обычный доступ к игре." if banning else "Игрок снова сможет играть.",
                "",
                "📝 причина: <i>укажите сейчас</i>",
            ],
        ),
        kb.prompt_keyboard(),
    )


# ---------------------------------------------------------------------------
# generic reason input -> stage every remaining mutation
# ---------------------------------------------------------------------------
@router.message(AdminStates.reason)
@guard
async def reason_input(message: Message, context: FSMContext) -> None:
    reason = (message.text or "").strip()[:240]
    if not reason or reason.startswith("/"):
        await message.answer("⚠️ Нужна причина (минимум 1 символ).", reply_markup=kb.prompt_keyboard())
        return
    kind = await data_of(context, KEY_KIND)
    user_id = await require_user(context, message)
    if not kind or user_id is None:
        await context.set_state(None)
        return
    amount = await data_of(context, KEY_AMOUNT)
    extra: dict[str, Any] = {}

    if kind == kb.ACT_COINS:
        if await data_of(context, "exact"):
            extra = {"target": int(amount or 0), "delta": int(amount or 0)}
        else:
            extra = {"delta": int(amount or 0)}
        title = "ИЗМЕНИТЬ БАЛАНС"
        rows = ["дельта рассчитана бэкендом", ""]
        operation = kb.ACT_BALANCE if await data_of(context, "exact") else kb.ACT_COINS
        await _finalise(message, context, operation, extra, reason, title, rows, user_id)
        return
    if kind == kb.ACT_ROLLS:
        await _finalise(
            message, context, kb.ACT_ROLLS, {"amount": int(amount or 1)}, reason, "ВЫДАТЬ РОЛЛЫ", [], user_id
        )
        return
    if kind == kb.ACT_ROLLS_RESET:
        await _finalise(message, context, kb.ACT_ROLLS_RESET, {}, reason, "⚠️ СБРОС РОЛЛОВ СЕГОДНЯ", [], user_id)
        return
    if kind == kb.ACT_XP:
        await _finalise(
            message,
            context,
            kb.ACT_XP,
            {"delta": int(amount or 0), "exact": None},
            reason,
            "ИЗМЕНИТЬ XP",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_LEVEL:
        await _finalise(
            message,
            context,
            kb.ACT_LEVEL,
            {"level": int(amount or 1)},
            reason,
            "УСТАНОВИТЬ УРОВЕНЬ",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_STREAK:
        await _finalise(
            message,
            context,
            kb.ACT_STREAK,
            extra or {},
            reason,
            "ИЗМЕНИТЬ СТРИК",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_PROG_RESET:
        await _finalise(message, context, kb.ACT_PROG_RESET, {}, reason, "⚠️ СБРОС ПРОГРЕССИИ", [], user_id)
        return
    if kind == kb.ACT_MISSION:
        code = await data_of(context, "mission_code") or await data_of(context, "pending_code") or ""
        if not code:
            code = str(amount or "")
        await _finalise(
            message,
            context,
            kb.ACT_MISSION,
            {"code": code, "action": await data_of(context, "mission_action") or "progress"},
            reason,
            "ЗАДАНИЕ",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_ACHIEVEMENT:
        await _finalise(
            message,
            context,
            kb.ACT_ACHIEVEMENT,
            {"code": str(amount or "")},
            reason,
            "ВЫДАТЬ ДОСТИЖЕНИЕ",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_COSMETIC:
        await _finalise(
            message,
            context,
            kb.ACT_COSMETIC,
            {"code": str(amount or ""), "action": await data_of(context, "action") or "grant"},
            reason,
            "КОСМЕТИКА",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_TITLE:
        await _finalise(
            message,
            context,
            kb.ACT_TITLE,
            {"title": str(amount or "")},
            reason,
            "ВЫДАТЬ ТИТУЛ",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_PREMIUM:
        await _finalise(
            message,
            context,
            kb.ACT_PREMIUM,
            {"days": int(amount or 30)},
            reason,
            "ВЫДАТЬ PRO",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_PREMIUM_REVOKE:
        await _finalise(
            message, context, kb.ACT_PREMIUM_REVOKE, {"revoke": True}, reason, "⚠️ ОТОЗВАТЬ PRO", [], user_id
        )
        return
    if kind in (kb.ACT_BAN, kb.ACT_UNBAN):
        await _finalise(
            message,
            context,
            kind,
            {"banned": kind == kb.ACT_BAN},
            reason,
            "ЗАБАНИТЬ" if kind == kb.ACT_BAN else "РАЗБАНИТЬ",
            [],
            user_id,
        )
        return
    if kind == kb.ACT_REWARD:
        await _finalise(
            message,
            context,
            kb.ACT_REWARD,
            {"reward_kind": await data_of(context, "reward_kind"), "amount": int(amount or 0)},
            reason,
            "БЫСТРАЯ НАГРАДА",
            [],
            user_id,
        )
        return
    await context.set_state(None)
    await message.answer("⚠️ Неизвестное действие.", reply_markup=kb.prompt_keyboard())


async def _finalise(
    target: CallbackQuery | Message,
    context: FSMContext,
    action: str,
    payload: dict[str, Any],
    reason: str,
    title: str,
    rows: list[str],
    user_id: int,
) -> None:
    """Store the operation and show the confirmation keyboard."""
    body = [
        f"игрок: {await _user_label(target, context, user_id)}",
        *rows,
        f"📝 причина: {esc(reason)}",
    ]
    operation_id = await stage(context, action, {"user_id": user_id, **payload}, title, body)
    await context.set_state(None)
    await clear_flow_data(context)

    await render(
        target,
        confirm(title, body),
        kb.confirm_keyboard(operation_id),
        answer=isinstance(target, Message),
    )


# ---------------------------------------------------------------------------
# confirmation dispatcher
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith(kb.pack(kb.CONFIRM)))
@guard
async def confirm_operation(callback: CallbackQuery, context: FSMContext) -> None:
    """Execute a staged operation exactly once."""
    parts = kb.unpack(callback.data or "")
    if len(parts) < 3:
        await toast(callback, "Bad request.")
        return
    operation_id = parts[2]
    operation = await ops.pop(context, operation_id)
    if operation is None:
        await toast(callback, "Operation expired or already used.")
        return
    await callback.answer("Выполняю…")
    try:
        await _execute(callback, operation)
    except Exception as exc:
        await render_error(callback, exc)


@router.callback_query(F.data.startswith(kb.pack(kb.CANCEL)))
@guard
async def cancel_operation(callback: CallbackQuery, context: FSMContext) -> None:
    parts = kb.unpack(callback.data or "")
    if len(parts) > 2:
        await ops.pop(context, parts[2])
    await context.set_state(None)
    await clear_flow_data(context)
    await callback.answer("Отменено")
    await render(
        callback.message,
        "🚫 <b>ОТМЕНЕНО</b>\n━━━━━━━━━━\n\nОперация не выполнялась.",
        kb.back_row(),
    )


async def _execute(callback: CallbackQuery, operation: dict[str, Any]) -> None:
    action = str(operation.get("action"))
    payload = dict(operation.get("payload") or {})
    reason = str(payload.pop("reason", "") or "admin panel")
    operation_id = ops.new_operation_id()
    client = get_client()
    user_id = payload.get("user_id")

    if action == kb.ACT_COINS:
        result = await client.mutate(
            "/economy/coins",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            delta=payload.get("delta", 0),
        )
        await _show_wallet_result(callback, result)
        return
    if action == kb.ACT_BALANCE:
        result = await client.mutate(
            "/economy/balance",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            target=payload.get("target", 0),
        )
        await _show_wallet_result(callback, result)
        return
    if action == kb.ACT_ROLLS:
        result = await client.mutate(
            "/rolls/grant",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            amount=payload.get("amount", 1),
        )
    elif action == kb.ACT_ROLLS_RESET:
        result = await client.mutate(
            "/rolls/reset-daily",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
        )
    elif action == kb.ACT_XP:
        request: dict[str, Any] = {"user_id": user_id}
        if data_of_flag(payload, "exact"):
            request["xp"] = payload.get("delta", 0)
        else:
            request["delta"] = payload.get("delta", 0)
        result = await client.mutate(
            "/progression/xp",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            **request,
        )
    elif action == kb.ACT_LEVEL:
        result = await client.mutate(
            "/progression/level",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            level=payload.get("level", 1),
        )
    elif action == kb.ACT_STREAK:
        streak_payload: dict[str, Any] = {"user_id": user_id}
        if "current" in payload:
            streak_payload["current"] = payload["current"]
        if "longest" in payload:
            streak_payload["longest"] = payload["longest"]
        streak_payload["reset"] = bool(payload.get("reset"))
        result = await client.mutate(
            "/progression/streak",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            **streak_payload,
        )
    elif action == kb.ACT_PROG_RESET:
        result = await client.mutate(
            "/progression/reset",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
        )
    elif action == kb.ACT_MISSION:
        result = await client.mutate(
            "/missions/action",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            code=payload.get("code", ""),
            action=payload.get("action", "progress"),
            amount=int(payload.get("amount", 1) or 1),
        )
    elif action == kb.ACT_ACHIEVEMENT:
        result = await client.mutate(
            "/achievements/action",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            code=payload.get("code", ""),
            revoke=bool(payload.get("revoke", False)),
        )
    elif action == kb.ACT_COSMETIC:
        result = await client.mutate(
            "/cosmetics/action",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            code=payload.get("code", ""),
            action=payload.get("action", "grant"),
        )
    elif action == kb.ACT_TITLE:
        result = await client.mutate(
            "/titles/grant",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            title=payload.get("title", ""),
        )
    elif action == kb.ACT_PREMIUM:
        result = await client.mutate(
            "/premium/action",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            days=int(payload.get("days", 30) or 30),
        )
    elif action == kb.ACT_PREMIUM_REVOKE:
        result = await client.mutate(
            "/premium/action",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            revoke=True,
        )
    elif action in (kb.ACT_BAN, kb.ACT_UNBAN):
        result = await client.mutate(
            "/users/ban",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            banned=action == kb.ACT_BAN,
        )
    elif action == kb.ACT_REWARD:
        result = await client.mutate(
            "/rewards/grant",
            admin_telegram_id=telegram_id(callback),
            operation_id=operation_id,
            reason=reason,
            user_id=user_id,
            kind=payload.get("reward_kind", "coins"),
            amount=int(payload.get("amount", 0) or 0),
            code=payload.get("code", ""),
        )
    else:
        await render(callback.message, "⚠️ Неизвестная операция.", kb.back_row())
        return

    await _show_result(callback, result, user_id)


def data_of_flag(payload: dict[str, Any], key: str) -> bool:
    return bool(payload.get(key))


async def _show_wallet_result(callback: CallbackQuery, result: dict[str, Any]) -> None:
    balance = result.get("balance")
    delta = result.get("delta")
    rows = [
        f"баланс: <b>{num(balance)} NUMORA</b>",
    ]
    if delta is not None:
        rows.insert(0, f"изменение: <b>{'+' if int(delta) >= 0 else ''}{num(delta)}</b>")
    rows.append(f"транзакция: {result.get('transaction_id', '—')}")
    if result.get("replayed"):
        rows.append("<i>повтор запроса — начислено один раз</i>")

    await render(
        callback.message,
        result_ok("💰 ГОТОВО", [*rows, f"audit: {result.get('audit_id', '—')}"]),
        kb.back_row(),
    )


async def _show_result(
    callback: CallbackQuery,
    result: dict[str, Any],
    user_id: int | None,
) -> None:
    """Generic success screen, then a button back to the player card."""

    rows: list[str] = []
    for key, label in (
        ("balance", "баланс"),
        ("bonus_rolls", "бонусные роллы"),
        ("rolls_remaining", "осталось роллов"),
        ("xp", "XP"),
        ("level", "уровень"),
        ("current_streak", "стрик"),
        ("longest_streak", "рекорд"),
        ("progress", "прогресс задания"),
        ("completed", "выполнено"),
        ("plates_count", "номеров"),
        ("is_banned", "бан"),
        ("active", "PRO активен"),
        ("expires_at", "PRO до"),
        ("owned", "владеет"),
        ("equipped", "надето"),
        ("titles", "титулы"),
    ):
        value = result.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        rows.append(f"{label}: <b>{esc(value)}</b>")
    if result.get("replayed"):
        rows.append("<i>повтор запроса — операция уже была выполнена</i>")
    rows.append(f"audit: <code>{result.get('audit_id', '—')}</code>")
    await render(callback.message, result_ok("✅ ГОТОВО", rows), kb.back_row())
