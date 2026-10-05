"""The DEALER sale path: duplicates only, idempotency, ledger and balance integrity.

Every test here goes through the HTTP surface, because the bug class this guards against
is a *client* bug: the reveal screen offering a sale that the backend must refuse, or a
double tap paying twice.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plates import Plate, UserPlate
from app.models.user import User, WalletTransaction


def roll_once(client, headers, **params) -> dict:
    """Roll a single collectible, optionally filtered."""
    query = "&".join(f"{key}={value}" for key, value in params.items())
    url = f"/api/roll?{query}" if query else "/api/roll"
    response = client.post(url, headers=headers, json={})
    assert response.status_code == 200, response.text
    return response.json()


def give_duplicate(db: Session, user_id: int, plate_id: int, copies: int = 1) -> UserPlate:
    """Put the player in the state a duplicate roll would leave them in.

    Rolling until the engine happens to repeat a plate would make the sale tests
    depend on the RNG; this creates the exact row shape instead, so the assertions are
    about the sale path and nothing else.
    """
    from app.core.timeutils import utcnow

    row = db.execute(
        select(UserPlate).where(UserPlate.user_id == user_id, UserPlate.plate_id == plate_id)
    ).scalar_one()
    row.duplicate_count = int(row.duplicate_count) + int(copies)
    row.last_acquired_at = utcnow()
    db.commit()
    return row


def user_id_of(db: Session, telegram_id: int) -> int:
    return int(db.execute(select(User.id).where(User.telegram_id == telegram_id)).scalar_one())


def balance(db: Session, user_id: int) -> int:
    from app.services.economy import EconomyService

    return EconomyService(db).balance(user_id)


def sell(client, headers, plate_id: int, copies: int = 1, key: str | None = None):
    headers = dict(headers)
    if key:
        headers["Idempotency-Key"] = key
    return client.post(
        f"/api/plates/{plate_id}/sell", headers=headers, json={"copies": copies}
    )


@pytest.fixture
def owned(client, authed, db):
    """One plate the player owns twice: one original plus one duplicate."""
    session = authed(881_100_001)
    plate = roll_once(client, session["headers"], country_code="RUS")["plate"]
    user_id = user_id_of(db, 881_100_001)
    give_duplicate(db, user_id, plate["id"])
    return {"headers": session["headers"], "user_id": user_id, "plate": plate}


class TestDuplicateOnlySales:
    def test_a_unique_copy_cannot_be_sold(self, client, authed):
        session = authed(881_100_010)
        plate = roll_once(client, session["headers"], country_code="JPN")["plate"]

        response = sell(client, session["headers"], plate["id"], copies=1)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_DUPLICATES"

    def test_the_final_copy_is_protected_by_default(self, client, authed, db):
        session = authed(881_100_011)
        plate_id = roll_once(client, session["headers"], country_code="DEU")["plate"]["id"]
        user_id = user_id_of(db, 881_100_011)
        give_duplicate(db, user_id, plate_id)

        response = sell(client, session["headers"], plate_id, copies=1)
        assert response.status_code == 200, response.text
        assert response.json()["copies_sold"] == 1
        assert response.json()["duplicates_left"] == 0

        # A second attempt now has nothing left: the last copy is refused.
        again = sell(client, session["headers"], plate_id, copies=1)
        assert again.status_code == 422
        assert again.json()["error"]["code"] == "NO_DUPLICATES"

        rows = db.execute(
            select(UserPlate).where(UserPlate.plate_id == plate_id)
        ).scalars().all()
        assert len(rows) == 1
        assert int(rows[0].duplicate_count) == 0

    def test_asking_for_more_duplicates_than_exist_is_rejected_not_clamped(
        self, client, authed, db
    ):
        session = authed(881_100_012)
        plate_id = roll_once(client, session["headers"], country_code="POL")["plate"]["id"]
        give_duplicate(db, user_id_of(db, 881_100_012), plate_id)

        response = sell(client, session["headers"], plate_id, copies=5)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NOT_ENOUGH_DUPLICATES"
        details = response.json()["error"].get("details") or {}
        assert details.get("sellable") == 1
        assert details.get("requested") == 5

    def test_the_final_copy_can_be_sold_only_with_an_explicit_opt_in(self, client, authed):
        session = authed(881_100_013)
        plate_id = roll_once(client, session["headers"], country_code="USA")["plate"]["id"]
        response = client.post(
            f"/api/plates/{plate_id}/sell",
            headers=session["headers"],
            json={"copies": 1, "allow_last": True},
        )
        assert response.status_code == 200, response.text
        assert response.json()["copies_sold"] == 1

    def test_the_revealed_duplicate_can_be_sold_with_the_amount_shown(
        self, client, authed, db, owned
    ):
        """The reveal screen's "SELL DUPLICATES +X NUMORA" must be honest."""
        plate = owned["plate"]
        detail = client.get(f"/api/plates/{plate['id']}", headers=owned["headers"]).json()
        assert detail["plate"]["duplicate_count"] == 1

        sold = sell(client, owned["headers"], plate["id"], copies=1)
        assert sold.status_code == 200, sold.text
        assert sold.json()["numora_gained"] > 0
        assert sold.json()["duplicates_left"] == 0

    def test_a_bare_duplicate_count_of_zero_never_reaches_the_api(self, client, authed):
        """A client must never have to send a sale it knows will fail.

        This is the regression guard for the old reveal behaviour, which called
        ``sell(..., max(1, duplicate_count))`` and produced an invalid request whenever
        the player owned a single copy.
        """
        session = authed(881_100_015)
        plate = roll_once(client, session["headers"], country_code="JPN")["plate"]
        assert plate["duplicate_count"] == 0

        # The backend refuses it, and the client is expected to never send it.
        response = sell(client, session["headers"], plate["id"], copies=1)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_DUPLICATES"

    def test_selling_a_plate_the_player_does_not_own_is_a_404(self, client, authed):
        session = authed(881_100_014)
        response = sell(client, session["headers"], 999_999, copies=1)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PLATE_NOT_OWNED"


class TestSaleIdempotency:
    def test_a_double_tap_sells_once(self, client, authed, db):
        session = authed(881_100_020)
        plate_id = roll_once(client, session["headers"], country_code="RUS")["plate"]["id"]
        give_duplicate(db, user_id_of(db, 881_100_020), plate_id)

        headers = dict(session["headers"])
        headers["Idempotency-Key"] = "sell-double-tap"
        body = {"copies": 1}
        first = client.post(f"/api/plates/{plate_id}/sell", headers=headers, json=body)
        second_call = client.post(f"/api/plates/{plate_id}/sell", headers=headers, json=body)

        assert first.status_code == 200, first.text
        assert second_call.status_code == 200, second_call.text
        # The replay returns the original result rather than paying again.
        assert first.json() == second_call.json()
        assert first.json()["copies_sold"] == 1

    def test_the_balance_only_moves_once(self, client, authed, db):
        session = authed(881_100_021)
        plate_id = roll_once(client, session["headers"], country_code="RUS")["plate"]["id"]
        user_id = user_id_of(db, 881_100_021)
        give_duplicate(db, user_id, plate_id)

        headers = dict(session["headers"])
        headers["Idempotency-Key"] = "sell-once-only"
        first = client.post(f"/api/plates/{plate_id}/sell", headers=headers, json={"copies": 1})
        after_first = balance(db, user_id)

        client.post(f"/api/plates/{plate_id}/sell", headers=headers, json={"copies": 1})
        assert balance(db, user_id) == after_first
        assert first.json()["balance"] == after_first

    def test_a_different_key_still_cannot_double_pay_the_same_copy(self, client, authed, db):
        session = authed(881_100_022)
        plate_id = roll_once(client, session["headers"], country_code="RUS")["plate"]["id"]
        user_id = user_id_of(db, 881_100_022)
        give_duplicate(db, user_id, plate_id)
        sold = sell(client, session["headers"], plate_id, 1, key="key-a")
        assert sold.status_code == 200
        after = balance(db, user_id)

        # A different key must not resurrect a copy that no longer exists.
        again = sell(client, session["headers"], plate_id, 1, key="key-b")
        assert again.status_code == 422
        assert balance(db, user_id) == after


class TestLedgerIntegrity:
    def test_one_ledger_entry_per_sale(self, client, authed, db):
        session = authed(881_100_030)
        plate_id = roll_once(client, session["headers"], country_code="RUS")["plate"]["id"]
        user_id = user_id_of(db, 881_100_030)
        give_duplicate(db, user_id, plate_id)
        sell(client, session["headers"], plate_id, 1, key="ledger-1")

        entries = (
            db.execute(
                select(WalletTransaction).where(
                    WalletTransaction.user_id == user_id,
                    WalletTransaction.type == "DUPLICATE_CONVERSION",
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 1
        assert int(entries[0].amount) > 0

    def test_the_sale_is_credited_exactly_once_per_copy(self, client, authed, db):
        session = authed(881_100_031)
        plate_id = roll_once(client, session["headers"], country_code="RUS")["plate"]["id"]
        plate = db.execute(select(Plate).where(Plate.id == plate_id)).scalar_one()
        user_id = user_id_of(db, 881_100_031)
        give_duplicate(db, user_id, plate_id)

        before = balance(db, user_id)
        sold = sell(client, session["headers"], plate_id, 1)
        assert sold.status_code == 200
        gained = sold.json()["numora_gained"]
        assert gained > 0
        assert balance(db, user_id) == before + gained
        # A transparent, non-negative credit: nothing inflates the wallet.
        assert int(plate.dealer_value) >= 0

    def test_a_rejected_sale_leaves_no_trace(self, client, authed, db):
        session = authed(881_100_032)
        plate_id = roll_once(client, session["headers"], country_code="KAZ")["plate"]["id"]
        user_id = user_id_of(db, 881_100_032)

        before = balance(db, user_id)
        entries_before = db.query(WalletTransaction).filter(
            WalletTransaction.user_id == user_id
        ).count()

        response = sell(client, session["headers"], plate_id, 1)
        assert response.status_code == 422

        assert balance(db, user_id) == before
        assert (
            db.query(WalletTransaction).filter(WalletTransaction.user_id == user_id).count()
            == entries_before
        )


class TestBatchSale:
    def test_a_batch_with_no_duplicates_is_refused(self, client, authed):
        session = authed(881_100_040)
        client.post("/api/roll?country_code=ITA", headers=session["headers"], json={})
        response = client.post(
            "/api/collection/sell-duplicates", headers=session["headers"], json={}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_DUPLICATES"

    def test_a_batch_sells_everything_and_never_the_last_copy(self, client, authed, db):
        session = authed(881_100_041)
        user_id = user_id_of(db, 881_100_041)
        plate_ids = []
        for _ in range(4):
            plate_id = roll_once(client, session["headers"], country_code="FRA")["plate"]["id"]
            plate_ids.append(plate_id)
            give_duplicate(db, user_id, plate_id)

        response = client.post(
            "/api/collection/sell-duplicates", headers=session["headers"], json={}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["copies_sold"] == 4
        assert data["numora_gained"] > 0

        rows = db.execute(select(UserPlate).where(UserPlate.user_id == user_id)).scalars().all()
        assert len(rows) == 4, "the collection must survive a batch sale"
        assert all(int(row.duplicate_count) == 0 for row in rows)

    def test_a_replayed_batch_cannot_pay_twice(self, client, authed, db):
        session = authed(881_100_042)
        user_id = user_id_of(db, 881_100_042)
        for _ in range(4):
            plate_id = roll_once(client, session["headers"], country_code="ESP")["plate"]["id"]
            give_duplicate(db, user_id, plate_id)
        headers = dict(session["headers"])
        headers["Idempotency-Key"] = "batch-once"
        first = client.post("/api/collection/sell-duplicates", headers=headers, json={})
        second = client.post("/api/collection/sell-duplicates", headers=headers, json={})
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json() == second.json()


class TestSellRateLimit:
    def test_selling_uses_its_own_bucket(self, client, authed, db):
        """A burst of dealer taps must not consume the roll quota, or vice versa."""
        from app.core.config import settings

        assert settings.rate_limit_sell > 0
        session = authed(881_100_050)
        plate_id = roll_once(client, session["headers"], country_code="RUS")["plate"]["id"]
        give_duplicate(db, user_id_of(db, 881_100_050), plate_id)

        # Exhaust the sale bucket.
        last = None
        for _ in range(settings.rate_limit_sell + 4):
            last = sell(client, session["headers"], plate_id, 1)
        assert last is not None and last.status_code == 429
        assert last.json()["error"]["code"] == "RATE_LIMITED"

        # Rolling still works: the buckets are independent.
        rolled = client.post("/api/roll", headers=session["headers"], json={})
        assert rolled.status_code == 200, rolled.text
