"""The SIM line: real operator brands, synthetic numbers and provider weighting.

The contract this module protects:

* a card prints a **real, current** operator brand for its country;
* the number printed on it is **synthetic game data**, never a subscriber line;
* a provider influences the **game** rarity and value, within narrow bounds;
* a card written before the provider catalogue existed still renders.
"""

from __future__ import annotations

import re
from typing import ClassVar

import pytest
from sqlalchemy import select

from app.api.plate_serializers import sim_details
from app.game import providers as provider_catalogue
from app.game import sim_cards
from app.game.collectibles import CollectibleKind, kind_for_plate_type, sim_templates
from app.game.countries import COUNTRIES
from app.game.providers import (
    MAX_PROVIDER_MODIFIER,
    MIN_PROVIDER_MODIFIER,
    clamp_modifier,
    curated_countries,
    provider_by_code,
    providers_for,
)
from app.models.plates import Plate, SimProvider

PLAYABLE = [country for country in COUNTRIES if country.playable]


class TestProviderCatalogue:
    def test_every_playable_country_has_at_least_two_providers(self):
        for country in PLAYABLE:
            line = providers_for(country.code)
            assert len(line) >= 2, country.code

    def test_russia_uses_its_current_real_operators(self):
        brands = {provider.brand for provider in providers_for("RUS")}
        assert {"MTS", "MegaFon", "Beeline", "T2"} == brands

    def test_tele2_is_not_used_as_a_russian_brand(self):
        """Tele2 Russia was rebranded to T2; new content must use the current brand."""
        codes = {provider.code for provider in providers_for("RUS")}
        assert "t2" in codes
        assert "tele2" not in codes
        brands = " ".join(provider.brand for provider in providers_for("RUS")).lower()
        assert "tele2" not in brands

    def test_poland_uses_its_current_real_operators(self):
        brands = {provider.brand for provider in providers_for("POL")}
        assert {"Orange", "Play", "T-Mobile", "Plus"} == brands

    def test_the_launch_countries_all_have_curated_real_brands(self):
        curated = set(curated_countries())
        for code in ("RUS", "POL", "KAZ", "DEU", "GBR", "FRA", "ITA", "JPN", "USA", "ARE"):
            assert code in curated, code
            for provider in providers_for(code):
                assert provider.real_brand, (code, provider.code)

    def test_a_country_without_a_curated_line_gets_documented_game_brands(self):
        line = providers_for("PER")
        assert line
        assert all(provider.real_brand is False for provider in line)
        # Game brands must not be styled as if they were a real carrier.
        assert all(provider.brand.startswith("PER ") for provider in line)

    def test_provider_codes_are_unique_and_stable(self):
        codes = [provider.code for provider in provider_catalogue.PROVIDERS]
        assert len(codes) == len(set(codes))

    def test_every_provider_belongs_to_a_real_country_code(self):
        known = {country.code for country in COUNTRIES}
        for provider in provider_catalogue.PROVIDERS:
            assert provider.country in known, provider.code

    def test_modifiers_stay_inside_their_documented_bounds(self):
        for provider in provider_catalogue.PROVIDERS:
            assert MIN_PROVIDER_MODIFIER <= provider.rarity_modifier <= MAX_PROVIDER_MODIFIER
            assert MIN_PROVIDER_MODIFIER <= provider.value_modifier <= MAX_PROVIDER_MODIFIER

    def test_a_provider_can_never_alone_manufacture_a_tier(self):
        """The spread is deliberately narrow so the *number* always dominates."""
        values = [provider.rarity_modifier for provider in provider_catalogue.PROVIDERS]
        assert max(values) - min(values) <= 0.25

    def test_clamp_modifier_is_defensive(self):
        assert clamp_modifier(9.9) == MAX_PROVIDER_MODIFIER
        assert clamp_modifier(0.01) == MIN_PROVIDER_MODIFIER
        assert clamp_modifier(None) == 1.0
        assert clamp_modifier("nonsense") == 1.0


class TestSyntheticNumbers:
    def test_every_pattern_starts_with_the_calling_code(self):
        for country in PLAYABLE:
            for template in sim_templates(country.code):
                assert template.pattern.startswith("+" + country.calling_code.lstrip("+"))

    def test_a_printed_number_is_synthetic_and_matches_the_country_block(self, db):
        """Rendered numbers look local but are generated game data."""
        for country in ("RUS", "POL", "USA", "DEU", "JPN", "KAZ"):
            fmt = sim_cards.sim_format(country)
            head = "+" + fmt.calling_code.lstrip("+")
            for _ in range(6):
                text = _render_number(country)
                assert text.startswith(head + " ")
                tail = text[len(head) + 1 :]
                block, _sep, digits = tail.partition(" ")
                # The first block is one of the country's own stylised blocks.
                assert block in {prefix for prefix, _weight in fmt.prefixes}, (country, text)
                # The remainder is digits only, in the country's own grouping.
                assert digits.replace(" ", "").isdigit(), text
                assert [len(chunk) for chunk in digits.split(" ")] == list(fmt.groups), text

    def test_generated_numbers_keep_the_country_block(self):
        for country in ("RUS", "POL", "USA", "DEU"):
            fmt = sim_cards.sim_format(country)
            for prefix, _weight in fmt.prefixes:
                assert any(
                    template.pattern.startswith(f"+{fmt.calling_code.lstrip('+')} {prefix}")
                    for template in sim_templates(country)
                ), (country.code, prefix)

    def test_an_unconfigured_country_falls_back_to_the_documented_game_block(self):
        fmt = sim_cards.sim_format("PER")
        assert fmt.prefixes == ((sim_cards.GAME_PREFIX + "00", 1.0),)
        assert fmt.groups == (3, 4)

    def test_every_card_is_flagged_synthetic(self, client, authed, db):
        session = authed(882_100_001)
        data = client.post("/api/roll?category=SIM_CARD", headers=session["headers"], json={})
        details = data.json()["plate"]["details"]
        assert details["synthetic"] is True
        assert details["synthetic_number"] == data.json()["plate"]["plate_text"]

        row = db.execute(
            select(Plate).where(Plate.id == data.json()["plate"]["id"])
        ).scalar_one()
        assert row.details["synthetic"] is True


class TestProviderOnACard:
    def test_a_card_carries_a_real_brand_and_its_game_modifiers(self, client, authed):
        session = authed(882_100_002)
        seen: set[str] = set()
        for _ in range(8):
            data = client.post(
                "/api/roll?category=SIM_CARD&country_code=RUS", headers=session["headers"], json={}
            ).json()
            details = data["plate"]["details"]
            assert details["operator"] in {"MTS", "MegaFon", "Beeline", "T2"}
            assert details["operator_is_real"] is True
            assert details["operator_local"]
            assert MIN_PROVIDER_MODIFIER <= details["rarity_modifier"] <= MAX_PROVIDER_MODIFIER
            assert MIN_PROVIDER_MODIFIER <= details["value_modifier"] <= MAX_PROVIDER_MODIFIER
            seen.add(details["operator_code"])
        assert len(seen) >= 2, "one operator should not monopolise a country"

    def test_a_card_reports_its_operator_series_and_edition(self, client, authed):
        session = authed(882_100_003)
        details = client.post(
            "/api/roll?category=SIM_CARD&country_code=POL", headers=session["headers"], json={}
        ).json()["plate"]["details"]
        assert details["series"].startswith("N-")
        assert details["edition"] in sim_cards.EDITION_CODES
        assert details["calling_code"] == sim_cards.sim_format("POL").calling_code

    def test_the_same_number_always_prints_the_same_series(self):
        assert sim_cards.series_for("+7 900 123 45 67") == sim_cards.series_for(
            "+7 900 123 45 67"
        )
        assert sim_cards.series_for("+7 900 123 45 67") != sim_cards.series_for(
            "+7 900 987 65 43"
        )

    def test_a_retired_fictional_operator_still_renders(self, db):
        """A card written with the retired operator set must keep a brand label."""

        class _Legacy:
            plate_type = "SIM"
            details: ClassVar[dict] = {
                "operator_code": "numa",
                "synthetic_number": "+7 900 000 00 01",
            }
            plate_text = "+7 900 000 00 01"

        payload = sim_details(_Legacy())
        assert payload is not None
        assert payload["synthetic"] is True
        assert payload["operator"]
        assert payload["operator_is_real"] is False

    def test_a_vehicle_plate_has_no_sim_payload(self):
        class _Plate:
            plate_type = "STANDARD"
            details: ClassVar[dict] = {}
            plate_text = "A 001 BC 77"

        assert sim_details(_Plate()) is None
        assert kind_for_plate_type(_Plate().plate_type) is CollectibleKind.VEHICLE_PLATE


class TestProviderTemplates:
    def test_each_provider_gets_its_own_templates(self):
        codes = {template.config["provider_code"] for template in sim_templates("RUS")}
        assert codes == {"mts", "megafon", "beeline", "t2"}

    def test_template_weights_follow_the_provider_weight(self):
        """A bigger brand is more common inside the game, like any real market."""
        totals: dict[str, list[float]] = {}
        for template in sim_templates("RUS"):
            totals.setdefault(template.config["provider_code"], []).append(template.weight)
        averages = {code: sum(values) / len(values) for code, values in totals.items()}
        assert averages["mts"] > averages["beeline"] > averages["t2"]

    def test_no_duplicate_template_codes(self):
        for country in PLAYABLE:
            codes = [template.code for template in sim_templates(country.code)]
            assert len(codes) == len(set(codes)), country.code

    def test_the_provider_catalogue_is_seeded_and_matches_the_module(self, db):
        rows = db.execute(select(SimProvider)).scalars().all()
        assert len(rows) == len(provider_catalogue.PROVIDERS)
        by_code = {row.code: row for row in rows}
        for definition in provider_catalogue.PROVIDERS:
            row = by_code[definition.code]
            assert row.brand == definition.brand
            assert row.country_code == definition.country
            assert row.is_real_brand == definition.real_brand

    def test_seeding_twice_does_not_duplicate_providers(self, db):
        from app.seed import seed_providers

        before = len(db.execute(select(SimProvider)).scalars().all())
        seed_providers(db)
        db.commit()
        assert len(db.execute(select(SimProvider)).scalars().all()) == before

    @pytest.mark.parametrize("code", ["RUS", "POL", "KAZ", "DEU", "GBR", "FRA", "ITA", "JPN", "USA", "ARE"])
    def test_the_country_api_advertises_the_provider_line(self, client, authed, code):
        session = authed(882_100_100 + len(code))
        data = client.get(f"/api/countries/{code}", headers=session["headers"]).json()
        providers = data["sim"]["providers"]
        assert providers, code
        for provider in providers:
            assert provider["code"]
            assert provider["brand"]
            assert provider["is_real_brand"] is True
            assert MIN_PROVIDER_MODIFIER <= provider["rarity_modifier"] <= MAX_PROVIDER_MODIFIER
        # The compatibility alias is derived from the same catalogue.
        assert [item["code"] for item in data["sim"]["operators"]] == [
            item["code"] for item in providers
        ]


class TestProviderWeighting:
    def test_a_boring_number_with_a_big_brand_stays_ordinary(self):
        """The exact anti-pattern the design forbids: brand == legendary."""
        from app.game.plate_patterns import PlateAnalysis
        from app.game.plate_rarity import compute_rarity_score

        plain = PlateAnalysis(
            plate_text="+7 900 123 45 67",
            digits=list("1234567"),
            letters=[],
            numeric_core="1234567",
            traits=["has_letters"],
            scores={"has_letters": 4},
            tags=[],
        )
        weak = compute_rarity_score(plain, provider_modifier=MIN_PROVIDER_MODIFIER)
        strong = compute_rarity_score(plain, provider_modifier=MAX_PROVIDER_MODIFIER)
        assert strong - weak <= 6
        assert _tier(strong) != "LEGENDARY"
        assert _tier(strong) != "MYTHIC"

    def test_an_extraordinary_number_with_a_plain_brand_can_still_climb(self):
        from app.game.plate_patterns import PlateAnalysis
        from app.game.plate_rarity import compute_rarity_score

        special = PlateAnalysis(
            plate_text="+7 900 777 77 77",
            digits=list("7777777"),
            letters=[],
            numeric_core="7777777",
            traits=["palindrome", "triple_digit", "all_same"],
            scores={"palindrome": 40, "triple_digit": 28, "all_same": 45},
            tags=[],
        )
        weak = compute_rarity_score(special, provider_modifier=MIN_PROVIDER_MODIFIER)
        strong = compute_rarity_score(special, provider_modifier=MAX_PROVIDER_MODIFIER)
        assert strong > weak
        # The pattern, not the brand, is what moved it.
        assert strong - weak < weak

    def test_an_unknown_provider_code_resolves_to_nothing(self):
        assert provider_by_code("nope") is None
        assert provider_by_code(None) is None


def _tier(score: int) -> str:
    """The rarity tier a raw score falls into, for assertions about the ladder."""
    from app.game.plate_rarity import resolve_final_rarity

    return resolve_final_rarity(
        natural="COMMON", luck="COMMON", score=score, traits=[], template_floor="COMMON"
    ).value


def _render_number(country_code: str) -> str:
    """Render one synthetic number exactly the way the engine would."""
    from app.game.plate_generator import render_template
    from app.game.plate_templates import parse_template
    from app.game.rng import default_rng

    country = next(item for item in COUNTRIES if item.code == country_code)
    template = sim_templates(country_code)[0]
    plate_text, _styles = render_template(
        parse_template(template.pattern),
        alphabet=country.alphabet,
        region_code=None,
        rng=default_rng(),
    )
    return plate_text
