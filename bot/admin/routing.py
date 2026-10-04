"""Callback routing architecture for the admin panel.

Why this module exists
----------------------
aiogram resolves an update in two deterministic steps:

1. the router's **own** observers, in registration order, then
2. its **sub-routers**, depth first, in the order they were attached.

That means a broad filter registered on the parent router - for example
``F.data.startswith("a:")`` - wins over *every* handler attached later, including
whole sub-routers. The old panel had exactly that handler in the middle of
``bot.admin.router``, so every admin callback below it (users, economy, test lab,
ranks, the confirm dispatcher, ...) was answered with "Unknown action" even though
a correct handler existed further down.

The rule the panel now obeys:

* **specific routes win** - every real route is registered on a router that is
  attached before the fallback;
* **the generic fallback runs last** - it lives on its own router which
  :func:`attach_fallback` appends after every real sub-router;
* **unknown callbacks are rejected safely** - the fallback answers the query so
  Telegram never leaves a spinner running, and it logs the raw payload without
  executing anything;
* **no valid admin callback becomes "Unknown action"** - :func:`handled_routes`
  reports which route codes the panel answers, and
  ``bot/tests/test_admin_routing.py`` drives the real dispatcher for every one of
  them rather than trusting handler names.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, Chat, Message, User

from admin import keyboards as kb
from admin.common import guard
from admin.keyboards import exact_routes, pack, prefix_routes

logger = logging.getLogger("bot.admin.routing")

#: Route codes the fallback answers itself (it never reaches a real screen).
BUILTIN_ROUTES: frozenset[str] = frozenset(
    {
        kb.HOME,
        kb.BACK,
        kb.REFRESH,
        kb.NOOP,
    }
)

#: Sub-routers attached by :mod:`bot.admin.router`, in resolution order.
SUB_ROUTER_NAMES: tuple[str, ...] = ("admin-world", "admin-players")


def fallback_router() -> Router:
    """Build (once) the router that rejects unknown panel callbacks."""
    existing = getattr(fallback_router, "_router", None)
    if existing is not None:
        return existing

    sub = Router(name="admin-fallback")

    @sub.callback_query(F.data.startswith(kb.PREFIX + ":"))
    @guard
    async def unknown_route(callback: CallbackQuery) -> None:
        """Reject, never execute. Answers the query so Telegram stops waiting."""
        logger.warning("unknown admin callback rejected: %s", callback.data)
        await callback.answer("Unknown action.", show_alert=False)

    for name in BUILTIN_ROUTES:
        _OWNERS.setdefault(name, set()).add("builtin")
    _OWNERS.setdefault("", set()).add("unknown_route")

    fallback_router._router = sub  # type: ignore[attr-defined]
    return sub


#: route code -> names of the handlers that own it. Filled by
#: :func:`declare_routes`, which the panel's handler modules call once their
#: routes are attached.
_OWNERS: dict[str, set[str]] = {}


def declare_routes(handler: Any, *codes: str) -> Any:
    """Record which panel routes ``handler`` answers. Returns the handler."""
    for code in codes:
        _OWNERS.setdefault(str(code), set()).add(getattr(handler, "__name__", str(handler)))
    return handler


def handled_routes() -> frozenset[str]:
    """Every route code the panel can answer, excluding the catch-all."""
    return frozenset(code for code in _OWNERS if code)


def attach_fallback(parent: Router) -> Router:
    """Attach the reject-everything router to ``parent`` **last**.

    Called once, after every real sub-router has been attached. Ordering is the
    whole point: the fallback must be the final observer the dispatcher reaches.
    """
    sub = fallback_router()
    if sub in parent.sub_routers:
        return parent
    parent.include_router(sub)
    return parent


async def resolve_owner(root: Router, callback: CallbackQuery) -> str | None:
    """Return the name of the handler aiogram would pick for ``callback``.

    Walks the router chain in exactly the dispatcher's order (own handlers first,
    then sub-routers depth first) and evaluates each handler's filters the same way
    ``Dispatcher._propagate_event`` does. Tests use it to prove *which* handler a
    callback reaches, rather than trusting the set of registered names.
    """
    for handler in root.callback_query.handlers:
        matched, _data = await handler.check(callback)
        if matched:
            return getattr(handler.callback, "__name__", str(handler.callback))
    for sub in root.sub_routers:
        owner = await resolve_owner(sub, callback)
        if owner is not None:
            return owner
    return None


async def resolved_routes(root: Router, actor: User) -> dict[str, str]:
    """Map every advertised route code to the handler that answers it.

    Prefix routes are probed with an argument, because their filter is
    ``startswith("a:<code>:")`` and would not match a bare ``a:<code>``.
    """
    out: dict[str, str] = {}
    for code, probe_data in advertised_routes():
        probe = CallbackQuery(
            id="probe",
            from_user=actor,
            chat_instance="probe",
            message=Message(
                message_id=1,
                date=datetime.datetime.now(tz=datetime.UTC),
                chat=Chat(id=actor.id, type="private"),
                text="probe",
            ),
            data=probe_data,
        )
        out[code] = await resolve_owner(root, probe) or "<unhandled>"
    return out


def advertised_routes() -> tuple[tuple[str, str], ...]:
    """Every ``(route code, probe payload)`` a shipped keyboard can produce."""
    seen: dict[str, str] = {}
    for code in exact_routes():
        seen.setdefault(code, pack(code))
    for code in prefix_routes():
        seen.setdefault(code, pack(code, "1"))
    return tuple(seen.items())


__all__ = [
    "BUILTIN_ROUTES",
    "SUB_ROUTER_NAMES",
    "advertised_routes",
    "attach_fallback",
    "declare_routes",
    "fallback_router",
    "handled_routes",
    "resolve_owner",
    "resolved_routes",
]
