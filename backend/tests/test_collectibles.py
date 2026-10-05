"""Tests for the collectible domain: exactly two kinds, server-owned validation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import ValidationError
from app.game.collectibles import (
    KINDS,
    CollectibleKind,
    category_for_plate_type,
    kind_for_plate_type,
    matches_kind,
    normalize_kind,
    parse_hunt_filter,
    plate_types_for,
    sim_templates,
    templates_for_kind,
)
from app.game.countries import COUNTRIES
from app.models.plates import Country, Plate
from app.services.catalog import snapshot


def roll(client, authed, *, category: str | None = None, country_code: str | None = None, **kw):
    """Roll once with optional hunt filters, asserting the call succeeded."""
    session = authed(**kw)
    params: list[str] = []
    if category:
        params.append(f"category={category}")
    if country_code:
        params.append(f"country_code={country_code}")
    query = ("?" + "&".join(params)) if params else ""
    response = client.post(f"/api/roll{query}", headers=session["headers"], json={})
    assert response.status_code == 200, response.text
    return response.json()


class TestKinds:
    def test_there_are_exactly_two_collectible_kinds(self):
        assert [kind.value for kind in KINDS] == ["VEHICLE_PLATE", "SIM_CARD"]

    def test_there_is_no_phone_number_kind(self):
        values = {kind.value for kind in KINDS}
        assert "PHONE_NUMBER" not in values
        assert not any("PHONE" in value for value in values)

    def test_a_phone_number_is_not_a_collectible(self):
        """A number printed on a card belongs to the SIM card, not to a third kind."""
        assert normalize_kind("PHONE_NUMBER") is None
        assert normalize_kind("phone_number") is None
        assert normalize_kind("PHONE") is None
        with pytest.raises(ValidationError):
            parse_hunt_filter(category="PHONE_NUMBER")

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [
            ("STANDARD", CollectibleKind.VEHICLE_PLATE),
            ("COMMERCIAL", CollectibleKind.VEHICLE_PLATE),
            ("MOTORCYCLE", CollectibleKind.VEHICLE_PLATE),
            ("HISTORICAL", CollectibleKind.VEHICLE_PLATE),
            ("GOVERNMENT_STYLE", CollectibleKind.VEHICLE_PLATE),
            ("DIPLOMATIC_STYLE", CollectibleKind.VEHICLE_PLATE),
            ("", CollectibleKind.VEHICLE_PLATE),
            ("SIM", CollectibleKind.SIM_CARD),
            # Rows written before the SIM line existed are folded into SIM cards by
            # migration 0005 and must resolve to the same kind.
            ("PHONE", CollectibleKind.SIM_CARD),
        ],
    )
    def test_a_stored_plate_type_maps_to_exactly_one_kind(self, stored, expected):
        assert kind_for_plate_type(stored) is expected
        assert category_for_plate_type(stored) is expected

    def test_the_two_kinds_partition_every_known_plate_type(self):
        vehicle = plate_types_for(CollectibleKind.VEHICLE_PLATE)
        sim = plate_types_for(CollectibleKind.SIM_CARD)
        assert vehicle & sim == frozenset()
        for kind in KINDS:
            assert plate_types_for(kind)

    def test_matches_kind_agrees_with_the_mapping(self):
        assert matches_kind("SIM", CollectibleKind.SIM_CARD)
        assert not matches_kind("SIM", CollectibleKind.VEHICLE_PLATE)
        assert matches_kind("STANDARD", CollectibleKind.VEHICLE_PLATE)
        assert not matches_kind("STANDARD", CollectibleKind.SIM_CARD)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("VEHICLE_PLATE", CollectibleKind.VEHICLE_PLATE),
            ("plate", CollectibleKind.VEHICLE_PLATE),
            ("PLATES", CollectibleKind.VEHICLE_PLATE),
            ("vehicle", CollectibleKind.VEHICLE_PLATE),
            ("SIM_CARD", CollectibleKind.SIM_CARD),
            ("sim", CollectibleKind.SIM_CARD),
            ("SIMS", CollectibleKind.SIM_CARD),
            ("nonsense", None),
            (None, None),
        ],
    )
    def test_client_aliases_are_accepted_but_nonsense_is_not(self, value, expected):
        assert normalize_kind(value) is expected


class TestHuntFilterValidation:
    def test_no_filter_means_the_whole_world(self):
        assert parse_hunt_filter() == {"category": None, "country_code": None}

    def test_all_and_world_mean_no_filter(self):
        for token in ("", "ALL", "WORLD", "any"):
            assert parse_hunt_filter(category=token)["category"] is None

    def test_an_unknown_kind_is_rejected_rather_than_ignored(self):
        # A silent fallback would leave the player hunting plates while the UI shows
        # something else, which reads as a cheat.
        with pytest.raises(ValidationError):
            parse_hunt_filter(category="PHONE")
        with pytest.raises(ValidationError):
            parse_hunt_filter(category="STICKER")

    def test_a_country_code_is_upper_cased(self):
        assert parse_hunt_filter(country_code=" rus ")["country_code"] == "RUS"

    def test_an_absurd_country_code_is_rejected(self):
        with pytest.raises(ValidationError):
            parse_hunt_filter(country_code="A" * 20)


class TestSimTemplates:
    def test_every_playable_country_has_sim_templates(self):
        for country in COUNTRIES:
            if not country.playable:
                continue
            assert sim_templates(country.code), f"{country.code} has no SIM templates"

    def test_sim_templates_are_sim_typed_and_synthetic(self):
        for template in sim_templates("RUS"):
            assert template.plate_type == "SIM"
            assert template.config["synthetic"] is True
            assert template.config["kind"] == "SIM_CARD"
            assert template.config["operator_code"]
            assert template.config["edition"]

    def test_every_sim_pattern_renders_the_country_calling_code(self):
        for country in COUNTRIES:
            if not country.playable or not country.calling_code:
                continue
            for template in sim_templates(country.code):
                assert template.pattern.startswith("+" + country.calling_code.lstrip("+"))

    def test_locked_countries_never_emit_sim_templates(self):
        locked = [c for c in COUNTRIES if not c.playable]
        assert locked
        assert sim_templates(locked[0].code) == ()

    def test_vehicle_countries_contribute_nothing_to_the_sim_kind(self):
        assert templates_for_kind("RUS", CollectibleKind.VEHICLE_PLATE) == ()


class TestHuntFiltering:
    def test_no_filter_still_works(self, client, authed):
        data = roll(client, authed)
        assert data["plate"]["kind"] in {kind.value for kind in KINDS}

    def test_a_vehicle_hunt_returns_a_vehicle(self, client, authed):
        data = roll(client, authed, category="VEHICLE_PLATE")
        assert data["plate"]["kind"] == "VEHICLE_PLATE"
        assert data["plate"]["details"] is None

    def test_a_sim_hunt_returns_a_sim_card_with_a_printed_number(self, client, authed):
        data = roll(client, authed, category="SIM_CARD")
        assert data["plate"]["kind"] == "SIM_CARD"
        details = data["plate"]["details"]
        assert details is not None
        assert details["synthetic"] is True
        assert details["operator"]
        assert details["series"]
        assert details["edition"]
        # The printed number is what the engine rendered, not something composed here.
        assert details["synthetic_number"] == data["plate"]["plate_text"]

    def test_a_vehicle_hunt_is_never_a_sim_card(self, client, authed):
        for offset in range(3):
            data = roll(client, authed, category="VEHICLE_PLATE", telegram_id=5600001 + offset)
            assert data["plate"]["plate_type"] != "SIM"

    def test_an_unknown_kind_is_a_422(self, client, authed):
        session = authed()
        response = client.post("/api/roll?category=STICKER", headers=session["headers"], json={})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_CATEGORY"

    def test_a_phone_number_category_is_a_422(self, client, authed):
        session = authed()
        response = client.post(
            "/api/roll?category=PHONE_NUMBER", headers=session["headers"], json={}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_CATEGORY"

    def test_a_country_filter_stays_in_that_country(self, client, authed):
        data = roll(client, authed, country_code="JPN")
        assert data["plate"]["country"]["code"] == "JPN"

    def test_a_country_filter_accepts_the_alpha2_code(self, client, authed):
        data = roll(client, authed, country_code="jp")
        assert data["plate"]["country"]["code"] == "JPN"

    def test_a_locked_country_is_rejected(self, client, authed):
        locked = next(c.code for c in COUNTRIES if not c.playable)
        session = authed()
        response = client.post(
            f"/api/roll?country_code={locked}", headers=session["headers"], json={}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "COUNTRY_LOCKED"

    def test_an_unknown_country_is_rejected(self, client, authed):
        session = authed()
        response = client.post(
            "/api/roll?country_code=ZZZ", headers=session["headers"], json={}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_COUNTRY"

    def test_a_roll_never_leaks_a_locked_country(self, client, authed):
        locked = {c.code for c in COUNTRIES if not c.playable}
        for offset in range(4):
            data = roll(client, authed, telegram_id=5610001 + offset)
            assert data["plate"]["country"]["code"] not in locked


class TestSimCardsInTheCollection:
    def test_a_sim_card_is_stored_with_its_details(self, client, authed, db):
        data = roll(client, authed, category="SIM_CARD")
        plate = db.execute(select(Plate).where(Plate.id == data["plate"]["id"])).scalar_one()
        assert plate.plate_type == "SIM"
        assert plate.details["operator"]
        assert plate.details["synthetic_number"] == plate.plate_text
        assert plate.details["synthetic"] is True

    def test_a_vehicle_plate_is_stored_without_details(self, client, authed, db):
        data = roll(client, authed, category="VEHICLE_PLATE")
        plate = db.execute(select(Plate).where(Plate.id == data["plate"]["id"])).scalar_one()
        assert plate.plate_type != "SIM"
        assert plate.details == {}

    def test_no_row_exists_for_a_bare_phone_number(self, client, authed, db):
        roll(client, authed, category="SIM_CARD")
        rows = db.execute(select(Plate)).scalars().all()
        # Everything that exists is a physical object: a plate or a card. No row
        # exists for a number on its own.
        assert rows
        assert all(row.plate_type != "PHONE" for row in rows)


class TestKindMix:
    """The SIM line must stay a rarity, and the pool must stay clean."""

    def test_the_generation_pool_has_no_duplicate_layout_codes(self, db):
        ctx = snapshot(db, settings.rarity_weights).context
        duplicates: list[str] = []
        for country in ctx.countries:
            seen: set[str] = set()
            for option in ctx.templates_by_country.get(country.code, ()):
                if option.code in seen:
                    duplicates.append(f"{country.code}:{option.code}")
                seen.add(option.code)
        assert duplicates == []

    def test_sim_cards_stay_a_rarity_of_the_pool(self, db):
        """A per-template weight factor would let the template *count* decide how
        often a card appears, so the share is asserted against the whole pool."""
        ctx = snapshot(db, settings.rarity_weights).context
        sim = 0.0
        vehicle = 0.0
        for country in ctx.countries:
            for option in ctx.templates_by_country.get(country.code, ()):
                if option.plate_type == "SIM":
                    sim += option.weight
                else:
                    vehicle += option.weight
        share = sim / (sim + vehicle)
        assert 0.02 < share < 0.35, share

    def test_every_playable_country_offers_both_kinds(self, db):
        ctx = snapshot(db, settings.rarity_weights).context
        for country in ctx.countries:
            options = ctx.templates_by_country.get(country.code, ())
            assert any(option.plate_type == "SIM" for option in options), country.code
            assert any(option.plate_type != "SIM" for option in options), country.code


class TestCountrySeed:
    def test_the_catalogue_covers_iso_3166_1(self):
        assert len(COUNTRIES) >= 240

    def test_the_catalogue_has_both_playable_and_locked_countries(self):
        playable = [c for c in COUNTRIES if c.playable]
        locked = [c for c in COUNTRIES if not c.playable]
        assert len(playable) >= 40
        assert len(locked) >= 100

    def test_every_country_row_is_seeded_with_its_iso_identifiers(self, db):
        rows = db.execute(select(Country)).scalars().all()
        assert len(rows) >= 240
        for row in rows:
            assert row.code and len(row.code) == 3
            assert row.iso_alpha2 and len(row.iso_alpha2) == 2
            assert row.flag

    def test_locked_countries_are_seeded_but_not_playable(self, db):
        rows = db.execute(
            select(Country).where(Country.is_playable.is_(False))
        ).scalars().all()
        assert rows
        for row in rows:
            # The SIM format is written even for a locked country, so releasing it
            # later only needs layouts and one flag.
            assert row.sim_config.get("calling_code")

    def test_a_playable_country_has_sim_data(self, db):
        rows = db.execute(
            select(Country).where(Country.is_playable.is_(True))
        ).scalars().all()
        assert rows
        for row in rows:
            assert row.sim_config.get("synthetic") is True
            assert row.sim_config.get("operators")
