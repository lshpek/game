"""Admin API - every endpoint is protected by the admin dependency."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, rate_limit
from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.logging import error_buffer
from app.core.timeutils import start_of_utc_day, utcnow
from app.db.session import get_db
from app.game.rarity import load_rarity_weights
from app.models.enums import PaymentStatus
from app.models.number import Number
from app.models.payment import Payment
from app.models.roll import Roll
from app.models.user import User, Wallet, WalletTransaction
from app.schemas.payments import (
    AdminCoinAdjustRequest,
    AdminRarityConfigResponse,
    AdminSeasonToggleRequest,
    AdminStatsResponse,
    AdminUserItem,
)
from app.services.economy import EconomyService
from app.services.premium import PremiumService
from app.services.seasons import SeasonService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(rate_limit("admin", "rate_limit_admin"))])


@router.get("/stats", response_model=AdminStatsResponse, summary="High-level game statistics")
def stats(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> AdminStatsResponse:
    today = start_of_utc_day()

    users_total = int(db.execute(select(func.count()).select_from(User)).scalar_one() or 0)
    users_new_today = int(
        db.execute(select(func.count()).select_from(User).where(User.created_at >= today)).scalar_one() or 0
    )
    rolls_total = int(db.execute(select(func.count()).select_from(Roll)).scalar_one() or 0)
    rolls_today = int(
        db.execute(select(func.count()).select_from(Roll).where(Roll.created_at >= today)).scalar_one() or 0
    )
    numbers_discovered = int(db.execute(select(func.count()).select_from(Number)).scalar_one() or 0)
    coins = int(db.execute(select(func.coalesce(func.sum(Wallet.coins), 0))).scalar_one() or 0)
    payments_paid = int(
        db.execute(
            select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.PAID.value)
        ).scalar_one()
        or 0
    )
    revenue = int(
        db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == PaymentStatus.PAID.value)
        ).scalar_one()
        or 0
    )
    distribution = {
        str(rarity): int(count)
        for rarity, count in db.execute(select(Number.rarity, func.count()).group_by(Number.rarity)).all()
    }
    active = SeasonService(db).active()

    return AdminStatsResponse(
        users_total=users_total,
        users_new_today=users_new_today,
        rolls_total=rolls_total,
        rolls_today=rolls_today,
        numbers_discovered=numbers_discovered,
        coins_in_circulation=coins,
        payments_paid=payments_paid,
        revenue_stars=revenue,
        active_season=active.code if active else None,
        rarity_distribution=distribution,
    )


@router.get("/users", response_model=list[AdminUserItem], summary="Browse users")
def list_users(
    search: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserItem]:
    stmt = select(User, Wallet).outerjoin(Wallet, Wallet.user_id == User.id)
    if search:
        cleaned = search.strip().lstrip("@")
        conditions = [User.username.ilike(f"%{cleaned}%"), User.first_name.ilike(f"%{cleaned}%")]
        if cleaned.isdigit():
            conditions.append(User.telegram_id == int(cleaned))
        stmt = stmt.where(or_(*conditions))

    rows = db.execute(stmt.order_by(User.id.desc()).limit(limit).offset(offset)).all()
    return [
        AdminUserItem(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            is_banned=bool(user.is_banned),
            coins=int(wallet.coins if wallet else 0),
            total_rolls=int(user.total_rolls),
            unique_numbers=int(user.unique_numbers_count),
            best_value=int(user.best_value),
            created_at=user.created_at.isoformat() if user.created_at else None,
        )
        for user, wallet in rows
    ]


@router.post("/users/coins", summary="Adjust a user's COINS balance (audited)")
def adjust_coins(
    payload: AdminCoinAdjustRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if db.get(User, payload.user_id) is None:
        raise NotFoundError("User not found.", code="USER_NOT_FOUND")

    tx = EconomyService(db).admin_adjust(
        payload.user_id,
        payload.delta,
        reason=payload.reason,
        admin_telegram_id=admin.telegram_id,
    )
    db.commit()
    return {"success": True, "user_id": payload.user_id, "delta": payload.delta, "balance": int(tx.balance_after)}


@router.post("/users/{user_id}/ban", summary="Ban or unban a user")
def set_ban(
    user_id: int,
    banned: bool = Query(default=True),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="USER_NOT_FOUND")
    user.is_banned = banned
    db.commit()
    return {"success": True, "user_id": user_id, "is_banned": banned}


@router.post("/users/{user_id}/premium", summary="Grant a premium entitlement (support flow)")
def grant_premium(
    user_id: int,
    days: int = Query(default=30, ge=1, le=3650),
    tier: str = Query(default="PRO", max_length=16),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    entitlement = PremiumService(db, settings).grant(user_id, tier=tier, days=days, source="ADMIN")
    db.commit()
    return {
        "success": True,
        "user_id": user_id,
        "tier": entitlement.tier,
        "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
    }


@router.get("/economy/transactions", summary="Recent ledger entries")
def transactions(
    limit: int = Query(default=50, ge=1, le=500),
    tx_type: str | None = Query(default=None, max_length=32),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    stmt = select(WalletTransaction, User).join(User, User.id == WalletTransaction.user_id)
    if tx_type:
        stmt = stmt.where(WalletTransaction.type == tx_type.upper())
    rows = db.execute(stmt.order_by(WalletTransaction.id.desc()).limit(limit)).all()
    return [
        {
            "id": tx.id,
            "user_id": tx.user_id,
            "telegram_id": user.telegram_id,
            "type": tx.type,
            "amount": int(tx.amount),
            "balance_after": int(tx.balance_after),
            "reference_type": tx.reference_type,
            "reference_id": tx.reference_id,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }
        for tx, user in rows
    ]


@router.get("/errors", summary="Recent server errors (in-process ring buffer)")
def errors(
    limit: int = Query(default=50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
) -> dict[str, object]:
    return {"generated_at": utcnow().isoformat(), "items": error_buffer.snapshot(limit)}


@router.get("/seasons", summary="All seasons with status")
def seasons(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    service = SeasonService(db)
    return [service.serialize(row) for row in service.list_all()]


@router.post("/seasons/toggle", summary="Activate or deactivate a season")
def toggle_season(
    payload: AdminSeasonToggleRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    service = SeasonService(db)
    if payload.active:
        season = service.activate(payload.code)
    else:
        season = service.get(payload.code)
        season.is_active = False
    db.commit()
    return {"success": True, "code": season.code, "is_active": bool(season.is_active)}


@router.get("/rarity-config", response_model=AdminRarityConfigResponse, summary="Effective rarity weights")
def rarity_config(admin: User = Depends(get_current_admin)) -> AdminRarityConfigResponse:
    override = settings.rarity_weights_override
    return AdminRarityConfigResponse(
        weights=load_rarity_weights(override),
        source="RARITY_WEIGHTS_OVERRIDE" if override else "defaults",
    )
