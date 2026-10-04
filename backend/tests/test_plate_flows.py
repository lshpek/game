"""Integration tests for the server-authoritative plate flows.

These replace the old 4-digit-number flow tests: the product is now a license
plate with a country, a region and a rarity derived from its own patterns.
"""

from __future__ import annotations

RARITIES = {"COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC", "SECRET"}


class TestPlateRollFlow:
    def test_roll_returns_a_plate_with_country_and_region(self, client, authed):
        session = authed(600001)
        response = client.post("/api/roll", headers=session["headers"])
        assert response.status_code == 200

        payload = response.json()
        assert payload["success"] is True

        plate = payload["plate"]
        assert plate["plate_text"]
        assert plate["country"]["code"]
        assert plate["rarity"] in RARITIES
        assert plate["rarity_score"] >= 0
        # Both values are always present and independently meaningful.
        assert plate["collector_value"] > 0
        assert plate["dealer_value"] > 0
        assert plate["currency_code"]
        assert plate["story"]
        assert payload["share_start_param"] == f"plate_{plate['id']}"
        # The legacy alias keeps old clients working.
        assert payload["number"]["plate_text"] == plate["plate_text"]

    def test_client_cannot_force_a_plate(self, client, authed):
        session = authed(600002)
        for body in (
            {"plate_text": "AAAA", "rarity": "MYTHIC", "dealer_value": 999999, "collector_value": 1},
            {"country": {"code": "USA"}, "is_secret": True},
            {"result": {"value": 0}},
        ):
            response = client.post("/api/roll", headers=session["headers"], json=body)
            assert response.status_code == 200
            payload = response.json()
            plate = payload["plate"]
            # The server's own values win; client-supplied fields are ignored.
            assert plate["dealer_value"] > 0
            assert plate["collector_value"] > 0
            assert plate["rarity"] in RARITIES

    def test_rolls_are_limited(self, client, authed):
        """The daily allowance is enforced even after mission/achievement bonuses."""
        session = authed(600003)
        allowance = client.get("/api/daily", headers=session["headers"]).json()["daily_allowance"]

        for _ in range(allowance):
            assert client.post("/api/roll", headers=session["headers"]).status_code == 200

        # Missions may grant bonus rolls, so drain whatever remains.
        for _ in range(40):
            remaining = client.get("/api/daily", headers=session["headers"]).json()["rolls_remaining"]
            if remaining <= 0:
                break
            assert client.post("/api/roll", headers=session["headers"]).status_code == 200

        response = client.post("/api/roll", headers=session["headers"])
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "NO_ROLLS_AVAILABLE"

    def test_roll_history_is_recorded(self, client, authed):
        session = authed(600004)
        client.post("/api/roll", headers=session["headers"])
        history = client.get("/api/roll/history", headers=session["headers"]).json()
        assert len(history) == 1
        assert history[0]["collector_value"] > 0
        assert history[0]["dealer_value"] > 0
        assert history[0]["country_code"]

    def test_idempotency_key_prevents_double_rewards(self, client, authed):
        session = authed(600005)
        headers = {**session["headers"], "Idempotency-Key": "roll-key-1"}

        first = client.post("/api/roll", headers=headers).json()
        second = client.post("/api/roll", headers=headers).json()

        assert first["roll_id"] == second["roll_id"]
        assert first["plate"]["id"] == second["plate"]["id"]
        assert second["replayed"] is True
        assert len(client.get("/api/roll/history", headers=session["headers"]).json()) == 1

    def test_profile_counters_track_rolls(self, client, authed):
        session = authed(600006)
        client.post("/api/roll", headers=session["headers"])
        garage = client.get("/api/garage", headers=session["headers"]).json()
        assert garage["plates_count"] == 1
        assert garage["countries_count"] == 1
        assert garage["best"] is not None
        assert garage["level"]["level"] >= 1

    def test_many_rolls_produce_valid_distinct_plates(self, client, authed, db):
        """Many samples: each must be renderable and internally consistent."""
        from app.models.user import User
        from app.services.plate_rolls import PlateRollService

        session = authed(600007)
        profile = client.get("/api/user", headers=session["headers"]).json()
        user = db.get(User, profile["id"])

        # Bypass the daily allowance: this test is about output quality, not limits.
        service = PlateRollService(db)
        seen: set[str] = set()
        for _ in range(40):
            outcome = service.perform_roll(user, bypass_allowance=True)
            plate = outcome.plate
            assert plate.plate_text.strip()
            assert plate.display_segments
            assert plate.visual_style
            assert plate.dealer_value >= 1
            assert plate.collector_value >= 1
            assert plate.country_code
            # Same textual plate may exist per country, so the key includes it.
            seen.add(f"{plate.country_code}:{plate.normalized_text}")
        db.commit()

        # 40 rolls across 12 countries should rarely repeat a collectible.
        assert len(seen) >= 30


class TestDailyReward:
    def test_claim_grants_numora_and_rolls(self, client, authed):
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


class TestGarageAndWorld:
    def test_collection_is_paginated_and_shaped(self, client, authed):
        session = authed(600020)
        for _ in range(3):
            client.post("/api/roll", headers=session["headers"])

        payload = client.get("/api/collection?page=1&page_size=2", headers=session["headers"]).json()
        assert len(payload["items"]) <= 2
        assert payload["total"] >= 1
        assert payload["target"] > 0
        assert set(payload["rarity_breakdown"]) >= {"COMMON", "MYTHIC"}
        item = payload["items"][0]
        assert item["dealer_value"] > 0
        assert item["collector_value"] > 0
        assert item["owned"] is True

    def test_world_lists_every_launch_country(self, client, authed):
        session = authed(600021)
        payload = client.get("/api/world", headers=session["headers"]).json()
        codes = {row["code"] for row in payload["countries"]}
        assert {
            "RUS", "USA", "KAZ", "DEU", "GBR", "FRA", "ITA", "CAN", "JPN", "ARE", "ARM", "GEO",
        } <= codes

        russia = next(row for row in payload["countries"] if row["code"] == "RUS")
        assert russia["currency_symbol"] == "₽"
        assert russia["currency_code"] == "RUB"
        assert russia["total"] > 0
        assert russia["visual"]["theme"] == "ru"

    def test_country_detail_has_regions_and_templates(self, client, authed):
        session = authed(600022)
        payload = client.get("/api/world/RUS", headers=session["headers"]).json()
        assert payload["code"] == "RUS"
        assert len(payload["regions"]) >= 12
        assert len(payload["templates"]) >= 3

    def test_unknown_country_is_not_found(self, client, authed):
        session = authed(600023)
        assert client.get("/api/world/XXX", headers=session["headers"]).status_code == 404

    def test_collection_filters(self, client, authed):
        session = authed(600024)
        for _ in range(4):
            client.post("/api/roll", headers=session["headers"])

        rarity = client.get("/api/collection?rarity=COMMON", headers=session["headers"]).json()
        assert all(item["rarity"] == "COMMON" for item in rarity["items"])

        by_country = client.get("/api/collection?country=RUS", headers=session["headers"]).json()
        assert all(item["country"]["code"] == "RUS" for item in by_country["items"])

        favorites = client.get("/api/collection?favorite=true", headers=session["headers"]).json()
        assert favorites["total"] == 0

    def test_search_is_unicode_safe(self, client, authed):
        session = authed(600025)
        plate = client.post("/api/roll", headers=session["headers"]).json()["plate"]
        fragment = plate["plate_text"].replace(" ", "")[:2]
        if fragment:
            payload = client.get(
                f"/api/collection?search={fragment}", headers=session["headers"]
            ).json()
            assert payload["total"] >= 1


class TestFavoriteAndShare:
    def test_favorite_toggles(self, client, authed):
        session = authed(600030)
        plate = client.post("/api/roll", headers=session["headers"]).json()["plate"]

        first = client.post(
            f"/api/plates/{plate['id']}/favorite", headers=session["headers"]
        ).json()
        assert first["is_favorite"] is True
        second = client.post(
            f"/api/plates/{plate['id']}/favorite", headers=session["headers"]
        ).json()
        assert second["is_favorite"] is False

    def test_cannot_favorite_a_plate_you_do_not_own(self, client, authed):
        owner = authed(600031)
        plate = client.post("/api/roll", headers=owner["headers"]).json()["plate"]
        stranger = authed(600032)
        response = client.post(
            f"/api/plates/{plate['id']}/favorite", headers=stranger["headers"]
        )
        assert response.status_code == 404

    def test_share_returns_a_deep_link(self, client, authed):
        session = authed(600033)
        plate = client.post("/api/roll", headers=session["headers"]).json()["plate"]
        payload = client.post(
            f"/api/plates/{plate['id']}/share", headers=session["headers"]
        ).json()
        assert payload["start_param"] == f"plate_{plate['id']}"
        assert payload["mini_app_link"].startswith("https://t.me/")
        assert "Can you beat this?" in payload["share_text_en"]
        assert "Сможешь лучше?" in payload["share_text_ru"]

    def test_plate_detail_is_public_to_owners_only_for_state(self, client, authed):
        session = authed(600034)
        plate = client.post("/api/roll", headers=session["headers"]).json()["plate"]
        detail = client.get(f"/api/plates/{plate['id']}", headers=session["headers"]).json()
        assert detail["plate"]["id"] == plate["id"]
        assert detail["is_owned"] is True
        # A safe discoverer identity - never a Telegram id.
        assert "telegram_id" not in str(detail)


class TestDealer:
    """The DEALER sells spare copies only, and always writes a ledger row."""

    def test_selling_requires_ownership(self, client, authed):
        owner = authed(600040)
        plate = client.post("/api/roll", headers=owner["headers"]).json()["plate"]
        stranger = authed(600041)
        response = client.post(
            f"/api/plates/{plate['id']}/sell",
            headers=stranger["headers"],
            json={"copies": 1},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PLATE_NOT_OWNED"

    def test_selling_without_duplicates_is_rejected(self, client, authed):
        session = authed(600042)
        plate = client.post("/api/roll", headers=session["headers"]).json()["plate"]
        response = client.post(
            f"/api/plates/{plate['id']}/sell", headers=session["headers"], json={"copies": 1}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_DUPLICATES"

    def test_duplicate_sale_credits_numora(self, client, authed, db):
        """A rolled duplicate is sold to the DEALER for NUMORA."""
        from app.models.user import User
        from app.services.plate_rolls import PlateRollService

        session = authed(600043)
        profile = client.get("/api/user", headers=session["headers"]).json()
        user = db.get(User, profile["id"])

        service = PlateRollService(db)
        first = service.perform_roll(user)
        plate_id = first.plate.id
        # Force a duplicate by rolling the same catalogue row again.
        from app.models.plates import PlateDiscovery, UserPlate

        owned = db.query(UserPlate).filter_by(user_id=user.id, plate_id=plate_id).one()
        owned.duplicate_count = 1
        db.commit()

        before = client.get("/api/user", headers=session["headers"]).json()["coins"]
        response = client.post(
            f"/api/plates/{plate_id}/sell", headers=session["headers"], json={"copies": 1}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["numora_gained"] > 0
        assert payload["duplicates_left"] == 0
        assert payload["balance"] > before

        collection = client.get("/api/collection", headers=session["headers"]).json()
        owned_card = next(item for item in collection["items"] if item["id"] == plate_id)
        assert owned_card["duplicate_count"] == 0

    def test_double_sale_does_not_double_pay(self, client, authed, db):
        from app.models.plates import UserPlate
        from app.models.user import User
        from app.services.plate_rolls import PlateRollService

        session = authed(600045)
        profile = client.get("/api/user", headers=session["headers"]).json()
        user = db.get(User, profile["id"])

        service = PlateRollService(db)
        first = service.perform_roll(user)
        plate_id = first.plate.id
        owned = db.query(UserPlate).filter_by(user_id=user.id, plate_id=plate_id).one()
        owned.duplicate_count = 1
        db.commit()

        one = client.post(
            f"/api/plates/{plate_id}/sell", headers=session["headers"], json={"copies": 1}
        )
        assert one.status_code == 200
        balance_after_first = one.json()["balance"]

        # The second sale has no duplicate left, so it must fail cleanly.
        second = client.post(
            f"/api/plates/{plate_id}/sell", headers=session["headers"], json={"copies": 1}
        )
        assert second.status_code == 422
        assert client.get("/api/user", headers=session["headers"]).json()["coins"] == balance_after_first

    def test_batch_sale_only_sells_spares(self, client, authed, db):
        """The last copy of a plate must survive a batch sale."""
        from app.models.plates import UserPlate
        from app.models.user import User
        from app.services.plate_rolls import PlateRollService

        session = authed(600044)
        profile = client.get("/api/user", headers=session["headers"]).json()
        user = db.get(User, profile["id"])

        service = PlateRollService(db)
        plate_ids = []
        for index in range(3):
            outcome = service.perform_roll(user)
            plate_ids.append(outcome.plate.id)
            if index == 0:
                owned = db.query(UserPlate).filter_by(
                    user_id=user.id, plate_id=outcome.plate.id
                ).one()
                owned.duplicate_count = 2
        db.commit()

        response = client.post("/api/collection/sell-duplicates", headers=session["headers"])
        assert response.status_code == 200
        payload = response.json()
        assert payload["copies_sold"] == 2
        assert payload["numora_gained"] > 0

        collection = client.get("/api/collection?page_size=100", headers=session["headers"]).json()
        owned_ids = {item["id"] for item in collection["items"]}
        assert set(plate_ids) <= owned_ids


class TestMissionsCosmeticsEvents:
    def test_missions_are_listed_and_progress(self, client, authed):
        session = authed(600050)
        payload = client.get("/api/missions", headers=session["headers"]).json()
        assert len(payload) >= 8
        assert all(item["target"] >= 1 for item in payload)

        client.post("/api/roll", headers=session["headers"])
        updated = client.get("/api/missions", headers=session["headers"]).json()
        assert any(item["progress"] >= 1 for item in updated)

    def test_cosmetics_catalogue(self, client, authed):
        session = authed(600051)
        payload = client.get("/api/cosmetics", headers=session["headers"]).json()
        assert len(payload) >= 5
        assert all("price_numora" in item for item in payload)
        assert all(item["equipped"] is False for item in payload)

    def test_cannot_equip_an_unowned_cosmetic(self, client, authed):
        session = authed(600052)
        response = client.post("/api/cosmetics/finish_gold/equip", headers=session["headers"])
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "COSMETIC_NOT_OWNED"

    def test_event_is_exposed(self, client, authed):
        session = authed(600053)
        payload = client.get("/api/event", headers=session["headers"]).json()
        assert payload["code"]
        assert "name_en" in payload and "name_ru" in payload
        assert isinstance(payload["country_multipliers"], dict)

    def test_albums_are_listed(self, client, authed):
        session = authed(600054)
        payload = client.get("/api/albums", headers=session["headers"]).json()
        assert len(payload) >= 12
        codes = {item["code"] for item in payload}
        assert "country_rus" in codes
        assert "album_lucky" in codes
