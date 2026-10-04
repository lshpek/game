"""Audit durability: a failed admin action must stay observable.

The audit row used to be written in the same transaction as the mutation, so a
failed mutation rolled the *evidence* back too: an operator asking "did someone try
to grant this?" was answered by a database that had forgotten the attempt.

The contract asserted here:

* a successful operation records ``OK`` with before/after state;
* a rejected validation records nothing (it never claimed an id);
* a mutation that fails *after* the claim records ``FAILED`` in its own committed
  transaction;
* the FAILED row keeps the operation id, the actor, the target and the original
  timestamp;
* a retry of the same operation id replays instead of running again;
* the failure metadata carries a short diagnostic and never a secret.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.models.admin import AdminAuditLog
from app.models.enums import AdminAction, AdminCategory
from app.services.admin import AdminActor, AdminService
from tests.conftest import TEST_ADMIN_TELEGRAM_ID, TEST_SERVICE_TOKEN
from tests.test_platform import make_user


@pytest.fixture
def actor() -> AdminActor:
    return AdminActor(telegram_id=TEST_ADMIN_TELEGRAM_ID, user_id=None)


def _rows(db: Session, operation_id: str) -> list[AdminAuditLog]:
    return list(
        db.execute(select(AdminAuditLog).where(AdminAuditLog.operation_id == operation_id)).scalars()
    )


class TestSuccessfulOperations:
    def test_a_successful_action_records_ok_with_state(self, client, db, actor):
        user = make_user(db, client, 890001)
        service = AdminService(db)
        result = service.adjust_coins(
            actor,
            user_id=user.id,
            delta=500,
            reason="support ticket 1",
            operation_id="op-audit-ok-1",
        )
        assert result["replayed"] is False

        rows = _rows(db, "op-audit-ok-1")
        assert len(rows) == 1
        row = rows[0]
        assert row.result == "OK"
        assert row.action == AdminAction.COIN_ADJUST.value
        assert row.category == AdminCategory.ECONOMY.value
        assert row.target_user_id == user.id
        assert row.target_telegram_id == user.telegram_id
        assert row.admin_telegram_id == TEST_ADMIN_TELEGRAM_ID
        assert row.amount == 500
        assert row.reason == "support ticket 1"
        assert row.before_json is not None
        assert row.result_json is not None
        assert row.created_at is not None

    def test_a_replay_returns_the_original_payload(self, client, db, actor):
        """A retried request must not change shape, or the caller cannot tell."""
        user = make_user(db, client, 890002)
        service = AdminService(db)
        first = service.adjust_coins(
            actor, user_id=user.id, delta=250, reason="support ticket 2", operation_id="op-audit-replay-1"
        )
        second = service.adjust_coins(
            actor, user_id=user.id, delta=250, reason="support ticket 2", operation_id="op-audit-replay-1"
        )
        assert second["replayed"] is True
        assert second["audit_id"] == first["audit_id"]
        assert {k: v for k, v in second.items() if k != "replayed"} == {
            k: v for k, v in first.items() if k != "replayed"
        }
        assert len(_rows(db, "op-audit-replay-1")) == 1

    def test_each_operation_type_is_recorded_under_its_own_category(self, client, db, actor):
        user = make_user(db, client, 890003)
        service = AdminService(db)
        service.adjust_coins(
            actor, user_id=user.id, delta=10, reason="coins", operation_id="op-audit-cat-1"
        )
        service.grant_rolls(
            actor, user_id=user.id, amount=3, reason="rolls", operation_id="op-audit-cat-2"
        )
        service.premium_action(
            actor, user_id=user.id, days=30, reason="pro", operation_id="op-audit-cat-3"
        )
        rows = {
            row.operation_id: row
            for row in db.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.operation_id.in_(
                        ["op-audit-cat-1", "op-audit-cat-2", "op-audit-cat-3"]
                    )
                )
            ).scalars()
        }
        assert rows["op-audit-cat-1"].category == AdminCategory.ECONOMY.value
        assert rows["op-audit-cat-2"].category == AdminCategory.ROLLS.value
        assert rows["op-audit-cat-3"].category == AdminCategory.PREMIUM.value
        assert rows["op-audit-cat-2"].amount == 3
        assert rows["op-audit-cat-3"].amount == 30


class TestRejectedValidations:
    def test_a_validation_failure_is_not_recorded_as_a_success(self, client, db, actor):
        """Nothing was attempted, so nothing is claimed."""
        user = make_user(db, client, 890010)
        service = AdminService(db)
        with pytest.raises(ValidationError):
            service.adjust_coins(
                actor,
                user_id=user.id,
                delta=0,  # a zero adjustment is rejected before anything is claimed
                reason="nothing to give",
                operation_id="op-audit-invalid-1",
            )
        assert _rows(db, "op-audit-invalid-1") == []

    def test_a_missing_target_is_not_recorded(self, client, db, actor):
        from app.core.errors import NotFoundError

        service = AdminService(db)
        with pytest.raises(NotFoundError):
            service.adjust_coins(
                actor, user_id=99999999, delta=10, reason="ghost", operation_id="op-audit-ghost-1"
            )
        assert _rows(db, "op-audit-ghost-1") == []


class TestFailedMutations:
    @staticmethod
    def _boom(*args, **kwargs):
        raise RuntimeError("database exploded")

    def test_a_failure_after_the_claim_is_recorded_as_failed(self, client, db, actor, monkeypatch):
        user = make_user(db, client, 890020)
        service = AdminService(db)
        before = len(_rows(db, "op-audit-fail-1"))
        assert before == 0

        monkeypatch.setattr(service.economy, "admin_adjust", self._boom)
        with pytest.raises(RuntimeError):
            service.adjust_coins(
                actor, user_id=user.id, delta=777, reason="boom", operation_id="op-audit-fail-1"
            )

        rows = _rows(db, "op-audit-fail-1")
        assert len(rows) == 1, "the failed attempt left no trace"
        row = rows[0]
        assert row.result == "FAILED"
        assert row.target_user_id == user.id
        assert row.admin_telegram_id == TEST_ADMIN_TELEGRAM_ID
        assert row.reason == "boom"
        assert row.created_at is not None
        assert row.metadata_json["error_type"] == "RuntimeError"
        assert row.metadata_json["original_operation_id"] == "op-audit-fail-1"

    def test_a_failed_mutation_leaves_no_game_state_behind(self, client, db, actor, monkeypatch):
        """The rollback is real: the balance must not move."""
        from app.services.economy import EconomyService

        user = make_user(db, client, 890021)
        service = AdminService(db)
        before = EconomyService(db).balance(user.id)
        monkeypatch.setattr(service.economy, "admin_adjust", self._boom)
        with pytest.raises(RuntimeError):
            service.adjust_coins(
                actor, user_id=user.id, delta=5000, reason="boom", operation_id="op-audit-fail-2"
            )
        db.expire_all()
        assert EconomyService(db).balance(user.id) == before

    def test_a_retry_after_a_failure_does_not_grant_twice(self, client, db, actor, monkeypatch):
        user = make_user(db, client, 890022)
        service = AdminService(db)
        monkeypatch.setattr(service.economy, "admin_adjust", self._boom)
        with pytest.raises(RuntimeError):
            service.adjust_coins(
                actor, user_id=user.id, delta=900, reason="boom", operation_id="op-audit-fail-3"
            )
        monkeypatch.undo()

        from app.services.economy import EconomyService

        first = service.adjust_coins(
            actor, user_id=user.id, delta=900, reason="retry", operation_id="op-audit-fail-3"
        )
        second = service.adjust_coins(
            actor, user_id=user.id, delta=900, reason="retry", operation_id="op-audit-fail-3"
        )
        assert second["replayed"] is True
        assert second["audit_id"] == first["audit_id"]
        assert EconomyService(db).balance(user.id) == 900

    def test_failure_metadata_never_stores_a_stack_trace(self, client, db, actor, monkeypatch):
        class _Secret(RuntimeError):
            pass

        def _leaky(*args, **kwargs):
            raise _Secret("token=super-secret-value")

        user = make_user(db, client, 890023)
        service = AdminService(db)
        monkeypatch.setattr(service.economy, "admin_adjust", _leaky)
        with pytest.raises(_Secret):
            service.adjust_coins(
                actor, user_id=user.id, delta=1, reason="leak", operation_id="op-audit-fail-4"
            )
        row = _rows(db, "op-audit-fail-4")[0]
        assert row.metadata_json["error_type"] == "_Secret"
        assert "Traceback" not in row.metadata_json["error_message"]
        # The message is kept for diagnosis, but truncated to a single line.
        assert "\n" not in row.metadata_json["error_message"]

    def test_a_failed_action_is_visible_in_the_audit_viewer(self, client, db, actor, monkeypatch):
        user = make_user(db, client, 890024)
        service = AdminService(db)
        monkeypatch.setattr(service.economy, "admin_adjust", self._boom)
        with pytest.raises(RuntimeError):
            service.adjust_coins(
                actor, user_id=user.id, delta=7, reason="boom", operation_id="op-audit-fail-5"
            )
        monkeypatch.undo()

        response = client.get(
            "/api/admin/bot/audit",
            headers={
                "X-Service-Token": TEST_SERVICE_TOKEN,
                "X-Admin-Telegram-Id": str(TEST_ADMIN_TELEGRAM_ID),
            },
            params={"result": "FAILED"},
        )
        assert response.status_code == 200, response.text
        assert any(item["operation_id"] == "op-audit-fail-5" for item in response.json()["items"])


class TestAuditViewer:
    def test_two_admins_each_see_only_their_own_log(self, client, db, monkeypatch):
        """Regression: the panel's "mine" scope reported the first configured id.

        With more than one operator, "mine" has to mean *the current actor* - so the
        test acts as the second admin and must not see the first admin's rows.
        """
        from app.core.config import settings

        monkeypatch.setattr(settings, "admin_telegram_ids", frozenset({900001, 900002}))
        first = {"X-Service-Token": TEST_SERVICE_TOKEN, "X-Admin-Telegram-Id": "900001"}
        second = {"X-Service-Token": TEST_SERVICE_TOKEN, "X-Admin-Telegram-Id": "900002"}

        service = AdminService(db)
        user = make_user(db, client, 890030)
        service.adjust_coins(
            AdminActor(telegram_id=900001, user_id=None),
            user_id=user.id,
            delta=11,
            reason="by admin one",
            operation_id="op-audit-mine-1",
        )
        service.adjust_coins(
            AdminActor(telegram_id=900002, user_id=None),
            user_id=user.id,
            delta=22,
            reason="by admin two",
            operation_id="op-audit-mine-2",
        )

        mine_one = client.get("/api/admin/bot/audit", headers=first, params={"admin_telegram_id": 900001}).json()
        mine_two = client.get("/api/admin/bot/audit", headers=second, params={"admin_telegram_id": 900002}).json()
        mine_one_ids = {item["operation_id"] for item in mine_one["items"]}
        mine_two_ids = {item["operation_id"] for item in mine_two["items"]}
        assert "op-audit-mine-1" in mine_one_ids
        assert "op-audit-mine-1" not in mine_two_ids
        assert "op-audit-mine-2" in mine_two_ids
        assert "op-audit-mine-2" not in mine_one_ids

        everyone = client.get("/api/admin/bot/audit", headers=first).json()
        ids = {item["operation_id"] for item in everyone["items"]}
        assert {"op-audit-mine-1", "op-audit-mine-2"} <= ids

    def test_the_audit_viewer_can_be_filtered_to_failures(self, client, db, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "admin_telegram_ids", frozenset({900001}))
        headers = {"X-Service-Token": TEST_SERVICE_TOKEN, "X-Admin-Telegram-Id": "900001"}
        service = AdminService(db)
        user = make_user(db, client, 890032)
        service.adjust_coins(
            AdminActor(telegram_id=900001, user_id=None),
            user_id=user.id,
            delta=5,
            reason="ok one",
            operation_id="op-audit-filter-ok",
        )

        def _boom(*args, **kwargs):
            raise RuntimeError("nope")

        monkeypatch.setattr(service.economy, "admin_adjust", _boom)
        with pytest.raises(RuntimeError):
            service.adjust_coins(
                AdminActor(telegram_id=900001, user_id=None),
                user_id=user.id,
                delta=5,
                reason="bad one",
                operation_id="op-audit-filter-fail",
            )

        failed = client.get("/api/admin/bot/audit", headers=headers, params={"result": "FAILED"}).json()
        ids = {item["operation_id"] for item in failed["items"]}
        assert "op-audit-filter-fail" in ids
        assert "op-audit-filter-ok" not in ids

    def test_the_audit_viewer_paginates(self, client, db, actor):
        user = make_user(db, client, 890031)
        service = AdminService(db)
        for index in range(5):
            service.adjust_coins(
                actor,
                user_id=user.id,
                delta=index + 1,
                reason=f"page {index}",
                operation_id=f"op-audit-page-{index}",
            )
        headers = {
            "X-Service-Token": TEST_SERVICE_TOKEN,
            "X-Admin-Telegram-Id": str(TEST_ADMIN_TELEGRAM_ID),
        }
        page1 = client.get(
            "/api/admin/bot/audit", headers=headers, params={"page": 1, "page_size": 2, "target_user_id": user.id}
        ).json()
        page2 = client.get(
            "/api/admin/bot/audit", headers=headers, params={"page": 2, "page_size": 2, "target_user_id": user.id}
        ).json()
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        assert page1["has_more"] is True
        ids = {item["id"] for item in page1["items"]} & {item["id"] for item in page2["items"]}
        assert ids == set(), "audit pages overlapped"
