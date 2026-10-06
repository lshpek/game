"""Unit tests for the pure plate engine.

These cover what must never regress: Unicode normalisation, pattern detection,
rarity scoring, valuation and template generation.
"""

from __future__ import annotations

import pytest

from app.game import sim_cards
from app.game.countries import COUNTRIES
from app.game.plate_generator import (
    RegionOption,
    TemplateOption,
    build_generated_plate,
    render_template,
    styles_for_text,
)
from app.game.plate_patterns import analyze_plate, split_plate
from app.game.plate_rarity import (
    RARITY_ORDER,
    RARITY_RANK,
    Rarity,
    compute_rarity_score,
    load_rarity_weights,
    natural_rarity,
    pity_weights,
    resolve_final_rarity,
    score_rarity,
)
from app.game.plate_status import RUSSIAN_STATUS_SERIES, collector_bio, status_series_for
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

    @pytest.mark.parametrize("region_code", ["77", "78", "50", "23", "16"])
    def test_numeric_region_codes_render_without_rewriting(self, region_code):
        plate, _styles = render_template(
            parse_template("R"),
            alphabet="АВЕКМНОРСТУХ",
            region_code=region_code,
            rng=None,
            country_code="RUS",
        )
        assert plate == region_code


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
        assert score_rarity(100) is Rarity.MYTHIC
        assert score_rarity(130) is Rarity.MYTHIC

    def test_natural_rarity_from_patterns(self):
        plain = natural_rarity(analyze_plate("123 AB"))
        lucky = natural_rarity(analyze_plate("7777 AB"))
        assert RARITY_RANK[lucky.value] > RARITY_RANK[plain.value]

    def test_global_target_weights_are_exact(self):
        assert load_rarity_weights() == {
            "COMMON": 54.0,
            "UNCOMMON": 30.0,
            "RARE": 13.0,
            "EPIC": 2.5,
            "LEGENDARY": 0.4,
            "MYTHIC": 0.09,
            "SECRET": 0.01,
        }

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

    def test_template_floor_cannot_promote_an_ordinary_plate(self):
        analysis = analyze_plate("482 AB")
        rarity = resolve_final_rarity(
            natural=natural_rarity(analysis),
            luck=Rarity.COMMON,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
            template_floor="RARE",
        )
        assert rarity is Rarity.COMMON

    def test_random_luck_cannot_promote_an_ordinary_plate(self):
        analysis = analyze_plate("482 AB")
        rarity = resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.LEGENDARY,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
        )
        assert rarity is Rarity.COMMON

    def test_provider_and_discovery_modifiers_do_not_change_quality(self):
        analysis = analyze_plate("482 AB")
        plain = compute_rarity_score(analysis)
        assert compute_rarity_score(
            analysis,
            country_modifier=3,
            template_multiplier=4,
            event_modifier=5,
            novelty_bonus=100,
            provider_modifier=1.2,
        ) == plain

    def test_ugly_random_sim_digits_stay_common_even_when_secret_is_targeted(self):
        number = "+7 912 359 7912"
        parsed = sim_cards.parse_sim_number("RUS", number)
        assert parsed is not None
        analysis = analyze_plate(number, plate_type="SIM", quality_digits=parsed[1])
        rarity = resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.SECRET,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
        )
        assert rarity is Rarity.COMMON

    def test_overlapping_traits_do_not_stack_to_epic_or_legendary(self):
        analysis = analyze_plate("A7770BC")
        assert compute_rarity_score(analysis) == 28
        assert resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.LEGENDARY,
            score=compute_rarity_score(analysis),
            traits=analysis.traits,
        ) is Rarity.RARE

    def test_region_letters_do_not_contribute_to_pattern_quality(self):
        with_region = analyze_plate("HH AB 1234", region_code="HH")
        serial_only = analyze_plate("AB 1234")
        assert compute_rarity_score(with_region) == compute_rarity_score(serial_only)

    def test_stronger_patterns_step_up_the_rarity_ladder(self):
        def score_for(digits: str) -> int:
            return compute_rarity_score(
                analyze_plate(f"+7 900 {digits}", plate_type="SIM", quality_digits=digits)
            )

        assert score_rarity(score_for("9146825")) is Rarity.COMMON
        assert score_rarity(score_for("123")) is Rarity.UNCOMMON
        assert score_rarity(score_for("777")) is Rarity.RARE
        assert score_rarity(score_for("12345")) is Rarity.EPIC
        assert score_rarity(score_for("777777")) is Rarity.LEGENDARY
        assert score_rarity(score_for("77777777")) is Rarity.MYTHIC

    def test_secret_requires_a_perfect_repeated_number_not_a_flag(self):
        perfect = analyze_plate(
            "+7 900 7777777777", plate_type="SIM", quality_digits="7777777777"
        )
        assert resolve_final_rarity(
            natural=Rarity.COMMON,
            luck=Rarity.COMMON,
            score=compute_rarity_score(perfect),
            traits=perfect.traits,
        ) is Rarity.SECRET
        assert resolve_final_rarity(
            natural=Rarity.MYTHIC,
            luck=Rarity.SECRET,
            score=130,
            traits=["pair"],
            force_secret=True,
        ) is Rarity.MYTHIC

    def test_quality_conditioned_generation_reaches_each_configured_tier(self, db):
        import random

        from app.core.config import settings
        from app.game.plate_generator import PlateGenerator
        from app.services.catalog import build_snapshot

        context = build_snapshot(db, settings.rarity_weights).context
        for index, target in enumerate(RARITY_ORDER):
            generated = PlateGenerator(context, random.Random(500 + index)).generate(
                luck=target
            )
            assert generated.rarity is target

    def test_full_pipeline_rarity_distribution_matches_configured_weights(self, db):
        """The end-to-end pipeline must reproduce the configured rarity shares.

        Luck is sampled from the weights and then biases the *pattern* generation
        (quality-targeted digits/letters); the final rarity is then scored purely
        from the resulting patterns. If either link broke, the observed shares
        would drift from the configuration - this test catches that drift with a
        chi-square goodness-of-fit over a sample rather than a single seed.
        """
        import random

        from app.core.config import settings
        from app.game.plate_generator import PlateGenerator
        from app.game.rng import roll_rarity
        from app.services.catalog import build_snapshot

        weights = load_rarity_weights()
        total_weight = sum(weights.values())
        expected = {r.value: weights.get(r.value, 0.0) / total_weight for r in Rarity}

        context = build_snapshot(db, settings.rarity_weights).context

        sample_size = 6_000
        observed: dict[str, int] = {r.value: 0 for r in Rarity}
        rng = random.Random(20240607)
        for _ in range(sample_size):
            luck = roll_rarity(settings.rarity_weights, rng)
            generated = PlateGenerator(context, rng).generate(luck=luck)
            observed[generated.rarity.value] += 1

        # Chi-square goodness-of-fit against the configured weights (6 degrees of
        # freedom: 7 tiers - 1). The 95th critical value for 6 dof is 12.59.
        chi_square = 0.0
        for code, exp_share in expected.items():
            exp_count = exp_share * sample_size
            if exp_count > 0:
                chi_square += (observed[code] - exp_count) ** 2 / exp_count
        assert chi_square < 12.59, (
            f"Rarity distribution drifted from configured weights "
            f"(chi_square={chi_square:.1f}, observed={observed})"
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

    def test_status_series_boosts_collector_value_not_dealer_value(self):
        plain = compute_values(Rarity.EPIC, ["triple"])
        associated = compute_values(Rarity.EPIC, ["triple"], collector_multiplier=1.75)
        assert associated[0] == plain[0]
        assert associated[1] > plain[1]


class TestPlateStatus:
    def test_requested_russian_series_have_qualified_categories(self):
        assert set(RUSSIAN_STATUS_SERIES) == {
            "АМР", "ЕКХ", "ММР", "КОО", "АОО", "ААА", "ММС", "РМР", "ВОР", "МУР", "ООО", "МММ"
        }
        assert status_series_for("RUS", ["А", "МР"]).category == "PUBLIC_ASSOCIATION"
        assert status_series_for("RUS", ["М", "ММ"]).category == "AESTHETIC_ONLY"
        assert status_series_for("USA", ["A", "MR"]) is None

    def test_epic_bio_is_structured_and_makes_no_ownership_claim(self):
        bio = collector_bio(
            rarity="EPIC",
            kind="VEHICLE_PLATE",
            country_code="RUS",
            letter_groups=["А", "МР"],
            traits=["triple", "symmetric_plate"],
            region_code="77",
            region_name_en="Moscow",
            region_name_ru="Москва",
        )
        assert bio is not None
        assert bio["status_category"] == "PUBLIC_ASSOCIATION"
        assert bio["series_code"] == "АМР"
        assert bio["region_code"] == "77"
        assert "triple" in bio["pattern_codes"]
        assert "owner" in str(bio["association_en"])

    def test_bio_is_omitted_below_epic(self):
        assert collector_bio(
            rarity="RARE", kind="VEHICLE_PLATE", country_code="RUS",
            letter_groups=["А", "МР"], traits=["triple"],
        ) is None

    def test_status_metadata_is_attached_to_a_generated_collectible(self):
        russia = next(country for country in COUNTRIES if country.code == "RUS")
        template_def = next(template for template in russia.templates if template.code == "ru_standard")
        template = TemplateOption(
            code=template_def.code,
            pattern=template_def.pattern,
            weight=template_def.weight,
            plate_type=template_def.plate_type,
            rarity_floor=template_def.rarity_floor,
            requires_region=True,
        )
        region = RegionOption("77", "Moscow", "Москва", 1.0)
        generated = build_generated_plate(
            plate_text="А777МР 77",
            country=russia,
            region=region,
            template=template,
            luck=Rarity.SECRET,
            styles=styles_for_text("А777МР 77", "77"),
        )
        assert generated.details["status_series"]["code"] == "АМР"
        assert generated.details["status_series"]["category"] == "PUBLIC_ASSOCIATION"
        assert generated.rarity is not Rarity.SECRET


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
