"""Admin panel unit tests: routing, authorisation, confirmation flow, FSM parsing.

These tests never touch the network. The HTTP client is replaced with a stub so
the panel's own behaviour - who may enter, which routes exist, what a confirm
button executes - is verified in isolation.
"""

from __future__ import annotations

from typing import Any

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from admin import keyboards as kb
from admin import ops
from admin.common import ACCESS_DENIED_TEXT, guard
from admin.config import AdminConfig, _parse_admin_ids
from admin.router import router
from admin.states import AdminStates, clear_flow_data, selected_user_id, set_selected_user

ADMIN_ID = 1604952820
STRANGER_ID = 42


def _key(user_id: int = ADMIN_ID) -> StorageKey:
    return StorageKey(bot_id=1, chat_id=5, user_id=user_id)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
class StubUser:
    def __init__(self, telegram_id: int) -> None:
        self.id = telegram_id


class StubMessage:
    def __init__(self) -> None:
        self.text: str | None = None
        self.edited: str | None = None
        self.markup: Any = None
        self.answered: str | None = None
        self.reply_markup: Any = None

    async def edit_text(self, text: str, reply_markup: Any = None) -> None:
        self.edited = text
        self.markup = reply_markup
        self.reply_markup = reply_markup

    async def edit_reply_markup(self, reply_markup: Any = None) -> None:
        self.markup = reply_markup
        self.reply_markup = reply_markup

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answered = text
        self.reply_markup = reply_markup


class StubCallback:
    def __init__(self, telegram_id: int, data: str = "") -> None:
        self.from_user = StubUser(telegram_id)
        self.data = data
        self.message = StubMessage()
        self.answers: list[str] = []
        self.alerts: list[bool] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answers.append(text)
        self.alerts.append(show_alert)


@pytest.fixture
def context() -> FSMContext:
    return FSMContext(MemoryStorage(), _key())


@pytest.fixture(autouse=True)
def _admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the shared config at a known admin id for the whole module.

    ``bot/tests/conftest.py`` already pins it; this keeps the module self-contained
    if it is ever run on its own.
    """
    monkeypatch.setattr(
        "admin.common.config",
        AdminConfig(admin_ids=frozenset({ADMIN_ID}), service_token="test-token"),
    )


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------
class TestAdminConfig:
    def test_parses_a_plain_id(self):
        assert _parse_admin_ids("1604952820") == frozenset({1604952820})

    def test_parses_a_comma_separated_list(self):
        assert _parse_admin_ids("1, 2 ,3") == frozenset({1, 2, 3})

    def test_ignores_junk_and_empty_entries(self):
        assert _parse_admin_ids("1,,abc,  ,2") == frozenset({1, 2})

    def test_empty_value_means_no_admins(self):
        assert _parse_admin_ids(None) == frozenset()
        assert _parse_admin_ids("") == frozenset()

    def test_is_admin_requires_a_configured_id(self):
        allowed = AdminConfig(admin_ids=frozenset({ADMIN_ID}), service_token="t")
        assert allowed.is_admin(ADMIN_ID) is True
        assert allowed.is_admin(STRANGER_ID) is False
        assert allowed.is_admin(None) is False

    def test_panel_needs_both_ids_and_a_token(self):
        assert AdminConfig(admin_ids=frozenset({1}), service_token="t").enabled is True
        assert AdminConfig(admin_ids=frozenset({1}), service_token="").enabled is False
        assert AdminConfig(admin_ids=frozenset(), service_token="t").enabled is False


# ---------------------------------------------------------------------------
# callback data
# ---------------------------------------------------------------------------
class TestCallbackData:
    def test_roundtrip(self):
        data = kb.pack(kb.USER_OPEN, 42)
        assert data == "a:uo:42"
        assert kb.unpack(data) == ["a", "uo", "42"]

    def test_stays_inside_the_telegram_limit(self):
        assert len(kb.pack(kb.USER_OPEN, 999_999_999).encode()) <= kb.CB_LEN

    def test_every_shipped_route_is_short_enough(self):
        for route in (kb.HOME, kb.USERS, kb.TESTLAB, kb.AUDIT, kb.CONFIRM):
            assert len(kb.pack(route, "x" * 16).encode()) <= kb.CB_LEN

    def test_foreign_callbacks_are_not_parsed_as_panel_routes(self):
        assert kb.unpack("start") == []
        assert kb.unpack("") == []


# ---------------------------------------------------------------------------
# pending operations
# ---------------------------------------------------------------------------
class TestPendingOperations:
    async def test_put_get_pop(self, context: FSMContext):
        await ops.put(context, "abc", {"action": "coins"})
        assert await ops.get(context, "abc") == {"action": "coins"}

        popped = await ops.pop(context, "abc")
        assert popped == {"action": "coins"}
        assert await ops.get(context, "abc") is None

    async def test_pop_returns_none_for_a_replayed_callback(self, context: FSMContext):
        await ops.put(context, "dup", {"action": "coins"})
        assert await ops.pop(context, "dup") is not None
        # Telegram double-tap: the same callback fires twice.
        assert await ops.pop(context, "dup") is None

    async def test_ids_are_unpredictable(self):
        ids = {ops.new_operation_id() for _ in range(200)}
        assert len(ids) == 200
        assert all(len(value) >= 10 for value in ids)

    async def test_buffer_is_bounded(self, context: FSMContext):
        for index in range(ops.MAX_PENDING + 10):
            await ops.put(context, f"op{index}", {"n": index})
        assert await ops.count(context) <= ops.MAX_PENDING


# ---------------------------------------------------------------------------
# authorisation guard
# ---------------------------------------------------------------------------
class TestGuard:
    async def test_non_admin_callback_is_rejected_with_a_generic_message(self):
        callback = StubCallback(STRANGER_ID, kb.pack(kb.HOME))
        calls: list[str] = []

        @guard
        async def handler(event, *args, **kwargs):
            calls.append("called")

        await handler(callback)
        assert calls == []
        assert callback.answers == [ACCESS_DENIED_TEXT]
        assert callback.message.edited is None

    async def test_non_admin_message_is_rejected(self):
        answered: list[str] = []

        class StubMessageEvent:
            def __init__(self) -> None:
                self.from_user = StubUser(STRANGER_ID)
                self.text = "/admin"

            async def answer(self, text: str, **kwargs) -> None:
                answered.append(text)

        @guard
        async def handler(event, *args, **kwargs):
            answered.append("called")

        await handler(StubMessageEvent())
        assert answered == [ACCESS_DENIED_TEXT]

    async def test_admin_passes_through(self):
        callback = StubCallback(ADMIN_ID, kb.pack(kb.HOME))
        calls: list[str] = []

        @guard
        async def handler(event, *args, **kwargs):
            calls.append("called")

        await handler(callback)
        assert calls == ["called"]

    async def test_denial_never_mentions_admin_ids(self):
        callback = StubCallback(STRANGER_ID, kb.pack(kb.HOME))

        @guard
        async def handler(event, *args, **kwargs):
            pass

        await handler(callback)
        assert str(ADMIN_ID) not in callback.answers[0]
        assert "admin" not in callback.answers[0].lower()


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------
class TestRouting:
    def _handlers(self, observer_name: str) -> list[Any]:
        """Handlers of the main router *and* every attached sub-router.

        aiogram only propagates sub-router observers once the router is attached
        to a Dispatcher, so the tests collect them explicitly.
        """
        found = list(getattr(router, observer_name).handlers)
        for sub in router.sub_routers:
            found.extend(getattr(sub, observer_name).handlers)
        return found

    def test_router_registers_the_core_sections(self):
        names = {
            handler.callback.__name__
            for handler in self._handlers("callback_query")
            if hasattr(handler.callback, "__name__")
        }
        for expected in (
            "go_home",
            "go_back",
            "refresh",
            "unknown_route",
            "users_menu",
            "user_open",
            "economy_menu",
            "confirm_operation",
            "cancel_operation",
            "lab_menu",
            "lab_simulate",
            "lab_live_prompt",
            "plates_menu",
            "ranks_menu",
            "countries_menu",
            "events_menu",
            "analytics_menu",
            "audit_menu",
            "system_menu",
            "ledger_menu",
        ):
            assert expected in names, expected

    def test_every_registered_handler_is_guarded(self):
        """No handler may bypass the admin check."""
        unguarded: list[str] = []
        for observer_name in ("callback_query", "message"):
            for observer in self._handlers(observer_name):
                if not getattr(observer.callback, "__wrapped_by_guard__", False):
                    unguarded.append(f"{observer_name}:{getattr(observer.callback, '__name__', '?')}")
        assert unguarded == []

    def test_state_aware_text_handlers_exist(self):
        states = {
            observer.callback.__name__: observer
            for observer in self._handlers("message")
            if hasattr(observer.callback, "__name__")
        }
        for expected in (
            "handle_start",
            "users_search_input",
            "coin_amount_input",
            "balance_input",
            "coin_reason_input",
            "xp_amount_input",
            "level_input",
            "premium_days_input",
            "roll_count_input",
            "lab_text_input",
            "plate_search_input",
            "reason_input",
        ):
            assert expected in states, expected


# ---------------------------------------------------------------------------
# FSM helpers
# ---------------------------------------------------------------------------
class TestFSMHelpers:
    async def test_selected_user_roundtrip(self, context: FSMContext):
        assert await selected_user_id(context) is None
        await set_selected_user(context, 42)
        assert await selected_user_id(context) == 42
        await set_selected_user(context, None)
        assert await selected_user_id(context) is None

    async def test_two_admins_do_not_share_state(self):
        first = FSMContext(MemoryStorage(), _key(1))
        second = FSMContext(MemoryStorage(), _key(2))
        await set_selected_user(first, 11)
        assert await selected_user_id(first) == 11
        assert await selected_user_id(second) is None

    async def test_clear_flow_data_keeps_the_selected_user(self, context: FSMContext):
        await set_selected_user(context, 42)
        await context.update_data(amount=100, kind="coins")
        await clear_flow_data(context)
        assert await selected_user_id(context) == 42
        assert (await context.get_data()).get("amount") is None

    async def test_clear_flow_data_can_drop_the_user_too(self, context: FSMContext):
        await set_selected_user(context, 42)
        await context.update_data(amount=100)
        await clear_flow_data(context, keep_user=False)
        assert await selected_user_id(context) is None


# ---------------------------------------------------------------------------
# FSM input parsing
# ---------------------------------------------------------------------------
class TestInputParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("100", 100),
            ("1 000", 1000),
            ("1_000", 1000),
            ("2,500", 2500),
            ("+250", 250),
            ("-250", -250),
            ("  42  ", 42),
        ],
    )
    def test_clean_number(self, raw, expected):
        from admin.players import _clean_number

        assert _clean_number(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abc", "12abc", "--5", None])
    def test_clean_number_rejects_junk(self, raw):
        from admin.players import _clean_number

        assert _clean_number(raw) is None

    def test_every_fsm_state_is_distinct(self):
        states = [
            AdminStates.search_user,
            AdminStates.coin_amount,
            AdminStates.coin_reason,
            AdminStates.balance_target,
            AdminStates.roll_count,
            AdminStates.xp_amount,
            AdminStates.xp_exact,
            AdminStates.streak_value,
            AdminStates.level_value,
            AdminStates.premium_days,
            AdminStates.plate_text,
            AdminStates.reason,
            AdminStates.cosmetic_code,
            AdminStates.achievement_code,
            AdminStates.mission_progress,
        ]
        assert len({state.state for state in states}) == len(states)


# ---------------------------------------------------------------------------
# formatters
# ---------------------------------------------------------------------------
class TestFormatters:
    def test_num_formats_with_spaces(self):
        from admin.formatters import num

        assert num(18450) == "18 450"
        assert num(None) == "-"

    def test_signed_marks_direction(self):
        from admin.formatters import signed

        assert signed(1000) == "+1 000"
        assert signed(-1000) == "-1 000"

    def test_esc_blocks_html_injection(self):
        from admin.formatters import esc

        assert esc("<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"
        assert "<" not in esc("<script>")
        assert "&" in esc("a & b")

    def test_home_screen_contains_no_raw_secrets(self):
        from admin.formatters import home

        payload = {
            "users": {"total": 1, "new_today": 0, "active_today": 1},
            "rolls": {"total": 2, "today": 1},
            "collection": {"plates": 3, "countries": 1, "first_discoveries": 1},
            "economy": {"circulation": 10, "issued_today": 5, "spent_today": 1},
            "monetization": {"paid_purchases": 1, "stars_revenue": 100, "pro_active": 1},
            "season": {"code": "S1", "is_active": True, "event_code": "E1"},
            "system": {"api": "ok", "database": "ok", "errors_recent": 0},
        }
        text = home(payload)
        assert "NUMORA ADMIN CONTROL" in text
        assert "secret" not in text.lower()

    def test_system_screen_renders_without_a_token(self):
        from admin.formatters import system

        text = system(
            {
                "api_health": "ok",
                "database_health": "ok",
                "version": "1.0.0",
                "environment": "test",
                "rate_limit_enabled": True,
                "service_token_set": False,
                "recent_errors": [],
            }
        )
        assert "НЕ НАСТРОЕН" in text
        assert "BOT_TOKEN" not in text

    def test_truncate_keeps_messages_within_the_telegram_limit(self):
        from admin.formatters import truncate

        assert len(truncate("x" * 10_000)) <= 4096

    def test_user_card_surfaces_the_key_fields(self):
        from admin.formatters import user_card

        text = user_card(
            {
                "id": 42,
                "telegram_id": 1604952820,
                "username": "alex",
                "display_name": "Alex",
                "coins": 18450,
                "collector_level": {"level": 17, "title_ru": "Коллекционер", "xp": 4280, "xp_for_level": 500},
                "premium": {"active": True, "expires_at": "2026-01-01T00:00:00+00:00"},
                "is_banned": False,
            }
        )
        assert "18 450" in text
        assert "1604952820" in text
        assert "уровень" in text.lower()


# ---------------------------------------------------------------------------
# keyboards
# ---------------------------------------------------------------------------
class TestKeyboards:
    def test_home_covers_every_section(self):
        markup = kb.home_keyboard()
        texts = [button.text for row in markup.inline_keyboard for button in row]
        assert len(markup.inline_keyboard) >= 6
        assert any("Юзеры" in text for text in texts)
        assert any("Экономика" in text for text in texts)
        assert any("Test Lab" in text for text in texts)
        assert any("Обновить" in text for text in texts)

    def test_every_button_has_a_valid_route(self):
        for markup in (
            kb.home_keyboard(),
            kb.economy_keyboard(),
            kb.user_keyboard(),
            kb.lab_keyboard(mode="SIMULATION", has_user=True),
            kb.plates_keyboard(),
            kb.audit_keyboard(page=2, has_more=True),
        ):
            for row in markup.inline_keyboard:
                for button in row:
                    assert button.callback_data
                    assert kb.unpack(button.callback_data)[0] == kb.PREFIX

    def test_confirmation_keyboard_only_carries_the_operation_id(self):
        markup = kb.confirm_keyboard("AbCdEfGhIjK")
        payloads = [button.callback_data for row in markup.inline_keyboard for button in row]
        assert payloads == ["a:cf:AbCdEfGhIjK", "a:cx:AbCdEfGhIjK"]
        # No amount, reason or player id may leak into a callback payload.
        assert all(":" not in value.split(":", 2)[2] for value in payloads)

    def test_submenus_offer_a_way_back(self):
        for markup in (
            kb.users_keyboard(),
            kb.economy_keyboard(),
            kb.progression_keyboard(),
            kb.plates_keyboard(),
            kb.cosmetics_keyboard(),
        ):
            texts = [button.text for row in markup.inline_keyboard for button in row]
            assert any("Назад" in text or "Главная" in text for text in texts)

    def test_protected_admin_gets_a_noop_ban_keyboard(self):
        markup = kb.ban_keyboard(is_banned=False, is_protected=True)
        payloads = [button.callback_data for row in markup.inline_keyboard for button in row]
        assert all(not payload.startswith(f"a:{kb.USER_BAN}") for payload in payloads)
