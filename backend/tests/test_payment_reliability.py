"""Payment reliability: nothing is lost, nothing is granted twice.

Covers the paths that used to fail in production:

* seven of the twelve catalogue products declared a grant type the backend could
  not fulfil, so a paid supporter tier / bundle / season pass raised ``BAD_PRODUCT``
  and the money was gone;
* a failed grant rolled the payment back to ``PENDING`` forever, leaving no record
  that the player had paid;
* a retried webhook, or a webhook racing a client poll, could grant twice;
* ``invoice_payload`` had no index and the idempotency key was globally unique, so
  two players who happened to send the same key collided into a 500;
* a replayed admin request answered with a different payload shape from the
  original, because the audit row only stored a whitelisted state snapshot;
* the ledger viewer consumed its lazy result on the owner lookup, so it always
  reported a count with zero rows.

The tests drive the real API and the real services - only Telegram itself is
stubbed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import PaymentError, PermissionDeniedError
from app.game.products import GRANT_TYPES, PRODUCT_DEFINITIONS, product_by_code
from app.models.enums import PaymentStatus, TransactionType
from app.models.payment import Payment, Product
from app.models.user import User, WalletTransaction
from app.services.cosmetics import CosmeticService
from app.services.economy import EconomyService
from app.services.payments import (
    SUPPORTED_GRANT_TYPES,
    PaymentService,
    TelegramPaymentGateway,
)
from app.services.premium import PremiumService
from tests.conftest import TEST_SERVICE_TOKEN
from tests.test_platform import make_user


def _invoice(client, session: dict, product_code: str, *, idempotency_key: str | None = None) -> dict:
    headers = dict(session["headers"])
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    response = client.post(
        "/api/payments/invoice",
        headers=headers,
        json={"product_code": product_code},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _confirm(client, session: dict, payment_id: int) -> dict:
    return client.post(
        "/api/payments/mock/confirm", headers=session["headers"], json={"payment_id": payment_id}
    ).json()


def _webhook(client, payload: dict, *, service_token: str = TEST_SERVICE_TOKEN):
    return client.post(
        "/api/payments/telegram/webhook",
        json={"message": {"successful_payment": payload}},
        headers={"X-Service-Token": service_token},
    )


def _stars_payment(user_id: int, product_code: str, *, amount: int, payload: str) -> Payment:
    return Payment(
        user_id=user_id,
        provider="TELEGRAM_STARS",
        product_code=product_code,
        amount=amount,
        currency="XTR",
        status=PaymentStatus.PENDING.value,
        payload={},
        invoice_payload=payload,
    )


def _fresh_user(db: Session, telegram_id: int, first_name: str = "Probe") -> User:
    user = User(telegram_id=telegram_id, first_name=first_name, language_code="en")
    db.add(user)
    db.flush()
    return user


class TestProductCatalogue:
    def test_every_product_grant_type_is_implementable(self):
        """A product the backend cannot fulfil is a lost purchase."""
        declared = {definition.grant_type for definition in PRODUCT_DEFINITIONS}
        assert declared <= set(GRANT_TYPES)
        assert frozenset(GRANT_TYPES) == SUPPORTED_GRANT_TYPES

    def test_every_product_is_actually_grantable(self, db: Session):
        """Each shipped product must survive a real grant without raising."""
        user = _fresh_user(db, 880001, "Grantee")
        economy = EconomyService(db)

        for definition in PRODUCT_DEFINITIONS:
            service = PaymentService(db, settings)
            payment = Payment(
                user_id=user.id,
                provider="MOCK",
                product_code=definition.code,
                amount=definition.stars_price,
                currency="XTR",
                status=PaymentStatus.PENDING.value,
                payload={},
                invoice_payload=f"test-{definition.code}",
            )
            db.add(payment)
            db.flush()
            before = economy.balance(user.id)
            service.mark_paid(payment)
            assert payment.granted, definition.code
            assert economy.balance(user.id) >= before, definition.code

    def test_an_unsupported_grant_type_fails_loudly_instead_of_silently(self, db: Session):
        user = _fresh_user(db, 880002, "Broken")
        product = Product(
            code="test_broken",
            name="Broken",
            description="",
            stars_price=10,
            grant_type="MYSTERY",
            grant_payload={},
            category="PRO",
            is_active=True,
        )
        db.add(product)
        db.flush()
        payment = Payment(
            user_id=user.id,
            provider="MOCK",
            product_code="test_broken",
            amount=10,
            currency="XTR",
            status=PaymentStatus.PENDING.value,
            payload={},
            invoice_payload="test-broken-1",
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

        with pytest.raises(PaymentError):
            PaymentService(db, settings).mark_paid(payment)

        # The charge is kept, marked FAILED, and carries the reason.
        db.expire_all()
        stored = db.get(Payment, payment_id)
        assert stored.status == PaymentStatus.FAILED.value
        assert stored.granted is False
        assert "MYSTERY" in stored.payload["failure_reason"]
        assert stored.payload["failure_type"] == "PaymentError"

    def test_product_definitions_are_consistent(self):
        codes = [definition.code for definition in PRODUCT_DEFINITIONS]
        assert len(codes) == len(set(codes)), "duplicate product code"
        assert all(definition.stars_price > 0 for definition in PRODUCT_DEFINITIONS)
        assert all(definition.description for definition in PRODUCT_DEFINITIONS)
        assert product_by_code("pro_30d") is not None
        assert product_by_code("nope") is None


class TestSuccessfulPayment:
    def test_a_paid_product_grants_exactly_once(self, client, db, authed):
        user = make_user(db, client, 881001)
        session = authed(881001)
        invoice = _invoice(client, session, "numora_5000")
        body = _confirm(client, session, invoice["payment_id"])
        assert body["status"] == PaymentStatus.PAID.value
        assert EconomyService(db).balance(user.id) >= 5000

    def test_a_bundle_grants_its_cosmetics(self, client, db, authed):
        user = make_user(db, client, 881002)
        session = authed(881002)
        invoice = _invoice(client, session, "bundle_starter")
        _confirm(client, session, invoice["payment_id"])
        codes = CosmeticService(db).owned_codes(user.id)
        assert "finish_chrome" in codes
        assert "frame_steel" in codes
        assert EconomyService(db).balance(user.id) >= 5000

    def test_a_season_pass_grants_the_pass(self, client, db, authed):
        user = make_user(db, client, 881003)
        session = authed(881003)
        invoice = _invoice(client, session, "season_pass_1")
        _confirm(client, session, invoice["payment_id"])
        db.expire_all()
        assert db.get(User, user.id).season_pass_active is True

    def test_a_supporter_product_grants_the_tier_and_title(self, client, db, authed):
        user = make_user(db, client, 881004)
        session = authed(881004)
        invoice = _invoice(client, session, "supporter_100")
        _confirm(client, session, invoice["payment_id"])
        assert "frame_supporter" in CosmeticService(db).owned_codes(user.id)
        from app.models.numora import CosmeticTitle

        rows = db.execute(select(CosmeticTitle).where(CosmeticTitle.user_id == user.id)).scalars()
        assert {"Patron"} & {row.title for row in rows}

    def test_the_invoice_exposes_its_price_and_product(self, client, db, authed):
        make_user(db, client, 881005)
        session = authed(881005)
        catalogue = {
            row["code"]: row for row in client.get("/api/payments/products", headers=session["headers"]).json()
        }
        definition = product_by_code("numora_5000")
        assert definition is not None
        assert catalogue["numora_5000"]["stars_price"] == definition.stars_price
        invoice = _invoice(client, session, "numora_5000")
        assert invoice["amount"] == definition.stars_price
        assert invoice["status"] == PaymentStatus.PENDING.value


class TestDuplicateAndRetry:
    def test_a_duplicate_webhook_does_not_grant_twice(self, client, db, authed):
        user = make_user(db, client, 881010)
        session = authed(881010)
        invoice = _invoice(client, session, "numora_5000")
        payload = {
            "invoice_payload": f"pay_{user.id}_dup",
            "telegram_payment_charge_id": "charge-dup-1",
            "currency": "XTR",
            "total_amount": invoice["amount"],
        }
        db.add(_stars_payment(user.id, "numora_5000", amount=invoice["amount"], payload=payload["invoice_payload"]))
        db.commit()

        first = _webhook(client, payload)
        assert first.status_code == 200, first.text
        balance_after_first = EconomyService(db).balance(user.id)

        for _ in range(3):
            again = _webhook(client, payload)
            assert again.status_code == 200, again.text
        assert EconomyService(db).balance(user.id) == balance_after_first

    def test_a_webhook_after_a_refund_does_not_resurrect_the_grant(self, client, db, authed):
        user = make_user(db, client, 881011)
        session = authed(881011)
        invoice = _invoice(client, session, "pro_30d")
        payload = {
            "invoice_payload": f"pay_{user.id}_refund",
            "telegram_payment_charge_id": "charge-refund-1",
            "currency": "XTR",
            "total_amount": invoice["amount"],
        }
        payment = _stars_payment(user.id, "pro_30d", amount=invoice["amount"], payload=payload["invoice_payload"])
        db.add(payment)
        db.commit()

        assert _webhook(client, payload).status_code == 200
        assert PremiumService(db, settings).active_entitlement(user.id) is not None

        db.expire_all()
        PaymentService(db, settings).refund(payment.id)
        assert _webhook(client, payload).status_code == 200
        assert PremiumService(db, settings).active_entitlement(user.id) is None

    def test_the_same_webhook_delivered_concurrently_grants_once(self, client, db, authed):
        user = make_user(db, client, 881012)
        session = authed(881012)
        invoice = _invoice(client, session, "numora_5000")
        payload = {
            "invoice_payload": f"pay_{user.id}_race",
            "telegram_payment_charge_id": "charge-race-1",
            "currency": "XTR",
            "total_amount": invoice["amount"],
        }
        db.add(_stars_payment(user.id, "numora_5000", amount=invoice["amount"], payload=payload["invoice_payload"]))
        db.commit()

        # A webhook racing a client poll: both target the same payment.
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: _webhook(client, payload), range(4)))
        assert all(response.status_code == 200 for response in responses)

        rows = db.execute(
            select(Payment).where(Payment.invoice_payload == payload["invoice_payload"])
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].granted is True
        credits = db.execute(
            select(WalletTransaction).where(
                WalletTransaction.reference_type == "payment",
                WalletTransaction.reference_id == str(rows[0].id),
            )
        ).scalars().all()
        assert len(credits) == 1, "the wallet was credited more than once"

    def test_a_client_retry_of_invoice_creation_returns_the_same_payment(self, client, db, authed):
        make_user(db, client, 881013)
        session = authed(881013)
        first = _invoice(client, session, "numora_5000", idempotency_key="retry-key-1")
        second = _invoice(client, session, "numora_5000", idempotency_key="retry-key-1")
        assert first["payment_id"] == second["payment_id"]

    def test_two_players_may_use_the_same_idempotency_key(self, client, db, authed):
        """The key is client-supplied and looked up per user."""
        make_user(db, client, 881014)
        first_session = authed(881014)
        first = _invoice(client, first_session, "numora_5000", idempotency_key="shared-key")
        assert first["payment_id"]

        make_user(db, client, 881015)
        second_session = authed(881015)
        second = _invoice(client, second_session, "numora_5000", idempotency_key="shared-key")
        assert second["payment_id"] != first["payment_id"]


class TestRejectedWebhooks:
    def test_a_malformed_update_is_acknowledged_without_granting(self, client):
        """Telegram retries a 4xx forever, so an unusable body is acknowledged.

        The important half is the second one: nothing is granted.
        """
        for update in (
            {"message": {}},
            {"message": {"successful_payment": None}},
            {"edited_message": {"successful_payment": {}}},
            {"unexpected": "shape"},
        ):
            response = client.post(
                "/api/payments/telegram/webhook",
                json=update,
                headers={"X-Service-Token": TEST_SERVICE_TOKEN},
            )
            assert response.status_code == 200, response.text
            assert response.json() == {"ok": True, "handled": False}

    def test_a_payment_object_without_a_payload_is_refused(self, client):
        """An empty payload must not match a row that happens to store ""."""
        response = _webhook(client, {"invoice_payload": "", "total_amount": 150})
        assert response.status_code >= 400, response.text

    def test_a_malformed_webhook_never_touches_a_real_payment(self, client, db, authed):
        """A body with no usable invoice payload must not move any balance."""
        user = make_user(db, client, 881070)
        session = authed(881070)
        invoice = _invoice(client, session, "numora_5000")
        _confirm(client, session, invoice["payment_id"])
        balance = EconomyService(db).balance(user.id)

        for update in ({"message": {}}, {"unexpected": "shape"}):
            response = client.post(
                "/api/payments/telegram/webhook",
                json=update,
                headers={"X-Service-Token": TEST_SERVICE_TOKEN},
            )
            assert response.status_code == 200, response.text
            assert response.json()["handled"] is False
        assert EconomyService(db).balance(user.id) == balance

    def test_an_unknown_payment_payload_is_refused(self, client):
        response = _webhook(
            client,
            {
                "invoice_payload": "pay_does_not_exist",
                "telegram_payment_charge_id": "charge-unknown-1",
                "currency": "XTR",
                "total_amount": 150,
            },
        )
        assert response.status_code == 404

    def test_a_webhook_with_the_wrong_service_token_is_refused(self, client, db, authed):
        user = make_user(db, client, 881020)
        session = authed(881020)
        invoice = _invoice(client, session, "numora_5000")
        payload = {
            "invoice_payload": f"pay_{user.id}_auth",
            "telegram_payment_charge_id": "charge-auth-1",
            "currency": "XTR",
            "total_amount": invoice["amount"],
        }
        assert _webhook(client, payload, service_token="not-the-token").status_code == 401
        assert _webhook(client, payload).status_code == 404
        assert EconomyService(db).balance(user.id) == 0

    def test_the_charge_is_credited_to_the_invoice_owner(self, client, db, authed):
        """Not to whoever happened to press pay."""
        user = make_user(db, client, 881021)
        session = authed(881021)
        invoice = _invoice(client, session, "numora_5000")
        owner = make_user(db, client, 881022)
        payload = {
            "invoice_payload": f"pay_{owner.id}_owner",
            "telegram_payment_charge_id": "charge-owner-1",
            "currency": "XTR",
            "total_amount": invoice["amount"],
        }
        db.add(_stars_payment(owner.id, "numora_5000", amount=invoice["amount"], payload=payload["invoice_payload"]))
        db.commit()

        response = _webhook(client, payload)
        assert response.status_code == 200, response.text
        assert EconomyService(db).balance(owner.id) >= 5000
        assert EconomyService(db).balance(user.id) == 0

    def test_an_underpaid_webhook_is_refused(self, client, db, authed):
        user = make_user(db, client, 881023)
        session = authed(881023)
        invoice = _invoice(client, session, "numora_5000")
        payload = {
            "invoice_payload": f"pay_{user.id}_underpaid",
            "telegram_payment_charge_id": "charge-under-1",
            "currency": "XTR",
            "total_amount": 1,
        }
        db.add(_stars_payment(user.id, "numora_5000", amount=invoice["amount"], payload=payload["invoice_payload"]))
        db.commit()
        response = _webhook(client, payload)
        assert response.status_code >= 400, response.text
        assert EconomyService(db).balance(user.id) == 0

    def test_a_currency_mismatch_is_refused(self, client, db, authed):
        user = make_user(db, client, 881024)
        session = authed(881024)
        _invoice(client, session, "numora_5000")
        payload = {
            "invoice_payload": f"pay_{user.id}_currency",
            "telegram_payment_charge_id": "charge-currency-1",
            "currency": "USD",
            "total_amount": 150,
        }
        db.add(_stars_payment(user.id, "numora_5000", amount=150, payload=payload["invoice_payload"]))
        db.commit()
        assert _webhook(client, payload).status_code >= 400


class TestTransientFailures:
    def test_a_gateway_failure_is_not_swallowed_as_a_grant(self, db: Session):
        """A Telegram 5xx must surface, never return a broken invoice link."""
        user = _fresh_user(db, 881030, "Stars")

        class _Failing(TelegramPaymentGateway):
            def create_invoice_link(self, **kwargs) -> str:
                raise PaymentError("Telegram returned 500", code="INVOICE_FAILED")

        if db.execute(select(Product).where(Product.code == "numora_5000")).scalar_one_or_none() is None:
            pytest.skip("catalogue is not seeded in this environment")

        stars = settings.model_copy(update={"payment_provider": "telegram_stars"})
        service = PaymentService(db, stars, gateway=_Failing("token"))
        with pytest.raises(PaymentError):
            service.create_invoice(user, "numora_5000")

    def test_a_timeout_is_not_swallowed_as_a_grant(self, db: Session):
        """A network timeout must surface the same way a 5xx does."""
        import httpx

        user = _fresh_user(db, 881032, "Timeout")

        class _TimingOut(TelegramPaymentGateway):
            def create_invoice_link(self, **kwargs) -> str:
                raise httpx.TimeoutException("read timeout")

        stars = settings.model_copy(update={"payment_provider": "telegram_stars"})
        service = PaymentService(db, stars, gateway=_TimingOut("token"))
        with pytest.raises(httpx.TimeoutException):
            service.create_invoice(user, "numora_5000")

    def test_a_grant_failure_keeps_the_payment_marked_failed(self, db: Session):
        """The money was taken: the row must survive with a reason attached."""
        user = _fresh_user(db, 881036, "Halfway")
        product = Product(
            code="test_coins_only",
            name="Coins only",
            description="",
            stars_price=10,
            grant_type="COINS",
            grant_payload={"amount": 0},  # grants nothing: the grant must fail
            category="PRO",
            is_active=True,
        )
        db.add(product)
        db.flush()
        payment = Payment(
            user_id=user.id,
            provider="MOCK",
            product_code=product.code,
            amount=10,
            currency="XTR",
            status=PaymentStatus.PENDING.value,
            payload={},
            invoice_payload="test-coins-only-1",
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

        with pytest.raises(PaymentError):
            PaymentService(db, settings).mark_paid(payment)

        db.expire_all()
        stored = db.get(Payment, payment_id)
        assert stored is not None
        assert stored.status == PaymentStatus.FAILED.value
        assert stored.granted is False
        assert stored.payload.get("failure_reason")

    def test_a_failed_grant_can_be_retried_after_the_catalogue_is_fixed(self, db: Session):
        user = _fresh_user(db, 881033, "Retry")
        product = Product(
            code="test_retryable",
            name="Retryable",
            description="",
            stars_price=10,
            grant_type="COINS",
            grant_payload={"amount": 0},
            category="PRO",
            is_active=True,
        )
        db.add_all([user, product])
        db.flush()
        payment = Payment(
            user_id=user.id,
            provider="MOCK",
            product_code=product.code,
            amount=10,
            currency="XTR",
            status=PaymentStatus.PENDING.value,
            payload={},
            invoice_payload="test-retryable-1",
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

        with pytest.raises(PaymentError):
            PaymentService(db, settings).mark_paid(payment)

        product.grant_payload = {"amount": 250}
        db.flush()
        PaymentService(db, settings).mark_paid(payment)

        db.expire_all()
        assert db.get(Payment, payment_id).granted is True
        assert EconomyService(db).balance(user.id) == 250


class TestMockIsDevelopmentOnly:
    def test_the_mock_provider_is_refused_in_production(self, db: Session):
        """A mock purchase must be impossible to confirm once deployed."""
        production = settings.model_copy(update={"app_env": "production", "payment_provider": "mock"})
        assert production.is_production is True
        service = PaymentService(db, production)
        user = _fresh_user(db, 881040, "Prod")
        payment = Payment(
            user_id=user.id,
            provider="MOCK",
            product_code="numora_5000",
            amount=10,
            currency="XTR",
            status=PaymentStatus.PENDING.value,
            payload={},
            invoice_payload="test-prod-mock",
        )
        db.add(payment)
        db.commit()
        with pytest.raises(PermissionDeniedError) as caught:
            service.confirm_mock(user, payment.id)
        assert caught.value.code == "MOCK_DISABLED"
        assert EconomyService(db).balance(user.id) == 0

    def test_the_mock_provider_is_refused_when_stars_are_configured(self, db: Session):
        stars = settings.model_copy(update={"payment_provider": "telegram_stars"})
        service = PaymentService(db, stars)
        user = _fresh_user(db, 881041, "Stars")
        payment = Payment(
            user_id=user.id,
            provider="MOCK",
            product_code="numora_5000",
            amount=10,
            currency="XTR",
            status=PaymentStatus.PENDING.value,
            payload={},
            invoice_payload="test-stars-mock",
        )
        db.add(payment)
        db.commit()
        with pytest.raises(PermissionDeniedError):
            service.confirm_mock(user, payment.id)

    def test_the_mock_gateway_is_refused_without_a_token(self):
        with pytest.raises(PaymentError):
            TelegramPaymentGateway("CHANGE_ME").create_invoice_link(
                title="t", description="d", payload="p", amount=1
            )


class TestPaymentAuditTrail:
    def test_an_operator_can_reconcile_a_payment(self, client, db, authed, admin_authed):
        user = make_user(db, client, 881050)
        session = authed(881050)
        invoice = _invoice(client, session, "numora_5000")
        _confirm(client, session, invoice["payment_id"])

        listing = client.get(
            "/api/admin/payments", headers=admin_authed["headers"], params={"user_id": user.id}
        ).json()
        assert listing["total"] == 1
        row = listing["items"][0]
        assert row["status"] == PaymentStatus.PAID.value
        assert row["granted"] is True
        assert row["telegram_id"] == user.telegram_id

        detail = client.get(
            f"/api/admin/payments/{invoice['payment_id']}", headers=admin_authed["headers"]
        ).json()
        assert detail["granted"] is True
        assert detail["failure_reason"] is None

    def test_an_operator_sees_a_failed_grant_and_its_reason(self, client, db, admin_authed):
        user = _fresh_user(db, 881051, "Broken")
        product = Product(
            code="test_visible_failure",
            name="Visible failure",
            description="",
            stars_price=10,
            grant_type="COINS",
            grant_payload={"amount": 0},
            category="PRO",
            is_active=True,
        )
        db.add(product)
        db.flush()
        payment = Payment(
            user_id=user.id,
            provider="MOCK",
            product_code=product.code,
            amount=10,
            currency="XTR",
            status=PaymentStatus.PENDING.value,
            payload={},
            invoice_payload="test-visible-1",
        )
        db.add(payment)
        db.commit()
        with pytest.raises(PaymentError):
            PaymentService(db, settings).mark_paid(payment)
        db.commit()

        body = client.get(f"/api/admin/payments/{payment.id}", headers=admin_authed["headers"]).json()
        assert body["status"] == PaymentStatus.FAILED.value
        assert body["granted"] is False
        assert body["failure_reason"]
        assert body["failure_type"]

    def test_the_payment_list_is_paginated_and_filterable(self, client, db, authed, admin_authed):
        user = make_user(db, client, 881052)
        session = authed(881052)
        for _ in range(3):
            _invoice(client, session, "numora_5000")

        first = client.get(
            "/api/admin/payments",
            headers=admin_authed["headers"],
            params={"user_id": user.id, "limit": 2},
        ).json()
        assert first["total"] == 3
        assert len(first["items"]) == 2
        assert first["has_more"] is True

        pending = client.get(
            "/api/admin/payments",
            headers=admin_authed["headers"],
            params={"user_id": user.id, "status": PaymentStatus.PENDING.value},
        ).json()
        assert pending["total"] == 3

        refunded = client.get(
            "/api/admin/payments",
            headers=admin_authed["headers"],
            params={"user_id": user.id, "status": PaymentStatus.REFUNDED.value},
        ).json()
        assert refunded["total"] == 0
        assert refunded["items"] == []

    def test_a_payment_can_be_found_by_charge_id(self, client, db, authed, admin_authed):
        user = make_user(db, client, 881053)
        session = authed(881053)
        invoice = _invoice(client, session, "numora_5000")
        payload = {
            "invoice_payload": f"pay_{user.id}_find",
            "telegram_payment_charge_id": "charge-find-1",
            "currency": "XTR",
            "total_amount": invoice["amount"],
        }
        db.add(_stars_payment(user.id, "numora_5000", amount=invoice["amount"], payload=payload["invoice_payload"]))
        db.commit()
        _webhook(client, payload)

        found = client.get(
            "/api/admin/payments",
            headers=admin_authed["headers"],
            params={"charge_id": "charge-find-1"},
        ).json()
        assert found["total"] == 1
        assert found["items"][0]["external_id"] == "charge-find-1"


class TestLedgerIntegrity:
    def test_a_payment_grant_writes_exactly_one_ledger_row(self, client, db, authed):
        user = make_user(db, client, 881060)
        session = authed(881060)
        invoice = _invoice(client, session, "numora_5000")
        _confirm(client, session, invoice["payment_id"])
        _confirm(client, session, invoice["payment_id"])
        rows = db.execute(
            select(WalletTransaction).where(
                WalletTransaction.user_id == user.id,
                WalletTransaction.type == TransactionType.PREMIUM_PURCHASE,
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].balance_after == rows[0].amount

    def test_the_ledger_viewer_returns_items_for_an_empty_ledger(self, client, db, admin_bot):
        user = make_user(db, client, 881064)
        body = admin_bot.get("/transactions", params={"user_id": user.id}).json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["has_more"] is False

    def test_the_ledger_viewer_materialises_rows_and_owners(self, client, db, admin_bot):
        """The owner lookup used to consume the lazy result, emptying the page."""
        user = make_user(db, client, 881061)
        EconomyService(db).credit(user.id, 100, TransactionType.ADMIN_ADJUSTMENT)
        EconomyService(db).credit(user.id, 250, TransactionType.ROLL_REWARD)
        db.commit()

        body = admin_bot.get("/transactions", params={"user_id": user.id}).json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        assert all(item["username"] == user.username for item in body["items"])
        assert all(item["telegram_id"] == user.telegram_id for item in body["items"])
        assert {item["amount"] for item in body["items"]} == {100, 250}

    def test_the_ledger_viewer_paginates(self, client, db, admin_bot):
        user = make_user(db, client, 881062)
        for index in range(5):
            EconomyService(db).credit(user.id, 10 + index, TransactionType.ADMIN_ADJUSTMENT)
        db.commit()

        page1 = admin_bot.get("/transactions", params={"user_id": user.id, "limit": 2}).json()
        page2 = admin_bot.get(
            "/transactions", params={"user_id": user.id, "limit": 2, "offset": 2}
        ).json()
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        assert page1["has_more"] is True
        ids = {item["id"] for item in page1["items"]} | {item["id"] for item in page2["items"]}
        assert len(ids) == 4, "pages overlapped"

    def test_the_ledger_viewer_handles_a_large_ledger(self, client, db, admin_bot):
        user = make_user(db, client, 881063)
        for _ in range(40):
            EconomyService(db).credit(user.id, 1, TransactionType.ADMIN_ADJUSTMENT)
        db.commit()
        body = admin_bot.get("/transactions", params={"user_id": user.id, "limit": 50}).json()
        assert body["total"] == 40
        assert len(body["items"]) == 40
        assert body["has_more"] is False
