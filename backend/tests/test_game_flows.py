"""Integration tests for the critical server-authoritative flows."""

from __future__ import annotations


class FixedRng:
    """Deterministic RNG used to force a specific number in tests."""

    def __init__(self, number: int) -> None:
        self.number = number

    def random(self) -> float:
        return 0.0

    def randint(self, a: int, b: int) -> int:
        return self.number

    def choice(self, seq):
        return seq[0]


class TestRollFlow:
    def test_roll_is_server_decided(self, client, authed):
        session = authed(600001)
        response = client.post("/api/roll", headers=session["headers"])
        assert response.status_code == 200

        payload = response.json()
        assert payload["success"] is True
        number = payload["number"]["number"]
        assert len(number) == 4 and number.isdigit()
        assert payload["rarity"] in {"COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC", "SECRET"}
        assert payload["number"]["value"] > 0
        assert payload["number"]["story"]
        assert payload["share_start_param"] == f"number_{number}"

    def test_client_cannot_force_a_number(self, client, authed):
        session = authed(600002)
        for body in (
            {"number": "7777", "rarity": "MYTHIC", "value": 999999},
            {"number": 7777, "rarity": "SECRET"},
            {"result": {"value_str": "0000"}},
        ):
            response = client.post("/api/roll", headers=session["headers"], json=body)
            assert response.status_code == 200
            result = response.json()
            # The server's own value is authoritative; extra fields are ignored.
            assert result["number"]["value"] > 0
            assert result["value"] != 999999

    def test_rolls_are_limited(self, client, authed):
        session = authed(600003)
        allowance = client.get("/api/daily", headers=session["headers"]).json()["daily_allowance"]

        for _ in range(allowance):
            assert client.post("/api/roll", headers=session["headers"]).status_code == 200

        response = client.post("/api/roll", headers=session["headers"])
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "NO_ROLLS_AVAILABLE"

    def test_roll_history_is_recorded(self, client, authed):
        session = authed(600004)
        client.post("/api/roll", headers=session["headers"])
        history = client.get("/api/roll/history", headers=session["headers"]).json()
        assert len(history) == 1
        assert history[0]["value"] > 0

    def test_idempotency_key_prevents_double_rewards(self, client, authed):
        session = authed(600005)
        headers = {**session["headers"], "Idempotency-Key": "roll-key-1"}

        first = client.post("/api/roll", headers=headers).json()
        second = client.post("/api/roll", headers=headers).json()

        assert first["roll_id"] == second["roll_id"]
        assert first["number"]["number"] == second["number"]["number"]
        assert second["replayed"] is True
        assert len(client.get("/api/roll/history", headers=session["headers"]).json()) == 1

    def test_profile_counters_track_rolls(self, client, authed):
        session = authed(600006)
        client.post("/api/roll", headers=session["headers"])
        profile = client.get("/api/user", headers=session["headers"]).json()
        assert profile["total_rolls"] == 1
        assert profile["unique_numbers"] == 1
        assert profile["best_value"] > 0


class TestDailyReward:
    def test_claim_grants_coins_and_rolls(self, client, authed):
        session = authed(600010)
        before = client.get("/api/user", headers=session["headers"]).json()["coins"]

        payload = client.post("/api/daily/claim", headers=session["headers"]).json()
        assert payload["coins_granted"] > 0
        assert payload["streak"] == 1

        after = client.get("/api/user", headers=session["headers"]).json()["coins"]
        assert after > before

    def test_claim_is_rejected_twice_in_a_day(self, client, authed):
        session = authed(600011)
        assert client.post("/api/daily/claim", headers=session["headers"]).status_code == 200
        second = client.post("/api/daily/claim", headers=session["headers"])
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "DAILY_ALREADY_CLAIMED"


class TestCollection:
    def test_collection_is_paginated_and_shaped(self, client, authed):
        session = authed(600020)
        for _ in range(3):
            client.post("/api/roll", headers=session["headers"])

        payload = client.get("/api/collection?page=1&page_size=2", headers=session["headers"]).json()
        assert len(payload["items"]) <= 2
        assert payload["total"] >= 1
        assert payload["target"] == 10_000
        assert set(payload["rarity_breakdown"]) >= {"COMMON", "MYTHIC"}

    def test_number_detail_works_for_undiscovered_numbers(self, client, authed):
        session = authed(600021)
        payload = client.get("/api/numbers/4242", headers=session["headers"]).json()
        assert payload["number"] == "4242"
        assert payload["owned"] is False
        assert payload["value"] > 0

    def test_invalid_number_is_rejected(self, client, authed):
        session = authed(600022)
        assert client.get("/api/numbers/12345", headers=session["headers"]).status_code == 422

    def test_collection_filters_by_rarity(self, client, authed):
        session = authed(600023)
        client.post("/api/roll", headers=session["headers"])
        payload = client.get("/api/collection?rarity=MYTHIC", headers=session["headers"]).json()
        assert all(item["rarity"] == "MYTHIC" for item in payload["items"])


class TestContainers:
    def test_listing_shows_prices_and_affordability(self, client, authed):
        session = authed(600030)
        payload = client.get("/api/containers", headers=session["headers"]).json()
        assert {"basic", "premium", "mystery"} <= {row["code"] for row in payload}
        basic = next(row for row in payload if row["code"] == "basic")
        assert basic["price"] == 100
        assert basic["affordable"] is False

    def test_purchase_without_funds_is_rejected(self, client, authed):
        session = authed(600031)
        response = client.post("/api/containers/open", headers=session["headers"], json={"code": "basic"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INSUFFICIENT_FUNDS"

    def test_premium_box_is_locked_for_free_users(self, client, authed):
        session = authed(600032)
        response = client.post("/api/containers/open", headers=session["headers"], json={"code": "pro"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONTAINER_UNAVAILABLE"

    def test_purchase_is_idempotent_and_deducts_once(self, client, authed, admin_authed):
        session = authed(600033)
        profile = client.get("/api/user", headers=session["headers"]).json()
        adjustment = client.post(
            "/api/admin/users/coins",
            headers=admin_authed["headers"],
            json={"user_id": profile["id"], "delta": 5000, "reason": "test"},
        )
        assert adjustment.status_code == 200
        balance_before = client.get("/api/user", headers=session["headers"]).json()["coins"]
        assert balance_before == 5000

        headers = {**session["headers"], "Idempotency-Key": "box-1"}
        first = client.post("/api/containers/open", headers=headers, json={"code": "basic"})
        assert first.status_code == 200, first.text
        second = client.post("/api/containers/open", headers=headers, json={"code": "basic"})
        assert second.status_code == 200, second.text

        first_payload, second_payload = first.json(), second.json()
        assert first_payload["opening_id"] == second_payload["opening_id"]
        assert second_payload["replayed"] is True

        # Exactly one purchase must appear in the ledger, whatever the rewards.
        ledger = client.get(
            "/api/admin/economy/transactions?tx_type=CONTAINER_PURCHASE",
            headers=admin_authed["headers"],
        ).json()
        purchases = [row for row in ledger if row["user_id"] == profile["id"]]
        assert len(purchases) == 1
        assert purchases[0]["amount"] == -100

        # The balance reflects the purchase plus any achievement rewards granted.
        earned = sum(item["reward_coins"] for item in first_payload["unlocked_achievements"])
        balance_after = client.get("/api/user", headers=session["headers"]).json()["coins"]
        assert balance_after == balance_before - 100 + earned

    def test_unknown_container_is_not_found(self, client, authed):
        session = authed(600034)
        response = client.post("/api/containers/open", headers=session["headers"], json={"code": "nope"})
        assert response.status_code == 404


class TestDuplicates:
    def test_conversion_requires_a_duplicate(self, client, authed):
        session = authed(600040)
        roll = client.post("/api/roll", headers=session["headers"]).json()
        response = client.post(f"/api/numbers/{roll['number']['number']}/convert", headers=session["headers"])
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_DUPLICATES"

    def test_duplicate_is_flagged_and_convertible(self, client, authed, db):
        session = authed(600041)
        profile = client.get("/api/user", headers=session["headers"]).json()

        from app.models.user import User
        from app.services.rolls import RollService

        user = db.get(User, profile["id"])
        service = RollService(db, rng=FixedRng(3131))

        first = service.perform_roll(user)
        second = service.perform_roll(user)
        db.expire_all()

        assert first.number.value_str == "3131"
        assert first.is_duplicate is False
        assert second.is_duplicate is True
        # Value decays slightly as a number becomes less "novel".
        assert 0 < second.value <= first.value

        balance_before = client.get("/api/user", headers=session["headers"]).json()["coins"]
        response = client.post("/api/numbers/3131/convert", headers=session["headers"])
        assert response.status_code == 200
        payload = response.json()
        assert payload["number"] == "3131"
        assert payload["coins_gained"] > 0
        assert payload["duplicates_left"] == 0
        assert payload["balance"] > balance_before

        detail = client.get("/api/numbers/3131", headers=session["headers"]).json()
        assert detail["owned"] is True
        assert detail["duplicate_count"] == 0
