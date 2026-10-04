#!/usr/bin/env python
"""Telegram bot for the Number Collector Mini App.

Responsibilities:

* ``/start`` sends a button that opens the Mini App;
* deep-link payloads (``ref_<id>``, ``number_1337``, ``challenge_<code>``) are
  forwarded to the Mini App so Telegram delivers them through ``initData``;
* successful Telegram Stars payments are forwarded to the backend, which is the
  only component allowed to grant rewards;
* ``/admin`` (also ``/panel`` and ``/a``) opens the internal admin control
  centre for the ids listed in ``ADMIN_TELEGRAM_IDS``.

The bot never mutates game state directly - it only routes. The admin panel
likewise only renders screens and forwards intent: every authorisation decision,
validation, mutation and audit entry happens in the backend, which the panel
reaches through the service-to-service ``/api/admin/bot/*`` API.

Usage::

    python bot.py            # start polling (needs a real BOT_TOKEN)
    python bot.py --check    # validate configuration without contacting Telegram
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramUnauthorizedError,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Configuration - loaded from the project-root .env (no python-dotenv needed
# for deployment: real env vars always win, the file is just the fallback).
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.getenv("BOT_ENV_FILE", PROJECT_ROOT / ".env"))
load_dotenv(ENV_FILE, override=False)

# ``python bot.py`` puts the script's own directory on sys.path, which would make
# ``bot`` resolve to this file instead of the package. Put the project root first
# so ``bot.admin`` imports resolve identically locally and inside the container.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from admin.client import close_shared_clients
from bot.admin.common import config as ADMIN_CONFIG
from bot.admin.common import refresh_commands, verify_panel
from bot.admin.formatters import esc
from bot.admin.router import router as admin_router
from bot.admin.states import AdminStates

BOT_TOKEN = os.getenv("BOT_TOKEN", "CHANGE_ME")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "CHANGE_ME").lstrip("@")
MINI_APP_SHORT_NAME = os.getenv("MINI_APP_SHORT_NAME", "numora")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "CHANGE_ME")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

PLACEHOLDERS = {"", "CHANGE_ME", "change_me", "CHANGEME"}
LOCALHOST_URLS = {
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
}
MAX_START_PARAM_LENGTH = 64

# --------------------------------------------------------------------------
# Deep links
#
# A collectible deep link is ``<kind>_<token>``. ``<kind>`` selects how the token is
# resolved, ``<token>`` is what actually travels on the wire - so internal database
# ids stay inside the backend and only a short public token is exposed.
#
#   plate_<id>          an existing collectible by catalogue id
#   collectible_<token> a collectible by its public share token
#   number_<id>         legacy four-digit number (kept for old links)
#   challenge_<code>    a head-to-head challenge
#   ref_<id>            a referral
#   country_<code>      jump straight into a country's album
#   album_<code>        jump straight into an album
# --------------------------------------------------------------------------
DEEPLINK_KINDS: frozenset[str] = frozenset(
    {
        "plate",
        "collectible",
        "number",
        "challenge",
        "ref",
        "country",
        "album",
    }
)
#: Only these kinds may carry a numeric argument that looks like an id.
NUMERIC_KINDS: frozenset[str] = frozenset({"plate", "number", "ref"})
#: Start params that must never be forwarded verbatim into a URL.
_BLOCKED_START_PARAMS = frozenset({"admin", "panel", "a"})


def normalize_start_param(raw: str | None) -> str | None:
    """Validate a Telegram ``/start`` payload and return it in canonical form.

    Only ``<kind>_<token>`` shapes with a sane token survive, so the payload can be
    forwarded to the Mini App without any further escaping or re-validation.
    """
    if not raw:
        return None
    value = raw.strip()
    for prefix in ("/start_", "start=", "/start "):
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
    if not value or len(value) > MAX_START_PARAM_LENGTH:
        return None
    kind, separator, token = value.partition("_")
    if not separator or kind.lower() not in DEEPLINK_KINDS or not token:
        return None
    kind = kind.lower()
    if kind in NUMERIC_KINDS and not token.isdigit():
        return None
    if kind in NUMERIC_KINDS and int(token) <= 0:
        return None
    if any(char.isspace() for char in token):
        return None
    if kind in _BLOCKED_START_PARAMS:
        return None
    return f"{kind}_{token}"

# Chat hygiene: the player sends /start once and the chat keeps exactly one bot
# message (the text plus the Play button). Everything else - the command itself,
# any other command, stray text, transient confirmations - is deleted again.
# Requires the bot to be an admin with the "Delete messages" permission; without
# it the bot silently keeps working and the chat just stays as it was.
CLEAN_CHAT = os.getenv("TELEGRAM_CLEAN_CHAT", "true").strip().lower() not in {"0", "false", "no", "off"}
CLEAN_PRIVATE_ONLY = os.getenv("TELEGRAM_CLEAN_PRIVATE_ONLY", "true").strip().lower() not in {"0", "false", "no", "off"}
CLEANUP_DELAY = float(os.getenv("TELEGRAM_CLEANUP_DELAY", "8"))

# Telegram must deliver callback_query updates for the admin panel's inline
# keyboards; message-only polling would silently break every button.
ALLOWED_UPDATES = ["message", "callback_query"]

# The one bot message each chat is meant to keep. In-memory is fine: if it is
# lost (restart, cleared history) the bot simply posts the welcome again.
_welcome_messages: dict[int, int] = {}

# Strong references to pending cleanup tasks so they are not collected early.
_pending_cleanups: set[asyncio.Task[None]] = set()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot")

router = Router()
http: httpx.AsyncClient | None = None

# Set during startup so helpers can edit the stored welcome message without
# threading the Bot through every call.
bot_instance: Bot | None = None

# Admin panel readiness, evaluated once so ``--check`` can report it.
ADMIN_PANEL_ENABLED = ADMIN_CONFIG.enabled
ADMIN_ADMIN_IDS = frozenset(ADMIN_CONFIG.admin_ids)
ADMIN_ADMIN_IDS_COUNT = len(ADMIN_ADMIN_IDS)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
WELCOME_TEXT = (
    "🔢 <b>NUMORA</b>\n"
    "<i>Global Number Collector</i>\n\n"
    "Hunt collectible numbers from every corner of the world.\n\n"
    "• 🚘 real vehicle plates from 30+ countries\n"
    "• 📱 synthetic phone numbers you will never see on a bill\n"
    "• 💎 COMMON → MYTHIC → SECRET rarities, computed from the number itself\n"
    "• 🌍 complete countries, categories and albums\n"
    "• 🏆 first discoveries, leaderboards, challenges, PRO\n\n"
    "Tap Play to start hunting."
)

HELP_TEXT = (
    "🔢 <b>NUMORA</b>\n<i>Global Number Collector</i>\n\n"
    "<b>How to play</b>\n"
    "1. Tap Play and open the game\n"
    "2. ROLL - each roll reveals one collectible number\n"
    "3. Hunt countries and categories: vehicles, phone numbers, more to come\n"
    "4. Chase rarities, finish albums and share your best find\n\n"
    "<b>Useful</b>\n"
    "• rarity comes from the structure of the number, not from a dice roll alone\n"
    "• collector value and dealer value are in-game fiction, not money\n"
    "• duplicates turn into NUMORA\n"
    "• PRO adds daily rolls and a duplicate multiplier\n"
    "• daily missions, streaks and challenges pay out every day\n\n"
    "Tap Play to open the game."
)


def mini_app_url(start_param: str | None = None) -> str:
    """Public HTTPS URL of the Mini App (Telegram requires HTTPS off localhost)."""
    base = f"{FRONTEND_URL}/{MINI_APP_SHORT_NAME}"
    return f"{base}?startapp={start_param}" if start_param else base


def open_keyboard(start_param: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎰 Play", web_app=WebAppInfo(url=mini_app_url(start_param)))]]
    )


async def delete_quietly(message: types.Message | None) -> bool:
    """Delete a message, tolerating every reason Telegram may refuse.

    Deleting someone else's message requires the bot to be an administrator, so
    this never raises: without the permission the chat simply stays as it was.
    """
    if message is None or not CLEAN_CHAT or message.chat is None:
        return False
    if CLEAN_PRIVATE_ONLY and message.chat.type != "private":
        return False
    try:
        await message.delete()
        return True
    except TelegramForbiddenError:
        _warn_delete_permission()
        return False
    except TelegramBadRequest:
        # "message to delete not found" - e.g. it was already removed.
        return False


_delete_warned = False


def _warn_delete_permission() -> None:
    global _delete_warned
    if _delete_warned:
        return
    _delete_warned = True
    logger.warning(
        "Cannot delete messages: promote the bot to admin with the 'Delete messages' permission to keep the chat clean."
    )


async def delete_after(message: types.Message | None, delay: float = 8.0) -> None:
    """Remove a bot message shortly after posting it.

    Used for confirmations the player should read but that must not pile up in
    the chat. Runs as a background task so the handler returns immediately.
    """

    async def _worker() -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:  # pragma: no cover - shutdown
            raise
        await delete_quietly(message)

    # Keep a reference so the task is not garbage collected mid-sleep.
    _pending_cleanups.add(asyncio.create_task(_worker()))


async def show_welcome(message: types.Message, start_param: str | None = None) -> None:
    """Post (or refresh) the single message the player is meant to keep.

    ``/start`` and ``/help`` both end up here, so the private chat ends up with
    exactly one bot message: the text plus the Play button.
    """
    keyboard = open_keyboard(start_param)
    chat_id = message.chat.id if message.chat else None

    existing = _welcome_messages.get(chat_id) if chat_id is not None else None
    if existing is not None and bot_instance is not None:
        try:
            await bot_instance.edit_message_text(
                text=WELCOME_TEXT, chat_id=chat_id, message_id=existing, reply_markup=keyboard
            )
            return
        except TelegramBadRequest:
            # The stored message is gone (cleared history, bot restarted, ...).
            _welcome_messages.pop(chat_id, None)

    sent = await message.answer(WELCOME_TEXT, reply_markup=keyboard)
    if chat_id is not None and sent is not None:
        _welcome_messages[chat_id] = sent.message_id


def config_problems() -> list[str]:
    """Human-readable list of everything that stops the bot from working."""
    problems: list[str] = []
    if BOT_TOKEN in PLACEHOLDERS:
        problems.append("BOT_TOKEN is missing or still a placeholder (get one from @BotFather).")
    elif ":" not in BOT_TOKEN:
        problems.append("BOT_TOKEN is malformed - it must look like '123456789:AAE...'.")
    if FRONTEND_URL.startswith("http://") and FRONTEND_URL not in LOCALHOST_URLS:
        problems.append(
            f"FRONTEND_URL ({FRONTEND_URL}) is not HTTPS. Telegram only opens Mini Apps over HTTPS outside localhost."
        )
    if CLEAN_CHAT and not problems:
        logger.info("Message cleanup is ON: incoming commands/text are deleted and only the Play message is kept.")
    return problems


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------
@router.message(CommandStart())
async def handle_start(message: types.Message) -> None:
    """``/start`` - the only message the player keeps in the chat."""
    raw = message.text or ""
    payload = normalize_start_param(raw[len("/start") :]) if raw.startswith("/start") else None
    await delete_quietly(message)
    await show_welcome(message, payload)


@router.message(Command("help"))
async def handle_help(message: types.Message) -> None:
    """``/help`` - deletes itself and rewrites the single welcome message."""
    await delete_quietly(message)
    chat_id = message.chat.id if message.chat else None
    existing = _welcome_messages.get(chat_id) if chat_id is not None else None
    if existing is not None and bot_instance is not None:
        try:
            await bot_instance.edit_message_text(
                text=HELP_TEXT, chat_id=chat_id, message_id=existing, reply_markup=open_keyboard()
            )
            return
        except TelegramBadRequest:
            _welcome_messages.pop(chat_id, None)
    await message.answer(HELP_TEXT, reply_markup=open_keyboard())


@router.message(F.successful_payment)
async def handle_successful_payment(message: types.Message) -> None:
    """Forward a paid invoice to the backend, which is the only grant authority.

    The player is told the outcome of the *forward*, never of the grant: the
    backend may legitimately fail and be retried by Telegram, so claiming the
    reward is granted here would be a lie the system cannot keep.
    """
    payment = message.successful_payment
    logger.info(
        "Successful payment: payload=%s amount=%s charge=%s",
        payment.invoice_payload,
        payment.total_amount,
        payment.telegram_payment_charge_id,
    )
    await delete_quietly(message)
    forwarded, detail = await forward_payment_update(message.model_dump(mode="json"))
    if forwarded:
        text = "✅ Payment received. Opening the game to show your reward 🎉"
    else:
        text = (
            "⚠️ Payment received, but the reward is still processing.\n"
            "It will be applied automatically — just reopen the game.\n"
            f"<i>reference: {esc(detail[:24])}</i>"
        )
    confirmation = await message.answer(text)
    await delete_after(confirmation, CLEANUP_DELAY)


@router.message(Command("panelcheck"))
async def handle_panel_check(message: types.Message) -> None:
    """Report why the admin panel is not working, in the operator's own chat.

    Registered **before** the filterless ``discard_everything_else``: a bare
    ``@router.message()`` matches every message, so anything placed after it is
    unreachable in practice. This command exists precisely because "the commands
    are in the picker but nothing happens" has no other explanation - it prints the
    things that can break it: the id, the allow list, the backend and whether the
    panel call actually succeeds.
    """
    try:
        await _panel_check(message)
    except Exception as exc:  # pragma: no cover - diagnostics must never fail
        logger.error("panelcheck failed", exc_info=True)
        await message.answer(f"⚠️ Проверка не завершилась: <code>{esc(type(exc).__name__)}</code>")


async def _panel_check(message: types.Message) -> None:
    actor_id = message.from_user.id if message.from_user else None
    if not ADMIN_PANEL_ENABLED:
        await message.answer(
            "⚠️ <b>Панель выключена</b>\n\n"
            "Нужны <code>ADMIN_TELEGRAM_IDS</code> и настоящий <code>SERVICE_TOKEN</code>."
        )
        return
    if actor_id not in ADMIN_ADMIN_IDS:
        await message.answer("🔒 Нет доступа.")
        return

    problem = await verify_panel(message.bot, int(actor_id))
    lines = [
        "🩺 <b>Проверка панели</b>",
        f"ваш id: <code>{actor_id}</code>",
        f"вы в списке админов: {'да' if actor_id in ADMIN_ADMIN_IDS else 'нет'}",
        f"bot token: {'задан' if BOT_TOKEN not in PLACEHOLDERS else 'НЕ ЗАДАН'}",
        f"service token: {'задан' if SERVICE_TOKEN not in PLACEHOLDERS else 'НЕ ЗАДАН'}",
        f"backend: <code>{esc(BACKEND_URL)}</code>",
        f"панель: {'✅ работает' if problem is None else '❌ ' + esc(problem)}",
    ]
    if problem is not None:
        lines.append("\n<i>Подробности в логе сервиса бота.</i>")
    await message.answer("\n".join(lines))


@router.message()
async def discard_everything_else(message: types.Message) -> None:
    """Last handler: no command, no text, nothing to keep.

    Stray messages (unknown commands, plain text, stickers in private chat) are
    simply removed so the chat only ever holds the Play message.

    Registered **last** on purpose. A filterless ``@router.message()`` matches every
    single message, so anything added after it is only reachable if the earlier
    handlers happen to decline.
    """
    await delete_quietly(message)


async def forward_payment_update(update: dict[str, Any]) -> tuple[bool, str]:
    """Forward a successful payment to the backend for idempotent granting.

    Returns ``(forwarded, detail)``. ``forwarded`` is only ``True`` when the
    backend *acknowledged* the update, so the caller never promises a reward it
    cannot prove. The backend keys the grant on the Telegram charge id, so a retry
    of this exact update replays instead of granting twice.
    """
    if SERVICE_TOKEN in PLACEHOLDERS:
        logger.error("SERVICE_TOKEN is not configured; payment updates cannot be forwarded.")
        return False, "SERVICE_TOKEN unset"
    if http is None:
        logger.error("HTTP client is not initialised; skipping payment forwarding.")
        return False, "client not ready"

    charge = str((update.get("message") or {}).get("successful_payment") or {}).get("telegram_payment_charge_id", "")
    url = f"{BACKEND_URL}/api/payments/telegram/webhook"
    headers = {
        "X-Service-Token": SERVICE_TOKEN,
        # Telegram's own secret token, when configured, is equally accepted.
        "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET or SERVICE_TOKEN,
    }

    # Three attempts with a short backoff: a transient 5xx or a connection reset
    # must not cost the player their purchase.
    for attempt in range(1, 4):
        try:
            response = await http.post(url, json=update, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("payment forward attempt %s failed: %s", attempt, type(exc).__name__)
            if attempt == 3:
                logger.error("giving up forwarding payment charge=%s: %s", charge, exc)
                return False, "network error"
            await asyncio.sleep(0.5 * attempt)
            continue

        status = response.status_code
        if status < 400:
            logger.info("payment charge=%s forwarded: HTTP %s", charge, status)
            return True, str(status)
        if 400 <= status < 500 and status != 429:
            # A rejected update will be rejected again; do not hammer the backend.
            logger.error(
                "payment charge=%s rejected permanently: HTTP %s %s",
                charge,
                status,
                response.text[:200].replace("\n", " "),
            )
            return False, f"HTTP {status}"
        logger.warning("payment forward attempt %s got HTTP %s", attempt, status)
        if attempt == 3:
            return False, f"HTTP {status}"
        await asyncio.sleep(0.5 * attempt)
    return False, "exhausted"


@router.callback_query()
async def ignore_foreign_callbacks(callback: types.CallbackQuery) -> None:
    """Swallow callbacks from keyboards the bot did not create.

    Without this, pressing a stale inline button would leave a spinner running
    until Telegram timed the query out.
    """
    await callback.answer()


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------
async def on_startup(bot: Bot) -> None:
    """aiogram injects the Bot instance, so no dispatcher lookup is needed."""
    global bot_instance
    bot_instance = bot

    me = await bot.get_me()
    logger.info("Bot connected as @%s (id=%s)", me.username, me.id)

    # Ordinary players see only /start and /help. The admin commands are scoped to
    # the configured ids, and the backend re-verifies them on every request.
    unscoped = await refresh_commands(bot)
    if unscoped:
        logger.error(
            "Admin commands are missing for Telegram id(s) %s - /admin will still work there, "
            "but the command will not be listed in the picker.",
            ", ".join(unscoped),
        )

    if not ADMIN_PANEL_ENABLED:
        logger.warning(
            "Admin panel disabled: set ADMIN_TELEGRAM_IDS and a non-placeholder SERVICE_TOKEN to enable /admin."
        )
        return

    # Prove the panel can actually be served before an operator taps /admin. A
    # broken backend, a wrong token or a routing mismatch is a startup problem, not
    # something to discover from "the commands are there but nothing happens".
    for telegram_id in sorted(ADMIN_ADMIN_IDS):
        problem = await verify_panel(bot, telegram_id)
        if problem is None:
            logger.info("Admin panel verified for Telegram id %s", telegram_id)
        else:
            logger.error("Admin panel BROKEN for Telegram id %s: %s", telegram_id, problem)
            logger.info("  Player facing hint: run `/panelcheck` in the bot chat for details.")


def explain_error(exc: Exception) -> str:
    """Turn aiogram's terse errors into something actionable."""
    if isinstance(exc, TelegramUnauthorizedError):
        return (
            "Telegram rejected BOT_TOKEN (HTTP 401). Copy a fresh token from @BotFather "
            "and make sure the .env file is the one the bot loads."
        )
    if isinstance(exc, TelegramNetworkError):
        return f"Cannot reach the Telegram API: {getattr(exc, 'message', exc)}"
    return f"{type(exc).__name__}: {exc}"


async def run() -> int:
    """Start the bot and block until interrupted."""
    problems = config_problems()
    if problems:
        logger.error("Bot configuration is incomplete:")
        for problem in problems:
            logger.error("  - %s", problem)
        logger.error("Fill the values in the project-root .env file (see .env.example).")
        return 1

    global http
    http = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    # MemoryStorage is enough: the panel's state is short-lived per-admin text
    # input, and aiogram keys it by (bot, chat, user) so two admins never collide.
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.state = AdminStates
    # The admin router is registered first so its guard sees every event, and it
    # is an outer router: player commands still fall through to ``router``.
    dispatcher.include_router(admin_router)
    dispatcher.include_router(router)
    dispatcher.startup.register(on_startup)

    try:
        if WEBHOOK_URL:
            logger.info("Starting webhook on %s", WEBHOOK_URL)
            await dispatcher.start_webhook(
                bot,
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET or None,
                allowed_updates=ALLOWED_UPDATES,
            )
        else:
            logger.info("Starting long polling (set TELEGRAM_WEBHOOK_URL to use a webhook)")
            await dispatcher.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as exc:
        logger.error("Bot stopped: %s", explain_error(exc))
        return 1
    finally:
        if http is not None:
            await http.aclose()
        # Release the admin panel's pooled backend connections too.
        await close_shared_clients()
        # Always release aiogram's aiohttp session, even on the error path.
        await bot.session.close()
    return 0


def check() -> int:
    """``--check`` mode: validate config and imports without contacting Telegram."""
    logger.info("Checking bot configuration...")
    logger.info("  BOT_TOKEN            : %s", "SET" if BOT_TOKEN not in PLACEHOLDERS else "MISSING")
    logger.info("  TELEGRAM_BOT_USERNAME: %s", BOT_USERNAME)
    logger.info("  MINI_APP_SHORT_NAME  : %s", MINI_APP_SHORT_NAME)
    logger.info("  FRONTEND_URL         : %s", FRONTEND_URL)
    logger.info("  Mini App URL         : %s", mini_app_url("ref_12345"))
    logger.info("  BACKEND_URL          : %s", BACKEND_URL)
    logger.info("  SERVICE_TOKEN        : %s", "SET" if SERVICE_TOKEN not in PLACEHOLDERS else "MISSING")
    logger.info("  ADMIN_TELEGRAM_IDS   : %s", ADMIN_ADMIN_IDS_COUNT or "MISSING")
    logger.info("  Admin panel          : %s", "ENABLED" if ADMIN_PANEL_ENABLED else "DISABLED")
    logger.info("  Env file             : %s (%s)", ENV_FILE, "found" if ENV_FILE.is_file() else "missing")
    logger.info("  Mode                 : %s", "webhook" if WEBHOOK_URL else "polling")
    logger.info("  Allowed updates      : %s", ", ".join(ALLOWED_UPDATES))

    problems = config_problems()
    if problems:
        logger.error("Configuration problems:")
        for problem in problems:
            logger.error("  - %s", problem)
        return 1

    logger.info("Player handlers registered: %s", len(router.message.handlers))
    logger.info("Admin handlers registered : %s", len(admin_router.callback_query.handlers))
    logger.info("Configuration OK.")
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return check()
    if not Path(__file__).is_file():  # pragma: no cover - defensive
        logger.error("bot.py is missing")
        return 1
    return asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
