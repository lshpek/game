"""End-to-end dispatcher routing for the admin panel.

These tests drive the real ``Dispatcher.feed_update`` pipeline with a real Bot
whose network layer is stubbed, so the whole chain is exercised: router order,
the admin guard, and the fact that ``/admin`` reaches the panel while ``/start``
still reaches the game.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import Chat, Message, Update, User

from bot.admin.common import ACCESS_DENIED_TEXT
from bot.admin.router import router as admin_router
from bot.admin.states import AdminStates
from bot.bot import ALLOWED_UPDATES
from bot.bot import router as player_router

ADMIN_ID = 1604952820
STRANGER_ID = 42

PANEL_MARKERS = ("NUMORA ADMIN CONTROL", "Юзеры", "Система")


class RecordingSession:
    """Records every Telegram call instead of performing it."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def make_request(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return SendMessage(
                message_id=99,
                date=datetime.datetime.now(),
                chat_id=method.chat_id,
                text="ok",
            )
        if isinstance(method, EditMessageText):
            return EditMessageText(ok=True, result=None)
        if isinstance(method, AnswerCallbackQuery):
            return AnswerCallbackQuery(ok=True)
        raise AssertionError(f"unexpected method {type(method).__name__}")


def _bodies(session: RecordingSession) -> list[str]:
    """Every text the bot tried to send or write."""
    return [str(call.text) for call in session.calls if hasattr(call, "text")]


@pytest.fixture(scope="module")
def session() -> RecordingSession:
    return RecordingSession()


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch: pytest.MonkeyPatch, session: RecordingSession) -> None:
    """No test may reach the real Telegram API."""
    monkeypatch.setattr(AiohttpSession, "make_request", session.make_request)
    monkeypatch.setattr(AiohttpSession, "close", lambda self: asyncio.sleep(0))
    session.calls.clear()


@pytest.fixture(scope="module")
def dispatcher() -> Dispatcher:
    """One dispatcher for the module: a Router may only be attached once."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.state = AdminStates
    dp.include_router(admin_router)
    dp.include_router(player_router)
    return dp


@pytest.fixture(scope="module")
def bot() -> Bot:
    # Offline token: the session is stubbed, so nothing is ever sent.
    return Bot(token="123456:AAEofflineTestToken")


def _message(text: str, user_id: int) -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=2,
            date=datetime.datetime.now(),
            chat=Chat(id=1, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Tester"),
            text=text,
        ),
    )


class TestCommandRouting:
    async def test_admin_command_reaches_the_admin_router(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _message("/admin", ADMIN_ID))
        handlers = [call for call in session.calls if isinstance(call, (SendMessage, EditMessageText))]
        assert handlers, "the panel produced no message"

    async def test_admin_aliases_work(self, dispatcher, bot, session):
        for alias in ("/panel", "/a"):
            session.calls.clear()
            await dispatcher.feed_update(bot, _message(alias, ADMIN_ID))
            assert any(isinstance(call, (SendMessage, EditMessageText)) for call in session.calls), alias

    async def test_non_admin_is_refused_generically(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _message("/admin", STRANGER_ID))
        bodies = [str(call.text) for call in session.calls if hasattr(call, "text")]
        assert bodies, "the refusal was not delivered"
        assert all(ACCESS_DENIED_TEXT in body for body in bodies)
        # Never leak who is an admin.
        assert all(str(ADMIN_ID) not in body for body in bodies)
        assert all("NUMORA ADMIN CONTROL" not in body for body in bodies)

    async def test_start_still_opens_the_game_for_admins(self, dispatcher, bot, session):
        """The admin router must not swallow the player command."""
        await dispatcher.feed_update(bot, _message("/start", ADMIN_ID))
        bodies = [str(call.text) for call in session.calls if hasattr(call, "text")]
        assert bodies
        assert any("Number Collector" in body for body in bodies)
        assert not any("ADMIN CONTROL" in body for body in bodies)

    async def test_help_still_works_for_everyone(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _message("/help", STRANGER_ID))
        bodies = [str(call.text) for call in session.calls if hasattr(call, "text")]
        assert any("/start" in body for body in bodies)

    def test_polling_requests_callback_updates(self):
        assert "callback_query" in ALLOWED_UPDATES
        assert "message" in ALLOWED_UPDATES


class TestConfigIsLazy:
    """Regression: the admin list must not be snapshotted before dotenv runs.

    ``bot.admin`` is importable on its own. If it read the environment at import
    time, a plain ``import bot.admin`` before ``load_dotenv()`` would leave the
    list empty and ``/admin`` would refuse everyone with "Access denied".
    """

    def test_config_resolves_after_dotenv(self, monkeypatch: pytest.MonkeyPatch):
        from bot.admin import common

        monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
        monkeypatch.delenv("SERVICE_TOKEN", raising=False)
        common.reload_config()
        assert common.get_config().admin_ids == frozenset()

        # Simulate .env being loaded *after* the import.
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", str(ADMIN_ID))
        monkeypatch.setenv("SERVICE_TOKEN", "token")
        common.reload_config()

        assert common.get_config().is_admin(ADMIN_ID) is True
        assert common.is_admin(ADMIN_ID) is True
        assert common.is_admin(STRANGER_ID) is False
        assert common.config.enabled is True
        monkeypatch.undo()
        common.reload_config()

    def test_client_is_built_from_the_lazy_config(self, monkeypatch: pytest.MonkeyPatch):
        from bot.admin import common

        monkeypatch.setenv("BACKEND_URL", "http://backend.test")
        common.reload_config()
        client = common.get_client()
        assert client._base_url == "http://backend.test"
        monkeypatch.undo()
        common.reload_config()
