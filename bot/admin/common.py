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

import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.admin import ops
from bot.admin.client import AdminAPIError, AdminAPIUnavailable, AdminBotClient
from bot.admin.config import ACCESS_DENIED_TEXT, AdminConfig, load_config
from bot.admin.formatters import truncate
from bot.admin.states import get_data, selected_user_id

logger = logging.getLogger("bot.admin")

_resolved: AdminConfig | None = None


def get_config() -> AdminConfig:
    """Resolve the admin configuration from the environment, once.

    Deliberately lazy: the panel modules can be imported before ``bot.py`` has
    called ``load_dotenv()``, and snapshotting the environment at import time
    would silently produce an empty admin list - i.e. ``/admin`` would refuse
    everyone with "Access denied".
    """
    global _resolved
    if _resolved is None:
        _resolved = load_config()
    return _resolved


def reload_config() -> AdminConfig:
    """Re-read the environment (used by tests and after a settings change)."""
    global _resolved
    _resolved = load_config()
    return _resolved


class _LazyConfig:
    """Attribute proxy so ``config.admin_ids`` resolves on first use."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return getattr(get_config(), name)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return repr(get_config())


config = _LazyConfig()


def get_client() -> AdminBotClient:
    """Build a client from the environment. Credentials never leave this object."""
    resolved = get_config()
    return AdminBotClient(resolved.backend_url, resolved.service_token, timeout=resolved.request_timeout)


def is_admin(telegram_id: int | None) -> bool:
    return config.is_admin(telegram_id)


def telegram_id(target: Message | CallbackQuery) -> int:
    """The acting admin's Telegram id, straight from the event.

    Never read it from ``callback.message``: a message that arrived in a channel has
    no ``from_user`` at all, and a message forwarded by somebody else would
    attribute the action to the wrong operator.
    """
    user = target.from_user
    if user is None or user.id is None:
        raise PermissionError("the acting admin is unknown for this event")
    return int(user.id)


def actor_of(target: Message | CallbackQuery) -> int | None:
    """Like :func:`telegram_id` but ``None`` instead of raising."""
    user = getattr(target, "from_user", None)
    return int(user.id) if user is not None and user.id is not None else None


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
def _is_callback(event: Any) -> bool:
    """True for a ``CallbackQuery``.

    Duck-typed on the ``data`` attribute instead of ``isinstance`` so the panel
    also works with aiogram-compatible test doubles.
    """
    return isinstance(event, CallbackQuery) or hasattr(event, "data")


def _message_of(event: Any) -> Message | None:
    """The panel message behind a callback. ``None`` for a plain message event."""
    return getattr(event, "message", None)


def _incoming_message(event: Any) -> Message | None:
    """The message the event *arrived with* - the one worth cleaning up."""
    inner = _message_of(event)
    if inner is not None:
        return inner
    return event if hasattr(event, "delete") else None


async def render(
    target: Message | CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    *,
    answer: bool = False,
) -> None:
    """Edit the panel in place, tolerating "message is not modified"."""
    message = _message_of(target)
    text = truncate(text)
    try:
        if answer or message is None:
            await target.answer(text, reply_markup=keyboard)
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
async def deny(target: CallbackQuery | Message) -> None:
    """Generic refusal. Never reveals who *is* an admin.

    The incoming command is removed as well (best effort - see
    :func:`bot.bot.delete_quietly`), so an unauthorised ``/admin`` leaves no
    trace in the chat either.
    """
    message = _incoming_message(target)
    if _is_callback(target):
        await target.answer(ACCESS_DENIED_TEXT, show_alert=True)
    else:
        await target.answer(ACCESS_DENIED_TEXT)

    if message is None:
        return
    try:
        from bot.bot import delete_quietly

        await delete_quietly(message)
    except Exception:  # pragma: no cover - cleanup must never mask the refusal
        logger.debug("could not clean up a refused message", exc_info=True)


def guard(handler: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    """Middleware that rejects any event from a non-admin.

    Applied to every handler in the package, so no individual handler can forget
    the check.

    Two deliberate deviations from a plain ``functools.wraps`` wrapper, both about
    how aiogram decides what to inject:

    * ``__wrapped__`` is **not** set. ``CallableObject`` calls
      ``inspect.unwrap(callback)`` and then builds the argument list from the
      *unwrapped* signature, so a wrapper advertising ``(event, *args, **kwargs)``
      through ``wraps`` would still receive only the parameters the inner handler
      declares - and would therefore never see the ``state`` aiogram provides.
    * The ``FSMContext`` aiogram injects as ``state`` is forwarded under the name
      the inner handler asks for. Every handler in this package spells it
      ``context``; without the rename every one of them raises
      ``TypeError: missing 1 required positional argument: 'context'`` on every
      single event, which is precisely the bug that made the panel unusable.

    The metadata that matters to humans, aiogram and the tests is copied by hand,
    which keeps handler names visible without re-introducing ``__wrapped__``.
    """
    wants_context = "context" in inspect.signature(handler).parameters
    signature = inspect.signature(handler)
    accepted = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
    }
    takes_everything = any(
        parameter.kind == parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )

    async def wrapper(event: CallbackQuery | Message, *args: Any, **kwargs: Any) -> None:
        user = event.from_user
        if not config.is_admin(user.id if user else None):
            if not config.enabled:
                logger.warning("admin panel is disabled: ADMIN_TELEGRAM_IDS or SERVICE_TOKEN is unset")
            await deny(event)
            return
        call_kwargs = dict(kwargs) if takes_everything else {key: value for key, value in kwargs.items() if key in accepted}
        if wants_context and "context" not in call_kwargs:
            # The FSMContext can arrive two ways: injected by aiogram as ``state``,
            # or passed positionally when a guarded handler calls another guarded
            # handler directly (the panel does this to refresh a screen). In the
            # positional case it must *not* also be injected by keyword.
            positional = next((value for value in args if isinstance(value, FSMContext)), None)
            if positional is not None:
                await handler(event, *args, **call_kwargs)
                return True
            context = call_kwargs.get("state") or kwargs.get("state")
            if context is None:
                # No FSM in this scope: fail loudly instead of with a TypeError
                # three frames deeper.
                raise RuntimeError(
                    f"{getattr(handler, '__name__', handler)} needs an FSMContext but none was injected"
                )
            call_kwargs["context"] = context
        await handler(event, *args, **call_kwargs)
        # aiogram stops walking observers only when a handler returns something
        # truthy. Returning ``None`` here would let every panel callback fall
        # through to the reject-everything fallback and answer "Unknown action."
        # after already having rendered the right screen.
        return True

    for attribute in ("__name__", "__qualname__", "__doc__", "__module__"):
        setattr(wrapper, attribute, getattr(handler, attribute, type(handler).__name__))
    wrapper.__dict__.pop("__wrapped__", None)
    wrapper.__wrapped_by_guard__ = True  # type: ignore[attr-defined]
    wrapper.__panel_handler__ = handler  # type: ignore[attr-defined]
    return wrapper


async def data_of(context: FSMContext, key: str, default: Any = None) -> Any:
    """Read one flow value, falling back to ``default``."""
    return (await get_data(context)).get(key, default)


async def require_user(context: FSMContext, target: Any) -> int | None:
    """Return the selected player, or prompt the admin to pick one first."""
    user_id = await selected_user_id(context)
    if user_id is None:
        await render(
            target,
            "👤 <b>Игрок не выбран</b>\n\nНайдите игрока и откройте его карточку.",
            None,
        )
    return user_id


async def refresh_commands(bot: Bot) -> list[str]:
    """Publish the command list, with the admin commands scoped per operator.

    Returns the ids whose command list could not be published, so a failure is
    visible in the startup log instead of surfacing much later as "the commands are
    in the picker but nothing happens".

    Scoping matters: ``set_my_commands`` with ``BotCommandScopeDefault`` replaces the
    list *everybody* sees, so a single global list would advertise ``/admin`` to every
    player. ``BotCommandScopeChat`` publishes the admin list only into that operator's
    own chat, which is exactly the audience it belongs to.
    """
    from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

    from bot.admin.config import ADMIN_COMMANDS, USER_COMMANDS

    default = [BotCommand(command=cmd, description=text) for cmd, text in USER_COMMANDS]
    admin_commands = [BotCommand(command=cmd, description=text) for cmd, text in ADMIN_COMMANDS]

    await bot.set_my_commands(default, scope=BotCommandScopeDefault())
    failed: list[str] = []
    for telegram_id in sorted(config.admin_ids):
        try:
            # ``BotCommandScopeChat`` is keyword-only. Passing the id positionally
            # raises inside pydantic and takes the whole bot down on startup.
            await bot.set_my_commands(
                default + admin_commands,
                scope=BotCommandScopeChat(chat_id=telegram_id),
            )
        except TelegramAPIError as exc:
            # One unreachable chat must not cost every other operator their menu.
            logger.error("could not publish the admin command list: %s", exc)
            failed.append(str(telegram_id))
        logger.info("Admin commands published for Telegram id %s", telegram_id)
    return failed


async def verify_panel(bot: Bot, telegram_id: int) -> str | None:
    """Check at startup that the panel can actually reach and be served by the backend.

    Returns ``None`` when everything works, otherwise a short operator-readable
    reason. This is the difference between "the panel is broken" being discovered by
    an operator tapping ``/admin`` and it being reported in the startup log.
    """
    try:
        await get_client().dashboard(int(telegram_id))
    except AdminAPIUnavailable as exc:
        return f"backend unreachable ({exc.code})"
    except AdminAPIError as exc:
        return f"backend refused the panel call: {exc.code} (HTTP {exc.status})"
    except Exception as exc:  # pragma: no cover - defensive
        return f"{type(exc).__name__}: {exc}"
    return None


__all__ = [
    "ACCESS_DENIED_TEXT",
    "PendingOperation",
    "actor_of",
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
    "telegram_id",
    "toast",
    "verify_panel",
]
