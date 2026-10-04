"""Internal control-surface API (``/api/admin/bot/*``).

This is the surface the Telegram admin panel talks to. It is deliberately kept
separate from the player-facing ``/api/admin`` routes:

* **Authentication** is service-to-service (``X-Service-Token``) plus a Telegram
  id that is *verified* against ``settings.admin_telegram_ids``. No player JWT,
  and no ``is_admin=true`` flag is ever trusted.
* **Authorisation** is resolved once, in :func:`app.api.deps.get_admin_bot_context`,
  and every handler receives the resulting :class:`AdminActor`.
* **Business logic** lives in :mod:`app.services.admin` and
  :mod:`app.services.test_lab`; this module only validates input, delegates and
  serialises.
* Every mutation carries a caller-supplied ``operation_id`` that becomes the
  unique audit key, so a replayed callback can never grant twice.

The existing ``/api/admin`` endpoints are untouched and keep serving the
player-JWT admin tooling.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminBotContext, get_admin_bot_context, rate_limit
from app.core.config import settings
from app.core.errors import ValidationError
from app.db.session import get_db
from app.schemas import admin as schemas
from app.services.admin import AdminService

router = APIRouter(
    prefix="/admin/bot",
    tags=["admin-bot"],
    dependencies=[
        Depends(rate_limit("admin_bot", "rate_limit_admin_bot")),
        Depends(get_admin_bot_context),
    ],
)

# Expensive aggregate screens get their own, tighter bucket.
read_dependencies = [Depends(rate_limit("admin_bot_read", "rate_limit_admin_read"))]


def service(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db, settings)


# ---------------------------------------------------------------------------
# dashboard / catalogue
# ---------------------------------------------------------------------------
@router.get("/dashboard", summary="Control-centre snapshot")
def dashboard(svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.dashboard()


@router.get("/catalog", summary="Dynamic catalogues: countries, rarities, presets")
def catalog(svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.test_lab_catalog()


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
@router.get("/users", summary="Search players")
def users(
    query: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1, le=500),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.search_users(query, page=page)


@router.get("/users/{user_id}", summary="Full player snapshot")
def user_detail(user_id: int, svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.user_detail(user_id)


@router.get("/users/{user_id}/economy", summary="Balance plus the ledger tail")
def user_economy(
    user_id: int,
    limit: int = Query(default=12, ge=1, le=30),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.user_economy(user_id, limit=limit)


@router.post("/users/ban", response_model=schemas.OperationResponse, summary="Ban or unban a player")
def ban(
    payload: schemas.BanRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.set_ban(
        context.actor,
        user_id=payload.user_id,
        banned=payload.banned,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


# ---------------------------------------------------------------------------
# economy / rolls
# ---------------------------------------------------------------------------
@router.post("/economy/coins", response_model=schemas.OperationResponse, summary="Adjust NUMORA")
def adjust_coins(
    payload: schemas.CoinAdjustRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.adjust_coins(
        context.actor,
        user_id=payload.user_id,
        delta=payload.delta,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post("/economy/balance", response_model=schemas.OperationResponse, summary="Set an exact balance")
def set_balance(
    payload: schemas.BalanceSetRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.set_balance(
        context.actor,
        user_id=payload.user_id,
        target=payload.target,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post("/rolls/grant", response_model=schemas.OperationResponse, summary="Grant bonus rolls")
def grant_rolls(
    payload: schemas.RollGrantRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.grant_rolls(
        context.actor,
        user_id=payload.user_id,
        amount=payload.amount,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post(
    "/rolls/reset-daily",
    response_model=schemas.OperationResponse,
    summary="Refund today's spent rolls (dangerous)",
)
def reset_daily_rolls(
    payload: schemas.RollResetRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.reset_daily_rolls(
        context.actor,
        user_id=payload.user_id,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.get(
    "/transactions",
    summary="Append-only ledger viewer",
    dependencies=read_dependencies,
)
def transactions(
    user_id: int | None = Query(default=None, gt=0),
    tx_type: str | None = Query(default=None, max_length=32),
    sign: str | None = Query(default=None, pattern="^(in|out)$"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10_000),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.transactions(user_id=user_id, tx_type=tx_type, sign=sign, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# progression
# ---------------------------------------------------------------------------
@router.post("/progression/xp", response_model=schemas.OperationResponse, summary="Add or set XP")
def change_xp(
    payload: schemas.XpChangeRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    if payload.delta is None and payload.xp is None:
        raise ValidationError("Either delta or xp must be provided.", code="INVALID_AMOUNT")
    data = svc.change_xp(
        context.actor,
        user_id=payload.user_id,
        delta=payload.delta,
        exact=payload.xp,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post("/progression/level", response_model=schemas.OperationResponse, summary="Set the collector level")
def set_level(
    payload: schemas.LevelSetRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.set_level(
        context.actor,
        user_id=payload.user_id,
        level=payload.level,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post("/progression/streak", response_model=schemas.OperationResponse, summary="Set the streak")
def set_streak(
    payload: schemas.StreakSetRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.set_streak(
        context.actor,
        user_id=payload.user_id,
        current=payload.current,
        longest=payload.longest,
        reset=payload.reset,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post(
    "/progression/reset",
    response_model=schemas.OperationResponse,
    summary="Wipe progression back to level 1 (dangerous)",
)
def reset_progression(
    payload: schemas.ProgressionResetRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.reset_progression(
        context.actor,
        user_id=payload.user_id,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


# ---------------------------------------------------------------------------
# missions / achievements
# ---------------------------------------------------------------------------
@router.get("/users/{user_id}/missions", summary="Today's mission board")
def missions(user_id: int, svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.missions_board(user_id)


@router.post("/missions/action", response_model=schemas.OperationResponse, summary="Mission progress/complete/reset")
def mission_action(
    payload: schemas.MissionActionRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.mission_action(
        context.actor,
        user_id=payload.user_id,
        code=payload.code,
        action=payload.action,
        amount=payload.amount,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.get("/users/{user_id}/achievements", summary="Achievement board")
def achievements(user_id: int, svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.achievements_board(user_id)


@router.post(
    "/achievements/action",
    response_model=schemas.OperationResponse,
    summary="Grant or revoke an achievement",
)
def achievement_action(
    payload: schemas.AchievementActionRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    handler = svc.revoke_achievement if payload.revoke else svc.grant_achievement
    data = handler(
        context.actor,
        user_id=payload.user_id,
        code=payload.code,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


# ---------------------------------------------------------------------------
# cosmetics / rewards / premium
# ---------------------------------------------------------------------------
@router.get("/cosmetics", summary="Cosmetic catalogue", dependencies=read_dependencies)
def cosmetics(
    query: str | None = Query(default=None, max_length=48),
    kind: str | None = Query(default=None, max_length=32),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.cosmetics_catalogue(query=query, kind=kind)


@router.post("/cosmetics/action", response_model=schemas.OperationResponse, summary="Grant / equip / unequip")
def cosmetic_action(
    payload: schemas.CosmeticActionRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.cosmetic_action(
        context.actor,
        user_id=payload.user_id,
        code=payload.code,
        action=payload.action,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post("/titles/grant", response_model=schemas.OperationResponse, summary="Grant a title")
def grant_title(
    payload: schemas.TitleGrantRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.grant_title(
        context.actor,
        user_id=payload.user_id,
        title=payload.title,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.get("/users/{user_id}/premium", summary="Premium status")
def premium(user_id: int, svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.premium_status(user_id)


@router.post("/premium/action", response_model=schemas.OperationResponse, summary="Grant or revoke PRO")
def premium_action(
    payload: schemas.PremiumActionRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.premium_action(
        context.actor,
        user_id=payload.user_id,
        days=payload.days,
        revoke=payload.revoke,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post("/rewards/grant", response_model=schemas.OperationResponse, summary="Quick grant menu")
def grant_reward(
    payload: schemas.RewardGrantRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.grant_reward(
        context.actor,
        user_id=payload.user_id,
        kind=payload.kind,
        amount=payload.amount,
        code=payload.code,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


# ---------------------------------------------------------------------------
# plates
# ---------------------------------------------------------------------------
@router.get("/plates", summary="Plate catalogue browser", dependencies=read_dependencies)
def plates(
    query: str | None = Query(default=None, max_length=32),
    sort: str = Query(default="recent", max_length=16),
    country_code: str | None = Query(default=None, max_length=8),
    rarity: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1, le=500),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.search_plates(
        query=query, sort=sort, country_code=country_code, rarity=rarity, page=page
    )


@router.get("/plates/{plate_id}", summary="Plate detail", dependencies=read_dependencies)
def plate_detail(plate_id: int, svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.plate_detail(plate_id)


@router.post("/plates/grant", response_model=schemas.OperationResponse, summary="Grant a plate")
def grant_plate(
    payload: schemas.PlateGrantRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.grant_plate(
        context.actor,
        user_id=payload.user_id,
        plate_id=payload.plate_id,
        reason=payload.reason,
        operation_id=payload.operation_id,
        mark_first_discovery=payload.mark_first_discovery,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post(
    "/plates/first-discovery",
    response_model=schemas.OperationResponse,
    summary="Set the world-first discoverer (dangerous)",
)
def first_discovery(
    payload: schemas.FirstDiscoveryRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.set_first_discovery(
        context.actor,
        plate_id=payload.plate_id,
        user_id=payload.user_id,
        override=payload.override,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


# ---------------------------------------------------------------------------
# test lab
# ---------------------------------------------------------------------------
@router.post("/testlab/simulate", summary="Read-only roll preview (never mutates)")
def simulate(
    payload: schemas.TestRollRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.simulate_roll(
        context.actor,
        country_code=payload.country_code,
        region_code=payload.region_code,
        template_code=payload.template_code,
        rarity=payload.rarity,
        preset=payload.preset,
        require_trait=payload.require_trait,
        request_id=context.request_id,
    )


@router.post(
    "/testlab/live",
    response_model=schemas.OperationResponse,
    summary="Live forced roll for one player (dangerous)",
)
def live_roll(
    payload: schemas.LiveTestRollRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.live_test_roll(
        context.actor,
        user_id=payload.user_id,
        country_code=payload.country_code,
        region_code=payload.region_code,
        template_code=payload.template_code,
        rarity=payload.rarity,
        preset=payload.preset,
        require_trait=payload.require_trait,
        mark_first_discovery=payload.mark_first_discovery,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.post(
    "/testlab/force-plate",
    response_model=schemas.OperationResponse,
    summary="Materialise an admin-authored plate",
)
def force_plate(
    payload: schemas.ForcePlateGrantRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.force_plate(
        context.actor,
        plate_text=payload.plate_text,
        user_id=payload.user_id,
        country_code=payload.country_code,
        rarity=payload.rarity,
        mark_first_discovery=payload.mark_first_discovery,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


# ---------------------------------------------------------------------------
# world / reporting
# ---------------------------------------------------------------------------
@router.get("/ranks", summary="Collection leaderboards", dependencies=read_dependencies)
def ranks(
    category: str = Query(default="COLLECTION", max_length=24),
    period: str = Query(default="daily", max_length=16),
    limit: int = Query(default=10, ge=1, le=25),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.ranks(category=category, period=period, limit=limit)


@router.get("/countries", summary="Country catalogue with counts", dependencies=read_dependencies)
def countries(svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.countries()


@router.post("/countries/toggle", response_model=schemas.OperationResponse, summary="Activate/deactivate a country")
def toggle_country(
    payload: schemas.CountryToggleRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.toggle_country(
        context.actor,
        country_id=payload.country_id,
        active=payload.active,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.get("/events", summary="Events and the live one", dependencies=read_dependencies)
def events(svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.events()


@router.post("/events/toggle", response_model=schemas.OperationResponse, summary="Activate/deactivate an event")
def toggle_event(
    payload: schemas.EventToggleRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.toggle_event(
        context.actor,
        event_id=payload.event_id,
        active=payload.active,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.get("/seasons", summary="Seasons", dependencies=read_dependencies)
def seasons(svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.seasons()


@router.post("/seasons/toggle", response_model=schemas.OperationResponse, summary="Activate/deactivate a season")
def toggle_season(
    payload: schemas.SeasonToggleRequest,
    context: AdminBotContext = Depends(get_admin_bot_context),
    svc: AdminService = Depends(service),
) -> schemas.OperationResponse:
    data = svc.toggle_season(
        context.actor,
        code=payload.code,
        active=payload.active,
        reason=payload.reason,
        operation_id=payload.operation_id,
        request_id=context.request_id,
    )
    return schemas.OperationResponse(
        replayed=bool(data.get("replayed")), audit_id=data.get("audit_id"), data=data
    )


@router.get("/analytics", summary="Bounded chat analytics", dependencies=read_dependencies)
def analytics(
    period: str = Query(default="today", max_length=8),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.analytics(period)


@router.get("/system", summary="Health, version and environment")
def system(svc: AdminService = Depends(service)) -> dict[str, object]:
    return svc.system()


@router.get("/errors", summary="Recent server errors (no stack traces)", dependencies=read_dependencies)
def errors(
    limit: int = Query(default=20, ge=1, le=50),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.errors_view(limit)


@router.get("/audit", summary="Admin audit log", dependencies=read_dependencies)
def audit(
    page: int = Query(default=1, ge=1, le=1000),
    admin_telegram_id: int | None = Query(default=None, gt=0),
    target_user_id: int | None = Query(default=None, gt=0),
    action: str | None = Query(default=None, max_length=48),
    category: str | None = Query(default=None, max_length=24),
    svc: AdminService = Depends(service),
) -> dict[str, object]:
    return svc.audit_log(
        page=page,
        admin_telegram_id=admin_telegram_id,
        target_user_id=target_user_id,
        action=action,
        category=category,
    )


__all__ = ["router"]
