#!/usr/bin/env python
"""Telegram bot for the Number Collector Mini App.

Responsibilities:

* ``/start`` sends a button that opens the Mini App;
* deep-link payloads (``ref_<id>``, ``number_1337``, ``challenge_<code>``) are
  forwarded to the Mini App so Telegram delivers them through ``initData``;
* successful Telegram Stars payments are forwarded to the backend, which is the
  only component allowed to grant rewards.

The bot never mutates game state directly - it only routes.

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
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Configuration - loaded from the project-root .env (no python-dotenv needed
# for deployment: real env vars always win, the file is just the fallback).
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.getenv("BOT_ENV_FILE", PROJECT_ROOT / ".env"))
load_dotenv(ENV_FILE, override=False)

BOT_TOKEN = os.getenv("BOT_TOKEN", "CHANGE_ME")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "CHANGE_ME").lstrip("@")
MINI_APP_SHORT_NAME = os.getenv("MINI_APP_SHORT_NAME", "game")
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
START_PARAM_PREFIXES = ("ref_", "number_", "challenge_")
MAX_START_PARAM_LENGTH = 64

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot")

router = Router()
http: httpx.AsyncClient | None = None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def mini_app_url(start_param: str | None = None) -> str:
    """Public HTTPS URL of the Mini App (Telegram requires HTTPS off localhost)."""
    base = f"{FRONTEND_URL}/{MINI_APP_SHORT_NAME}"
    return f"{base}?startapp={start_param}" if start_param else base


def open_keyboard(start_param: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Play", web_app=WebAppInfo(url=mini_app_url(start_param)))]
        ]
    )


def normalize_start_param(raw: str | None) -> str | None:
    """Forward only payloads we recognise, and only when they look sane."""
    if not raw:
        return None
    value = raw.strip()
    for prefix in ("/start_", "start="):
        if value.startswith(prefix):
            value = value[len(prefix):]
    if len(value) > MAX_START_PARAM_LENGTH:
        return None
    return value if value.startswith(START_PARAM_PREFIXES) else None


def config_problems() -> list[str]:
    """Human-readable list of everything that stops the bot from working."""
    problems: list[str] = []
    if BOT_TOKEN in PLACEHOLDERS:
        problems.append("BOT_TOKEN is missing or still a placeholder (get one from @BotFather).")
    elif ":" not in BOT_TOKEN:
        problems.append("BOT_TOKEN is malformed - it must look like '123456789:AAE...'.")
    if FRONTEND_URL.startswith("http://") and FRONTEND_URL not in LOCALHOST_URLS:
        problems.append(
            f"FRONTEND_URL ({FRONTEND_URL}) is not HTTPS. Telegram only opens Mini Apps over "
            "HTTPS outside localhost."
        )
    return problems


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------
@router.message(CommandStart())
async def handle_start(message: types.Message) -> None:
    raw = message.text or ""
    payload = normalize_start_param(raw[len("/start"):]) if raw.startswith("/start") else None
    await message.answer(
        "🎰 Number Collector\n\nRoll random four-digit numbers, collect them and compete with friends.",
        reply_markup=open_keyboard(payload),
    )


@router.message(Command("help"))
async def handle_help(message: types.Message) -> None:
    await message.answer(
        "/start - open the game\n/help - this message\n\nRoll numbers, open boxes and share your best find!",
        reply_markup=open_keyboard(),
    )


async def forward_payment_update(update: dict[str, Any]) -> None:
    """Forward successful payments to the backend for idempotent granting."""
    if SERVICE_TOKEN in PLACEHOLDERS:
        logger.warning("SERVICE_TOKEN is not configured; payment updates will not be forwarded.")
        return
    if http is None:
        logger.warning("HTTP client is not initialised; skipping payment forwarding.")
        return
    try:
        response = await http.post(
            f"{BACKEND_URL}/api/payments/telegram/webhook",
            json=update,
            headers={"X-Service-Token": SERVICE_TOKEN},
        )
        logger.info("Payment update forwarded: HTTP %s", response.status_code)
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        logger.error("Failed to forward payment update: %s", exc)


@router.message(F.successful_payment)
async def handle_successful_payment(message: types.Message) -> None:
    payment = message.successful_payment
    logger.info("Successful payment: payload=%s amount=%s", payment.invoice_payload, payment.total_amount)
    await forward_payment_update(message.model_dump(mode="json"))
    await message.answer("Payment received. Your rewards are being added — open the game to see them! 🎉")


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------
async def on_startup(bot: Bot) -> None:
    """aiogram injects the Bot instance, so no dispatcher lookup is needed."""
    me = await bot.get_me()
    logger.info("Bot connected as @%s (id=%s)", me.username, me.id)
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Open the game"),
            types.BotCommand(command="help", description="Help"),
        ]
    )


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
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    dispatcher.startup.register(on_startup)

    try:
        if WEBHOOK_URL:
            logger.info("Starting webhook on %s", WEBHOOK_URL)
            await dispatcher.start_webhook(
                bot,
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET or None,
                allowed_updates=["message"],
            )
        else:
            logger.info("Starting long polling (set TELEGRAM_WEBHOOK_URL to use a webhook)")
            await dispatcher.start_polling(bot, allowed_updates=["message"])
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as exc:
        logger.error("Bot stopped: %s", explain_error(exc))
        return 1
    finally:
        if http is not None:
            await http.aclose()
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
    logger.info("  Env file             : %s (%s)", ENV_FILE, "found" if ENV_FILE.is_file() else "missing")
    logger.info("  Mode                 : %s", "webhook" if WEBHOOK_URL else "polling")

    problems = config_problems()
    if problems:
        logger.error("Configuration problems:")
        for problem in problems:
            logger.error("  - %s", problem)
        return 1

    logger.info("Handlers registered: %s", len(router.message.handlers))
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
