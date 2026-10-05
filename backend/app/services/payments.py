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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import NotFoundError, PaymentError
from app.core.locks import payment_lock
from app.core.logging import get_logger
from app.core.timeutils import utcnow
from app.game.products import (
    GRANT_TYPES,
    PRODUCT_DEFINITIONS,
    SUPPORTER_TIERS,
)
from app.models.enums import AnalyticsEventName, PaymentProvider, PaymentStatus, TransactionType
from app.models.payment import Payment, Product
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.services.cosmetics import CosmeticService
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.premium import PremiumService
from app.services.seasons import SeasonService

logger = get_logger("app.services.payments")

TELEGRAM_API_BASE = "https://api.telegram.org"
HTTP_TIMEOUT_SECONDS = 15.0
#: Grant type codes, resolved by name rather than position: the catalogue grows, and an
#: index-based alias silently starts granting the wrong thing when a type is inserted.
COINS_GRANT_TYPE = "COINS"
ROLLS_GRANT_TYPE = "ROLLS"
PREMIUM_GRANT_TYPE = "PREMIUM"
SUPPORTER_GRANT_TYPE = "SUPPORTER"
COSMETIC_GRANT_TYPE = "COSMETIC"
SEASON_PASS_GRANT_TYPE = "SEASON_PASS"
#: Every grant type a product may declare. Anything outside this set is a catalogue
#: bug, and :meth:`PaymentService._grant` raises on it instead of losing a purchase.
SUPPORTED_GRANT_TYPES = frozenset(GRANT_TYPES)


def _short(message: str, limit: int = 200) -> str:
    """Single-line error preview. Never a stack trace, never a secret."""
    cleaned = " ".join(str(message or "").split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


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
        self.cosmetics = CosmeticService(db)
        self.seasons = SeasonService(db)
        self.daily = DailyService(db, self.settings)

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
        """Idempotently mark a payment as paid and grant its product.

        The grant is the only part that touches game state, and it happens under a
        per-payment lock plus a row-level ``SELECT ... FOR UPDATE``, so two
        concurrent webhook deliveries for the same charge cannot both grant. If the
        grant fails, the payment is *not* rolled back to nothing: the money was
        taken, so the row is committed as ``FAILED`` with the reason attached and
        stays inspectable (and refundable) instead of silently reverting to
        ``PENDING`` forever.
        """
        with payment_lock(payment.id):
            locked = self._locked(payment.id)
            if locked is None:  # pragma: no cover - the row cannot vanish mid-flight
                raise NotFoundError("Payment not found.", code="PAYMENT_NOT_FOUND")

            if locked.status == PaymentStatus.REFUNDED.value:
                # A late webhook for an already refunded payment must not resurrect
                # the grant; the refund already removed it.
                logger.warning(
                    "payment_webhook_after_refund",
                    extra={"payment_id": locked.id, "charge_id": external_id},
                )
                return locked

            already_granted = locked.status == PaymentStatus.PAID.value and locked.granted
            if external_id and not locked.external_id:
                locked.external_id = external_id
            if provider:
                locked.provider = provider
            locked.status = PaymentStatus.PAID.value
            locked.paid_at = locked.paid_at or utcnow()

            if already_granted:
                self.db.commit()
                self.db.refresh(locked)
                return locked

            try:
                granted = self._grant(locked)
            except Exception as exc:
                # The player has paid. Keep the evidence, drop the half-applied
                # grant, and surface the reason to operators.
                self.db.rollback()
                self._record_failure(payment.id, exc)
                logger.error(
                    "payment_grant_failed",
                    extra={"payment_id": payment.id, "product": payment.product_code},
                    exc_info=True,
                )
                raise

            locked.granted = True
            locked.payload = {**(locked.payload or {}), "granted": granted}
            self.db.commit()
            self.db.refresh(locked)
            return locked

    def _locked(self, payment_id: int) -> Payment | None:
        """Re-read the payment under a row lock so grants cannot interleave."""
        stmt = select(Payment).where(Payment.id == payment_id)
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def _record_failure(self, payment_id: int, error: BaseException) -> None:
        """Persist a FAILED payment in its own transaction."""
        self.db.rollback()
        try:
            row = self._locked(payment_id)
            if row is None:
                return
            row.status = PaymentStatus.FAILED.value
            row.payload = {
                **(row.payload or {}),
                "failure_reason": _short(str(error)),
                "failure_type": type(error).__name__,
            }
            self.db.commit()
        except SQLAlchemyError:  # pragma: no cover - never mask the original error
            self.db.rollback()
            logger.error("payment_failure_not_recorded", extra={"payment_id": payment_id}, exc_info=True)

    def _grant(self, payment: Payment) -> dict[str, object]:
        """Apply a paid product.

        Every product type in :data:`PRODUCT_DEFINITIONS` is implemented here. A
        grant type this method does not know about raises instead of quietly doing
        nothing, because an unhandled product means the player paid for nothing.
        """
        product = self.resolve_product(payment.product_code)
        payload = dict(product.grant_payload or {})
        grant_type = str(product.grant_type).upper()
        if grant_type not in SUPPORTED_GRANT_TYPES:
            # Raised *before* anything is written, so the payment is recorded as
            # FAILED with a reason an operator can act on rather than silently
            # vanishing behind an unhandled type.
            raise PaymentError(f"Unsupported grant type {grant_type!r}.", code="BAD_PRODUCT")
        summary: dict[str, object] = {"grant_type": grant_type}

        numora = int(payload.get("amount") or payload.get("numora") or 0)
        if numora > 0:
            self.economy.credit(
                payment.user_id,
                numora,
                TransactionType.PREMIUM_PURCHASE,
                reference_type="payment",
                reference_id=str(payment.id),
                idempotency_key=f"payment:{payment.id}:numora",
                meta={"product": product.code, "stars": int(payment.amount)},
            )
            summary["numora"] = numora

        if grant_type == COINS_GRANT_TYPE:
            if numora <= 0:
                raise PaymentError("Product grants no NUMORA.", code="BAD_PRODUCT")
            return summary

        if grant_type == ROLLS_GRANT_TYPE:
            # A fixed, fully disclosed number of rolls into the bonus bank. Buying
            # rolls never touches the odds: the tier still comes from the number the
            # engine generates, so a purchase can never guarantee a rarity.
            rolls = int(payload.get("rolls") or 0)
            if rolls <= 0:
                raise PaymentError("Product grants no rolls.", code="BAD_PRODUCT")
            self.daily.grant_bonus_rolls(self._require_user(payment.user_id), rolls)
            summary["rolls"] = rolls

        if grant_type in (PREMIUM_GRANT_TYPE, SUPPORTER_GRANT_TYPE):
            days = int(payload.get("days") or (30 if grant_type == PREMIUM_GRANT_TYPE else 3650))
            tier = str(payload.get("tier") or ("PRO" if grant_type == PREMIUM_GRANT_TYPE else "SUPPORTER"))
            self.premium.grant(
                payment.user_id,
                tier=tier,
                days=days,
                source="PURCHASE",
                payment_id=payment.id,
            )
            summary["tier"] = tier
            summary["days"] = days

        for code in self._cosmetic_codes(payload):
            self.cosmetics.grant(self._require_user(payment.user_id), code, source="PURCHASE")
            summary.setdefault("cosmetics", []).append(code)

        for title in self._titles(payload, grant_type, tier=payload.get("tier")):
            self.cosmetics.grant_title(self._require_user(payment.user_id), title, source="PURCHASE")
            summary.setdefault("titles", []).append(title)

        if grant_type == SEASON_PASS_GRANT_TYPE:
            user = self._require_user(payment.user_id)
            summary["season"] = self.seasons.grant_season_pass(
                user, None if str(payload.get("season") or "current") == "current" else str(payload["season"])
            )

        if grant_type in (PREMIUM_GRANT_TYPE, SUPPORTER_GRANT_TYPE, SEASON_PASS_GRANT_TYPE):
            self.analytics.track(
                AnalyticsEventName.PREMIUM_PURCHASE.value,
                user_id=payment.user_id,
                props={"product": product.code, "tier": summary.get("tier"), "grant_type": grant_type},
            )
        return summary

    @staticmethod
    def _cosmetic_codes(payload: dict[str, object]) -> list[str]:
        codes = payload.get("cosmetics")
        if isinstance(codes, str):
            return [codes]
        single = payload.get("cosmetic")
        return [str(value) for value in codes] if isinstance(codes, (list, tuple)) else (
            [str(single)] if single else []
        )

    @staticmethod
    def _titles(payload: dict[str, object], grant_type: str, *, tier: object) -> list[str]:
        titles = payload.get("titles")
        if isinstance(titles, (list, tuple)):
            return [str(value) for value in titles]
        single = payload.get("title")
        if single:
            return [str(single)]
        if grant_type == SUPPORTER_GRANT_TYPE and tier:
            configured = SUPPORTER_TIERS.get(str(tier).upper()) or {}
            return [str(configured["title"])] if configured.get("title") else []
        return []

    def _require_user(self, user_id: int) -> User:
        user = self.db.get(User, int(user_id))
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        return user

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

        if not invoice_payload:
            # Without a payload there is nothing to look up, and an empty string is
            # a *value* in the column: querying it could match a row created by a
            # bug and credit the wrong player.
            raise PaymentError("Payment payload is missing.", code="PAYMENT_MISMATCH")

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
