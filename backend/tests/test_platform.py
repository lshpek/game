"""Ledger economy, payments and premium entitlements."""

from __future__ import annotations

import pytest

from app.core.errors import InsufficientFundsError
from app.models.enums import TransactionType
from app.models.user import User, WalletTransaction
from app.services.economy import EconomyService


def make_user(db, client, telegram_id: int) -> User:
    """Create a user through the public API and return the ORM row."""
    client.post("/api/auth/dev", json={"telegram_id": telegram_id})
    db.expire_all()
    return db.query(User).filter(User.telegram_id == telegram_id).one()


class TestLedger:
    def test_credit_writes_an_auditable_row(self, db, client):
        user = make_user(db, client, 800001)
        tx = EconomyService(db).credit(user.id, 500, TransactionType.DAILY_REWARD, reference_type="test")
        db.commit()

        assert tx.balance_after == 500
        assert tx.amount == 500
        stored = db.get(WalletTransaction, tx.id)
        assert stored is not None and stored.type == TransactionType.DAILY_REWARD.value

    def test_debit_updates_totals(self, db, client):
        user = make_user(db, client, 800002)
        service = EconomyService(db)
        service.credit(user.id, 300, TransactionType.ROLL_REWARD)
        service.debit(user.id, 120, TransactionType.CONTAINER_PURCHASE)
        db.commit()

        wallet = service.get_wallet(user.id)
        assert wallet.coins == 180
        assert wallet.total_earned == 300
        assert wallet.total_spent == 120

    def test_debit_is_rejected_without_funds(self, db, client):
        user = make_user(db, client, 800003)
        with pytest.raises(InsufficientFundsError):
            EconomyService(db).debit(user.id, 10_000, TransactionType.CONTAINER_PURCHASE)

    def test_idempotent_credit_does_not_double_pay(self, db, client):
        user = make_user(db, client, 800004)
        service = EconomyService(db)

        service.credit(user.id, 700, TransactionType.ACHIEVEMENT_REWARD, idempotency_key="achievement:X:1")
        service.credit(user.id, 700, TransactionType.ACHIEVEMENT_REWARD, idempotency_key="achievement:X:1")
        db.commit()

        assert service.balance(user.id) == 700

    def test_negative_amounts_are_rejected(self, db, client):
        user = make_user(db, client, 800005)
        with pytest.raises(ValueError):
            EconomyService(db).credit(user.id, -10, TransactionType.ADMIN_ADJUSTMENT)


class TestPayments:
    def test_products_are_listed(self, client, authed):
        session = authed(810001)
        payload = client.get("/api/payments/products", headers=session["headers"]).json()
        assert any(row["code"] == "numora_5000" for row in payload)
        assert all(row["stars_price"] > 0 for row in payload)

    def test_invoice_is_created_and_confirmed_once(self, client, authed):
        session = authed(810002)
        invoice = client.post(
            "/api/payments/invoice",
            headers={**session["headers"], "Idempotency-Key": "pay-1"},
            json={"product_code": "numora_5000"},
        ).json()
        assert invoice["provider"] == "MOCK"
        assert invoice["status"] == "PENDING"

        before = client.get("/api/user", headers=session["headers"]).json()["coins"]
        confirmed = client.post(
            "/api/payments/mock/confirm", headers=session["headers"], json={"payment_id": invoice["payment_id"]}
        ).json()
        assert confirmed["status"] == "PAID"
        assert confirmed["granted"] is True

        after = client.get("/api/user", headers=session["headers"]).json()["coins"]
        assert after == before + 5000

        # Re-confirming must never grant twice.
        client.post(
            "/api/payments/mock/confirm", headers=session["headers"], json={"payment_id": invoice["payment_id"]}
        )
        assert client.get("/api/user", headers=session["headers"]).json()["coins"] == after

    def test_invoice_idempotency(self, client, authed):
        session = authed(810003)
        headers = {**session["headers"], "Idempotency-Key": "pay-2"}
        first = client.post("/api/payments/invoice", headers=headers, json={"product_code": "numora_5000"}).json()
        second = client.post("/api/payments/invoice", headers=headers, json={"product_code": "numora_5000"}).json()
        assert first["payment_id"] == second["payment_id"]

    def test_premium_purchase_unlocks_the_pro_box(self, client, authed):
        session = authed(810004)
        invoice = client.post(
            "/api/payments/invoice", headers=session["headers"], json={"product_code": "pro_30d"}
        ).json()
        client.post(
            "/api/payments/mock/confirm", headers=session["headers"], json={"payment_id": invoice["payment_id"]}
        )

        premium = client.get("/api/premium", headers=session["headers"]).json()
        assert premium["active"] is True
        assert premium["tier"] == "PRO"
        assert "pro" in premium["unlocked_containers"]

    def test_unknown_product_is_not_found(self, client, authed):
        session = authed(810005)
        response = client.post("/api/payments/invoice", headers=session["headers"], json={"product_code": "nope"})
        assert response.status_code == 404

    def test_webhook_requires_a_secret(self, client):
        assert client.post("/api/payments/telegram/webhook", json={"message": {}}).status_code == 401


class TestAdmin:
    def test_admin_routes_are_forbidden_for_players(self, client, authed):
        session = authed(820001)
        response = client.get("/api/admin/stats", headers=session["headers"])
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_stats_are_visible_to_admins(self, client, admin_authed):
        response = client.get("/api/admin/stats", headers=admin_authed["headers"])
        assert response.status_code == 200
        assert response.json()["users_total"] > 0

    def test_coin_adjustment_is_audited(self, client, db, admin_authed):
        user = make_user(db, client, 820002)
        response = client.post(
            "/api/admin/users/coins",
            headers=admin_authed["headers"],
            json={
                "user_id": user.id,
                "delta": 1234,
                "reason": "support ticket 42",
                "operation_id": "op-coin-adjust-1",
            },
        ).json()
        assert response["balance"] == 1234
        assert EconomyService(db).balance(user.id) == 1234

    def test_a_replayed_coin_adjustment_does_not_double_grant(self, client, db, admin_authed):
        """A retried admin request must not pay out twice."""
        user = make_user(db, client, 820004)
        body = {
            "user_id": user.id,
            "delta": 500,
            "reason": "support ticket 43",
            "operation_id": "op-coin-replay-1",
        }
        first = client.post("/api/admin/users/coins", headers=admin_authed["headers"], json=body).json()
        second = client.post("/api/admin/users/coins", headers=admin_authed["headers"], json=body).json()
        assert first["balance"] == 500
        assert second["balance"] == 500
        assert second["replayed"] is True
        assert EconomyService(db).balance(user.id) == 500

    def test_a_coin_adjustment_without_an_operation_id_is_rejected(self, client, db, admin_authed):
        user = make_user(db, client, 820005)
        response = client.post(
            "/api/admin/users/coins",
            headers=admin_authed["headers"],
            json={"user_id": user.id, "delta": 10, "reason": "no id"},
        )
        assert response.status_code == 422
        assert EconomyService(db).balance(user.id) == 0

    def test_ledger_is_visible_to_admins(self, client, db, admin_authed):
        user = make_user(db, client, 820003)
        EconomyService(db).credit(user.id, 10, TransactionType.ADMIN_ADJUSTMENT)
        db.commit()
        rows = client.get("/api/admin/economy/transactions", headers=admin_authed["headers"]).json()
        assert any(row["user_id"] == user.id for row in rows)

    def test_rarity_config_is_exposed(self, client, admin_authed):
        payload = client.get("/api/admin/rarity-config", headers=admin_authed["headers"]).json()
        assert payload["source"] in {"defaults", "RARITY_WEIGHTS_OVERRIDE"}
        assert payload["weights"]["COMMON"] > 0

    def test_season_toggle(self, client, admin_authed):
        response = client.post(
            "/api/admin/seasons/toggle",
            headers=admin_authed["headers"],
            json={
                "code": "season-2-time",
                "active": True,
                "reason": "season 2 launch",
                "operation_id": "op-season-2",
            },
        ).json()
        assert response["is_active"] is True
        assert response["replayed"] is False

    def test_errors_endpoint_returns_a_bounded_snapshot(self, client, admin_authed):
        payload = client.get("/api/admin/errors", headers=admin_authed["headers"]).json()
        assert isinstance(payload["items"], list)
        assert len(payload["items"]) <= 50


class TestRateLimiting:
    def test_limit_is_enforced_and_errors_are_clean(self, client):
        from app.api.deps import rate_limiter
        from app.core.config import settings

        rate_limiter.reset()
        probe = 8_300_001
        limit = int(settings.rate_limit_auth) + 5

        statuses = [
            client.post("/api/auth/dev", json={"telegram_id": probe}).status_code
            for _ in range(limit)
        ]
        assert 429 in statuses, "rate limiter never triggered"

        response = client.post("/api/auth/dev", json={"telegram_id": probe})
        assert response.status_code == 429
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "RATE_LIMITED"
        assert "Traceback" not in response.text


class TestHealth:
    def test_health_reports_the_database(self, client):
        payload = client.get("/health").json()
        assert payload["status"] == "ok"
        assert payload["database"] == "ok"

    def test_unhandled_paths_return_json(self, client):
        response = client.get("/api/definitely-missing")
        assert response.status_code == 404

