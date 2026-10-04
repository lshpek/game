"""Chat hygiene: /start is the only message a player keeps.

Drives the real ``Dispatcher.feed_update`` pipeline with a stubbed Telegram
session and asserts the resulting sequence of sends/edits/deletes.
"""

from __future__ import annotations

import asyncio
import datetime

import pytest
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage
from aiogram.types import Chat, Message, Update, User

ADMIN_ID = 1604952820
STRANGER_ID = 42


def _update(text: str, user_id: int = STRANGER_ID) -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=42,
            date=datetime.datetime.now(),
            chat=Chat(id=1, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Tester"),
            text=text,
        ),
    )


class TestStartCommand:
    async def test_start_deletes_the_command_and_keeps_the_play_message(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start"))

        # The player's /start is removed.
        assert [call.message_id for call in session.of(DeleteMessage)] == [42]

        # Exactly one bot message survives, and it carries the Play button.
        assert len(session.of(SendMessage)) == 1
        welcome = session.of(SendMessage)[0]
        assert "Number Collector" in str(welcome.text)
        assert welcome.reply_markup is not None
        keyboard = welcome.reply_markup.inline_keyboard
        assert len(keyboard) == 1
        button = keyboard[0][0]
        assert button.text == "🎰 Play"
        assert button.web_app is not None
        assert button.web_app.url.endswith("/numora")

    async def test_deep_link_start_is_forwarded_to_the_mini_app(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start ref_12345"))
        welcome = session.of(SendMessage)[0]
        assert "startapp=ref_12345" in welcome.reply_markup.inline_keyboard[0][0].web_app.url

    async def test_unknown_start_payload_is_dropped(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start somethingelse"))
        welcome = session.of(SendMessage)[0]
        assert "startapp" not in (welcome.reply_markup.inline_keyboard[0][0].web_app.url or "")

    async def test_repeated_start_edits_one_message(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start"))
        session.reset()
        await dispatcher.feed_update(bot, _update("/start"))

        assert session.of(SendMessage) == []
        assert session.of(EditMessageText), "the welcome message was not reused"
        assert [call.message_id for call in session.of(DeleteMessage)] == [42]


class TestEverythingElseIsRemoved:
    async def test_help_deletes_itself_and_reuses_the_message(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start"))
        session.reset()
        await dispatcher.feed_update(bot, _update("/help"))

        assert [call.message_id for call in session.of(DeleteMessage)] == [42]
        assert session.of(SendMessage) == [], "/help must not add a second message"
        assert session.of(EditMessageText), "/help must rewrite the welcome message"
        assert "How to play" in str(session.of(EditMessageText)[0].text)

    async def test_unknown_command_is_deleted_without_a_reply(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start"))
        session.reset()
        await dispatcher.feed_update(bot, _update("/whatever"))

        assert [call.message_id for call in session.of(DeleteMessage)] == [42]
        assert session.of(SendMessage) == []
        assert session.of(EditMessageText) == []

    async def test_plain_text_is_deleted_without_a_reply(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/start"))
        session.reset()
        await dispatcher.feed_update(bot, _update("привет"))

        assert [call.message_id for call in session.of(DeleteMessage)] == [42]
        assert session.of(SendMessage) == []
        assert session.of(EditMessageText) == []

    async def test_text_before_start_is_also_removed(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("привет"))
        assert [call.message_id for call in session.of(DeleteMessage)] == [42]
        assert session.of(SendMessage) == []


class TestAdminPanelStillWorks:
    async def test_admin_command_is_deleted_and_panel_is_sent(self, dispatcher, bot, session, monkeypatch):
        from bot.admin import common

        class _OfflineClient:
            """Stands in for the HTTP client so no request leaves the process."""

            async def dashboard(self, telegram_id: int) -> dict:
                return {
                    "users": {"total": 1, "new_today": 0, "active_today": 1},
                    "rolls": {"total": 1, "today": 1},
                    "collection": {"plates": 1, "countries": 1, "first_discoveries": 1},
                    "economy": {"circulation": 10, "issued_today": 10, "spent_today": 0},
                    "monetization": {"paid_purchases": 0, "stars_revenue": 0, "pro_active": 0},
                    "season": {"code": "S1", "is_active": True, "event_code": None},
                    "system": {"api": "ok", "database": "ok", "errors_recent": 0},
                    "recent_actions": [],
                    "generated_at": "2026-10-04T10:00:00+00:00",
                }

        monkeypatch.setattr(common, "get_client", _OfflineClient)
        await dispatcher.feed_update(bot, _update("/admin", ADMIN_ID))

        assert [call.message_id for call in session.of(DeleteMessage)] == [42]
        assert session.of(SendMessage), "the panel produced no message"
        assert any("NUMORA ADMIN CONTROL" in str(call.text) for call in session.of(SendMessage))

    async def test_non_admin_command_is_deleted_and_refused(self, dispatcher, bot, session):
        await dispatcher.feed_update(bot, _update("/admin", STRANGER_ID))

        assert [call.message_id for call in session.of(DeleteMessage)] == [42]
        bodies = [str(c.text) for c in session.of(SendMessage)]
        assert bodies
        assert all("Access denied" in body for body in bodies)


class TestCleanupSwitch:
    def test_cleanup_is_on_by_default(self):
        from bot.bot import CLEAN_CHAT, CLEAN_PRIVATE_ONLY

        assert CLEAN_CHAT is True
        assert CLEAN_PRIVATE_ONLY is True

    def test_cleanup_can_be_disabled(self, monkeypatch: pytest.MonkeyPatch):
        """A deployment without the delete permission must not spam errors."""
        from bot.bot import delete_quietly

        monkeypatch.setattr("bot.bot.CLEAN_CHAT", False)

        class _Msg:
            chat = Chat(id=1, type="private")

            async def delete(self) -> None:  # pragma: no cover - must not run
                raise AssertionError("delete must not be called when cleanup is off")

        assert asyncio.run(delete_quietly(_Msg())) is False
