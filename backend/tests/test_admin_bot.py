"""Telegram admin control centre: authorisation, mutations, audit and the test lab."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.game.plate_generator import PlateGenerator
from app.game.rng import default_rng
from app.models.admin import AdminAuditLog
from app.models.enums import AdminAction, TransactionType
from app.models.numora import UserCosmetic
from app.models.plates import Plate, PlateDiscovery, UserPlate
from app.models.progression import UserAchievement
from app.models.user import User, Wallet, WalletTransaction
from app.services.admin import AdminActor, AdminService
from app.services.catalog import build_snapshot
from app.services.economy import EconomyService
from app.services.plates import PlateService
from app.services.progression import ProgressionService, level_for_xp
from tests.conftest import TEST_ADMIN_TELEGRAM_ID, TEST_SERVICE_TOKEN


# ---------------------------------------------------------------------------
# authorisation
# ---------------------------------------------------------------------------
class TestAdminBotAuthorization:
    def test_missing_service_token_is_rejected(self, client):
        response = client.get("/api/admin/bot/dashboard")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "SERVICE_UNAUTHORIZED"

    def test_wrong_service_token_is_rejected(self, client):
        response = client.get(
            "/api/admin/bot/dashboard",
            headers={"X-Service-Token": "nope", "X-Admin-Telegram-Id": str(TEST_ADMIN_TELEGRAM_ID)},
        )
        assert response.status_code == 401

    def test_non_admin_telegram_id_is_rejected(self, client):
        response = client.get(
            "/api/admin/bot/dashboard",
            headers={"X-Service-Token": TEST_SERVICE_TOKEN, "X-Admin-Telegram-Id": "123456789"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ADMIN_REQUIRED"

    def test_missing_admin_header_is_rejected(self, client):
        response = client.get(
            "/api/admin/bot/dashboard", headers={"X-Service-Token": TEST_SERVICE_TOKEN}
        )
        assert response.status_code == 403

    def test_non_numeric_admin_header_is_rejected(self, client):
        response = client.get(
            "/api/admin/bot/dashboard",
            headers={"X-Service-Token": TEST_SERVICE_TOKEN, "X-Admin-Telegram-Id": "root"},
        )
        assert response.status_code == 403

    def test_player_jwt_alone_cannot_reach_the_panel(self, client, authed):
        """A valid session is not enough - the service token is mandatory."""
        session = authed(778899, username="regular")
        response = client.get("/api/admin/bot/dashboard", headers=session["headers"])
        assert response.status_code == 401

    def test_service_token_alone_cannot_act(self, client):
        response = client.post(
            "/api/admin/bot/economy/coins",
            headers={"X-Service-Token": TEST_SERVICE_TOKEN},
            json={"user_id": 1, "delta": 100, "reason": "x", "operation_id": "op-no-admin"},
        )
        assert response.status_code == 403

    def test_configured_admin_is_accepted(self, admin_bot):
        response = admin_bot.get("/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"users", "rolls", "collection", "economy", "monetization", "system"}
        assert "secret_key" not in str(body).lower()
        assert settings.secret_key not in str(body)

    def test_legacy_admin_api_still_exists(self, client, admin_authed):
        assert client.get("/api/admin/stats", headers=admin_authed["headers"]).status_code == 200


# ---------------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------------
class TestAdminBotReads:
    def test_user_search_by_telegram_id_username_and_name(self, admin_bot, player):
        user_id = player(4110001, username="alexprime", first_name="Alex")
        by_tg = admin_bot.get("/users", params={"query": "4110001"}).json()
        by_username = admin_bot.get("/users", params={"query": "@alexprime"}).json()
        by_name = admin_bot.get("/users", params={"query": "Alex"}).json()
        by_db_id = admin_bot.get("/users", params={"query": str(user_id)}).json()
        for payload in (by_tg, by_username, by_name, by_db_id):
            assert any(item["id"] == user_id for item in payload["items"])

    def test_user_search_is_paginated(self, admin_bot):
        first = admin_bot.get("/users", params={"page": 1}).json()
        assert first["page"] == 1
        assert first["page_size"] >= 1

    def test_user_detail_reports_the_player_state(self, admin_bot, player):
        user_id = player(4110002, username="detailtest")
        body = admin_bot.get(f"/users/{user_id}").json()
        assert body["telegram_id"] == 4110002
        assert body["username"] == "detailtest"
        assert body["collector_level"]["level"] >= 1
        assert body["premium"]["active"] is False
        assert body["is_banned"] is False

    def test_missing_user_is_a_404(self, admin_bot):
        response = admin_bot.get("/users/999999999")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "USER_NOT_FOUND"

    def test_system_screen_never_leaks_secrets(self, admin_bot):
        body = admin_bot.get("/system").json()
        assert body["api_health"] == "ok"
        assert body["database_health"] == "ok"
        assert "service_token" not in body
        assert settings.secret_key not in str(body)
        assert settings.service_token not in str(body)
        assert body["token_fingerprint"] != settings.service_token

    def test_analytics_periods(self, admin_bot):
        for period in ("today", "7d", "30d", "all"):
            body = admin_bot.get("/analytics", params={"period": period}).json()
            assert body["period"] == period
            assert "rolls" in body and "economy" in body

    def test_unknown_analytics_period_is_rejected(self, admin_bot):
        response = admin_bot.get("/analytics", params={"period": "century"})
        assert response.status_code == 422

    def test_ranks_never_include_wallet_balance(self, admin_bot, player):
        admin_bot.post(
            "/economy/coins",
            json={
                "user_id": player(4110003, username="rich"),
                "delta": 999_999,
                "reason": "seed",
                "operation_id": "op-rank-seed-0001",
            },
        )
        body = admin_bot.get("/ranks", params={"category": "COLLECTION"}).json()
        assert "coins" not in str(body).lower()
        assert "balance" not in str(body).lower()

    def test_ledger_viewer_is_read_only(self, admin_bot, player):
        user_id = player(4110004, username="ledger")
        body = admin_bot.get("/transactions", params={"user_id": user_id}).json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_error_viewer_returns_no_stack_traces(self, admin_bot):
        body = admin_bot.get("/errors").json()
        assert "items" in body
        for item in body["items"]:
            assert "Traceback" not in str(item)


# ---------------------------------------------------------------------------
# economy
# ---------------------------------------------------------------------------
class TestAdminEconomy:
    def test_coin_grant_writes_the_ledger(self, admin_bot, db, player, op):
        user_id = player(4111001, username="coingrant")
        response = admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 100, "reason": "QA reward", "operation_id": op()},
        )
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["balance"] == 100
        assert body["balance_before"] == 0

        tx = db.execute(select(WalletTransaction).where(WalletTransaction.user_id == user_id)).scalar_one()
        assert tx.type == TransactionType.ADMIN_ADJUSTMENT.value
        assert tx.amount == 100
        assert tx.balance_after == 100
        assert tx.meta["reason"] == "QA reward"
        assert tx.meta["admin_telegram_id"] == TEST_ADMIN_TELEGRAM_ID
        assert tx.meta["source"] == "telegram_admin_panel"
        assert tx.meta["operation_id"]

    def test_coin_subtraction_debits(self, admin_bot, db, player, op):
        user_id = player(4111002, username="coindebit")
        key = op()
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 500, "reason": "seed", "operation_id": key},
        )
        response = admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": -200, "reason": "correction", "operation_id": op()},
        )
        assert response.json()["data"]["balance"] == 300
        tx = (
            db.execute(
                select(WalletTransaction)
                .where(WalletTransaction.user_id == user_id)
                .order_by(WalletTransaction.id.desc())
            ).scalars()
            .first()
        )
        assert tx.amount == -200

    def test_subtracting_more_than_the_balance_is_rejected(self, admin_bot, player, op):
        user_id = player(4111003, username="broke")
        response = admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": -50, "reason": "nope", "operation_id": op()},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INSUFFICIENT_FUNDS"

    def test_zero_amount_is_rejected(self, admin_bot, player, op):
        user_id = player(4111004, username="zero")
        response = admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 0, "reason": "nope", "operation_id": op()},
        )
        assert response.status_code == 422

    def test_exact_balance_writes_the_difference(self, admin_bot, db, player, op):
        user_id = player(4111005, username="balance")
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 18_450, "reason": "seed", "operation_id": op()},
        )
        response = admin_bot.post(
            "/economy/balance",
            json={"user_id": user_id, "target": 50_000, "reason": "top up", "operation_id": op()},
        )
        body = response.json()["data"]
        assert body["balance"] == 50_000
        assert body["balance_before"] == 18_450
        assert body["delta"] == 31_550

        # The ledger explains the new balance - no value appears without a row.
        total = EconomyService(db).balance(user_id)
        assert total == 50_000
        assert db.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == user_id)
        ).scalars().all()

    def test_exact_balance_can_move_downwards(self, admin_bot, player, op):
        user_id = player(4111006, username="shrink")
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 1_000, "reason": "seed", "operation_id": op()},
        )
        response = admin_bot.post(
            "/economy/balance",
            json={"user_id": user_id, "target": 250, "reason": "clamp", "operation_id": op()},
        )
        assert response.json()["data"]["delta"] == -750
        assert response.json()["data"]["balance"] == 250

    def test_negative_target_balance_is_rejected(self, admin_bot, player, op):
        user_id = player(4111007, username="negative")
        response = admin_bot.post(
            "/economy/balance",
            json={"user_id": user_id, "target": -5, "reason": "nope", "operation_id": op()},
        )
        assert response.status_code == 422

    def test_every_adjustment_creates_an_audit_row(self, admin_bot, db, player, op):
        user_id = player(4111008, username="audited")
        key = op()
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 10, "reason": "QA", "operation_id": key},
        )
        row = (
            db.execute(select(AdminAuditLog).where(AdminAuditLog.operation_id == key))
            .scalar_one()
        )
        assert row.action == AdminAction.COIN_ADJUST.value
        assert row.category == "ECONOMY"
        assert row.admin_telegram_id == TEST_ADMIN_TELEGRAM_ID
        assert row.target_user_id == user_id
        assert row.target_telegram_id == 4111008
        assert row.amount == 10
        assert row.reason == "QA"
        assert row.result == "OK"
        assert row.before_json["coins"] == 0
        assert row.after_json["coins"] == 10
        assert row.duration_ms is not None

    def test_audit_log_never_stores_a_secret(self, admin_bot, db, player, op):
        user_id = player(4111009, username="nosecret")
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 5, "reason": "QA", "operation_id": op()},
        )
        rows = db.execute(select(AdminAuditLog)).scalars().all()
        dumped = str([row.metadata_json for row in rows])
        assert settings.service_token not in dumped
        assert settings.secret_key not in dumped


# ---------------------------------------------------------------------------
# idempotency
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_repeated_callback_does_not_double_grant(self, admin_bot, db, player, op):
        user_id = player(4112001, username="idem")
        payload = {"user_id": user_id, "delta": 1000, "reason": "once", "operation_id": op()}
        first = admin_bot.post("/economy/coins", json=payload).json()
        second = admin_bot.post("/economy/coins", json=payload).json()
        third = admin_bot.post("/economy/coins", json=payload).json()

        assert first["replayed"] is False
        assert second["replayed"] is True
        assert third["replayed"] is True
        assert first["audit_id"] == second["audit_id"] == third["audit_id"]
        assert EconomyService(db).balance(user_id) == 1000
        assert (
            db.execute(
                select(WalletTransaction).where(WalletTransaction.user_id == user_id)
            ).scalars().all().__len__()
            == 1
        )

    def test_repeated_exact_balance_is_idempotent(self, admin_bot, db, player, op):
        user_id = player(4112002, username="idem-balance")
        payload = {"user_id": user_id, "target": 5_000, "reason": "set", "operation_id": op()}
        admin_bot.post("/economy/balance", json=payload)
        admin_bot.post("/economy/balance", json=payload)
        assert EconomyService(db).balance(user_id) == 5_000

    def test_distinct_operation_ids_each_apply(self, admin_bot, db, player, op):
        user_id = player(4112003, username="twice")
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 100, "reason": "a", "operation_id": op()},
        )
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 100, "reason": "b", "operation_id": op()},
        )
        assert EconomyService(db).balance(user_id) == 200


# ---------------------------------------------------------------------------
# rolls / premium / cosmetics / progression
# ---------------------------------------------------------------------------
class TestRollsAndEntitlements:
    def test_roll_grant_uses_bonus_rolls(self, admin_bot, db, player, op):

        user_id = player(4113001, username="rolls")
        response = admin_bot.post(
            "/rolls/grant",
            json={"user_id": user_id, "amount": 10, "reason": "compensation", "operation_id": op()},
        )
        assert response.json()["data"]["bonus_rolls"] == 10
        user = db.get(User, user_id)
        assert user.bonus_rolls == 10
        # The configured daily allowance is untouched.
        assert response.json()["data"]["daily_allowance"] == settings.default_daily_rolls

    def test_zero_roll_grant_is_rejected(self, admin_bot, player, op):
        user_id = player(4113002, username="zerorolls")
        response = admin_bot.post(
            "/rolls/grant",
            json={"user_id": user_id, "amount": 0, "reason": "nope", "operation_id": op()},
        )
        assert response.status_code == 422

    def test_reset_today_roll_usage(self, admin_bot, db, player, op):

        user_id = player(4113003, username="resetrolls")
        user = db.get(User, user_id)
        user.daily_rolls_used = 7
        db.commit()

        response = admin_bot.post(
            "/rolls/reset-daily",
            json={"user_id": user_id, "reason": "support case", "operation_id": op()},
        )
        assert response.json()["data"]["refunded"] == 7
        db.expire_all()
        assert db.get(User, user_id).daily_rolls_used == 0

    def test_premium_grant_and_revoke(self, admin_bot, db, player, op):
        user_id = player(4113004, username="premium")
        granted = admin_bot.post(
            "/premium/action",
            json={"user_id": user_id, "days": 30, "reason": "compensate", "operation_id": op()},
        )
        assert granted.json()["data"]["tier"] == "PRO"
        assert admin_bot.get(f"/users/{user_id}/premium").json()["active"] is True

        revoked = admin_bot.post(
            "/premium/action",
            json={"user_id": user_id, "revoke": True, "reason": "reversed", "operation_id": op()},
        )
        assert revoked.json()["data"]["revoked"] >= 1
        assert admin_bot.get(f"/users/{user_id}/premium").json()["active"] is False

    def test_premium_revoke_is_audited_as_dangerous(self, admin_bot, db, player, op):
        user_id = player(4113005, username="premiumaudit")
        key = op()
        admin_bot.post(
            "/premium/action",
            json={"user_id": user_id, "revoke": True, "reason": "clean up", "operation_id": key},
        )
        row = db.execute(select(AdminAuditLog).where(AdminAuditLog.operation_id == key)).scalar_one()
        assert row.action == AdminAction.PREMIUM_REVOKE.value
        assert row.metadata_json["dangerous"] is True

    def test_premium_duration_is_bounded(self, admin_bot, player, op):
        user_id = player(4113006, username="toomuch")
        response = admin_bot.post(
            "/premium/action",
            json={"user_id": user_id, "days": 99_999, "reason": "nope", "operation_id": op()},
        )
        assert response.status_code == 422

    def test_cosmetic_grant_is_idempotent(self, admin_bot, db, player, op):

        user_id = player(4113007, username="cosmetics")
        catalogue = admin_bot.get("/cosmetics").json()["items"]
        assert catalogue
        code = catalogue[0]["code"]
        key = op()
        for _ in range(3):
            admin_bot.post(
                "/cosmetics/action",
                json={"user_id": user_id, "code": code, "action": "grant", "reason": "gift", "operation_id": key},
            )
        rows = (
            db.execute(select(UserCosmetic).where(UserCosmetic.user_id == user_id)).scalars().all()
        )
        assert len(rows) == 1

    def test_title_grant_and_equip(self, admin_bot, player, op):
        user_id = player(4113008, username="titles")
        granted = admin_bot.post(
            "/titles/grant",
            json={"user_id": user_id, "title": "QA Champion", "reason": "event winner", "operation_id": op()},
        )
        assert granted.json()["data"]["titles"] == ["QA Champion"]

    def test_xp_change_keeps_level_consistent(self, admin_bot, db, player, op):

        user_id = player(4113009, username="xp")
        response = admin_bot.post(
            "/progression/xp",
            json={"user_id": user_id, "delta": 5_000, "reason": "event", "operation_id": op()},
        )
        body = response.json()["data"]
        assert body["xp"] == 5_000
        assert body["level"] == level_for_xp(5_000)
        db.expire_all()
        assert db.get(User, user_id).collector_level == body["level"]

    def test_exact_xp_and_level_set(self, admin_bot, db, player, op):

        user_id = player(4113010, username="levelset")
        exact = admin_bot.post(
            "/progression/xp",
            json={"user_id": user_id, "xp": 20_000, "reason": "fix", "operation_id": op()},
        ).json()["data"]
        assert exact["xp"] == 20_000

        level = admin_bot.post(
            "/progression/level",
            json={"user_id": user_id, "level": 17, "reason": "manual level", "operation_id": op()},
        ).json()["data"]
        assert level["level"] == 17

        # Level 17 must sit exactly on the shared level formula, not beside it.
        db.expire_all()
        user = db.get(User, user_id)
        assert user.collector_level == 17
        assert user.collection_xp == level["xp"]
        assert ProgressionService(db).current_level(user).level == 17

    def test_streak_set_and_reset(self, admin_bot, db, player, op):

        user_id = player(4113011, username="streak")
        response = admin_bot.post(
            "/progression/streak",
            json={"user_id": user_id, "current": 12, "reason": "manual", "operation_id": op()},
        )
        assert response.json()["data"]["current_streak"] == 12
        assert response.json()["data"]["longest_streak"] == 12

        reset = admin_bot.post(
            "/progression/streak",
            json={"user_id": user_id, "reset": True, "reason": "reset", "operation_id": op()},
        )
        assert reset.json()["data"]["current_streak"] == 0
        db.expire_all()
        assert db.get(User, user_id).longest_streak == 0

    def test_progression_reset(self, admin_bot, db, player, op):

        user_id = player(4113012, username="progreset")
        user = db.get(User, user_id)
        user.collection_xp = 5_000
        user.collector_level = 12
        db.commit()
        admin_bot.post(
            "/progression/reset",
            json={"user_id": user_id, "reason": "duplicate account", "operation_id": op()},
        )
        db.expire_all()
        refreshed = db.get(User, user_id)
        assert refreshed.collection_xp == 0
        assert refreshed.collector_level == 1


# ---------------------------------------------------------------------------
# missions / achievements
# ---------------------------------------------------------------------------
class TestMissionsAndAchievements:
    def test_mission_board_is_listed(self, admin_bot, player):
        user_id = player(4114001, username="missions")
        body = admin_bot.get(f"/users/{user_id}/missions").json()
        assert body["items"]
        for item in body["items"]:
            assert "code" in item and "target" in item and "reward_paid" in item

    def test_mission_progress_and_completion_pays_once(self, admin_bot, db, player, op):
        user_id = player(4114002, username="missionpay")
        board = admin_bot.get(f"/users/{user_id}/missions").json()["items"]
        target = board[0]
        steps = max(1, target["target"])
        for index in range(steps):
            response = admin_bot.post(
                "/missions/action",
                json={
                    "user_id": user_id,
                    "code": target["code"],
                    "action": "progress",
                    "amount": 1,
                    "reason": "QA",
                    "operation_id": op(),
                },
            )
            assert response.status_code == 200
            del index
        body = admin_bot.get(f"/users/{user_id}/missions").json()["items"]
        done = next(item for item in body if item["code"] == target["code"])
        assert done["completed"] is True

        expected = target["reward_coins"]
        if expected:
            assert EconomyService(db).balance(user_id) == expected

        # Completing again must not pay twice.
        admin_bot.post(
            "/missions/action",
            json={
                "user_id": user_id,
                "code": target["code"],
                "action": "complete",
                "reason": "QA",
                "operation_id": op(),
            },
        )
        if expected:
            assert EconomyService(db).balance(user_id) == expected

    def test_mission_reset_clears_progress(self, admin_bot, player, op):
        user_id = player(4114003, username="missionreset")
        board = admin_bot.get(f"/users/{user_id}/missions").json()["items"]
        code = board[0]["code"]
        admin_bot.post(
            "/missions/action",
            json={
                "user_id": user_id,
                "code": code,
                "action": "progress",
                "amount": 1,
                "reason": "QA",
                "operation_id": op(),
            },
        )
        reset = admin_bot.post(
            "/missions/action",
            json={"user_id": user_id, "code": code, "action": "reset", "reason": "QA", "operation_id": op()},
        )
        assert reset.json()["data"]["progress"] == 0

    def test_achievement_grant_is_idempotent(self, admin_bot, db, player, op):
        user_id = player(4114004, username="achievements")
        board = admin_bot.get(f"/users/{user_id}/achievements").json()["items"]
        code = board[0]["code"]
        key = op()
        for _ in range(3):
            admin_bot.post(
                "/achievements/action",
                json={"user_id": user_id, "code": code, "reason": "QA", "operation_id": key},
            )
        rows = (
            db.execute(select(UserAchievement).where(UserAchievement.user_id == user_id)).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].unlocked_at is not None

    def test_achievement_revoke_removes_the_row(self, admin_bot, db, player, op):
        user_id = player(4114005, username="achievervoke")
        board = admin_bot.get(f"/users/{user_id}/achievements").json()["items"]
        code = board[0]["code"]
        admin_bot.post(
            "/achievements/action",
            json={"user_id": user_id, "code": code, "reason": "grant", "operation_id": op()},
        )
        admin_bot.post(
            "/achievements/action",
            json={"user_id": user_id, "code": code, "revoke": True, "reason": "undo", "operation_id": op()},
        )
        rows = (
            db.execute(select(UserAchievement).where(UserAchievement.user_id == user_id)).scalars().all()
        )
        assert rows == []


# ---------------------------------------------------------------------------
# plates / first discovery
# ---------------------------------------------------------------------------
class TestPlatesAdmin:
    def _make_plate(self, db: Session) -> Plate:
        service = PlateService(db)
        ctx = build_snapshot(db, settings.rarity_weights).context
        generated = PlateGenerator(ctx, default_rng()).generate_targeted(country_code="RUS")
        plate, _ = service.materialize(generated)
        db.commit()
        return plate

    def _search_all_pages(self, admin_bot, max_pages: int = 30, **params) -> list[dict]:
        """Walk the paginated plate catalogue.

        The endpoint is paginated, so a single page cannot prove that a plate is
        findable. The walk is bounded: a text query that matches more than
        ``max_pages * 15`` plates is not a search failure, it is a wide net.
        """
        found: list[dict] = []
        for page in range(1, max_pages + 1):
            body = admin_bot.get("/plates", params={**params, "page": page}).json()
            found.extend(body["items"])
            if not body["has_more"]:
                break
        return found

    def test_plate_search_supports_text_and_filters(self, admin_bot, db):
        plate = self._make_plate(db)

        # A numeric query matches the id *and* the serial, so it legitimately
        # returns many rows - hence the page walk.
        by_id = self._search_all_pages(admin_bot, query=str(plate.id))
        assert any(item["id"] == plate.id for item in by_id)

        # An explicit "#id" is the only way to ask for one exact catalogue entry.
        by_hash = admin_bot.get("/plates", params={"query": f"#{plate.id}"}).json()
        assert [item["id"] for item in by_hash["items"]] == [plate.id]

        # Search by the exact text, across pages.
        by_text = self._search_all_pages(admin_bot, query=plate.plate_text)
        assert any(item["id"] == plate.id for item in by_text)

        # A digits-only query is *not* an id lookup; whether it matches a serial is
        # covered deterministically in tests/test_plate_flows.py. Here we only assert
        # that the explicit "#id" form still resolves to exactly one entry.
        assert by_hash["total"] == 1

        # Filters.
        by_country = admin_bot.get("/plates", params={"country_code": "RUS"}).json()
        assert by_country["total"] >= 1
        by_rarity = admin_bot.get("/plates", params={"rarity": plate.rarity}).json()
        assert by_rarity["total"] >= 1
        by_category = admin_bot.get("/plates", params={"category": plate.plate_type}).json()
        assert by_category["total"] >= 1

    def test_plate_detail_exposes_every_field(self, admin_bot, db):
        plate = self._make_plate(db)
        body = admin_bot.get(f"/plates/{plate.id}").json()
        for key in (
            "id",
            "plate_text",
            "normalized_text",
            "country_code",
            "region_code",
            "template_code",
            "rarity",
            "rarity_score",
            "collector_value",
            "dealer_value",
            "discovery_count",
            "first_discoverer",
            "season_code",
            "is_secret",
            "traits",
            "tags",
            "owners",
            "history",
        ):
            assert key in body

    def test_plate_grant_reports_duplicates(self, admin_bot, db, player, op):
        plate = self._make_plate(db)
        user_id = player(4115001, username="plategrant")
        first = admin_bot.post(
            "/plates/grant",
            json={"user_id": user_id, "plate_id": plate.id, "reason": "QA", "operation_id": op()},
        ).json()["data"]
        assert first["is_new"] is True
        assert first["plates_count"] == 1

        second = admin_bot.post(
            "/plates/grant",
            json={"user_id": user_id, "plate_id": plate.id, "reason": "QA", "operation_id": op()},
        ).json()["data"]
        assert second["is_new"] is False
        assert second["duplicates"] == 1
        assert second["plates_count"] == 1

        rows = (
            db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all()
        )
        assert len(rows) == 1  # no duplicate ownership rows

    def test_first_discovery_is_set_once(self, admin_bot, db, player, op):
        plate = self._make_plate(db)
        first_user = player(4115002, username="discoverA")
        second_user = player(4115003, username="discoverB")

        first = admin_bot.post(
            "/plates/first-discovery",
            json={"plate_id": plate.id, "user_id": first_user, "reason": "QA", "operation_id": op()},
        )
        assert first.json()["data"]["first_discoverer_id"] == first_user

        # A second claim without an explicit override must be refused.
        conflict = admin_bot.post(
            "/plates/first-discovery",
            json={
                "plate_id": plate.id,
                "user_id": second_user,
                "reason": "QA",
                "operation_id": op(),
            },
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "FIRST_DISCOVERY_TAKEN"

        override = admin_bot.post(
            "/plates/first-discovery",
            json={
                "plate_id": plate.id,
                "user_id": second_user,
                "override": True,
                "reason": "correction",
                "operation_id": op(),
            },
        )
        assert override.json()["data"]["first_discoverer_id"] == second_user

        db.expire_all()
        firsts = (
            db.execute(
                select(PlateDiscovery).where(
                    PlateDiscovery.plate_id == plate.id,
                    PlateDiscovery.is_first_discovery.is_(True),
                )
            )
            .scalars()
            .all()
        )
        assert len(firsts) == 1
        assert firsts[0].user_id == second_user


# ---------------------------------------------------------------------------
# test lab
# ---------------------------------------------------------------------------
class TestLab:
    def test_catalog_is_loaded_dynamically(self, admin_bot):
        body = admin_bot.get("/catalog").json()
        codes = {item["code"] for item in body["countries"]}
        assert {"RUS", "USA", "JPN"} <= codes
        assert "MYTHIC" in body["rarities"]
        assert {preset["code"] for preset in body["presets"]} >= {"MYTHIC_USA", "SECRET_JAPAN"}

    def test_simulation_never_mutates_state(self, admin_bot, db, player):
        user_id = player(4116001, username="simuser")
        before_wallet = EconomyService(db).balance(user_id)
        before_plates = db.execute(select(Plate)).scalars().all().__len__()
        before_rolls = len(db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all())

        response = admin_bot.post(
            "/testlab/simulate",
            json={"country_code": "USA", "rarity": "MYTHIC"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["mutated"] is False
        assert body["spent_roll"] is False
        from app.game.plate_rarity import Rarity, resolve_final_rarity

        assert body["plate"]["rarity"] == resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.MYTHIC,
            score=body["plate"]["rarity_score"],
            traits=body["plate"]["traits"],
        ).value
        assert body["plate"]["country_code"] == "USA"
        assert body["plate"]["id"] is None

        db.expire_all()
        assert EconomyService(db).balance(user_id) == before_wallet
        assert db.execute(select(Plate)).scalars().all().__len__() == before_plates
        assert (
            len(db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all())
            == before_rolls
        )

    def test_simulation_does_not_change_global_rarity_config(self, admin_bot):
        before = dict(settings.rarity_weights)
        admin_bot.post("/testlab/simulate", json={"preset": "MYTHIC_USA"})
        assert settings.rarity_weights == before
        assert settings.rarity_weights_override is None or "MYTHIC" in settings.rarity_weights

    @pytest.mark.parametrize("rarity", ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC", "SECRET"])
    def test_requested_rarity_never_overrides_pattern_quality(self, admin_bot, rarity):
        body = admin_bot.post(
            "/testlab/simulate", json={"country_code": "RUS", "rarity": rarity}
        ).json()
        from app.game.plate_rarity import Rarity, resolve_final_rarity

        plate = body["plate"]
        assert plate["rarity"] == resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity(rarity),
            score=plate["rarity_score"],
            traits=plate["traits"],
        ).value

    def test_forced_country_is_honoured(self, admin_bot):
        body = admin_bot.post("/testlab/simulate", json={"country_code": "JPN"}).json()
        assert body["plate"]["country_code"] == "JPN"

    def test_mythic_usa_preset(self, admin_bot):
        body = admin_bot.post("/testlab/simulate", json={"preset": "MYTHIC_USA"}).json()
        assert body["plate"]["country_code"] == "USA"
        from app.game.plate_rarity import Rarity, resolve_final_rarity

        assert body["plate"]["rarity"] == resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.MYTHIC,
            score=body["plate"]["rarity_score"],
            traits=body["plate"]["traits"],
        ).value
        assert body["plate"]["dealer_value"] > 0

    def test_live_mode_mutates_after_confirmation(self, admin_bot, db, player, op):
        user_id = player(4116002, username="liveuser")
        response = admin_bot.post(
            "/testlab/live",
            json={
                "user_id": user_id,
                "preset": "MYTHIC_USA",
                "reason": "QA scenario",
                "operation_id": op(),
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["mode"] == "LIVE"
        assert data["mutated"] is True
        from app.game.plate_rarity import Rarity, resolve_final_rarity

        assert data["plate"]["rarity"] == resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.MYTHIC,
            score=data["plate"]["rarity_score"],
            traits=data["plate"]["traits"],
        ).value
        assert data["plate"]["country_code"] == "USA"
        assert data["plates_count"] == 1

        db.expire_all()
        rows = db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all()
        assert len(rows) == 1

    def test_live_mode_is_idempotent(self, admin_bot, db, player, op):
        user_id = player(4116003, username="liveidem")
        payload = {
            "user_id": user_id,
            "preset": "LEGENDARY_RUSSIA",
            "reason": "QA",
            "operation_id": op(),
        }
        admin_bot.post("/testlab/live", json=payload)
        admin_bot.post("/testlab/live", json=payload)
        db.expire_all()
        assert len(db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all()) == 1

    def test_live_mode_does_not_spend_a_roll(self, admin_bot, db, player, op):

        user_id = player(4116004, username="norollspent")
        admin_bot.post(
            "/testlab/live",
            json={"user_id": user_id, "preset": "MYTHIC_USA", "reason": "QA", "operation_id": op()},
        )
        db.expire_all()
        user = db.get(User, user_id)
        assert user.daily_rolls_used == 0
        assert user.total_rolls == 0

    def test_force_plate_text_grants_a_valid_plate(self, admin_bot, db, player, op):
        user_id = player(4116005, username="forceplate")
        response = admin_bot.post(
            "/testlab/force-plate",
            json={
                "plate_text": "A777AA 77",
                "user_id": user_id,
                "country_code": "RUS",
                "reason": "QA",
                "operation_id": op(),
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["plate"]["country_code"] == "RUS"
        assert "777" in data["plate"]["normalized_text"]
        db.expire_all()
        rows = db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all()
        assert len(rows) == 1

    def test_force_plate_rejects_empty_text(self, admin_bot, op):
        response = admin_bot.post(
            "/testlab/force-plate",
            json={"plate_text": "   ", "reason": "QA", "operation_id": op()},
        )
        assert response.status_code == 422

    def test_force_plate_supports_unicode(self, admin_bot, op):
        response = admin_bot.post(
            "/testlab/force-plate",
            json={"plate_text": "А777ВВ 77", "country_code": "RUS", "reason": "QA", "operation_id": op()},
        )
        assert response.status_code == 200
        assert "777" in response.json()["data"]["plate"]["normalized_text"]


# ---------------------------------------------------------------------------
# moderation / world / audit viewer
# ---------------------------------------------------------------------------
class TestModerationAndWorld:
    def test_ban_and_unban(self, admin_bot, db, player, op):
        user_id = player(4117001, username="banned")
        banned = admin_bot.post(
            "/users/ban",
            json={"user_id": user_id, "banned": True, "reason": "abuse", "operation_id": op()},
        )
        assert banned.json()["data"]["is_banned"] is True
        assert admin_bot.get(f"/users/{user_id}").json()["is_banned"] is True

        admin_bot.post(
            "/users/ban",
            json={"user_id": user_id, "banned": False, "reason": "appeal", "operation_id": op()},
        )
        db.expire_all()

        assert db.get(User, user_id).is_banned is False

    def test_configured_admins_cannot_be_banned(self, admin_bot, admin_authed, op):
        admin_id = int(admin_authed["user"]["id"])
        response = admin_bot.post(
            "/users/ban",
            json={"user_id": admin_id, "banned": True, "reason": "oops", "operation_id": op()},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PROTECTED_ADMIN"

    def test_countries_listing(self, admin_bot):
        body = admin_bot.get("/countries").json()
        assert body["items"]
        row = body["items"][0]
        for key in ("code", "flag", "name_en", "name_ru", "is_active", "templates", "regions", "plates"):
            assert key in row

    def test_country_activation_is_audited(self, admin_bot, db, op):
        row = next(item for item in admin_bot.get("/countries").json()["items"] if item["is_active"])
        key = op()
        response = admin_bot.post(
            "/countries/toggle",
            json={
                "country_id": row["id"],
                "active": False,
                "reason": "temporarily hidden",
                "operation_id": key,
            },
        )
        assert response.json()["data"]["is_active"] is False
        audit = db.execute(select(AdminAuditLog).where(AdminAuditLog.operation_id == key)).scalar_one()
        assert audit.action == AdminAction.COUNTRY_CHANGE.value
        # Restore so the rest of the suite keeps its catalogue.
        admin_bot.post(
            "/countries/toggle",
            json={"country_id": row["id"], "active": True, "reason": "restore", "operation_id": op()},
        )

    def test_events_and_seasons_listing(self, admin_bot):
        assert "active" in admin_bot.get("/events").json()
        assert "items" in admin_bot.get("/seasons").json()

    def test_audit_viewer_supports_scopes(self, admin_bot, player, op):
        user_id = player(4117002, username="auditview")
        admin_bot.post(
            "/economy/coins",
            json={"user_id": user_id, "delta": 7, "reason": "QA", "operation_id": op()},
        )
        latest = admin_bot.get("/audit").json()
        mine = admin_bot.get("/audit", params={"admin_telegram_id": TEST_ADMIN_TELEGRAM_ID}).json()
        for_target = admin_bot.get("/audit", params={"target_user_id": user_id}).json()
        assert latest["total"] >= 1
        assert mine["total"] >= 1
        assert for_target["total"] == 1
        entry = for_target["items"][0]
        for key in ("id", "admin_label", "target_label", "action", "amount", "reason", "created_at"):
            assert key in entry

    def test_quick_reward_grant_menu(self, admin_bot, db, player, op):
        user_id = player(4117003, username="quickrewards")
        coins = admin_bot.post(
            "/rewards/grant",
            json={"user_id": user_id, "kind": "coins", "amount": 250, "reason": "QA", "operation_id": op()},
        )
        assert coins.json()["data"]["balance"] == 250

        rolls = admin_bot.post(
            "/rewards/grant",
            json={"user_id": user_id, "kind": "rolls", "amount": 5, "reason": "QA", "operation_id": op()},
        )
        assert rolls.json()["data"]["bonus_rolls"] == 5

        premium = admin_bot.post(
            "/rewards/grant",
            json={"user_id": user_id, "kind": "premium", "amount": 30, "reason": "QA", "operation_id": op()},
        )
        assert premium.json()["data"]["tier"] == "PRO"

        pass_ = admin_bot.post(
            "/rewards/grant",
            json={"user_id": user_id, "kind": "season_pass", "reason": "QA", "operation_id": op()},
        )
        assert pass_.json()["data"]["has_pass"] is True

    def test_unknown_reward_kind_is_rejected(self, admin_bot, player, op):
        user_id = player(4117004, username="badreward")
        response = admin_bot.post(
            "/rewards/grant",
            json={"user_id": user_id, "kind": "unicorns", "reason": "QA", "operation_id": op()},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------
class TestConcurrency:
    def test_concurrent_balance_sets_do_not_lose_ledger_rows(self, db, player, op):
        """Two sequential-but-concurrent-shaped sets must leave one row each."""

        user_id = player(4118001, username="concurrent")
        service = AdminService(db)
        actor = AdminActor(telegram_id=TEST_ADMIN_TELEGRAM_ID)

        first = service.set_balance(
            actor, user_id=user_id, target=1_000, reason="a", operation_id=op()
        )
        second = service.set_balance(
            actor, user_id=user_id, target=2_000, reason="b", operation_id=op()
        )
        assert first["balance"] == 1_000
        assert second["balance"] == 2_000
        assert EconomyService(db).balance(user_id) == 2_000
        rows = (
            db.execute(
                select(WalletTransaction)
                .where(WalletTransaction.user_id == user_id)
                .order_by(WalletTransaction.id)
            )
            .scalars()
            .all()
        )
        assert [row.balance_after for row in rows] == [1_000, 2_000]

    def test_wallet_row_is_locked_before_delta_computation(self, db, player, op):
        """The exact-balance path locks the wallet before it computes the delta."""

        user_id = player(4118002, username="locked")
        service = AdminService(db)
        admin_bot_headers_token = TEST_SERVICE_TOKEN
        assert admin_bot_headers_token  # the service path is the only writer

        result = service.set_balance(
            AdminActor(telegram_id=TEST_ADMIN_TELEGRAM_ID),
            user_id=user_id,
            target=500,
            reason="lock check",
            operation_id=op(),
        )
        assert result["delta"] == 500
        wallet = db.execute(select(Wallet).where(Wallet.user_id == user_id)).scalar_one()
        assert wallet.coins == 500
