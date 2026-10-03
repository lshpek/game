"""Payments (Telegram Stars / mock) and premium entitlement endpoints."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, idempotency_key, rate_limit
from app.core.config import settings
from app.core.errors import AuthError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.schemas.payments import (
    InvoiceRequest,
    InvoiceResponse,
    MockConfirmRequest,
    PaymentItem,
    PremiumStatusResponse,
    ProductItem,
)
from app.services.payments import PaymentService
from app.services.premium import PremiumService

router = APIRouter(tags=["payments"])


def _payment_item(row) -> PaymentItem:
    return PaymentItem(
        id=row.id,
        provider=row.provider,
        product_code=row.product_code,
        amount=int(row.amount),
        currency=row.currency,
        status=row.status,
        granted=bool(row.granted),
        created_at=row.created_at.isoformat() if row.created_at else None,
        paid_at=row.paid_at.isoformat() if row.paid_at else None,
    )


@router.get("/payments/products", response_model=list[ProductItem], summary="Purchasable products")
def products(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ProductItem]:
    return [ProductItem(**row) for row in PaymentService(db, settings).list_products()]  # type: ignore[arg-type]


@router.post(
    "/payments/invoice",
    response_model=InvoiceResponse,
    dependencies=[Depends(rate_limit("payment", "rate_limit_payment"))],
    summary="Create an invoice (Telegram Stars or mock provider)",
)
def create_invoice(
    payload: InvoiceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    key: str | None = Depends(idempotency_key),
) -> InvoiceResponse:
    result = PaymentService(db, settings).create_invoice(user, payload.product_code, idempotency_key=key)
    payment = result.payment
    return InvoiceResponse(
        payment_id=payment.id,
        provider=result.provider,
        product_code=payment.product_code,
        amount=int(payment.amount),
        currency=payment.currency,
        status=payment.status,
        invoice_link=result.invoice_link,
        mock_confirm_url=result.mock_confirm_url,
    )


@router.get("/payments/history", response_model=list[PaymentItem], summary="Payment history")
def payment_history(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PaymentItem]:
    rows = PaymentService(db, settings).history(user.id, limit=max(1, min(limit, 100)))
    return [_payment_item(row) for row in rows]


@router.post(
    "/payments/mock/confirm",
    response_model=PaymentItem,
    dependencies=[Depends(rate_limit("payment", "rate_limit_payment"))],
    summary="Development-only mock payment confirmation",
)
def confirm_mock(
    payload: MockConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentItem:
    return _payment_item(PaymentService(db, settings).confirm_mock(user, payload.payment_id))


def _verify_service_token(provided: str | None) -> None:
    """Accept either the Telegram webhook secret or the internal service token."""
    if not provided:
        raise AuthError("Missing webhook credentials.", code="WEBHOOK_UNAUTHORIZED")
    allowed = {settings.telegram_webhook_secret, settings.service_token}
    allowed.discard("CHANGE_ME")
    if not allowed:
        raise AuthError("Webhook secret is not configured.", code="WEBHOOK_NOT_CONFIGURED")
    if not any(hmac.compare_digest(provided, candidate) for candidate in allowed):
        raise AuthError("Invalid webhook credentials.", code="WEBHOOK_UNAUTHORIZED")


@router.post("/payments/telegram/webhook", summary="Telegram payment update webhook (secret protected)")
def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Handle ``successful_payment`` updates from Telegram.

    Only Telegram (or the bot service, using the internal token) can reach this
    endpoint, and granting is idempotent per payment row.
    """
    _verify_service_token(x_telegram_bot_api_secret_token or x_service_token)

    service = PaymentService(db, settings)
    message = update.get("message") or update.get("edited_message") or {}
    successful = (message or {}).get("successful_payment")
    if not successful:
        return {"ok": True, "handled": False}

    payment = service.handle_successful_payment(successful)
    return {"ok": True, "handled": True, "payment_id": payment.id, "status": payment.status}


@router.get("/premium", response_model=PremiumStatusResponse, summary="Current premium entitlement")
def premium_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PremiumStatusResponse:
    service = PremiumService(db, settings)
    expires_at = service.expires_at(user.id)
    return PremiumStatusResponse(
        active=service.is_premium(user.id),
        tier=service.active_tier(user.id),
        expires_at=expires_at.isoformat() if expires_at else None,
        perks=service.perks(user.id),
        daily_rolls_bonus=service.daily_rolls_bonus(user.id),
        duplicate_multiplier=service.duplicate_coin_multiplier(user.id),
        unlocked_containers=sorted(service.unlocked_containers(user.id)),
    )


@router.post(
    "/payments/refund",
    response_model=PaymentItem,
    dependencies=[Depends(rate_limit("payment", "rate_limit_payment"))],
    summary="Refund a payment (admin only)",
)
def refund_payment(
    payment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentItem:
    if not user.is_admin:
        raise PermissionDeniedError("Administrator access required.")
    return _payment_item(PaymentService(db, settings).refund(payment_id))
