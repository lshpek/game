"""Shared plumbing for the admin handlers.

Every handler in this package goes through the helpers here, which gives the
panel three uniform guarantees:

1. **Authorisation is re-checked on every event.** A handler never assumes that
   the message which opened the panel belonged to an admin - it re-reads the id
   from the current event and compares it against ``ADMIN_TELEGRAM_IDS``.
2. **One panel message.** Navigation edits the existing message instead of
   posting a new one; only the very first ``/admin`` sends.
3. **No business logic.** Handlers format, delegate and render. Every mutation
   goes through :class:`bot.admin.client.AdminBotClient` to the backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.admin import ops
from bot.admin.client import AdminAPIError, AdminBotClient
from bot.admin.config import ACCESS_DENIED_TEXT, AdminConfig, load_config
from bot.admin.formatters import truncate
from bot.admin.states import selected_user_id

logger = logging.getLogger("bot.admin")

config: AdminConfig = load_config()


def get_client() -> AdminBotClient:
    """Build a client from the environment. Credentials never leave this object."""
    return AdminBotClient(config.backend_url, config.service_token, timeout=config.request_timeout)


def is_admin(telegram_id: int | None) -> bool:
    return config.is_admin(telegram_id)


def telegram_id(target: Message | CallbackQuery) -> int:
    """The acting admin's Telegram id, straight from the event."""
    return int(target.from_user.id)


@dataclass(slots=True)
class PendingOperation:
    """A mutation waiting for its confirm button."""

    action: str
    payload: dict[str, Any]
    title: str
    rows: list[str]
    confirm_text: str = "✅ Confirm"


async def stage(
    context: FSMContext,
    action: str,
    payload: dict[str, Any],
    title: str,
    rows: list[str],
    *,
    confirm_text: str = "✅ Confirm",
) -> str:
    """Register a pending operation and return its unpredictable id."""
    operation_id = ops.new_operation_id()
    await ops.put(
        context,
        operation_id,
        {
            "action": action,
            "payload": payload,
            "title": title,
            "rows": rows,
            "confirm_text": confirm_text,
        },
    )
    return operation_id


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
async def render(
    target: Message | CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    *,
    answer: bool = False,
) -> None:
    """Edit the panel in place, tolerating "message is not modified"."""
    message = target.message if isinstance(target, CallbackQuery) else target
    text = truncate(text)
    try:
        if answer or message is None:
            await target.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]
            return
        if keyboard is None:
            await message.edit_text(text)
        else:
            await message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        # Telegram refuses an edit that changes nothing; that is not a failure.
        if "message is not modified" in str(exc).lower():
            if keyboard is not None and message is not None and message.reply_markup != keyboard:
                try:
                    await message.edit_reply_markup(reply_markup=keyboard)
                except TelegramBadRequest:
                    pass
            return
        if answer and message is None:
            await target.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]
            return
        raise


async def toast(target: CallbackQuery | Message, text: str) -> None:
    """Show a short non-blocking notice (also answers the callback query)."""
    try:
        await target.answer(text, show_alert=False)
    except TelegramBadRequest:  # pragma: no cover - query too old
        if isinstance(target, Message):
            await target.answer(text)


async def render_error(target: CallbackQuery | Message, exc: Exception) -> None:
    """Turn any backend error into one short operator-readable line."""
    if isinstance(exc, AdminAPIError):
        logger.info("admin call failed: %s (%s)", exc.code, exc.status)
        await render(target, f"{exc.display()}\n\n<i>операция не выполнена</i>", None)
        return
    logger.exception("unexpected admin failure")
    await render(
        target,
        "⚠️ Внутренняя ошибка панели.\n<i>подробности в серверном логе</i>",
        None,
    )


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------
def deny(target: CallbackQuery | Message) -> None:
    """Generic refusal. Never reveals who *is* an admin."""
    if isinstance(target, CallbackQuery):
        target.answer(ACCESS_DENIED_TEXT, show_alert=True)


async def require_user(context: FSMContext, target: CallbackQuery | Message) -> int | None:
    """Return the selected player, or prompt the admin to pick one."""
    user_id = await selected_user_id(context)
    if user_id is None:
        await render(
            target,
            "👤 <b>Игрок не выбран</b>\n\nНайдите игрока и откройте его карточку.",
            None,
        )
    return user_id


def guard(handler: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    """Middleware that rejects any event from a non-admin.

    Applied to the whole admin router, so no individual handler can forget it.
    """

    async def wrapper(event: CallbackQuery | Message, *args: Any, **kwargs: Any) -> None:
        user = event.from_user
        if not config.is_admin(user.id if user else None):
            if not config.enabled:
                logger.warning("admin panel is disabled: ADMIN_TELEGRAM_IDS or SERVICE_TOKEN is unset")
            deny(event)
            return
        await handler(event, *args, **kwargs)

    wrapper.__name__ = getattr(handler, "__name__", "wrapper")
    wrapper.__doc__ = handler.__doc__
    return wrapper


def data_of(context: FSMContext, key: str, default: Any = None) -> Any:
    return (context.data or {}).get(key, default)


async def refresh_commands(bot: Bot) -> None:
    """Publish the command list, with ``/admin`` only for admins."""
    from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

    from bot.admin.config import ADMIN_COMMANDS, USER_COMMANDS

    default = [BotCommand(**{"command": cmd, "description": text}) for cmd, text in USER_COMMANDS]
    await bot.set_my_commands(default, scope=BotCommandScopeDefault())
    for telegram_id in sorted(config.admin_ids):
        scoped = default + [
            BotCommand(**{"command": cmd, "description": text}) for cmd, text in ADMIN_COMMANDS
        ]
        try:
            await bot.set_my_commands(scoped, scope=BotCommandScopeChat(telegram_id))
        except TelegramBadRequest:  # pragma: no cover - admin has never started the bot
            logger.debug("could not scope commands for %s", telegram_id)


__all__ = [
    "ACCESS_DENIED_TEXT",
    "PendingOperation",
    "config",
    "data_of",
    "deny",
    "get_client",
    "guard",
    "is_admin",
    "ops",
    "refresh_commands",
    "render",
    "render_error",
    "require_user",
    "stage",
    "toast",
]