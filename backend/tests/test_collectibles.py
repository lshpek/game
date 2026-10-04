"""Collectible categories: vehicle plates, synthetic phones and synthetic SIMs.

The contract these tests protect:

* a category is **data**, not a new table - PHONE and SIM ride the existing
  ``Plate`` pipeline, so ownership, duplicates, first discovery and the ledger
  behave identically for every kind;
* phone numbers and SIM cards are **synthetic game objects**. Nothing here builds,
  stores or resolves a number that could belong to a real subscriber, and the
  payloads are tagged so no downstream consumer can mistake one for one;
* rarity comes from the **structure** of the number, not from a dice throw;
* the hunt filter narrows the eligible pool only - it cannot forge a result;
* a malformed filter is rejected instead of silently falling back.
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.game.collectibles import (
    CATEGORIES,
    CollectibleCategory,
    category_for_plate_type,
    normalize_category,
    parse_hunt_filter,
    phone_templates,
    sim_templates,
)
from app.game.countries import COUNTRIES, COUNTRY_BY_CODE
from app.game.phone_patterns import (
    detect_phone_traits,
    digits_of,
    entropy_bits,
    has_ultra_pattern,
    low_entropy,
    palindrome,
    score_phone_traits,
)
from app.game.plate_patterns import analyze_plate


class TestCategoryModel:
    def test_the_three_categories_exist(self):
        assert [item.value for item in CATEGORIES] == [
            "VEHICLE_PLATE",
            "PHONE_NUMBER",
            "SIM_CARD",
        ]

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [
            ("VEHICLE", CollectibleCategory.VEHICLE_PLATE),
            ("STANDARD", CollectibleCategory.VEHICLE_PLATE),
            ("MOTORCYCLE", CollectibleCategory.VEHICLE_PLATE),
            ("PHONE", CollectibleCategory.PHONE_NUMBER),
            ("SIM", CollectibleCategory.SIM_CARD),
            (None, CollectibleCategory.VEHICLE_PLATE),
            ("something-new", CollectibleCategory.VEHICLE_PLATE),
        ],
    )
    def test_stored_plate_type_maps_to_a_category(self, stored, expected):
        assert category_for_plate_type(stored) is expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("PLATES", CollectibleCategory.VEHICLE_PLATE),
            ("vehicle_plate", CollectibleCategory.VEHICLE_PLATE),
            ("PHONES", CollectibleCategory.PHONE_NUMBER),
            ("phone", CollectibleCategory.PHONE_NUMBER),
            ("SIM_CARD", CollectibleCategory.SIM_CARD),
            ("sims", CollectibleCategory.SIM_CARD),
        ],
    )
    def test_client_aliases_normalise(self, value, expected):
        assert normalize_category(value) is expected

    def test_unknown_category_is_rejected_not_ignored(self):
        with pytest.raises(ValidationError) as caught:
            parse_hunt_filter(category="POSTAL_CODE")
        assert caught.value.code == "BAD_CATEGORY"

    def test_all_means_no_filter(self):
        for value in (None, "", "ALL", "world", "any"):
            assert parse_hunt_filter(category=value) == {"category": None, "country_code": None}

    @pytest.mark.parametrize("country", ["RU", "RUSSIANLAND", "R1S", "12"])
    def test_a_malformed_country_is_rejected(self, country):
        with pytest.raises(ValidationError) as caught:
            parse_hunt_filter(country_code=country)
        assert caught.value.code == "BAD_COUNTRY"

    def test_a_valid_filter_passes_through(self):
        parsed = parse_hunt_filter(category="PHONES", country_code="rus")
        assert parsed == {
            "category": CollectibleCategory.PHONE_NUMBER,
            "country_code": "RUS",
        }


class TestTemplateCatalogue:
    def test_every_country_contributes_phone_and_sim_templates(self):
        assert COUNTRIES, "the catalogue is empty"
        for country in COUNTRIES:
            assert phone_templates(country.code), country.code
            assert sim_templates(country.code), country.code

    def test_phone_templates_carry_the_country_calling_code(self):
        for code in COUNTRY_BY_CODE:
            for template in phone_templates(code):
                assert template.plate_type == "PHONE"
                assert "+" in template.pattern, (code, template.code)

    def test_sim_templates_are_tagged_synthetic_and_carry_an_edition(self):
        for code in COUNTRY_BY_CODE:
            for template in sim_templates(code):
                assert template.plate_type == "SIM"
                assert template.config["synthetic"] is True
                assert template.config["edition"]
                assert template.config["operator_code"]

    def test_sim_editions_climb_the_rarity_floor(self):
        floors = [template.rarity_floor for template in sim_templates("RUS")]
        assert floors[0] == "COMMON"
        assert "LEGENDARY" in floors
        # Heavier weights on the cheap editions, so a CROWN card really is rare.
        weights = {t.config["edition"]: t.weight for t in sim_templates("RUS")}
        assert weights["ORIGIN"] > weights["CROWN"]

    def test_a_brand_new_country_still_gets_a_fallback_phone_format(self):
        templates = phone_templates("ZZZ")
        assert templates
        assert templates[0].pattern.startswith("+")

    def test_templates_are_wired_into_the_country_catalogue(self):
        rus = COUNTRY_BY_CODE["RUS"]
        types = {template.plate_type for template in rus.templates}
        assert "PHONE" in types
        assert "SIM" in types
        # The vehicle templates must survive the extension untouched.
        assert any(template.plate_type not in {"PHONE", "SIM"} for template in rus.templates)

    def test_collectible_templates_are_heavier_to_see_than_vehicle_templates(self):
        """Phones and SIMs are rarer by design, not an equal share of the pool."""
        rus = COUNTRY_BY_CODE["RUS"]
        vehicle = [t for t in rus.templates if t.plate_type not in {"PHONE", "SIM"}]
        phone = [t for t in rus.templates if t.plate_type == "PHONE"]
        vehicle_share = sum(t.weight for t in vehicle)
        phone_share = sum(t.weight for t in phone)
        assert phone_share < vehicle_share, (phone_share, vehicle_share)


class TestSyntheticSafety:
    def test_every_phone_and_sim_is_tagged_synthetic(self):
        analysis = analyze_plate("+7 777 777-77-77", plate_type="PHONE", country_tag="eu")
        assert "synthetic" in analysis.tags
        assert "phone" in analysis.tags

        sim = analyze_plate("SC 1234 5678 NU", plate_type="SIM", country_tag="eu")
        assert "synthetic" in sim.tags
        assert "sim" in sim.tags

    def test_vehicle_plates_are_not_tagged_synthetic(self):
        analysis = analyze_plate("A777AA 77", plate_type="VEHICLE", country_tag="eu")
        assert "synthetic" not in analysis.tags

    def test_sim_operator_brands_are_invented(self):
        """No real operator brand may appear in the collectible line."""
        from app.game.collectibles import SIM_OPERATOR_FALLBACK, SIM_OPERATORS

        brands = {latin for entries in SIM_OPERATORS.values() for _code, latin, _local in entries}
        brands |= {latin for _code, latin, _local in SIM_OPERATOR_FALLBACK}
        assert brands == {"NUMA", "NOVA", "ORBIT", "VOLT", "PULSE", "AXIS", "ION"}
        # Deliberately not modelled on any real carrier.
        assert not brands & {"BEELINE", "MTS", "MEGAFON", "VERIZON", "AT&T"}

    def test_localised_operator_names_exist_for_every_brand(self):
        from app.game.collectibles import SIM_OPERATOR_FALLBACK, SIM_OPERATORS

        for entries in (*SIM_OPERATORS.values(), SIM_OPERATOR_FALLBACK):
            for _code, latin, local in entries:
                assert latin and local, latin


class TestStructuralRarity:
    @pytest.mark.parametrize(
        ("digits", "expected"),
        [
            ("777777", "triple_repeat"),
            ("1234567", "ascending"),
            ("7654321", "descending"),
            ("0123456789", "ascending"),
            ("1234321", "palindrome"),
            ("1212121212", "alternating"),
            ("000111000", "low_entropy"),
        ],
    )
    def test_traits_are_read_from_the_number_itself(self, digits, expected):
        assert expected in detect_phone_traits(digits)

    def test_a_plain_number_has_no_exotic_traits(self):
        assert detect_phone_traits("405912837") == []

    def test_traits_are_ordered_strongest_first(self):
        traits = detect_phone_traits("777777777777")
        assert traits[0] in {"perfect_symmetry", "quad_repeat", "triple_repeat"}

    def test_rarity_is_deterministic(self):
        """The same number must score the same on every roll and on every server."""
        first = detect_phone_traits("+7 777 777-77-77")
        second = detect_phone_traits("+7 777 777-77-77")
        assert first == second
        assert score_phone_traits(first) == score_phone_traits(second)

    def test_a_plain_number_scores_below_a_lucky_one(self):
        plain = score_phone_traits(detect_phone_traits("405912837"))
        lucky = score_phone_traits(detect_phone_traits("+1 777-777-7777"))
        assert lucky > plain

    def test_the_score_is_capped(self):
        everything = detect_phone_traits("7777777777771234321")
        assert score_phone_traits(everything) <= 100

    def test_an_ultra_pattern_is_rare(self):
        assert has_ultra_pattern("777777777")
        assert not has_ultra_pattern("405912837")

    def test_entropy_reports_structure(self):
        assert entropy_bits("0000000000") < entropy_bits("4059128374")

    def test_short_strings_never_crash(self):
        assert detect_phone_traits("") == []
        assert detect_phone_traits("+7") == []
        assert palindrome("1") is False
        assert low_entropy("12") is False

    def test_unicode_input_does_not_crash(self):
        # Digits from another script must be ignored rather than explode.
        assert detect_phone_traits("＋７ 777 777") is not None

    def test_a_phone_number_analyses_into_strong_traits(self):
        analysis = analyze_plate("+1 777-777-7777", plate_type="PHONE", country_tag="na")
        assert "triple_repeat" in analysis.traits
        assert analysis.scores["triple_repeat"] > 0
        assert sum(analysis.scores.values()) > 0


class TestHuntFiltering:
    def _roll(self, client, authed, **params):
        session = authed(700100)
        return client.post("/api/roll", headers=session["headers"], params=params).json()

    def test_a_phone_hunt_returns_a_phone(self, client, db, authed):
        result = self._roll(client, authed, category="PHONE_NUMBER")
        plate = result["plate"]
        assert plate["category"] == "PHONE_NUMBER"
        assert plate["plate_type"] == "PHONE"
        assert plate["plate_text"].startswith("+")

    def test_a_sim_hunt_returns_a_sim(self, client, db, authed):
        result = self._roll(client, authed, category="SIM_CARD")
        plate = result["plate"]
        assert plate["category"] == "SIM_CARD"
        assert plate["plate_type"] == "SIM"

    def test_a_vehicle_hunt_returns_a_vehicle(self, client, db, authed):
        result = self._roll(client, authed, category="VEHICLE_PLATE")
        assert result["plate"]["category"] == "VEHICLE_PLATE"

    def test_no_filter_still_works(self, client, db, authed):
        result = self._roll(client, authed)
        assert result["plate"]["id"]
        assert result["plate"]["category"] in {item.value for item in CATEGORIES}

    def test_a_country_hunt_stays_in_that_country(self, client, db, authed):
        result = self._roll(client, authed, category="PHONE_NUMBER", country_code="RUS")
        plate = result["plate"]
        assert plate["category"] == "PHONE_NUMBER"
        assert plate["country"]["code"] == "RUS"
        assert plate["plate_text"].startswith("+7")

    def test_a_malformed_category_is_refused(self, client, db, authed):
        session = authed(700101)
        response = client.post(
            "/api/roll", headers=session["headers"], params={"category": "BANK_ACCOUNT"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_CATEGORY"

    def test_a_malformed_country_is_refused(self, client, db, authed):
        session = authed(700102)
        response = client.post(
            "/api/roll", headers=session["headers"], params={"country_code": "RUSSIANLAND"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_COUNTRY"

    def test_an_impossible_combination_falls_back_instead_of_failing(self, client, db, authed):
        """An empty catalogue for the hunt must not break the player's roll."""
        session = authed(700103)
        response = client.post(
            "/api/roll",
            headers=session["headers"],
            params={"category": "SIM_CARD", "country_code": "ZZZ"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["plate"]["id"]

    def test_the_client_cannot_send_a_rarity_or_a_value(self, client, db, authed):
        """Any attempt to dictate the outcome is ignored: the server decides."""
        session = authed(700104)
        response = client.post(
            "/api/roll",
            headers=session["headers"],
            json={"rarity": "MYTHIC", "collector_value": 999_999_999, "plate_text": "A777AA 77"},
        )
        assert response.status_code == 200
        plate = response.json()["plate"]
        assert plate["collector_value"] < 999_999_999
        assert plate["plate_text"] != "A777AA 77"

    def test_a_hunted_roll_is_still_idempotent(self, client, db, authed):
        session = authed(700105)
        headers = {**session["headers"], "Idempotency-Key": "hunt-phone-1"}
        first = client.post("/api/roll", headers=headers, params={"category": "PHONE_NUMBER"}).json()
        second = client.post("/api/roll", headers=headers, params={"category": "PHONE_NUMBER"}).json()
        assert first["plate"]["id"] == second["plate"]["id"]
        assert first.get("replayed") in (True, False)
        assert second.get("replayed") is True


class TestResponseContract:
    def test_every_roll_result_carries_the_unified_category(self, client, db, authed):
        session = authed(700110)
        body = client.post("/api/roll", headers=session["headers"]).json()
        plate = body["plate"]
        for field in (
            "id",
            "category",
            "plate_text",
            "rarity",
            "rarity_score",
            "collector_value",
            "dealer_value",
            "traits",
            "story",
            "country",
            "visual",
        ):
            assert field in plate, field
        assert plate["country"]["flag"]
        assert body["balance"] is not None
        assert "rolls_remaining" in body or "roll" in body
