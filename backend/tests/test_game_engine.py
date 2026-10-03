"""Number analyzer, rarity, valuation and story rules."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.game.analyzer import analyze, normalize_number
from app.game.rarity import Rarity, load_rarity_weights, max_rarity, rarity_rank
from app.game.rules import longest_consecutive_run
from app.game.story import build_story
from app.game.valuation import compute_value, duplicate_conversion_reward, novelty_multiplier


class TestNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("7", "0007"), (7, "0007"), ("0007", "0007"), ("1234", "1234"), (9999, "9999"), ("0000", "0000")],
    )
    def test_zero_padding(self, raw, expected):
        assert normalize_number(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abcd", "10000", "-1"])
    def test_invalid_input_rejected(self, raw):
        with pytest.raises(ValidationError):
            normalize_number(raw)

    def test_leading_zero_is_preserved(self):
        assert normalize_number("0007") != "7"
        assert len(normalize_number("0007")) == 4


class TestTraits:
    @pytest.mark.parametrize(
        ("number", "trait"),
        [
            ("7777", "all_same"),
            ("7777", "four_of_kind"),
            ("7777", "contains_777"),
            ("6666", "contains_666"),
            ("1234", "contains_123"),
            ("1234", "ascending"),
            ("1234", "sequence"),
            ("4321", "descending"),
            ("0000", "contains_000"),
            ("0000", "round_number"),
            ("1221", "palindrome"),
            ("1212", "repeated_pattern"),
            ("1123", "pair"),
            ("1122", "two_pairs"),
            ("1112", "triple"),
            ("7770", "lucky_pattern"),
            ("1337", "meme_pattern"),
            ("2024", "year_like"),
            ("0007", "low_number"),
        ],
    )
    def test_trait_detected(self, number, trait):
        assert trait in analyze(number).traits

    def test_plain_number_has_no_special_traits(self):
        analysis = analyze("4517")
        assert "four_of_kind" not in analysis.traits
        assert "palindrome" not in analysis.traits

    @pytest.mark.parametrize(
        ("number", "expected"), [("1234", 4), ("1357", 1), ("1244", 2), ("7777", 1), ("9012", 3)]
    )
    def test_sequence_length(self, number, expected):
        assert longest_consecutive_run(number) == expected
        assert analyze(number).sequence_length == expected

    def test_analysis_is_deterministic(self):
        assert analyze("4242").traits == analyze("4242").traits
        assert analyze("4242").rarity is analyze("4242").rarity


class TestRarity:
    @pytest.mark.parametrize(
        ("number", "rarity"),
        [
            ("1337", Rarity.SECRET),
            ("8008", Rarity.SECRET),
            ("7777", Rarity.MYTHIC),
            ("0000", Rarity.MYTHIC),
            ("1234", Rarity.MYTHIC),
            ("4321", Rarity.LEGENDARY),
            ("0007", Rarity.LEGENDARY),
            ("7770", Rarity.RARE),  # three sevens + a lucky composition
            ("4517", Rarity.COMMON),
        ],
    )
    def test_natural_rarity(self, number, rarity):
        assert analyze(number).rarity is rarity

    def test_rarity_order_is_total(self):
        assert rarity_rank("SECRET") > rarity_rank("MYTHIC") > rarity_rank("LEGENDARY")
        assert rarity_rank("EPIC") > rarity_rank("RARE") > rarity_rank("UNCOMMON") > rarity_rank("COMMON")

    def test_max_rarity_picks_the_higher(self):
        assert max_rarity("COMMON", "MYTHIC") is Rarity.MYTHIC
        assert max_rarity("RARE", "EPIC") is Rarity.EPIC
        assert max_rarity("EPIC", "EPIC") is Rarity.EPIC

    def test_weights_can_be_overridden(self):
        weights = load_rarity_weights('{"COMMON": 50, "SECRET": 50}')
        assert weights["COMMON"] == 50
        assert weights["SECRET"] == 50
        assert weights["MYTHIC"] == 0.0

    @pytest.mark.parametrize("bad", ['{"NOPE": 10}', "not-json", '{"COMMON": -5}', '{"COMMON": 0}'])
    def test_invalid_weight_override_rejected(self, bad):
        with pytest.raises(ValidationError):
            load_rarity_weights(bad)

    def test_default_weights_sum_to_100(self):
        assert sum(load_rarity_weights().values()) == pytest.approx(100.0)


class TestValuation:
    def test_value_is_deterministic(self):
        assert compute_value("EPIC", ["triple"], "7777", 0) == compute_value("EPIC", ["triple"], "7777", 0)

    def test_higher_rarity_is_never_cheaper(self):
        assert compute_value(Rarity.LEGENDARY, [], "4517", 0) > compute_value(Rarity.COMMON, [], "4517", 0)

    def test_traits_increase_value(self):
        plain = compute_value(Rarity.COMMON, [], "4517", 0)
        fancy = compute_value(Rarity.COMMON, ["palindrome", "sequence"], "4517", 0)
        assert fancy > plain

    def test_novelty_decays_with_discovery_count(self):
        fresh = compute_value(Rarity.EPIC, ["triple"], "7770", 0)
        heavily_found = compute_value(Rarity.EPIC, ["triple"], "7770", 5000)
        assert fresh > heavily_found
        assert novelty_multiplier(0) > novelty_multiplier(1000) == 1.0

    def test_duplicate_conversion_is_positive_and_smaller(self):
        value = compute_value(Rarity.RARE, [], "1230", 0)
        reward = duplicate_conversion_reward(value)
        assert 0 < reward < value

    def test_conversion_has_a_floor(self):
        assert duplicate_conversion_reward(1) >= 5


class TestStories:
    def test_special_numbers_have_curated_stories(self):
        assert "007" in build_story(analyze("0007"))
        assert "leetspeak" in build_story(analyze("1337"))
        assert "Four sevens" in build_story(analyze("7777"))
        assert "Perfect sequence" in build_story(analyze("1234"))

    def test_ordinary_number_still_has_a_story(self):
        story = build_story(analyze("4517"))
        assert isinstance(story, str) and story

    def test_story_is_short(self):
        for value in ("0000", "1337", "4517", "1221", "4321"):
            assert len(build_story(analyze(value))) <= 240
