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

from admin.router import router as admin_router
from admin.states import AdminStates
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
        from aiogram.methods import (
            AnswerCallbackQuery,
            DeleteMessage,
            EditMessageText,
            SendMessage,
            SetMyCommands,
        )

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
        if isinstance(method, SetMyCommands):
            return SetMyCommands(ok=True, result=True, commands=method.commands)
        if isinstance(method, AnswerCallbackQuery):
            # ``callback_query_id`` is mandatory: returning an incomplete object used
            # to raise a pydantic ValidationError inside aiogram, which every test
            # calling ``answer()``/``toast()`` then reported as a panel failure.
            return AnswerCallbackQuery(
                ok=True,
                result=True,
                callback_query_id=getattr(method, "callback_query_id", "unknown"),
            )
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
def _reset_admin_http_pool() -> None:
    """Drop the shared admin HTTP pool between tests.

    The pool is process-wide on purpose (one set of connections for the whole bot),
    but pytest-asyncio gives every test its own event loop, and an ``httpx`` client
    bound to a closed loop raises on reuse. Clearing it here keeps the pooling
    behaviour honest without weakening the production code path.
    """
    from admin import client as admin_client

    admin_client._CLIENTS.clear()
    yield
    admin_client._CLIENTS.clear()


@pytest.fixture(autouse=True)
def _offline_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """No admin handler may reach the network, even by accident.

    Tests that need the panel to render something inject their own client by
    patching ``admin.common.get_client``; anything else would silently build a
    real connection to ``BACKEND_URL``, which is why this is enforced globally.
    """
    from admin import client as admin_client

    def _refuse(timeout: float) -> Any:
        raise AssertionError("the admin panel attempted a real backend call")

    monkeypatch.setattr(admin_client, "_shared_client", _refuse)


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

    Two operators are pinned on purpose: the audit viewer's "mine" scope is only
    correct when it uses the *current* actor, and that is only provable with more
    than one admin in the allow list.

    The workspace runs both suites in one process, and the backend suite rewrites
    ``ADMIN_TELEGRAM_IDS`` while it boots. Pinning the value here keeps the bot
    tests deterministic no matter which suite ran first.
    """
    from admin import common
    from admin.config import AdminConfig

    monkeypatch.setattr(
        common,
        "config",
        AdminConfig(
            admin_ids=frozenset({1604952820, 1604952821}),
            service_token="test-service-token",
            backend_url="http://backend.test",
        ),
    )
