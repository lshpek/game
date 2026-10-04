"""Dispatcher-level routing tests for the admin panel.

Every test here drives the **real** ``Dispatcher.feed_update`` pipeline with a real
``Bot`` whose network layer is stubbed and a stubbed backend client. Nothing
inspects registered handler names, because that is exactly what let the original
routing bug ship: the panel registered a correct handler for every route *and* a
broad ``F.data.startswith("a:")`` fallback above them, so every callback below the
fallback answered "Unknown action" while the name-based test stayed green. The
same blindness hid a second, worse defect - every handler declaring
``context: FSMContext`` raised ``TypeError`` because aiogram only injects a
parameter named ``state``.

What is asserted here:

* every route a button can produce is answered by its own screen;
* the fallback only ever fires for genuinely unknown payloads;
* no route code is stolen by a broader ``startswith`` filter;
* ``AdminStates.reason`` has exactly one dispatcher;
* confirming twice, or replaying a callback, never executes twice.
"""

from __future__ import annotations

import datetime
import time
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from admin import keyboards as kb
from admin import ops
from admin.common import ACCESS_DENIED_TEXT
from admin.router import router as admin_router
from admin.routing import fallback_router, resolve_owner, resolved_routes
from admin.states import AdminStates

ADMIN_ID = 1604952820
ADMIN_ID_2 = 1604952821
STRANGER_ID = 42
PLATE_ID = 7
OTHER_USER_ID = 555

# Section headers the panel really renders. Kept as literals so a rename shows up
# here instead of silently weakening an assertion.
ADMIN_HEADER = "ADMIN"
ECONOMY_HEADER = "ЭКОНОМИКА"
LAB_HEADER = "TEST LAB"
NUMBERS_HEADER = "НОМЕРА"
RANK_HEADER = "ТОП"
REWARDS_HEADER = "НАГРАДЫ"
COSMETICS_HEADER = "КОСМЕТИКА"
COUNTRIES_HEADER = "СТРАН"
EVENTS_HEADER = "ИВЕНТ"
ANALYTICS_HEADER = "АНАЛИТИКА"
SYSTEM_HEADER = "СИСТЕМА"
SEARCH_RESULTS_HEADER = "РЕЗУЛЬТАТЫ"
REASON_HINT = "причина"


# ---------------------------------------------------------------------------
# backend stub
# ---------------------------------------------------------------------------
DASHBOARD: dict[str, Any] = {
    "users": {"total": 3, "new_today": 1, "active_today": 2},
    "rolls": {"total": 9, "today": 4},
    "collection": {"plates": 12, "countries": 3, "first_discoveries": 2},
    "economy": {"circulation": 5000, "issued_today": 200, "spent_today": 50},
    "monetization": {"paid_purchases": 1, "stars_revenue": 250, "pro_active": 1},
    "season": {"code": "S1", "is_active": True, "event_code": "E1"},
    "system": {"api": "ok", "database": "ok", "errors_recent": 0},
    "recent_actions": [
        {
            "id": 1,
            "action": "coins",
            "admin_telegram_id": ADMIN_ID,
            "target_user_id": OTHER_USER_ID,
            "reason": "test",
            "result": "OK",
            "amount": 100,
            "created_at": "2026-01-01T00:00:00",
        }
    ],
}

USER_DETAIL: dict[str, Any] = {
    "id": OTHER_USER_ID,
    "telegram_id": 999,
    "username": "hunter",
    "display_name": "Hunter",
    "coins": 4200,
    "bonus_rolls": 3,
    "is_banned": False,
    "is_protected_admin": False,
    "equipped_cosmetics": [],
    "collector_level": {"level": 7, "title_ru": "Охотник", "xp": 300, "xp_for_level": 500},
    "premium": {"active": False, "expires_at": None},
}

PLATE_DETAIL: dict[str, Any] = {
    "id": PLATE_ID,
    "plate_text": "A777AA 77",
    "normalized_text": "A777AA 77",
    "country_code": "RUS",
    "country_flag": "🇷🇺",
    "region_code": "77",
    "template_code": "ru_std",
    "template_pattern": "LDDDAA DD",
    "plate_type": "VEHICLE_PLATE",
    "rarity": "EPIC",
    "rarity_score": 700,
    "collector_value": 777000,
    "dealer_value": 77700,
    "currency_symbol": "₽",
    "traits": ["repeating"],
    "tags": ["luck"],
    "story": "A plate from the streets of Moscow.",
    "discovery_count": 3,
    "owner_count": 2,
    "is_secret": False,
    "visual_style": "ru",
    "first_discoverer": {"username": "hunter", "display_name": "Hunter"},
}

CATALOG: dict[str, Any] = {
    "countries": [
        {"code": f"C{n:02d}", "name_en": f"Country {n}", "name_ru": f"Страна {n}", "flag": "🏳"}
        for n in range(1, 61)
    ],
    "rarities": ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC", "SECRET"],
    "traits": ["repeating", "palindrome", "ascending", "mirrored", "low_entropy"],
    "categories": [
        {"code": "VEHICLE_PLATE", "label": "Vehicle plate"},
        {"code": "PHONE_NUMBER", "label": "Phone number"},
    ],
    "regions": [{"code": "77", "label": "Moscow"}, {"code": "16", "label": "Tatarstan"}],
    "presets": [
        {"code": "MYTHIC_USA", "label": "MYTHIC USA", "emoji": "🔥"},
        {"code": "FIRST_DISCOVERY", "label": "First discovery", "emoji": "🥇"},
    ],
}

PLAYER_DETAIL: dict[str, Any] = {
    "id": OTHER_USER_ID,
    "telegram_id": 999,
    "username": "hunter",
    "display_name": "Hunter",
    "coins": 4200,
    "wallet": {"coins": 4200, "lifetime_earned": 9000, "lifetime_spent": 4800},
    "bonus_rolls": 3,
    "rolls": {"bonus": 3, "daily_remaining": 5, "total": 40},
    "streak": {"current": 6, "best": 9},
    "progression": {"xp": 300, "level": 7, "xp_to_next": 200},
    "stats": {"level": 7, "rolls": 40, "plates": 12, "value": 900000},
    "missions": [],
    "completed_missions": 4,
    "achievements": [],
    "unlocked_achievements": 2,
    "premium": {"active": False, "expires_at": None, "source": None},
    "ban": {"banned": False, "reason": None},
    "equipped_cosmetics": [],
    "collector_level": {"level": 7, "title_ru": "Охотник", "xp": 300, "xp_for_level": 500},
    "is_banned": False,
    "is_protected_admin": False,
}

READ_ROUTES: dict[str, Any] = {
    "/dashboard": DASHBOARD,
    "/catalog": CATALOG,
    "/ranks": {
        "entries": [
            {"user_id": 1, "username": "one", "display_name": "One", "score": 100},
            {"user_id": 2, "username": "two", "display_name": "Two", "score": 50},
            {"user_id": 3, "username": "three", "display_name": "Three", "score": 10},
        ],
        "categories": ["COLLECTION", "COUNTRIES"],
        "periods": ["daily", "weekly"],
    },
    "/countries": {
        "items": [
            {
                "id": n,
                "code": f"C{n:02d}",
                "name_en": f"Country {n}",
                "name_ru": f"Страна {n}",
                "flag": "🏳",
                "is_active": n % 2 == 0,
                "plates": n,
                "config": {"category": "VEHICLE_PLATE"},
            }
            for n in range(1, 4)
        ],
        "total": 3,
    },
    "/events": {
        "items": [
            {
                "id": 1,
                "code": "USA_WEEK",
                "name_ru": "США неделя",
                "name_en": "USA week",
                "is_active": True,
                "ends_at": "2026-12-31",
                "starts_at": "2026-01-01",
                "theme": {"primary": "#ff0000"},
            }
        ],
        "total": 1,
    },
    "/cosmetics": {"items": [{"code": "frame_chrome", "kind": "FRAME", "name_ru": "Хром", "price_stars": 50}]},
    "/rewards/catalog": {
        "items": [{"code": "numora_100", "label": "100 NUMORA", "emoji": "💰", "grants": ["coins"]}]
    },
    "/transactions": {"items": [], "total": 0, "has_more": False},
    "/audit": {"items": [], "total": 0, "has_more": False},
    "/analytics": {
        "totals": {"users": 3, "rolls": 40, "numora": 5000},
        "series": [{"date": "2026-01-01", "rolls": 4, "numora": 200}],
        "rarity": [{"rarity": "COMMON", "count": 10}],
        "countries": [{"code": "RUS", "count": 5}],
        "top": [{"user_id": 1, "value": 100}],
    },
    "/system": {
        "api_health": "ok",
        "database_health": "ok",
        "recent_errors": [],
        "uptime_seconds": 3600,
    },
    "/errors": {"items": [], "total": 0, "has_more": False},
    "/plates": {"items": [PLATE_DETAIL], "page": 1, "total": 1, "has_more": False, "sort": "recent"},
}


class StubBackend:
    """Records every admin call and returns canned, shape-correct payloads."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.mutations: list[dict[str, Any]] = []

    # --- transport ------------------------------------------------------
    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"method": method, "path": path, **kwargs})
        if method != "GET":
            body = dict(kwargs.get("json") or {})
            self.mutations.append({"method": method, "path": path, **body})
            return {"success": True, "replayed": False, "audit_id": 1, "data": {"coins": 5000}}
        route = path.rstrip("/") or "/"
        if route in READ_ROUTES:
            return READ_ROUTES[route]
        if route == "/users":
            params = dict(kwargs.get("params") or {})
            return {
                "items": [] if params.get("query") else [PLAYER_DETAIL],
                "page": int(params.get("page") or 1),
                "total": 1,
                "has_more": False,
            }
        if route.startswith("/users/"):
            return PLAYER_DETAIL
        if route.startswith("/plates/"):
            return PLATE_DETAIL
        return {"items": []}

    # --- typed helpers mirroring ``AdminBotClient`` ----------------------
    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("GET", path, **kwargs)

    async def dashboard(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/dashboard", admin_telegram_id=telegram_id)

    async def catalog(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/catalog", admin_telegram_id=telegram_id)

    async def search_users(self, telegram_id: int, query: str | None, page: int = 1) -> dict[str, Any]:
        return await self.get("/users", admin_telegram_id=telegram_id, params={"query": query or "", "page": page})

    async def user_detail(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}", admin_telegram_id=telegram_id)

    async def user_economy(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/economy", admin_telegram_id=telegram_id)

    async def user_missions(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/missions", admin_telegram_id=telegram_id)

    async def user_achievements(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/achievements", admin_telegram_id=telegram_id)

    async def user_premium(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/premium", admin_telegram_id=telegram_id)

    async def cosmetics(self, telegram_id: int, query: str | None = None) -> dict[str, Any]:
        return await self.get("/cosmetics", admin_telegram_id=telegram_id, params={"query": query or ""})

    async def plates(self, telegram_id: int, **params: Any) -> dict[str, Any]:
        return await self.get("/plates", admin_telegram_id=telegram_id, params=params)

    async def plate(self, telegram_id: int, plate_id: int) -> dict[str, Any]:
        return await self.get(f"/plates/{plate_id}", admin_telegram_id=telegram_id)

    async def ranks(self, telegram_id: int, category: str, period: str) -> dict[str, Any]:
        return await self.get(
            "/ranks", admin_telegram_id=telegram_id, params={"category": category, "period": period}
        )

    async def countries(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/countries", admin_telegram_id=telegram_id)

    async def events(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/events", admin_telegram_id=telegram_id)

    async def analytics(self, telegram_id: int, period: str) -> dict[str, Any]:
        return await self.get("/analytics", admin_telegram_id=telegram_id, params={"period": period})

    async def system(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/system", admin_telegram_id=telegram_id)

    async def transactions(self, telegram_id: int, **params: Any) -> dict[str, Any]:
        return await self.get("/transactions", admin_telegram_id=telegram_id, params=params)

    async def audit(self, telegram_id: int, **params: Any) -> dict[str, Any]:
        return await self.get("/audit", admin_telegram_id=telegram_id, params=params)

    async def mutate(
        self, path: str, *, admin_telegram_id: int, operation_id: str, reason: str, **body: Any
    ) -> dict[str, Any]:
        return self.request(
            "POST", path, json={"operation_id": operation_id, "reason": reason, **body}
        )

    def reads(self, route: str) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["path"].rstrip("/") == route]

    def paths(self) -> list[str]:
        return [call["path"] for call in self.calls]


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> StubBackend:
    stub = StubBackend()
    # The admin modules import ``get_client`` by name, so patching only
    # ``admin.common`` would leave the handler modules holding the real one.
    for module in ("admin.common", "admin.router", "admin.world", "admin.players"):
        monkeypatch.setattr(f"{module}.get_client", lambda: stub, raising=False)
    return stub


def _callback(data: str, *, user_id: int = ADMIN_ID, message_id: int = 100) -> Update:
    return Update(
        update_id=abs(hash(data)) % 100000 + 1,
        callback_query=CallbackQuery(
            id=f"cb-{data}",
            from_user=User(id=user_id, is_bot=False, first_name="Admin"),
            chat_instance="ci",
            message=Message(
                message_id=message_id,
                date=datetime.datetime.now(),
                chat=Chat(id=user_id, type="private"),
                text="panel",
            ),
            data=data,
        ),
    )


def _text_message(text: str, *, user_id: int = ADMIN_ID, message_id: int = 200, bot: Bot | None = None) -> Update:
    return Update(
        update_id=abs(hash(text)) % 100000 + 1,
        message=_mounted(text, user_id=user_id, message_id=message_id, bot=bot),
    )


def _mounted(text: str, *, user_id: int = ADMIN_ID, message_id: int = 200, bot: Bot | None = None) -> Message:
    """A ``Message`` bound to a bot.

    ``Message.answer()`` and friends are aiogram shortcuts that require the object to
    be attached to a bot instance; handlers legitimately use them, so tests that
    call a handler directly have to mount the message the same way Telegram would.
    """
    message = Message(
        message_id=message_id,
        date=datetime.datetime.now(),
        chat=Chat(id=user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Admin"),
        text=text,
    )
    return message.as_(bot) if bot is not None else message


def _bodies(session) -> list[str]:
    return [str(call.text) for call in session.of(SendMessage) + session.of(EditMessageText)]


def _answers(session) -> list[str]:
    return [str(call.text) for call in session.of(AnswerCallbackQuery)]


def _markups(session) -> list[Any]:
    """Every markup the bot sent or edited during the last press."""
    return [
        call.reply_markup
        for call in session.of(SendMessage) + session.of(EditMessageText)
        if call.reply_markup is not None
    ]


def _last_markup(session) -> Any:
    markups = _markups(session)
    assert markups, "no keyboard was sent"
    return markups[-1]


def _payloads(session) -> list[str]:
    markup = _last_markup(session)
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _all_payloads(session) -> list[str]:
    """Every callback payload the bot rendered, oldest press included.

    A staged flow spans several messages (prompt, then confirmation), so the
    confirm button is not always on the last one.
    """
    out: list[str] = []
    for markup in _markups(session):
        out.extend(
            button.callback_data for row in markup.inline_keyboard for button in row
        )
    return out


def _context(dispatcher: Dispatcher | None = None, bot: Bot | None = None) -> FSMContext:
    """An ``FSMContext`` for the panel.

    When a dispatcher is supplied the context shares its storage and identity, so a
    state written here is the state the dispatcher will read next - which is how a
    test can stage an operation and then press Confirm for real.
    """
    if dispatcher is None or bot is None:
        return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=ADMIN_ID, user_id=ADMIN_ID))
    return FSMContext(
        dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=ADMIN_ID, user_id=ADMIN_ID)
    )


def _probe(data: str, actor: User) -> CallbackQuery:
    return CallbackQuery(
        id="probe",
        from_user=actor,
        chat_instance="probe",
        message=Message(
            message_id=1,
            date=datetime.datetime.now(),
            chat=Chat(id=actor.id, type="private"),
            text="probe",
        ),
        data=data,
    )


def _binds_state(handler: Any, state: Any) -> bool:
    """True when one of the handler's filters pins the FSM state.

    aiogram keeps the raw ``State`` (a ``str`` subclass) as the filter callback when
    the decorator was given a single state, and a ``StateFilter`` otherwise.
    """
    from aiogram.filters import StateFilter
    from aiogram.fsm.state import State

    for spec in handler.filters:
        candidate = getattr(spec, "callback", None)
        if isinstance(candidate, State):
            if candidate == state:
                return True
        elif isinstance(candidate, StateFilter):
            target = getattr(candidate, "state", None) or getattr(candidate, "states", None)
            items = target if isinstance(target, (tuple, list, set)) else (target,)
            if state in items:
                return True
    return False


async def _press(dispatcher, bot, session, backend, data: str, *, user_id: int = ADMIN_ID) -> list[str]:
    """Press a callback through the real dispatcher; return every text produced."""
    session.reset()
    backend.calls.clear()
    await dispatcher.feed_update(bot, _callback(data, user_id=user_id))
    return _bodies(session)


async def _say(dispatcher, bot, session, text: str, *, user_id: int = ADMIN_ID) -> list[str]:
    session.reset()
    await dispatcher.feed_update(bot, _text_message(text, user_id=user_id))
    return _bodies(session)


async def _open_user(dispatcher, bot, session, backend) -> list[str]:
    """Select a player so player-scoped routes are reachable."""
    bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.USER_OPEN, OTHER_USER_ID))
    assert bodies, "the player card produced no output"
    return bodies


def _confirm_payload(session) -> str:
    payload = next(
        (data for data in _all_payloads(session) if data.startswith(f"a:{kb.CONFIRM}:")), None
    )
    assert payload, "no confirm button was rendered"
    return payload


def _cancel_payload(session) -> str:
    payload = next(
        (data for data in _all_payloads(session) if data.startswith(f"a:{kb.CANCEL}:")), None
    )
    assert payload, "no cancel button was rendered"
    return payload


async def _noop_delete(message: Any) -> bool:  # pragma: no cover - chat hygiene stub
    return True


def _all_markups() -> dict[str, Any]:
    """Every shipped keyboard, built with representative arguments.

    A keyboard that cannot be built is a broken screen, so the matrix doubles as a
    smoke test of the builders themselves.
    """
    return {
        "home": kb.home_keyboard(),
        "users": kb.users_keyboard(),
        "search": kb.search_results_keyboard([], page=1, has_more=False),
        "prompt": kb.prompt_keyboard(),
        "confirm": kb.confirm_keyboard("abc123XYZ-_"),
        "economy": kb.economy_keyboard(),
        "rolls": kb.rolls_keyboard(),
        "rewards": kb.rewards_keyboard(),
        "mission": kb.missions_item_keyboard(["rolls_5"]),
        "achievements": kb.achievements_item_keyboard([("first_roll", False)]),
        "premium": kb.premium_keyboard(),
        "ban": kb.ban_keyboard(False, False),
        "level": kb.progression_keyboard(),
        "streak": kb.streak_keyboard(),
        "cosmetic": kb.cosmetics_keyboard(),
        "cosmetics_found": kb.cosmetics_item_keyboard([{"code": "frame_chrome"}]),
        "rarities": kb.rarity_keyboard(["COMMON", "SECRET"]),
        "user_result": kb.user_result_keyboard(),
        "user_plates": kb.user_plates_keyboard(OTHER_USER_ID, page=2, has_more=True),
        "plate_list": kb.plate_list_keyboard(page=2, has_more=True, sort="rarest"),
        "plates": kb.plates_keyboard(),
        "plate": kb.plate_keyboard(PLATE_ID),
        "lab": kb.lab_keyboard(mode="LIVE", has_user=True),
        "preset": kb.preset_keyboard([{"code": "MYTHIC_USA", "label": "MYTHIC", "emoji": "🔥"}]),
        "ranks": kb.ranks_keyboard(["COLLECTION", "COUNTRIES"], ["daily"], [(1, "@one")]),
        "countries": kb.countries_keyboard(
            [{"id": 1, "code": "RUS", "flag": "🇷🇺", "is_active": True, "plates": 12}]
        ),
        "country_filter": kb.country_filter_keyboard([("RUS", "🇷🇺"), ("USA", "🇺🇸")], current="RUS"),
        "category_filter": kb.category_filter_keyboard(
            [("VEHICLE_PLATE", "Vehicle"), ("PHONE_NUMBER", "Phone")], current=None
        ),
        "rarity_filter": kb.rarity_filter_keyboard(["COMMON", "SECRET"], current="SECRET"),
        "country_picker": kb.country_keyboard([("RUS", "🇷🇺")], page=2, pages=5, query="ru"),
        "lab_category": kb.lab_category_keyboard([("PHONE_NUMBER", "Phone")], current="PHONE_NUMBER"),
        "lab_trait": kb.lab_trait_keyboard(["repeating", "palindrome"], current="repeating"),
        "lab_region": kb.lab_region_keyboard([("77", "Moscow")]),
        "events": kb.events_keyboard([{"id": 1, "code": "USA_WEEK", "is_active": True}]),
        "analytics": kb.analytics_keyboard("7d"),
        "audit": kb.audit_keyboard(page=2, has_more=True),
        "system": kb.system_keyboard(),
        "ledger": kb.ledger_keyboard(offset=2, has_more=True),
        "cosmetics_catalogue": kb.cosmetics_catalogue_keyboard(
            [{"code": "frame_chrome"}, {"code": "frame_gold"}]
        ),
        "rewards_catalogue": kb.rewards_catalogue_keyboard(
            [{"code": "numora_100", "label": "100 NUMORA", "emoji": "💰"}]
        ),
    }


# ---------------------------------------------------------------------------
# routing architecture
# ---------------------------------------------------------------------------
class TestRoutingArchitecture:
    def test_fallback_router_is_attached_last(self):
        """The reject-everything router must be the final sub-router.

        aiogram runs a router's own handlers before any sub-router, so a broad
        filter anywhere on ``admin`` would shadow the sub-routers entirely.
        """
        names = [sub.name for sub in admin_router.sub_routers]
        assert names == ["admin-world", "admin-players", fallback_router().name]
        assert names[-1] == "admin-fallback"

    def test_the_fallback_is_attached_exactly_once(self):
        assert sum(1 for sub in admin_router.sub_routers if sub.name == "admin-fallback") == 1

    async def test_only_the_fallback_accepts_an_unknown_payload(self):
        """A synthetic junk payload must resolve to ``unknown_route`` and nowhere else."""
        actor = User(id=ADMIN_ID, is_bot=False, first_name="Admin")
        assert await resolve_owner(admin_router, _probe(kb.pack("zzzz"), actor)) == "unknown_route"
        assert await resolve_owner(admin_router, _probe("not_a_panel_callback", actor)) is None

    async def test_every_advertised_route_resolves_to_a_real_handler(self):
        """No shipped button may resolve to the fallback or to nothing."""
        actor = User(id=ADMIN_ID, is_bot=False, first_name="Admin")
        resolved = await resolved_routes(admin_router, actor)
        unhandled = {code: owner for code, owner in resolved.items() if owner == "<unhandled>"}
        fallback = {code: owner for code, owner in resolved.items() if owner == "unknown_route"}
        assert unhandled == {}, unhandled
        assert fallback == {}, fallback

    async def test_player_subroutes_are_not_stolen_by_the_user_page_route(self):
        """``a:up`` must not answer ``a:upg``/``a:upi``/``a:upl``/``a:url``."""
        actor = User(id=ADMIN_ID, is_bot=False, first_name="Admin")
        expected = {
            kb.USER_PROGRESSION: "progression_menu",
            kb.USER_ROLLS: "rolls_menu",
            kb.USER_PLATES: "user_plates",
            kb.USER_PROFILE: "user_profile_menu",
        }
        for code, handler in expected.items():
            owner = await resolve_owner(admin_router, _probe(kb.pack(code), actor))
            assert owner == handler, (code, owner)

    def test_exactly_one_reason_dispatcher_exists(self):
        """A second ``AdminStates.reason`` handler steals every staged action."""
        handlers = []
        for router in (admin_router, *admin_router.sub_routers):
            for handler in router.message.handlers:
                if _binds_state(handler, AdminStates.reason):
                    handlers.append((router.name, handler.callback.__name__))
        assert handlers == [("admin-players", "reason_input")]

    def test_no_route_code_is_shadowed_by_a_broader_prefix_filter(self):
        """``up`` must not swallow ``upg``/``upi``/``upl``/``url`` and friends."""
        prefix_codes = set(kb.prefix_routes())
        offenders = [
            f"{prefix} (startswith) would swallow {exact} (exact)"
            for prefix in prefix_codes
            for exact in kb.exact_routes()
            if exact != prefix and exact.startswith(prefix)
        ]
        assert offenders == []

    def test_every_route_constant_is_unique(self):
        """Two routes sharing a code make one of them permanently unreachable."""
        seen: dict[str, str] = {}
        clashes: list[str] = []
        for name in dir(kb):
            if name.startswith("_") or name in {"PREFIX", "CB_LEN"}:
                continue
            value = getattr(kb, name)
            if not isinstance(value, str) or not value:
                continue
            if value in seen:
                clashes.append(f"{name} == {seen[value]} == {value!r}")
            seen[value] = name
        assert clashes == []

    def test_no_exact_route_ever_receives_extra_payload_parts(self):
        """A button that carries an argument needs a prefix filter.

        ``button(text, LAB_MODE, "live")`` produces ``a:tm:live``. If the handler
        matches ``a:tm`` with equality the button is dead, and the operator gets
        "Unknown action" - which is exactly how the LIVE/SIM toggle died.
        """
        offenders: list[tuple[str, str]] = []
        for name, markup in _all_markups().items():
            for row in markup.inline_keyboard:
                for item in row:
                    data = item.callback_data or ""
                    if not data.startswith(f"{kb.PREFIX}:"):
                        continue
                    code, _, tail = data[len(kb.PREFIX) + 1 :].partition(":")
                    if tail and code in kb.exact_routes():
                        offenders.append((name, data))
        assert offenders == [], offenders

    def test_callback_payloads_stay_inside_telegram_limits(self):
        """Every shipped keyboard must produce callback data Telegram accepts."""
        too_long: list[tuple[str, str]] = []
        empty: list[tuple[str, str]] = []
        for name, markup in _all_markups().items():
            for row in markup.inline_keyboard:
                for item in row:
                    if not (item.text or "").strip():
                        empty.append((name, item.callback_data or ""))
                    if item.callback_data and len(item.callback_data.encode("utf-8")) > 64:
                        too_long.append((name, item.callback_data))
        assert empty == [], empty
        assert too_long == [], too_long

class TestPanelAvailability:
    """``/admin``, ``/panel`` and ``/a`` must always produce an answer.

    The failure this guards against was completely silent: an exception inside the
    handler was absorbed by aiogram's error middleware, the command had already
    been deleted, and the operator was left staring at an empty chat with the
    commands still listed in the picker.
    """

    @pytest.mark.parametrize("alias", ["/panel", "/a", "/admin"])
    async def test_every_alias_answers(self, dispatcher, bot, session, backend, monkeypatch, alias):
        import bot.bot as bot_module

        monkeypatch.setattr(bot_module, "delete_quietly", _noop_delete)
        session.reset()
        await dispatcher.feed_update(bot, _text_message(alias))
        assert _bodies(session), f"{alias} produced no output at all"

    @pytest.mark.parametrize("alias", ["/panel", "/a", "/admin"])
    async def test_an_internal_failure_still_reaches_the_operator(
        self, dispatcher, bot, session, monkeypatch, alias
    ):
        """A backend blow-up must not look like an unhandled route."""
        import bot.bot as bot_module

        monkeypatch.setattr(bot_module, "delete_quietly", _noop_delete)

        class _Broken(StubBackend):
            def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("panel exploded")

        broken = _Broken()
        for module in ("admin.common", "admin.router", "admin.world", "admin.players"):
            monkeypatch.setattr(f"{module}.get_client", lambda: broken, raising=False)

        session.reset()
        await dispatcher.feed_update(bot, _text_message(alias))
        assert _bodies(session), f"{alias} swallowed the failure"

    async def test_the_operator_can_diagnose_the_panel_from_the_chat(
        self, dispatcher, bot, session, monkeypatch
    ):
        import bot.bot as bot_module

        monkeypatch.setattr(bot_module, "delete_quietly", _noop_delete)

        class _Broken(StubBackend):
            def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("backend unreachable")

        broken = _Broken()
        for module in ("admin.common", "admin.router", "admin.world", "admin.players"):
            monkeypatch.setattr(f"{module}.get_client", lambda: broken, raising=False)

        session.reset()
        await dispatcher.feed_update(bot, _text_message("/panelcheck"))
        bodies = _bodies(session)
        assert bodies, "/panelcheck produced no output"
        assert any("панель" in body.lower() or "Панель" in body for body in bodies)

    async def test_a_stranger_cannot_diagnose_the_panel(self, dispatcher, bot, session):
        session.reset()
        await dispatcher.feed_update(bot, _text_message("/panelcheck", user_id=STRANGER_ID))
        assert _bodies(session)


class TestCommandPublication:
    async def test_admin_commands_are_published_per_admin_chat(self):
        """The admin list must be scoped to those chats, never published globally."""
        from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault

        from admin.common import refresh_commands
        from admin.config import ADMIN_COMMANDS, USER_COMMANDS

        calls: list[tuple[int, list[str], Any]] = []

        class _Recorder:
            async def set_my_commands(self, commands, scope=None, **kwargs):
                scope_chat = getattr(scope, "chat_id", None)
                if isinstance(scope, BotCommandScopeDefault):
                    scope_chat = None
                elif not isinstance(scope, BotCommandScopeChat):
                    raise AssertionError("unexpected scope")
                calls.append((scope_chat, [c.command for c in commands], scope))

        failed = await refresh_commands(_Recorder())  # type: ignore[arg-type]
        assert failed == []

        default_scope = next(call for call in calls if call[0] is None)
        assert default_scope[1] == [cmd for cmd, _ in USER_COMMANDS]
        # Players must not see /admin advertised.
        assert "admin" not in default_scope[1]

        admin_scopes = [call for call in calls if call[0] is not None]
        assert len(admin_scopes) == 2, "one scoped call per configured admin"
        for _chat, commands, _scope in admin_scopes:
            for cmd, _text in ADMIN_COMMANDS:
                assert cmd in commands

    async def test_one_unreachable_chat_does_not_break_the_others(self):
        from aiogram.exceptions import TelegramRetryAfter

        from admin.common import refresh_commands

        seen: list[int | None] = []

        class _Flaky:
            async def set_my_commands(self, commands, scope=None, **kwargs):
                chat_id = getattr(scope, "chat_id", None)
                seen.append(chat_id)
                if chat_id == ADMIN_ID:
                    raise TelegramRetryAfter(method=None, message="too fast", retry_after=1)

        failed = await refresh_commands(_Flaky())  # type: ignore[arg-type]
        assert failed == [str(ADMIN_ID)]
        assert ADMIN_ID_2 in seen

    async def test_the_panel_is_probed_at_startup(self, monkeypatch):
        from admin.common import verify_panel

        class _Ok:
            async def dashboard(self, telegram_id: int) -> dict[str, Any]:
                return {"users": {}}

        monkeypatch.setattr("admin.common.get_client", lambda: _Ok())
        assert await verify_panel(None, ADMIN_ID) is None  # type: ignore[arg-type]

    async def test_an_unreachable_backend_is_reported(self, monkeypatch):
        from admin.client import AdminAPIUnavailable
        from admin.common import verify_panel

        class _Down:
            async def dashboard(self, telegram_id: int) -> dict[str, Any]:
                raise AdminAPIUnavailable("Backend unreachable.", code="UNREACHABLE")

        monkeypatch.setattr("admin.common.get_client", lambda: _Down())
        reason = await verify_panel(None, ADMIN_ID)  # type: ignore[arg-type]
        assert reason is not None
        assert "unreachable" in reason


# ---------------------------------------------------------------------------
# every route reaches its own screen
# ---------------------------------------------------------------------------
class TestRoutesReachTheirScreen:
    async def test_home(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.HOME))
        assert any(ADMIN_HEADER in body for body in bodies)

    @pytest.mark.parametrize("alias", ["/panel", "/a", "/admin"])
    async def test_entry_command_aliases(self, dispatcher, bot, session, monkeypatch, alias):
        import bot.bot as bot_module

        # ``delete_quietly`` is patched, not replaced: a bare assignment would leak
        # into every later test module and silently disable chat cleanup.
        monkeypatch.setattr(bot_module, "delete_quietly", _noop_delete)
        session.reset()
        await dispatcher.feed_update(bot, _text_message(alias))
        assert _bodies(session), alias

    async def test_users_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.USERS))
        assert bodies and not any("Unknown action" in text for text in [*bodies, *_answers(session)])

    async def test_economy_button(self, dispatcher, bot, session, backend):
        await _open_user(dispatcher, bot, session, backend)
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.ECONOMY))
        assert any(ECONOMY_HEADER in body.upper() for body in bodies)

    async def test_test_lab_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.TESTLAB))
        assert any(LAB_HEADER in body for body in bodies)

    async def test_numbers_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.PLATES))
        assert any(NUMBERS_HEADER in body for body in bodies)

    async def test_ranks_button_and_player_open(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.RANKS))
        assert any(RANK_HEADER in body.upper() for body in bodies)
        # Every ranked row must be a button that opens the real player card.
        assert kb.pack(kb.RANK_OPEN, 1) in _payloads(session)
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.RANK_OPEN, 1))
        assert any(str(OTHER_USER_ID) in body or "Hunter" in body for body in bodies)

    async def test_rewards_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.REWARDS))
        assert any(REWARDS_HEADER in body for body in bodies)

    async def test_cosmetics_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.COSMETICS))
        assert any(COSMETICS_HEADER in body for body in bodies)

    async def test_countries_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.COUNTRIES))
        assert any(COUNTRIES_HEADER in body.upper() for body in bodies)

    async def test_events_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.EVENTS))
        assert any(EVENTS_HEADER in body.upper() for body in bodies)

    async def test_analytics_button_and_period(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.ANALYTICS))
        assert any(ANALYTICS_HEADER in body for body in bodies)
        await _press(dispatcher, bot, session, backend, kb.pack(kb.ANALYTICS_PERIOD, "7d"))
        assert backend.reads("/analytics")

    async def test_audit_mine_scope_uses_the_current_actor(self, dispatcher, bot, session, backend):
        """Regression: ``mine`` used to report the first configured admin id."""
        await _press(dispatcher, bot, session, backend, kb.pack(kb.AUDIT))
        await _press(dispatcher, bot, session, backend, kb.pack(kb.AUDIT_SCOPE, "mine"), user_id=ADMIN_ID_2)
        audit_calls = backend.reads("/audit")
        assert audit_calls, "the audit log was never read"
        assert audit_calls[-1]["params"]["admin_telegram_id"] == ADMIN_ID_2

    async def test_audit_all_scope_does_not_filter_by_actor(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, kb.pack(kb.AUDIT))
        await _press(dispatcher, bot, session, backend, kb.pack(kb.AUDIT_SCOPE, "all"), user_id=ADMIN_ID_2)
        audit_calls = backend.reads("/audit")
        assert "admin_telegram_id" not in audit_calls[-1]["params"]

    async def test_system_button(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.SYSTEM))
        assert any(SYSTEM_HEADER in body.upper() for body in bodies)

    async def test_ledger_button(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, kb.pack(kb.LEDGER))
        assert backend.reads("/transactions")

    async def test_world_country_toggle_reaches_confirmation(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, kb.pack(kb.COUNTRIES))
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.COUNTRY_TOGGLE, 1))
        assert any(REASON_HINT in body for body in bodies)

    async def test_world_event_toggle_reaches_confirmation(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, kb.pack(kb.EVENTS))
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.EVENT_TOGGLE, 1))
        assert any(REASON_HINT in body for body in bodies)

    @pytest.mark.parametrize(
        "route",
        [
            kb.USER_ECONOMY,
            kb.USER_ROLLS,
            kb.USER_PLATES,
            kb.USER_PROFILE,
            kb.USER_PROGRESSION,
            kb.USER_MISSIONS,
            kb.USER_ACHIEVEMENTS,
            kb.USER_PREMIUM,
            kb.USER_COSMETICS,
            kb.USER_REWARDS,
        ],
    )
    async def test_player_sections_are_not_stolen_by_the_user_page_route(
        self, dispatcher, bot, session, backend, route
    ):
        await _open_user(dispatcher, bot, session, backend)
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(route))
        assert bodies, route
        assert not any("Unknown action" in body for body in bodies)
        assert not any(SEARCH_RESULTS_HEADER in body for body in bodies), route

    async def test_user_search_paging_is_still_reachable(self, dispatcher, bot, session, backend):
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.USER_PAGE, 2))
        assert any(SEARCH_RESULTS_HEADER in body for body in bodies)


# ---------------------------------------------------------------------------
# the fallback
# ---------------------------------------------------------------------------
class TestUnknownCallbacks:
    async def test_a_genuinely_unknown_payload_is_rejected(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, kb.pack("zzzz"))
        assert any("Unknown action" in answer for answer in _answers(session))

    async def test_a_foreign_callback_never_reaches_the_admin_router(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, "something_else")
        assert not any(ADMIN_HEADER in body for body in _bodies(session))

    async def test_the_fallback_never_executes_a_mutation(self, dispatcher, bot, session, backend):
        await _press(dispatcher, bot, session, backend, kb.pack(kb.CONFIRM, "forged-operation-id"))
        assert backend.mutations == []


# ---------------------------------------------------------------------------
# no valid callback is answered by the fallback
# ---------------------------------------------------------------------------
ALL_ROUTES: list[tuple[str, Any]] = [
    (kb.HOME, None),
    (kb.BACK, None),
    (kb.REFRESH, None),
    (kb.NOOP, None),
    (kb.USERS, None),
    (kb.ECONOMY, None),
    (kb.TESTLAB, None),
    (kb.PLATES, None),
    (kb.RANKS, None),
    (kb.REWARDS, None),
    (kb.COSMETICS, None),
    (kb.COUNTRIES, None),
    (kb.EVENTS, None),
    (kb.ANALYTICS, None),
    (kb.AUDIT, None),
    (kb.SYSTEM, None),
    (kb.LEDGER, None),
    (kb.CANCEL, "nope"),
    (kb.USER_SEARCH, None),
    (kb.USER_RECENT, None),
    (kb.USER_SNAPSHOT, None),
    (kb.USER_PAGE, 2),
    (kb.USER_OPEN, OTHER_USER_ID),
    (kb.USER_ECONOMY, None),
    (kb.USER_ROLLS, None),
    (kb.USER_PLATES, None),
    (kb.USER_PROFILE, None),
    (kb.USER_PROGRESSION, None),
    (kb.USER_MISSIONS, None),
    (kb.USER_ACHIEVEMENTS, None),
    (kb.USER_PREMIUM, None),
    (kb.USER_COSMETICS, None),
    (kb.USER_REWARDS, None),
    (kb.USER_BAN, None),
    (kb.COIN_PRESET, 100),
    (kb.COIN_BALANCE, None),
    (kb.COIN_CUSTOM, None),
    (kb.COIN_SUBTRACT, None),
    (kb.ROLL_PRESET, 5),
    (kb.ROLL_CUSTOM, None),
    (kb.XP_PRESET, 500),
    (kb.STREAK_VALUE, 7),
    (kb.PREMIUM_PRESET, 30),
    (kb.MISSION_PROGRESS, "rolls"),
    (kb.MISSION_COMPLETE, "rolls"),
    (kb.MISSION_RESET, "rolls"),
    (kb.ACHIEVEMENT_GRANT, "first_roll"),
    (kb.COSMETIC_SEARCH, None),
    (kb.COSMETIC_GRANT, "frame_chrome"),
    (kb.COSMETIC_EQUIP, "frame_chrome"),
    (kb.COSMETIC_UNEQUIP, "frame_chrome"),
    (kb.REWARD_KIND, "coins"),
    (kb.LAB_MODE, "sim"),
    (kb.LAB_SIMULATE, None),
    (kb.LAB_LIVE, None),
    (kb.LAB_TEXT, None),
    (kb.LAB_COUNTRY, "RUS"),
    (kb.LAB_RARITY, "MYTHIC"),
    (kb.LAB_PRESET, "MYTHIC_USA"),
    (kb.LAB_CATEGORY, "PHONE_NUMBER"),
    (kb.LAB_REGION, "77"),
    (kb.LAB_TRAIT, "repeating"),
    (kb.LAB_SEARCH, None),
    (kb.LAB_SEARCH_PAGE, 2),
    (kb.PLATE_SEARCH, None),
    (kb.PLATE_SORT, "recent"),
    (kb.PLATE_PAGE, 2),
    (kb.PLATE_OPEN, PLATE_ID),
    (kb.PLATE_GRANT, PLATE_ID),
    (kb.PLATE_FIRST, PLATE_ID),
    (kb.PLATE_COUNTRY_FILTER, "RUS"),
    (kb.PLATE_CATEGORY_FILTER, "PHONE_NUMBER"),
    (kb.PLATE_RARITY_FILTER, "MYTHIC"),
    (kb.PLATE_CLEAR, None),
    (kb.RANK_CATEGORY, "COUNTRIES"),
    (kb.RANK_PERIOD, "weekly"),
    (kb.RANK_OPEN, 1),
    (kb.ANALYTICS_PERIOD, "30d"),
    (kb.AUDIT_SCOPE, "all"),
    (kb.AUDIT_PAGE, 2),
    (kb.COUNTRY_TOGGLE, 1),
    (kb.EVENT_TOGGLE, 1),
]


class TestNoValidCallbackIsRejected:
    @pytest.mark.parametrize(("route", "arg"), ALL_ROUTES, ids=[route for route, _ in ALL_ROUTES])
    async def test_route_is_answered_by_its_own_handler(
        self, dispatcher, bot, session, backend, route, arg
    ):
        await _open_user(dispatcher, bot, session, backend)
        data = kb.pack(route) if arg is None else kb.pack(route, arg)
        bodies = await _press(dispatcher, bot, session, backend, data)
        answers = _answers(session)
        assert not any("Unknown action" in text for text in [*bodies, *answers]), (
            f"{route} fell through to the fallback"
        )

    @pytest.mark.parametrize("code", ["errors", "database", "api"])
    async def test_system_submenu_routes(self, dispatcher, bot, session, backend, code):
        await _press(dispatcher, bot, session, backend, kb.pack(kb.SYSTEM))
        bodies = await _press(dispatcher, bot, session, backend, kb.pack(kb.SYSTEM, code))
        assert not any("Unknown action" in text for text in [*bodies, *_answers(session)])


# ---------------------------------------------------------------------------
# operation id chain
# ---------------------------------------------------------------------------
class TestOperationIdChain:
    async def _stage_rolls(self, dispatcher, bot, session, backend) -> str:
        """Drive the real flow: open a player, pick a preset, type the reason."""
        await _open_user(dispatcher, bot, session, backend)
        await _press(dispatcher, bot, session, backend, kb.pack(kb.ROLL_PRESET, 5))
        await _say(dispatcher, bot, session, "player asked for extra rolls")
        return _confirm_payload(session)

    async def test_confirm_reuses_the_staged_operation_id(self, dispatcher, bot, session, backend):
        confirm_data = await self._stage_rolls(dispatcher, bot, session, backend)
        operation_id = confirm_data.split(":", 2)[2]
        await _press(dispatcher, bot, session, backend, confirm_data)
        assert backend.mutations, "the operation never reached the backend"
        assert backend.mutations[-1]["operation_id"] == operation_id

    async def test_confirming_twice_never_double_executes(self, dispatcher, bot, session, backend):
        confirm_data = await self._stage_rolls(dispatcher, bot, session, backend)
        await _press(dispatcher, bot, session, backend, confirm_data)
        assert len(backend.mutations) == 1
        # Telegram fires the very same callback again on a double tap.
        await _press(dispatcher, bot, session, backend, confirm_data)
        assert len(backend.mutations) == 1, "a duplicated callback executed twice"

    async def test_a_replayed_callback_is_reported_as_used(self, dispatcher, bot, session, backend):
        confirm_data = await self._stage_rolls(dispatcher, bot, session, backend)
        await _press(dispatcher, bot, session, backend, confirm_data)
        session.reset()
        await dispatcher.feed_update(bot, _callback(confirm_data))
        assert any(
            "already used" in answer or "expired" in answer for answer in _answers(session)
        ), _answers(session)

    async def test_cancel_drops_the_operation(self, dispatcher, bot, session, backend):
        await _open_user(dispatcher, bot, session, backend)
        await _press(dispatcher, bot, session, backend, kb.pack(kb.ROLL_PRESET, 5))
        await _say(dispatcher, bot, session, "never mind")
        cancel_data = _cancel_payload(session)
        await _press(dispatcher, bot, session, backend, cancel_data)
        assert backend.mutations == []
        await _press(dispatcher, bot, session, backend, cancel_data)
        assert backend.mutations == []

    async def test_no_operation_survives_its_ttl(self, monkeypatch: pytest.MonkeyPatch):
        context = _context()
        await ops.put(context, "abc", {"action": "coins"})
        assert await ops.pop(context, "abc") is not None

        # Stage normally, then move the clock past the TTL. The registry stamps its
        # own times and must ignore whatever a caller tries to back-date.
        await ops.put(context, "expired", {"action": "coins"})
        real = time.time
        monkeypatch.setattr(ops.time, "time", lambda: real() + ops.FLOW_TTL_SECONDS + 1)
        assert await ops.pop(context, "expired") is None
        assert await ops.get(context, "expired") is None

    async def test_the_buffer_is_bounded(self):
        context = _context()
        for index in range(ops.MAX_PENDING + 10):
            await ops.put(context, f"op-{index}", {"action": "coins"})
        assert await ops.count(context) <= ops.MAX_PENDING


# ---------------------------------------------------------------------------
# reason dispatcher coverage
# ---------------------------------------------------------------------------
STAGED_ACTIONS: list[tuple[str, str]] = [
    (kb.ACT_ROLLS, "/rolls/grant"),
    (kb.ACT_ROLLS_RESET, "/rolls/reset-daily"),
    (kb.ACT_XP, "/progression/xp"),
    (kb.ACT_LEVEL, "/progression/level"),
    (kb.ACT_STREAK, "/progression/streak"),
    (kb.ACT_PROG_RESET, "/progression/reset"),
    (kb.ACT_MISSION, "/missions/action"),
    (kb.ACT_ACHIEVEMENT, "/achievements/action"),
    (kb.ACT_COSMETIC, "/cosmetics/action"),
    (kb.ACT_TITLE, "/titles/grant"),
    (kb.ACT_PREMIUM, "/premium/action"),
    (kb.ACT_PREMIUM_REVOKE, "/premium/action"),
    (kb.ACT_BAN, "/users/ban"),
    (kb.ACT_REWARD, "/rewards/grant"),
    (kb.ACT_COINS, "/economy/coins"),
    (kb.ACT_PLATE_GRANT, "/numbers/grant"),
    (kb.ACT_FIRST_DISCOVERY, "/numbers/first-discovery"),
    (kb.ACT_COUNTRY, "/countries/toggle"),
    (kb.ACT_EVENT, "/events/toggle"),
    (kb.ACT_SEASON, "/seasons/toggle"),
    (kb.ACT_LIVE_ROLL, "/testlab/live"),
    (kb.ACT_FORCE_PLATE, "/testlab/force-plate"),
]


class TestReasonDispatcher:
    async def _stage(self, dispatcher, bot, session, backend, kind: str):
        from admin import players

        await _open_user(dispatcher, bot, session, backend)
        context = _context(dispatcher, bot)
        await context.set_state(AdminStates.reason)
        await context.update_data(
            kind=kind,
            amount=5,
            user_id=OTHER_USER_ID,
            plate_id=PLATE_ID,
            country_id=1,
            event_id=1,
            season_code="S1",
        )
        session.reset()
        await players.reason_input(_mounted("audit reason", bot=bot), context)
        return _confirm_payload(session)

    @pytest.mark.parametrize(("kind", "expected"), STAGED_ACTIONS, ids=[k for k, _ in STAGED_ACTIONS])
    async def test_every_staged_action_has_one_execution_path(
        self, dispatcher, bot, session, backend, kind, expected
    ):
        confirm_data = await self._stage(dispatcher, bot, session, backend, kind)
        await _press(dispatcher, bot, session, backend, confirm_data)
        assert backend.mutations, f"{kind} produced no backend call"
        assert backend.mutations[-1]["path"] == expected

    @pytest.mark.parametrize(("kind", "expected"), STAGED_ACTIONS, ids=[k for k, _ in STAGED_ACTIONS])
    async def test_no_staged_action_executes_twice(
        self, dispatcher, bot, session, backend, kind, expected
    ):
        confirm_data = await self._stage(dispatcher, bot, session, backend, kind)
        await _press(dispatcher, bot, session, backend, confirm_data)
        first = list(backend.mutations)
        await _press(dispatcher, bot, session, backend, confirm_data)
        assert backend.mutations == first, f"{kind} was granted twice"

    async def test_a_stale_reason_without_an_action_is_refused_not_silently_dropped(
        self, dispatcher, bot, session, backend
    ):
        await _open_user(dispatcher, bot, session, backend)
        context = _context(dispatcher, bot)
        await context.set_state(AdminStates.reason)
        from admin import players

        session.reset()
        await players.reason_input(_mounted("some reason", bot=bot), context)
        bodies = _bodies(session)
        assert bodies, "a stale reason vanished without a word"
        assert backend.mutations == []

    async def test_a_command_is_not_accepted_as_a_reason(self, dispatcher, bot, session, backend):
        """A slash command must never be swallowed as the reason for a grant."""
        from admin import players

        await _open_user(dispatcher, bot, session, backend)
        context = _context(dispatcher, bot)
        await context.set_state(AdminStates.reason)
        await context.update_data(kind=kb.ACT_ROLLS, amount=5, user_id=OTHER_USER_ID)
        session.reset()
        await players.reason_input(_mounted("/admin", bot=bot), context)
        assert any(REASON_HINT in body for body in _bodies(session))
        assert backend.mutations == []

    async def test_an_empty_reason_keeps_the_flow_alive(self, dispatcher, bot, session, backend):
        from admin import players

        await _open_user(dispatcher, bot, session, backend)
        context = _context(dispatcher, bot)
        await context.set_state(AdminStates.reason)
        await context.update_data(kind=kb.ACT_ROLLS, amount=5, user_id=OTHER_USER_ID)
        session.reset()
        await players.reason_input(_mounted("   ", bot=bot), context)
        assert any(REASON_HINT in body for body in _bodies(session))
        assert backend.mutations == []


# ---------------------------------------------------------------------------
# test lab country list
# ---------------------------------------------------------------------------
class TestTestLabCountryList:
    async def test_countries_are_paged_not_truncated_at_forty(self, dispatcher, bot, session, backend):
        """The catalogue has 60 countries; none of them may be unreachable."""
        await _press(dispatcher, bot, session, backend, kb.pack(kb.LAB_COUNTRY))
        seen: set[str] = set()
        page = 1
        while page < 10:
            await _press(dispatcher, bot, session, backend, kb.pack(kb.LAB_SEARCH_PAGE, page, ""))
            payloads = _payloads(session)
            codes = {data.split(":", 2)[2] for data in payloads if data.startswith(f"a:{kb.LAB_COUNTRY}:")}
            seen |= codes
            if not any(data.startswith(f"a:{kb.LAB_SEARCH_PAGE}:{page + 1}") for data in payloads):
                break
            page += 1
        assert len(seen) == 60, f"only {len(seen)} countries reachable"

    async def test_country_search_filters_by_name(self, dispatcher, bot, session, backend):
        from admin.world import lab_search_input

        context = _context(dispatcher, bot)
        await context.update_data(screen="lab-country-search")
        session.reset()
        await lab_search_input(_mounted("Country 7", bot=bot), context)
        codes = {data.split(":", 2)[2] for data in _payloads(session) if data.startswith(f"a:{kb.LAB_COUNTRY}:")}
        assert codes == {"C07"}, codes

    async def test_country_search_filters_by_category(self, dispatcher, bot, session, backend):
        from admin.world import _render_country_picker

        context = _context(dispatcher, bot)
        await context.update_data(country_query="RUS", category="PHONE_NUMBER")
        session.reset()
        await _render_country_picker(_mounted("x", bot=bot), context, "RUS")
        codes = {data.split(":", 2)[2] for data in _payloads(session) if data.startswith(f"a:{kb.LAB_COUNTRY}:")}
        assert codes == set(), "the category filter was ignored"

    async def test_country_search_with_no_match_says_so(self, dispatcher, bot, session, backend):
        from admin.world import lab_search_input

        context = _context(dispatcher, bot)
        await context.update_data(screen="lab-country-search")
        session.reset()
        await lab_search_input(_mounted("zzzzz", bot=bot), context)
        assert any("Ничего не найдено" in body for body in _bodies(session))


# ---------------------------------------------------------------------------
# plate search
# ---------------------------------------------------------------------------
class TestPlateSearch:
    async def test_a_bare_number_is_a_text_query_not_an_id(self, dispatcher, bot, session, backend):
        from admin.world import plate_search_input

        context = _context(dispatcher, bot)
        await context.update_data(screen="plate-search")
        session.reset()
        await plate_search_input(_mounted("777", bot=bot), context)
        reads = backend.reads("/plates")
        assert reads, "the query was never executed"
        assert reads[-1]["params"]["query"] == "777"

    async def test_an_explicit_hash_id_still_opens_a_catalogue_entry(self, dispatcher, bot, session, backend):
        from admin.world import plate_search_input

        context = _context(dispatcher, bot)
        await context.update_data(screen="plate-search")
        session.reset()
        await plate_search_input(_mounted(f"#{PLATE_ID}", bot=bot), context)
        assert any(path.startswith(f"/plates/{PLATE_ID}") for path in backend.paths()), backend.paths()

    async def test_country_category_and_rarity_filters_reach_the_api(self, dispatcher, bot, session, backend):
        await _open_user(dispatcher, bot, session, backend)
        for route, arg, expected in (
            (kb.PLATE_COUNTRY_FILTER, "RUS", "country_code"),
            (kb.PLATE_CATEGORY_FILTER, "PHONE_NUMBER", "category"),
            (kb.PLATE_RARITY_FILTER, "MYTHIC", "rarity"),
        ):
            await _press(dispatcher, bot, session, backend, kb.pack(route, arg))
            reads = backend.reads("/plates")
            assert reads, route
            assert reads[-1]["params"].get(expected) == arg.upper()

    async def test_clearing_filters_removes_them(self, dispatcher, bot, session, backend):
        await _open_user(dispatcher, bot, session, backend)
        await _press(dispatcher, bot, session, backend, kb.pack(kb.PLATE_COUNTRY_FILTER, "RUS"))
        await _press(dispatcher, bot, session, backend, kb.pack(kb.PLATE_CLEAR))
        reads = backend.reads("/plates")
        assert reads[-1]["params"].get("country_code") is None

    async def test_a_search_run_outside_the_number_browser_is_ignored(self, dispatcher, bot, session, backend):
        """``AdminStates.search_user`` is shared with the user lookup."""
        from admin.world import plate_search_input

        context = _context(dispatcher, bot)
        await context.update_data(screen="user-search")
        session.reset()
        await plate_search_input(_mounted("777", bot=bot), context)
        assert not _bodies(session), "the number browser hijacked the user search"
        assert backend.reads("/plates") == []


# ---------------------------------------------------------------------------
# authorisation still holds
# ---------------------------------------------------------------------------
class TestAuthorisation:
    @pytest.mark.parametrize("route", [kb.HOME, kb.USERS, kb.TESTLAB, kb.PLATES, kb.AUDIT])
    async def test_a_stranger_never_reaches_a_screen(self, dispatcher, bot, session, backend, route):
        await _press(dispatcher, bot, session, backend, kb.pack(route), user_id=STRANGER_ID)
        assert all(ACCESS_DENIED_TEXT in body for body in _bodies(session))
        assert backend.mutations == []

    async def test_a_stranger_never_reaches_a_confirmation(self, dispatcher, bot, session, backend):
        await _open_user(dispatcher, bot, session, backend)
        await _press(dispatcher, bot, session, backend, kb.pack(kb.CONFIRM, "forged"), user_id=STRANGER_ID)
        assert backend.mutations == []
