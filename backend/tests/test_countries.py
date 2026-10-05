"""The country system end to end: catalogue, selector API and active-country state.

Covers the acceptance path a player actually walks:

    select country -> roll -> receive collectible -> collection is in that country
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.game.countries import COUNTRIES, PLAYABLE_CODES, country_by_code, is_playable
from app.game.iso_countries import ISO_BY_ALPHA2, ISO_COUNTRIES, iso_country
from app.models.plates import Country, Plate, UserPlate
from app.models.user import User
from app.seed import seed_countries

#: Every country the first global release is expected to ship playable.
PRIORITY = {
    "RUS", "USA", "CAN", "MEX", "BRA", "ARG", "CHL", "COL", "GBR", "DEU",
    "FRA", "ITA", "ESP", "PRT", "NLD", "BEL", "CHE", "AUT", "POL", "CZE",
    "SVK", "HUN", "ROU", "BGR", "GRC", "SWE", "NOR", "DNK", "FIN", "ISL",
    "IRL", "EST", "LVA", "LTU", "UKR", "BLR", "JPN", "KOR", "CHN", "IND",
    "TUR", "ISR", "ARE", "SAU", "THA", "SGP", "AUS", "NZL",
}


class TestIsoReferenceData:
    def test_the_iso_table_is_complete(self):
        assert len(ISO_COUNTRIES) >= 240

    def test_every_entry_resolves_in_both_identifier_forms(self):
        for entry in ISO_COUNTRIES:
            assert iso_country(entry.alpha3) is entry
            assert iso_country(entry.alpha2) is entry
            assert ISO_BY_ALPHA2[entry.alpha2] is entry

    def test_identifiers_are_unique(self):
        alpha2 = [entry.alpha2 for entry in ISO_COUNTRIES]
        alpha3 = [entry.alpha3 for entry in ISO_COUNTRIES]
        assert len(set(alpha2)) == len(alpha2)
        assert len(set(alpha3)) == len(alpha3)

    def test_every_entry_carries_what_the_ui_needs(self):
        for entry in ISO_COUNTRIES:
            assert entry.name_en
            assert entry.name_ru
            assert entry.region_group
            assert entry.flag
            # A calling code is what a SIM card prints; empty is tolerated only for a
            # territory with none assigned, so the type must be a string either way.
            assert isinstance(entry.calling_code, str)

    def test_the_catalogue_covers_every_iso_entry(self):
        assert {country.code for country in COUNTRIES} == {
            entry.alpha3 for entry in ISO_COUNTRIES
        }

    def test_country_codes_are_iso_alpha3_and_carry_alpha2(self):
        for country in COUNTRIES:
            assert len(country.code) == 3
            assert len(country.iso_alpha2) == 2

    def test_alpha2_and_alpha3_resolve_to_the_same_entry(self):
        for country in COUNTRIES:
            assert country_by_code(country.code) is country
            assert country_by_code(country.iso_alpha2) is country

    def test_lookup_is_case_insensitive_and_safe_on_junk(self):
        assert country_by_code("rus") is not None
        assert country_by_code(" RU ") is not None
        assert country_by_code("zz") is None
        assert country_by_code("") is None
        assert country_by_code(None) is None


class TestPlayableState:
    def test_the_priority_group_ships_playable(self):
        assert PRIORITY <= set(PLAYABLE_CODES)

    def test_locked_countries_exist_and_are_marked(self):
        locked = [country for country in COUNTRIES if not country.playable]
        assert len(locked) >= 100
        assert all(is_playable(country.code) is False for country in locked)

    def test_playability_is_decidable_without_the_database(self):
        for country in COUNTRIES:
            assert is_playable(country.code) is country.playable

    def test_a_locked_country_keeps_a_full_identity(self):
        locked = next(country for country in COUNTRIES if not country.playable)
        assert locked.iso_alpha2
        assert locked.flag
        assert locked.name_en
        assert isinstance(locked.calling_code, str)


class TestCountriesApi:
    def test_the_atlas_lists_the_whole_iso_list(self, client, authed):
        data = client.get("/api/countries?limit=250", headers=authed()["headers"]).json()
        assert data["total"] >= 240
        assert data["playable_total"] >= 40
        assert data["locked_total"] >= 100
        assert data["playable_total"] + data["locked_total"] == data["total"]
        first = data["items"][0]
        for key in ("code", "iso_alpha2", "name_en", "name_ru", "flag", "is_playable"):
            assert key in first

    def test_the_atlas_paginates(self, client, authed):
        headers = authed()["headers"]
        page = client.get("/api/countries?limit=25&offset=0", headers=headers).json()
        nxt = client.get("/api/countries?limit=25&offset=25", headers=headers).json()
        assert len(page["items"]) == 25
        assert page["total"] == nxt["total"]
        assert page["items"][0]["code"] != nxt["items"][0]["code"]

    @pytest.mark.parametrize("term", ["rus", "RUS", "ru", "russia", "россия", "+7", "RU"])
    def test_search_matches_code_alpha2_name_and_calling_code(self, client, authed, term):
        # ``params`` so the client percent-encodes the term: a raw "+" would arrive as
        # a space and a Cyrillic query would be mangled, which would test the wrong
        # thing.
        headers = authed()["headers"]
        data = client.get("/api/countries", params={"search": term}, headers=headers).json()
        assert any(item["code"] == "RUS" for item in data["items"]), data

    def test_search_can_be_limited_to_playable_countries(self, client, authed):
        headers = authed()["headers"]
        data = client.get("/api/countries?playable_only=true&limit=250", headers=headers).json()
        assert data["items"]
        assert all(item["is_playable"] for item in data["items"])

    def test_search_can_be_limited_to_a_region(self, client, authed):
        headers = authed()["headers"]
        data = client.get("/api/countries?region=EUROPE&limit=250", headers=headers).json()
        assert data["items"]
        assert all(item["region_group"] == "EUROPE" for item in data["items"])

    def test_an_unknown_country_is_a_404(self, client, authed):
        response = client.get("/api/countries/ZZZ", headers=authed()["headers"])
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "COUNTRY_NOT_FOUND"

    def test_a_country_resolves_by_either_iso_form(self, client, authed):
        headers = authed()["headers"]
        by3 = client.get("/api/countries/RUS", headers=headers)
        by2 = client.get("/api/countries/RU", headers=headers)
        assert by3.status_code == by2.status_code == 200
        assert by3.json()["code"] == by2.json()["code"] == "RUS"
        # The card config the frontend draws a SIM from is always synthetic.
        assert by3.json()["sim"]["synthetic"] is True

    def test_the_atlas_requires_authentication(self, client):
        assert client.get("/api/countries").status_code == 401


class TestActiveCountry:
    def test_a_new_player_hunts_the_whole_world(self, client, authed):
        headers = authed(880010)["headers"]
        data = client.get("/api/countries/active", headers=headers).json()
        assert data["code"] is None
        assert data["country"] is None

    def test_selecting_a_country_stores_it_on_the_server(self, client, authed, db):
        headers = authed(880011)["headers"]
        response = client.post("/api/countries/active", json={"code": "JPN"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["code"] == "JPN"

        user = db.execute(select(User).where(User.telegram_id == 880011)).scalar_one()
        # Authoritative: the backend owns the selection, not the client.
        assert user.active_country_code == "JPN"

    def test_the_selection_survives_a_reload(self, client, authed):
        headers = authed(880012)["headers"]
        client.post("/api/countries/active", json={"code": "DEU"}, headers=headers)
        data = client.get("/api/countries/active", headers=headers).json()
        assert data["code"] == "DEU"
        assert data["country"]["name_en"] == "Germany"
        assert data["country"]["is_active_country"] is True

    def test_selecting_by_alpha2_works(self, client, authed, db):
        headers = authed(880013)["headers"]
        response = client.post("/api/countries/active", json={"code": "jp"}, headers=headers)
        assert response.json()["code"] == "JPN"
        user = db.execute(select(User).where(User.telegram_id == 880013)).scalar_one()
        assert user.active_country_code == "JPN"

    def test_clearing_the_selection_returns_to_the_world(self, client, authed, db):
        headers = authed(880014)["headers"]
        client.post("/api/countries/active", json={"code": "JPN"}, headers=headers)
        response = client.post("/api/countries/active", json={"code": None}, headers=headers)
        assert response.json()["code"] is None
        user = db.execute(select(User).where(User.telegram_id == 880014)).scalar_one()
        assert user.active_country_code is None

    def test_an_unknown_country_is_rejected(self, client, authed, db):
        headers = authed(880015)["headers"]
        response = client.post("/api/countries/active", json={"code": "ZZZ"}, headers=headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_COUNTRY"
        user = db.execute(select(User).where(User.telegram_id == 880015)).scalar_one()
        assert user.active_country_code is None

    def test_a_locked_country_is_rejected(self, client, authed, db):
        headers = authed(880016)["headers"]
        locked = next(c.code for c in COUNTRIES if not c.playable)
        response = client.post("/api/countries/active", json={"code": locked}, headers=headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "COUNTRY_LOCKED"
        user = db.execute(select(User).where(User.telegram_id == 880016)).scalar_one()
        assert user.active_country_code is None

    def test_changing_country_requires_authentication(self, client):
        assert client.post("/api/countries/active", json={"code": "JPN"}).status_code == 401


class TestActiveCountryDrivesTheRoll:
    def test_the_roll_follows_the_active_country(self, client, authed):
        headers = authed(880020)["headers"]
        client.post("/api/countries/active", json={"code": "ITA"}, headers=headers)
        data = client.post("/api/roll", headers=headers, json={}).json()
        assert data["plate"]["country"]["code"] == "ITA"

    def test_the_client_never_restates_the_country_to_the_server(self, client, authed):
        """With no country in the query, the stored selection decides."""
        headers = authed(880021)["headers"]
        client.post("/api/countries/active", json={"code": "CHE"}, headers=headers)
        data = client.post("/api/roll?category=SIM_CARD", headers=headers, json={}).json()
        assert data["plate"]["country"]["code"] == "CHE"
        assert data["plate"]["kind"] == "SIM_CARD"

    def test_clearing_the_selection_returns_the_roll_to_the_world(self, client, authed):
        headers = authed(880022)["headers"]
        client.post("/api/countries/active", json={"code": "POL"}, headers=headers)
        client.post("/api/countries/active", json={"code": None}, headers=headers)
        codes = {
            client.post("/api/roll", headers=headers, json={}).json()["plate"]["country"]["code"]
            for _ in range(6)
        }
        assert len(codes) > 1

    def test_an_explicit_country_overrides_the_active_one(self, client, authed):
        headers = authed(880023)["headers"]
        client.post("/api/countries/active", json={"code": "POL"}, headers=headers)
        data = client.post("/api/roll?country_code=ESP", headers=headers, json={}).json()
        assert data["plate"]["country"]["code"] == "ESP"

    def test_the_collection_follows_the_active_country(self, client, authed):
        headers = authed(880024)["headers"]
        client.post("/api/countries/active", json={"code": "GRC"}, headers=headers)
        client.post("/api/roll", headers=headers, json={})
        data = client.get("/api/collection", headers=headers).json()
        assert data["country_code"] == "GRC"
        assert data["items"]
        assert all(item["country"]["code"] == "GRC" for item in data["items"])


class TestCollectionFilters:
    @pytest.fixture(autouse=True)
    def _hunt_both_kinds(self, client, authed):
        headers = authed(880030)["headers"]
        client.post("/api/countries/active", json={"code": "USA"}, headers=headers)
        client.post("/api/roll?category=VEHICLE_PLATE", headers=headers, json={})
        client.post("/api/roll?category=SIM_CARD", headers=headers, json={})

    def test_all_returns_both_kinds(self, client, authed):
        headers = authed(880030)["headers"]
        data = client.get("/api/collection", headers=headers).json()
        assert {item["kind"] for item in data["items"]} == {"VEHICLE_PLATE", "SIM_CARD"}

    def test_the_plate_filter_returns_only_plates(self, client, authed):
        headers = authed(880030)["headers"]
        data = client.get("/api/collection?kind=VEHICLE_PLATE", headers=headers).json()
        assert data["items"]
        assert all(item["kind"] == "VEHICLE_PLATE" for item in data["items"])
        assert all(item["details"] is None for item in data["items"])

    def test_the_sim_filter_returns_only_sim_cards(self, client, authed):
        headers = authed(880030)["headers"]
        data = client.get("/api/collection?kind=SIM_CARD", headers=headers).json()
        assert data["items"]
        assert all(item["kind"] == "SIM_CARD" for item in data["items"])
        assert all(item["details"] is not None for item in data["items"])

    def test_the_filter_accepts_a_short_alias(self, client, authed):
        headers = authed(880030)["headers"]
        data = client.get("/api/collection?kind=sim", headers=headers).json()
        assert data["items"]
        assert all(item["kind"] == "SIM_CARD" for item in data["items"])

    def test_a_phone_number_filter_is_rejected(self, client, authed):
        headers = authed(880030)["headers"]
        response = client.get("/api/collection?kind=PHONE_NUMBER", headers=headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "BAD_CATEGORY"

    def test_the_collection_has_no_phone_number_kind(self, client, authed):
        headers = authed(880030)["headers"]
        data = client.get("/api/collection?page_size=100", headers=headers).json()
        assert all(item["kind"] in {"VEHICLE_PLATE", "SIM_CARD"} for item in data["items"])


class TestWorldEndpoint:
    def test_the_atlas_pages_and_reports_both_states(self, client, authed):
        headers = authed(880040)["headers"]
        data = client.get("/api/world?limit=10&offset=0", headers=headers).json()
        assert len(data["countries"]) == 10
        assert data["countries_total"] >= 240
        assert data["playable_total"] >= 40
        assert data["locked_total"] >= 100
        assert data["offset"] == 0
        assert data["limit"] == 10
        assert "is_playable" in data["countries"][0]
        assert "iso_alpha2" in data["countries"][0]

    def test_a_locked_country_is_listed_with_zero_total(self, client, authed):
        headers = authed(880040)["headers"]
        data = client.get("/api/world?limit=250", headers=headers).json()
        locked = [item for item in data["countries"] if not item["is_playable"]]
        assert locked
        for entry in locked:
            assert entry["total"] == 0
            assert entry["progress"] == 0.0

    def test_a_country_detail_resolves_by_either_iso_form(self, client, authed):
        headers = authed(880040)["headers"]
        by3 = client.get("/api/world/RUS", headers=headers)
        by2 = client.get("/api/world/RU", headers=headers)
        assert by3.status_code == by2.status_code == 200
        assert by3.json()["code"] == by2.json()["code"] == "RUS"

    def test_a_locked_country_detail_is_readable_but_marked(self, client, authed):
        headers = authed(880040)["headers"]
        locked = next(c.code for c in COUNTRIES if not c.playable)
        response = client.get(f"/api/world/{locked}", headers=headers)
        assert response.status_code == 200
        assert response.json()["is_playable"] is False
        assert response.json()["total"] == 0

    def test_an_unknown_country_detail_is_a_404(self, client, authed):
        headers = authed(880040)["headers"]
        assert client.get("/api/world/ZZZ", headers=headers).status_code == 404


class TestCatalogueReconciliation:
    def test_seeding_is_idempotent(self, db):
        before = db.execute(select(func.count(Country.id))).scalar_one()
        seed_countries(db)
        db.flush()
        assert db.execute(select(func.count(Country.id))).scalar_one() == before

    def test_reconciling_never_removes_a_country(self, db):
        """A country that leaves the catalogue keeps its row and its data."""
        before = {row.code for row in db.execute(select(Country)).scalars().all()}
        db.add(
            Country(
                code="ZZZ",
                iso_alpha2="ZZ",
                name_en="Retired",
                name_ru="Выведена",
                flag="\U0001F1FF\U0001F1E6",
                region_group="EUROPE",
                config={},
                sim_config={},
                is_active=True,
                is_playable=True,
                sort_order=9999,
            )
        )
        db.flush()
        seed_countries(db)
        db.flush()
        after = {row.code for row in db.execute(select(Country)).scalars().all()}
        assert "ZZZ" in after
        assert before <= after

    def test_existing_plates_are_untouched_by_the_catalogue(self, client, authed, db):
        headers = authed(880050)["headers"]
        result = client.post("/api/roll?category=SIM_CARD", headers=headers, json={}).json()
        seed_countries(db)
        db.flush()
        plate = db.execute(select(Plate).where(Plate.id == result["plate"]["id"])).scalar_one()
        assert plate.plate_type == "SIM"
        assert plate.details["synthetic_number"] == plate.plate_text


class TestPlayerFlowIntegration:
    """select country -> roll -> collectible -> save -> reload -> still there."""

    def test_the_whole_loop(self, client, authed, db):
        headers = authed(880060)["headers"]

        # 1. The player opens the app and sees the whole world.
        assert client.get("/api/countries/active", headers=headers).json()["code"] is None

        # 2. They choose a country.
        selected = client.post("/api/countries/active", json={"code": "BRA"}, headers=headers)
        assert selected.status_code == 200
        assert selected.json()["code"] == "BRA"

        # 3. They roll in that country. The kind is decided by the server, so the
        #    test asks for one explicitly rather than betting on the draw.
        first = client.post("/api/roll?category=VEHICLE_PLATE", headers=headers, json={}).json()
        assert first["plate"]["country"]["code"] == "BRA"
        assert first["plate"]["kind"] == "VEHICLE_PLATE"
        assert first["plate"]["owned"] is True

        # 4. They hunt SIM cards explicitly.
        sim = client.post("/api/roll?category=SIM_CARD", headers=headers, json={}).json()
        assert sim["plate"]["kind"] == "SIM_CARD"
        assert sim["plate"]["details"]["synthetic_number"] == sim["plate"]["plate_text"]

        # 5. The collection reflects the country context and both kinds.
        collection = client.get("/api/collection?page_size=100", headers=headers).json()
        assert collection["total"] >= 2
        assert {item["country"]["code"] for item in collection["items"]} == {"BRA"}
        assert {item["kind"] for item in collection["items"]} == {"VEHICLE_PLATE", "SIM_CARD"}

        # 6. A reload keeps everything: country and collection are server-side.
        assert client.get("/api/countries/active", headers=headers).json()["code"] == "BRA"
        assert client.get("/api/collection?page_size=100", headers=headers).json()["total"] == collection["total"]

        # 7. And the rows really exist, owned, in that country.
        user_id = db.execute(
            select(User.id).where(User.telegram_id == 880060)
        ).scalar_one()
        rows = db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id)
        ).scalars().all()
        assert len(rows) >= 2
        assert all(row.country_code == "BRA" for row in rows)