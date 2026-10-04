"""End-to-end dispatcher routing for the admin panel.

These tests drive the real ``Dispatcher.feed_update`` pipeline with a real Bot
whose network layer is stubbed, so the whole chain is exercised: router order,
the admin guard, and the fact that ``/admin`` reaches the panel while ``/start``
still reaches the game.
"""

from __future__ import annotations

import datetime

from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import Chat, Message, Update, User

from bot.admin.common import ACCESS_DENIED_TEXT
from bot.bot import ALLOWED_UPDATES

ADMIN_ID = 1604952820
STRANGER_ID = 42


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


def _bodies(session) -> list[str]:
    """Every text the bot tried to send or write."""
    return [str(call.text) for call in session.of(SendMessage) + session.of(EditMessageText)]


class TestCommandRouting:
    async def test_admin_command_reaches_the_admin_router(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _message("/admin", ADMIN_ID))
        assert session.of(SendMessage) or session.of(EditMessageText), "the panel produced no message"

    async def test_admin_aliases_work(self, dispatcher, bot, session):
        for alias in ("/panel", "/a"):
            session.reset()
            await dispatcher.feed_update(bot, _message(alias, ADMIN_ID))
            assert session.of(SendMessage) or session.of(EditMessageText), alias

    async def test_non_admin_is_refused_generically(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _message("/admin", STRANGER_ID))
        bodies = _bodies(session)
        assert bodies, "the refusal was not delivered"
        assert all(ACCESS_DENIED_TEXT in body for body in bodies)
        # Never leak who is an admin.
        assert all(str(ADMIN_ID) not in body for body in bodies)
        assert all("NUMORA ADMIN CONTROL" not in body for body in bodies)

    async def test_start_still_opens_the_game_for_admins(self, dispatcher, bot, session):
        """The admin router must not swallow the player command."""
        await dispatcher.feed_update(bot, _message("/start", ADMIN_ID))
        bodies = _bodies(session)
        assert bodies
        assert any("Number Collector" in body for body in bodies)
        assert not any("ADMIN CONTROL" in body for body in bodies)

    async def test_help_still_works_for_everyone(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _message("/help", STRANGER_ID))
        bodies = _bodies(session)
        assert any("How to play" in body or "/start" in body for body in bodies)

    def test_polling_requests_callback_updates(self):
        assert "callback_query" in ALLOWED_UPDATES
        assert "message" in ALLOWED_UPDATES


class TestConfigIsLazy:
    """Regression: the admin list must not be snapshotted before dotenv runs.

    ``bot.admin`` is importable on its own. If it read the environment at import
    time, a plain ``import bot.admin`` before ``load_dotenv()`` would leave the
    list empty and ``/admin`` would refuse everyone with "Access denied".
    """

    def test_config_resolves_after_dotenv(self, monkeypatch):
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

    def test_client_is_built_from_the_lazy_config(self, monkeypatch):
        from bot.admin import common

        monkeypatch.setenv("BACKEND_URL", "http://backend.test")
        common.reload_config()
        assert common.get_client()._base_url == "http://backend.test"
        monkeypatch.undo()
        common.reload_config()
