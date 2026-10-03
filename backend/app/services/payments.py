"""Telegram Stars payments with a clean mock provider.

Production notes:

* the invoice is created through the Telegram Bot API;
* the authoritative confirmation arrives from Telegram (``successful_payment``),
  never from the Mini App;
* granting is idempotent (``payments.granted`` + ledger idempotency key);
* refunds deactivate entitlements and are recorded on the payment row.

The ``mock`` provider exists so the whole flow can be exercised locally without
touching Telegram; it is refused in production.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import NotFoundError, PaymentError
from app.core.timeutils import utcnow
from app.game.products import PRODUCT_DEFINITIONS
from app.models.enums import AnalyticsEventName, PaymentProvider, PaymentStatus, TransactionType
from app.models.payment import Payment, Product
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.services.economy import EconomyService
from app.services.premium import PremiumService

TELEGRAM_API_BASE = "https://api.telegram.org"
HTTP_TIMEOUT_SECONDS = 15.0
COINS_GRANT_TYPE = "COINS"
PREMIUM_GRANT_TYPE = "PREMIUM"


@dataclass(slots=True)
class InvoiceResult:
    payment: Payment
    provider: str
    invoice_link: str | None
    mock_confirm_url: str | None


class TelegramPaymentGateway:
    """Thin wrapper around the Bot API invoice endpoints."""

    def __init__(self, bot_token: str, client: httpx.Client | None = None) -> None:
        self.bot_token = bot_token
        self.client = client or httpx.Client(timeout=HTTP_TIMEOUT_SECONDS)

    def _url(self, method: str) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}/{method}"

    def create_invoice_link(
        self,
        *,
        title: str,
        description: str,
        payload: str,
        amount: int,
        currency: str = "XTR",
    ) -> str:
        if not self.bot_token or self.bot_token == "CHANGE_ME":
            raise PaymentError("BOT_TOKEN is not configured for Telegram payments.")

        response = self.client.post(
            self._url("createInvoiceLink"),
            json={
                "title": title,
                "description": description,
                "payload": payload,
                "currency": currency,
                "prices": [{"label": title, "amount": amount}],
            },
        )
        data = response.json()
        if not data.get("ok"):
            raise PaymentError(
                f"Telegram rejected the invoice: {data.get('description', 'unknown error')}",
                code="INVOICE_FAILED",
            )
        return str(data["result"])

    def refund_star_payment(self, telegram_payment_charge_id: str) -> bool:
        response = self.client.post(
            self._url("refundStarPayment"),
            json={"telegram_payment_charge_id": telegram_payment_charge_id},
        )
        return bool(response.json().get("ok"))


class PaymentService:
    """Creates invoices, verifies payments and grants entitlements."""

    def __init__(
        self,
        db: Session,
        config: Settings | None = None,
        gateway: TelegramPaymentGateway | None = None,
    ) -> None:
        self.db = db
        self.settings = config or settings
        self.gateway = gateway or TelegramPaymentGateway(self.settings.bot_token)
        self.economy = EconomyService(db)
        self.premium = PremiumService(db, self.settings)
        self.analytics = AnalyticsService(db)

    # --- catalogue ------------------------------------------------------
    def list_products(self) -> list[dict[str, object]]:
        rows = (
            self.db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order))
            .scalars()
            .all()
        )
        if not rows:
            return [
                {
                    "code": item.code,
                    "name": item.name,
                    "description": item.description,
                    "stars_price": item.stars_price,
                    "grant_type": item.grant_type,
                }
                for item in PRODUCT_DEFINITIONS
            ]
        return [
            {
                "code": row.code,
                "name": row.name,
                "description": row.description,
                "stars_price": int(row.stars_price),
                "grant_type": str(row.grant_type).upper(),
            }
            for row in rows
        ]

    def resolve_product(self, code: str) -> Product:
        row = self.db.execute(
            select(Product).where(Product.code == code, Product.is_active.is_(True))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Product not found.", code="PRODUCT_NOT_FOUND")
        return row

    # --- invoice --------------------------------------------------------
    def create_invoice(self, user: User, product_code: str, *, idempotency_key: str | None = None) -> InvoiceResult:
        if idempotency_key:
            existing = self.db.execute(
                select(Payment).where(
                    Payment.user_id == user.id,
                    Payment.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return self._invoice_result(existing)

        product = self.resolve_product(product_code)
        provider = (
            PaymentProvider.TELEGRAM_STARS.value
            if self.settings.payment_provider == "telegram_stars"
            else PaymentProvider.MOCK.value
        )

        payment = Payment(
            user_id=user.id,
            provider=provider,
            product_code=product.code,
            amount=int(product.stars_price),
            currency=str(self.settings.payment_currency),
            status=PaymentStatus.PENDING.value,
            payload={"product_code": product.code, "grant_type": product.grant_type},
            invoice_payload=f"pay_{user.id}_{secrets.token_urlsafe(8)}",
            idempotency_key=idempotency_key,
        )
        self.db.add(payment)
        self.db.flush()
        self.db.commit()
        self.db.refresh(payment)
        return self._invoice_result(payment)

    def _invoice_result(self, payment: Payment) -> InvoiceResult:
        if payment.status == PaymentStatus.PAID.value:
            return InvoiceResult(payment, payment.provider, None, None)

        if payment.provider == PaymentProvider.MOCK.value:
            return InvoiceResult(
                payment,
                payment.provider,
                None,
                f"{self.settings.backend_url}/api/payments/mock/confirm",
            )

        product = self.resolve_product(payment.product_code)
        link = self.gateway.create_invoice_link(
            title=product.name,
            description=product.description or product.name,
            payload=payment.invoice_payload or f"pay_{payment.id}",
            amount=int(payment.amount),
            currency=payment.currency,
        )
        return InvoiceResult(payment, payment.provider, link, None)

    # --- confirmation ---------------------------------------------------
    def get_payment(self, payment_id: int) -> Payment:
        payment = self.db.get(Payment, payment_id)
        if payment is None:
            raise NotFoundError("Payment not found.", code="PAYMENT_NOT_FOUND")
        return payment

    def mark_paid(
        self,
        payment: Payment,
        *,
        external_id: str | None = None,
        provider: str | None = None,
    ) -> Payment:
        """Idempotently mark a payment as paid and grant its product."""
        if payment.status == PaymentStatus.PAID.value and payment.granted:
            return payment

        payment.status = PaymentStatus.PAID.value
        payment.paid_at = payment.paid_at or utcnow()
        if external_id:
            payment.external_id = external_id
        if provider:
            payment.provider = provider
        self.db.flush()

        if not payment.granted:
            self._grant(payment)
            payment.granted = True

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def _grant(self, payment: Payment) -> None:
        product = self.resolve_product(payment.product_code)
        payload = dict(product.grant_payload or {})
        grant_type = str(product.grant_type).upper()

        if grant_type == COINS_GRANT_TYPE:
            amount = int(payload.get("amount", 0))
            if amount > 0:
                self.economy.credit(
                    payment.user_id,
                    amount,
                    TransactionType.PREMIUM_PURCHASE,
                    reference_type="payment",
                    reference_id=str(payment.id),
                    idempotency_key=f"payment:{payment.id}",
                    meta={"product": product.code, "stars": int(payment.amount)},
                )
        elif grant_type == PREMIUM_GRANT_TYPE:
            days = int(payload.get("days", 30))
            tier = str(payload.get("tier", "PRO"))
            self.premium.grant(
                payment.user_id,
                tier=tier,
                days=days,
                source="PURCHASE",
                payment_id=payment.id,
            )
            self.analytics.track(
                AnalyticsEventName.PREMIUM_PURCHASE.value,
                user_id=payment.user_id,
                props={"product": product.code, "tier": tier, "days": days},
            )
        else:
            raise PaymentError("Unknown grant type on product.", code="BAD_PRODUCT")

    def refund(self, payment_id: int, *, telegram_charge_id: str | None = None) -> Payment:
        """Mark a payment refunded and revoke what it granted."""
        payment = self.get_payment(payment_id)
        if payment.status == PaymentStatus.REFUNDED.value:
            return payment

        if telegram_charge_id and payment.provider == PaymentProvider.TELEGRAM_STARS.value:
            self.gateway.refund_star_payment(telegram_charge_id)

        product = self.resolve_product(payment.product_code)
        if str(product.grant_type).upper() == PREMIUM_GRANT_TYPE:
            self.premium.revoke(payment.user_id, payment_id=payment.id)

        payment.status = PaymentStatus.REFUNDED.value
        payment.refunded_at = utcnow()
        payment.refunded_amount = int(payment.amount)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def handle_successful_payment(self, payload: dict[str, object]) -> Payment:
        """Entry point for a Telegram ``successful_payment`` payload."""
        invoice_payload = str(payload.get("invoice_payload") or "")
        telegram_charge_id = str(payload.get("telegram_payment_charge_id") or "") or None

        payment = self.db.execute(
            select(Payment).where(Payment.invoice_payload == invoice_payload)
        ).scalar_one_or_none()
        if payment is None:
            raise NotFoundError("Unknown payment payload.", code="PAYMENT_NOT_FOUND")

        expected_currency = str(payload.get("currency") or payment.currency)
        expected_amount = int(payload.get("total_amount") or payment.amount)
        if expected_currency != payment.currency or expected_amount < int(payment.amount):
            raise PaymentError("Payment amount does not match the invoice.", code="PAYMENT_MISMATCH")

        return self.mark_paid(
            payment, external_id=telegram_charge_id, provider=PaymentProvider.TELEGRAM_STARS.value
        )

    def confirm_mock(self, user: User, payment_id: int) -> Payment:
        """Development-only confirmation used with the mock provider."""
        from app.core.errors import PermissionDeniedError

        if self.settings.is_production or self.settings.payment_provider != "mock":
            raise PermissionDeniedError("Mock payments are disabled.", code="MOCK_DISABLED")

        payment = self.get_payment(payment_id)
        if payment.user_id != user.id:
            raise PermissionDeniedError("This payment belongs to another account.")
        return self.mark_paid(payment)

    def history(self, user_id: int, limit: int = 20) -> list[Payment]:
        stmt = select(Payment).where(Payment.user_id == user_id).order_by(Payment.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
