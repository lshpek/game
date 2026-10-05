"""The SIM line: fictional NUMORA carriers, synthetic numbers and weighting.

The contract this module protects:

* a card prints a **fictional NUMORA carrier** - never a real network's
  brand, so a realistic synthetic number can never read as a real
  person's subscriber line;
* the number printed on it is **synthetic game data**, never a subscriber
  line;
* a carrier influences the **game** rarity and value, within narrow bounds;
* a card written before the NUMORA catalogue - or with a real operator from
  the retired catalogue - still renders with the brand it was printed with.
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
    LEGACY_PROVIDERS,
    LINE_SIZE,
    MAX_PROVIDER_MODIFIER,
    MIN_PROVIDER_MODIFIER,
    NUMORA_CARRIERS,
    clamp_modifier,
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

    def test_every_country_prints_numora_carriers(self):
        """No country ever prints a real network's brand."""
        universe = {carrier.code for carrier in NUMORA_CARRIERS}
        for country in PLAYABLE:
            line = providers_for(country.code)
            assert len(line) >= 2, country.code
            # A line never repeats a carrier.
            assert len({provider.code for provider in line}) == len(line), country.code
            for provider in line:
                assert provider.code in universe, (country.code, provider.code)
                assert provider.real_brand is False, (country.code, provider.code)
                assert provider.brand, (country.code, provider.code)

    def test_no_real_operator_is_ever_generated(self):
        """The retired real-operator catalogue is render-only."""
        real_codes = {provider.code for provider in LEGACY_PROVIDERS}
        for country in PLAYABLE:
            for provider in providers_for(country.code):
                assert provider.code not in real_codes, (country.code, provider.code)

    def test_a_line_is_stable_and_drawn_from_the_numora_universe(self):
        """A country's line is derived from its code alone: identical on
        every boot, so a card's brand never depends on when it was rolled."""
        for country in ("RUS", "POL", "PER", "ZZZ"):
            assert providers_for(country) == providers_for(country)
            assert len(providers_for(country)) == LINE_SIZE
        universe = {carrier.brand for carrier in NUMORA_CARRIERS}
        for country in PLAYABLE:
            assert {provider.brand for provider in providers_for(country.code)} <= universe

    def test_provider_codes_are_unique_and_stable(self):
        codes = [carrier.code for carrier in provider_catalogue.NUMORA_CARRIERS]
        assert len(codes) == len(set(codes))

    def test_every_carrier_has_a_home_market(self):
        known = {country.code for country in COUNTRIES}
        for carrier in provider_catalogue.NUMORA_CARRIERS:
            assert carrier.country in known, carrier.code
            assert carrier.real_brand is False, carrier.code
        for provider in provider_catalogue.LEGACY_PROVIDERS:
            assert provider.country in known, provider.code
            assert provider.real_brand is True, provider.code

    def test_modifiers_stay_inside_their_documented_bounds(self):
        for carrier in provider_catalogue.NUMORA_CARRIERS:
            assert MIN_PROVIDER_MODIFIER <= carrier.rarity_modifier <= MAX_PROVIDER_MODIFIER
            assert MIN_PROVIDER_MODIFIER <= carrier.value_modifier <= MAX_PROVIDER_MODIFIER

    def test_a_carrier_can_never_alone_manufacture_a_tier(self):
        """The spread is deliberately narrow so the *number* always dominates."""
        values = [carrier.rarity_modifier for carrier in provider_catalogue.NUMORA_CARRIERS]
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
        for code in ("RUS", "POL", "USA", "DEU"):
            fmt = sim_cards.sim_format(code)
            for prefix, _weight in fmt.prefixes:
                assert any(
                    template.pattern.startswith(f"+{fmt.calling_code.lstrip('+')} {prefix}")
                    for template in sim_templates(code)
                ), (code, prefix)

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
    def test_a_card_carries_a_numora_brand_and_its_game_modifiers(self, client, authed):
        session = authed(882_100_002)
        brands = {provider.brand for provider in providers_for("RUS")}
        seen: set[str] = set()
        for _ in range(8):
            data = client.post(
                "/api/roll?category=SIM_CARD&country_code=RUS", headers=session["headers"], json={}
            ).json()
            details = data["plate"]["details"]
            assert details["operator"] in brands
            assert details["operator_is_real"] is False
            assert details["operator_local"]
            assert MIN_PROVIDER_MODIFIER <= details["rarity_modifier"] <= MAX_PROVIDER_MODIFIER
            assert MIN_PROVIDER_MODIFIER <= details["value_modifier"] <= MAX_PROVIDER_MODIFIER
            seen.add(details["operator_code"])
        assert len(seen) >= 2, "one carrier should not monopolise a country"

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

    def test_a_retired_real_operator_resolves_to_its_brand(self):
        """Generation with a retired code keeps the brand it was printed with."""
        details = sim_cards.card_details(
            country_code="RUS",
            operator_code="mts",
            edition="ORIGIN",
            number="+7 900 000 00 01",
        )
        assert details.operator == "MTS"
        assert details.operator_local == "МТС"
        assert details.operator_is_real is True
        assert details.operator_accent == "#ff0032"

    def test_a_vehicle_plate_has_no_sim_payload(self):
        class _Plate:
            plate_type = "STANDARD"
            details: ClassVar[dict] = {}
            plate_text = "A 001 BC 77"

        assert sim_details(_Plate()) is None
        assert kind_for_plate_type(_Plate().plate_type) is CollectibleKind.VEHICLE_PLATE


class TestProviderTemplates:
    def test_each_carrier_gets_its_own_templates(self):
        codes = {template.config["provider_code"] for template in sim_templates("RUS")}
        assert codes == {provider.code for provider in providers_for("RUS")}

    def test_template_weights_follow_the_provider_weight(self):
        """A bigger brand is more common inside the game, like any market."""
        totals: dict[str, list[float]] = {}
        for template in sim_templates("RUS"):
            totals.setdefault(template.config["provider_code"], []).append(template.weight)
        averages = {code: sum(values) / len(values) for code, values in totals.items()}
        by_weight = sorted(
            (provider.weight, provider.code) for provider in providers_for("RUS")
        )
        # The heaviest carrier prints the most often, the lightest the least.
        assert averages[by_weight[-1][1]] > averages[by_weight[0][1]]

    def test_no_duplicate_template_codes(self):
        for country in PLAYABLE:
            codes = [template.code for template in sim_templates(country.code)]
            assert len(codes) == len(set(codes)), country.code

    def test_the_provider_catalogue_is_seeded_and_matches_the_module(self, db):
        rows = db.execute(select(SimProvider)).scalars().all()
        assert len(rows) == len(provider_catalogue.NUMORA_CARRIERS)
        by_code = {row.code: row for row in rows}
        for definition in provider_catalogue.NUMORA_CARRIERS:
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
            assert provider["is_real_brand"] is False
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
        country_code=country_code,
    )
    return plate_text
