"""Unit tests for the pure plate engine.

These cover what must never regress: Unicode normalisation, pattern detection,
rarity scoring, valuation and template generation.
"""

from __future__ import annotations

import pytest

from app.game.countries import COUNTRIES
from app.game.plate_patterns import analyze_plate, split_plate
from app.game.plate_rarity import (
    RARITY_RANK,
    Rarity,
    compute_rarity_score,
    load_rarity_weights,
    natural_rarity,
    pity_weights,
    resolve_final_rarity,
    score_rarity,
)
from app.game.plate_stories import build_plate_story
from app.game.plate_templates import normalize_plate, parse_template
from app.game.plate_traits import PLATE_TRAITS
from app.game.plate_valuation import compute_values, duplicate_sale_value


class TestNormalizePlate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("a777aa 77", "A777AA 77"),
            ("A777-AA-77", "A777 AA 77"),
            ("  a  777   aa ", "A 777 AA"),
            ("AB-123-CD", "AB 123 CD"),
            ("7XK-7777", "7XK 7777"),
        ],
    )
    def test_latin(self, raw, expected):
        assert normalize_plate(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Cyrillic survives intact - a naive [A-Z0-9] filter would empty these.
            ("А777АА 77", "А777АА 77"),
            ("В777СХ 99", "В777СХ 99"),
        ],
    )
    def test_cyrillic_survives(self, raw, expected):
        assert normalize_plate(raw) == expected

    def test_japanese_survives(self):
        assert normalize_plate("ア123 イ45") == "ア123 イ45"

    def test_georgian_survives(self):
        # Unicode upper() maps Georgian onto Mtavruli - the point is that the
        # characters survive at all instead of being stripped to ASCII.
        result = normalize_plate("აბ123 ცდ")
        assert "123" in result
        assert len(result) >= 6
        assert normalize_plate(result) == result  # idempotent

    def test_armenian_survives(self):
        assert normalize_plate("ԱԲ123 ԳԴ") == "ԱԲ123 ԳԴ"

    def test_visual_variants_collapse(self):
        # Full-width digits normalise onto ASCII so lookups agree.
        assert normalize_plate("Ａ７７７") == "A777"

    def test_empty(self):
        assert normalize_plate("") == ""
        assert normalize_plate("   ") == ""


class TestTemplateParsing:
    def test_simple_pattern(self):
        parsed = parse_template("LDDD LL DD")
        assert parsed.letter_slots == 3
        assert parsed.digit_slots == 5
        assert not parsed.has_region_slot

    def test_region_slot(self):
        assert parse_template("R LL DDDD").has_region_slot

    def test_fixed_digits(self):
        assert parse_template("LDDD F7").digit_slots == 4

    def test_choice_group(self):
        # Guards the bug where ``X`` was double-counted: a bare token was
        # emitted before the group token, silently adding an extra slot.
        parsed = parse_template("X[6789] DDD")
        assert parsed.digit_slots == 4
        assert parsed.parts[0].choices == ("6", "7", "8", "9")
        # group + " " + D + D + D
        assert len(parsed.parts) == 5

    def test_letter_choice_group(self):
        # ``A[AB]`` is one letter slot restricted to two choices, not two slots.
        assert parse_template("A[AB] DDD").letter_slots == 1

    def test_rejects_empty(self):
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            parse_template("")

    def test_rejects_literals_only(self):
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            parse_template("---")

    @pytest.mark.parametrize("pattern", ["[ABC]", "D[]"])
    def test_rejects_malformed_groups(self, pattern):
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            parse_template(pattern)

    def test_every_catalog_template_parses(self):
        for country in COUNTRIES:
            for template in country.templates:
                parse_template(template.pattern)


class TestPatterns:
    def test_split_runs(self):
        digits, letters = split_plate("A777AA 77")
        assert digits == ["777", "77"]
        assert letters == ["A", "AA"]

    @pytest.mark.parametrize(
        ("text", "trait"),
        [
            ("A777AA", "contains_777"),
            ("1234 AB", "ascending"),
            ("4321 AB", "descending"),
            ("111111", "all_same"),
            ("007 AB", "contains_007"),
            ("2026 AB", "year_like"),
            ("1337 AB", "meme_pattern"),
            ("7777 AB", "special_run"),
            ("AB 1212", "repeated_pattern"),
            ("ABBA 12", "mirrored_letters"),
            ("A10001", "palindrome"),
            ("A00 00", "contains_000"),
            ("500 AB", "round_number"),
        ],
    )
    def test_detection(self, text, trait):
        assert trait in analyze_plate(text).traits

    def test_region_match_is_detected(self):
        assert "region_match" in analyze_plate("A777AA 77", region_code="77").traits

    def test_region_does_not_inflate_the_serial(self):
        """``A777AA 77`` is judged on 777, not on the combined 77777."""
        assert analyze_plate("A777AA 77", region_code="77").numeric_core == "777"

    def test_reason_chips_are_score_ordered(self):
        analysis = analyze_plate("A777AA 77", region_code="77")
        scores = [analysis.scores[code] for code in analysis.reasons]
        assert scores == sorted(scores, reverse=True)
        assert len(analysis.reasons) <= 4

    def test_tags_are_derived(self):
        tags = analyze_plate("A777AA 77", region_code="77").tags
        assert "lucky" in tags and "mirror" in tags

    def test_every_trait_code_is_registered(self):
        analysis = analyze_plate("A777AA 77", region_code="77")
        assert all(code in PLATE_TRAITS for code in analysis.traits)

    def test_unicode_plates_analyse(self):
        analysis = analyze_plate("ア123 イ45")
        assert analysis.letters  # non-Latin letters are captured
        assert "123" in analysis.numeric_core


class TestRarityEngine:
    def test_score_bands(self):
        assert score_rarity(0) is Rarity.COMMON
        assert score_rarity(12) is Rarity.UNCOMMON
        assert score_rarity(30) is Rarity.RARE
        assert score_rarity(60) is Rarity.EPIC
        assert score_rarity(90) is Rarity.LEGENDARY
        assert score_rarity(130) is Rarity.MYTHIC

    def test_natural_rarity_from_patterns(self):
        plain = natural_rarity(analyze_plate("123 AB"))
        lucky = natural_rarity(analyze_plate("7777 AB"))
        assert RARITY_RANK[lucky.value] > RARITY_RANK[plain.value]

    def test_a_boring_plate_never_reaches_legendary(self):
        """The whole point: rarity must be earned by patterns."""
        analysis = analyze_plate("482 AB")
        rarity = resolve_final_rarity(
            natural=natural_rarity(analysis),
            luck=Rarity.COMMON,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
        )
        assert rarity in (Rarity.COMMON, Rarity.UNCOMMON)

    def test_template_floor_is_respected(self):
        analysis = analyze_plate("482 AB")
        rarity = resolve_final_rarity(
            natural=natural_rarity(analysis),
            luck=Rarity.COMMON,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
            template_floor="RARE",
        )
        assert rarity is Rarity.RARE

    def test_luck_can_lift_but_never_lower(self):
        analysis = analyze_plate("482 AB")
        rarity = resolve_final_rarity(
            natural=Rarity.RARE,
            luck=Rarity.COMMON,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
        )
        assert rarity is Rarity.RARE

    def test_secret_requires_an_explicit_flag(self):
        assert (
            resolve_final_rarity(
                natural=Rarity.MYTHIC,
                luck=Rarity.MYTHIC,
                score=199,
                traits=["pair"],
                force_secret=False,
            )
            is Rarity.MYTHIC
        )
        assert (
            resolve_final_rarity(
                natural=Rarity.MYTHIC,
                luck=Rarity.MYTHIC,
                score=10,
                traits=["pair"],
                force_secret=True,
            )
            is Rarity.SECRET
        )

    def test_pity_only_ever_helps(self):
        base = load_rarity_weights()
        protected = pity_weights(base, rare_streak=100, epic_streak=100, legendary_streak=100)
        for code, weight in base.items():
            assert protected[code] >= weight - 1e-9

    def test_pity_is_inactive_without_a_streak(self):
        base = load_rarity_weights()
        assert pity_weights(base, rare_streak=0, epic_streak=0, legendary_streak=0) == base

    def test_weights_are_validated(self):
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            load_rarity_weights("{not json}")
        with pytest.raises(ValidationError):
            load_rarity_weights('{"NOPE": 1}')


class TestValuation:
    def test_higher_rarity_is_worth_more(self):
        low = compute_values(Rarity.COMMON, ["pair"])[0]
        high = compute_values(Rarity.LEGENDARY, ["all_same"])[0]
        assert high > low * 10

    def test_traits_increase_value(self):
        assert compute_values(Rarity.RARE, ["triple", "palindrome"])[0] > compute_values(
            Rarity.RARE, []
        )[0]

    def test_novelty_decays_with_discovery(self):
        fresh = compute_values(Rarity.RARE, ["triple"], discovery_count=0)[0]
        common = compute_values(Rarity.RARE, ["triple"], discovery_count=400)[0]
        assert fresh > common

    def test_collector_and_dealer_values_are_independent(self):
        dealer, collector = compute_values(Rarity.EPIC, ["triple"])
        assert dealer > 0 and collector > 0
        # The local value is a presentation, not an exchange rate.
        assert collector != dealer

    def test_duplicate_sale_has_a_floor(self):
        assert duplicate_sale_value(1) >= 3

    def test_duplicate_sale_scales(self):
        assert duplicate_sale_value(10_000) > duplicate_sale_value(1_000)

    def test_values_are_deterministic(self):
        assert compute_values(Rarity.RARE, ["triple"], discovery_count=5) == compute_values(
            Rarity.RARE, ["triple"], discovery_count=5
        )


class TestStories:
    def test_story_is_deterministic(self):
        first = build_plate_story(traits=["contains_777"], country_code="RUS")
        second = build_plate_story(traits=["contains_777"], country_code="RUS")
        assert first == second

    def test_story_is_localised(self):
        en = build_plate_story(traits=["contains_777"], country_code="RUS", lang="en")
        ru = build_plate_story(traits=["contains_777"], country_code="RUS", lang="ru")
        assert en != ru
        assert any(ord(ch) > 0x400 for ch in ru)

    def test_first_discovery_is_mentioned(self):
        story = build_plate_story(
            traits=["triple"], country_code="USA", is_first_discovery=True
        )
        assert "first recorded discovery" in story

    def test_secret_gets_its_own_story(self):
        story = build_plate_story(traits=["triple"], country_code="JPN", is_secret=True)
        assert "Secret" in story

    def test_story_never_makes_market_claims(self):
        """Stories must not imply real-world value or ownership."""
        story = build_plate_story(traits=["all_same"], country_code="RUS")
        lowered = story.lower()
        for banned in ("market", "resale", "real life", "owned by"):
            assert banned not in lowered
