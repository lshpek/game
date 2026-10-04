"""Shared fixtures for the bot test-suite.

aiogram allows a ``Router`` to be attached to exactly one ``Dispatcher``, so the
dispatcher is session-scoped and shared by every test module.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from bot.admin.router import router as admin_router
from bot.admin.states import AdminStates
from bot.bot import router as player_router


class RecordingSession:
    """Records every Telegram call instead of performing it."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def reset(self) -> None:
        self.calls.clear()

    def of(self, kind: type) -> list[Any]:
        return [call for call in self.calls if isinstance(call, kind)]

    async def make_request(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        from aiogram.methods import AnswerCallbackQuery, DeleteMessage, EditMessageText, SendMessage

        self.calls.append(method)
        if isinstance(method, SendMessage):
            return SendMessage(
                message_id=1000 + len(self.calls),
                date=datetime.datetime.now(),
                chat_id=method.chat_id,
                text=method.text or "",
            )
        if isinstance(method, EditMessageText):
            return EditMessageText(ok=True, result=None)
        if isinstance(method, DeleteMessage):
            return DeleteMessage(ok=True, chat_id=method.chat_id, message_id=method.message_id)
        if isinstance(method, AnswerCallbackQuery):
            return AnswerCallbackQuery(ok=True)
        raise AssertionError(f"unexpected method {type(method).__name__}")


@pytest.fixture(scope="session")
def session() -> RecordingSession:
    return RecordingSession()


@pytest.fixture(scope="session")
def dispatcher() -> Dispatcher:
    """One dispatcher for the whole session: a Router may only be attached once."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.state = AdminStates
    dp.include_router(admin_router)
    dp.include_router(player_router)
    return dp


@pytest.fixture(scope="session")
def bot() -> Bot:
    """Offline bot: the token is never used because the session is stubbed."""
    instance = Bot(token="123456:AAEofflineTestToken")
    import bot.bot as bot_module

    bot_module.bot_instance = instance
    return instance


@pytest.fixture(autouse=True)
def _offline_telegram(monkeypatch: pytest.MonkeyPatch, session: RecordingSession) -> None:
    """No test may reach the real Telegram API, and none may leak state."""
    monkeypatch.setattr(AiohttpSession, "make_request", session.make_request)
    monkeypatch.setattr(AiohttpSession, "close", lambda self: asyncio.sleep(0))
    session.reset()

    import bot.bot as bot_module

    bot_module._welcome_messages.clear()
    bot_module._pending_cleanups.clear()


@pytest.fixture(autouse=True)
def _pinned_admin_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the admin list for the panel tests.

    The workspace runs both suites in one process, and the backend suite rewrites
    ``ADMIN_TELEGRAM_IDS`` while it boots. Pinning the value here keeps the bot
    tests deterministic no matter which suite ran first.
    """
    from bot.admin import common
    from bot.admin.config import AdminConfig

    monkeypatch.setattr(
        common,
        "config",
        AdminConfig(
            admin_ids=frozenset({1604952820}),
            service_token="test-service-token",
            backend_url="http://backend.test",
        ),
    )
