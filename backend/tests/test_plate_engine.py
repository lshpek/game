"""Pattern Engine: deterministic, bounded, family-based, no double counting."""

from __future__ import annotations

import ast
import inspect
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from app.game import pattern_engine
from app.game.pattern_engine import analyze_pattern, compact_identifier, split_identifier

BACKEND_ROOT = Path(pattern_engine.__file__).resolve().parents[2]


def families(text: str, **kwargs) -> list[str]:
    return [pattern.family for pattern in analyze_pattern(text, **kwargs).detected_patterns]


def texts(text: str, family: str) -> list[str]:
    return [p.text for p in analyze_pattern(text).detected_patterns if p.family == family]


class TestDeterminism:
    def test_same_input_gives_identical_structured_result(self):
        first = analyze_pattern("A 777 AA 50", region_code="50")
        second = analyze_pattern("A 777 AA 50", region_code="50")
        assert first == second
        assert first.to_dict() == second.to_dict()

    def test_no_randomness_is_consulted(self):
        random.seed(1)
        before = analyze_pattern("AB 1221 CD").score
        random.seed(999)
        assert analyze_pattern("AB 1221 CD").score == before

    def test_separators_and_case_do_not_change_the_score(self):
        assert analyze_pattern("ab-123-cd").score == analyze_pattern("AB 123 CD").score
        assert compact_identifier("a b-1 2") == "AB12"

    def test_score_is_always_between_0_and_100(self):
        rng = random.Random(7)
        alphabet = "ABCEHKMOPTXY0123456789 -"
        for _ in range(5000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14)))
            assert 0 <= analyze_pattern(text).score <= 100

    def test_empty_identifier_is_a_zero(self):
        result = analyze_pattern("")
        assert result.score == 0
        assert result.detected_patterns == ()
        assert result.collector_tags == ()


class TestDetection:
    def test_triple(self):
        result = analyze_pattern("A 777 BC")
        assert texts("A 777 BC", "repeat") == ["777"]
        assert "TRIPLE" in result.collector_tags

    def test_double_and_repeated_runs(self):
        assert "DOUBLE" in analyze_pattern("K 482 TM 66").collector_tags
        assert "REPEATED" in analyze_pattern("A 7777 BC").collector_tags

    @pytest.mark.parametrize("text", ["1234", "4321", "ABC", "CBA"])
    def test_sequences_in_both_directions(self, text):
        assert "sequence" in families(text)
        assert "SEQUENCE" in analyze_pattern(text).collector_tags

    def test_descending_flag(self):
        pattern = analyze_pattern("4321").detected_patterns[0]
        assert pattern.descending is True
        assert analyze_pattern("1234").detected_patterns[0].descending is False

    @pytest.mark.parametrize("text", ["1221", "ABBA", "12321", "AA11AA"])
    def test_palindromes(self, text):
        result = analyze_pattern(text)
        assert "mirror" in families(text)
        assert "PALINDROME" in result.collector_tags

    @pytest.mark.parametrize("text", ["1212", "ABAB", "123123"])
    def test_repeated_blocks(self, text):
        assert "block" in families(text)
        assert "REPEATED" in analyze_pattern(text).collector_tags

    def test_letter_patterns_are_detected(self):
        assert texts("AAA 12", "repeat") == ["AAA"]
        assert analyze_pattern("AB 123 BA").detected_patterns

    def test_multiple_simultaneous_patterns(self):
        result = analyze_pattern("A 123 BC 77")
        assert {"sequence", "repeat"} <= set(families("A 123 BC 77"))
        assert len(result.detected_patterns) >= 2

    def test_a_plain_combination_has_no_patterns(self):
        result = analyze_pattern("B 905 XT 163")
        assert result.score == 0
        assert result.detected_patterns == ()

    def test_regional_tag_for_a_patterned_region_only(self):
        assert "REGIONAL" in analyze_pattern("A 123 BC 77", region_code="77").collector_tags
        assert "REGIONAL" not in analyze_pattern("A 123 BC 52", region_code="52").collector_tags


class TestNoDoubleCounting:
    def test_triple_is_one_pattern_not_five(self):
        result = analyze_pattern("A 777 BC")
        assert [p.family for p in result.detected_patterns] == ["repeat"]
        assert result.score == 20

    def test_triple_wrapped_by_one_equal_layer_is_not_a_mirror(self):
        assert "mirror" not in families("A 777 AA 50")
        assert analyze_pattern("A 777 AA 50").score == 25

    def test_pure_repeat_is_not_also_a_palindrome_or_block(self):
        assert families("77 7777 77") == ["repeat"]

    def test_nested_pattern_is_discounted_inside_a_mirror(self):
        result = analyze_pattern("1221")
        mirror = next(p for p in result.detected_patterns if p.family == "mirror")
        double = next(p for p in result.detected_patterns if p.family == "repeat")
        assert mirror.weight == 1.0
        assert double.weight < 1.0
        assert result.score < mirror.points + double.points

    def test_a_family_cannot_claim_overlapping_spans_twice(self):
        runs = [p for p in analyze_pattern("12345").detected_patterns if p.family == "sequence"]
        assert len(runs) == 1
        assert runs[0].text == "12345"

    def test_ordinary_plates_score_low(self):
        rng = random.Random(11)
        scores = []
        for _ in range(3000):
            digits = "".join(rng.choice("0123456789") for _ in range(3))
            letters = "".join(rng.choice("ABCEHKMOPTXY") for _ in range(2))
            scores.append(analyze_pattern(f"{digits[0]}{letters[0]}{digits[1:]}{letters[1]}").score)
        assert sum(scores) / len(scores) < 12
        assert sum(1 for score in scores if score >= 50) / len(scores) < 0.01


class TestScoreOrdering:
    def test_stronger_patterns_score_higher(self):
        double = analyze_pattern("A 188 BC").score
        triple = analyze_pattern("A 888 BC").score
        quad = analyze_pattern("A 8888 BC").score
        assert 0 < double < triple < quad

    def test_adding_an_independent_pattern_raises_the_score(self):
        assert analyze_pattern("A 777 BC 12").score < analyze_pattern("A 777 BB 12").score

    def test_a_single_repeated_character_is_the_perfect_score(self):
        assert analyze_pattern("777777").score == 100
        assert analyze_pattern("AAAAAA").score == 100

    def test_an_exceptional_combination_approaches_100(self):
        assert analyze_pattern("7777 AAAA 77").score >= 60
        assert analyze_pattern("777777 AAAAAA").score >= 85


class TestStructuredOutput:
    def test_result_exposes_the_documented_fields(self):
        data = analyze_pattern("A 777 AA 50", region_code="50").to_dict()
        assert set(data) >= {"score", "detected_patterns", "collector_tags", "explanation", "lore"}
        assert set(data["lore"]) == {
            "title",
            "short_description",
            "real_world_context",
            "patterns",
            "collector_tags",
        }

    def test_explanation_is_deterministic_and_names_the_lead_pattern(self):
        result = analyze_pattern("A 777 BC")
        assert "777" in result.explanation
        assert result.explanation == analyze_pattern("A 777 BC").explanation

    def test_tags_are_concise(self):
        assert len(analyze_pattern("77AAAA77").collector_tags) <= 4

    def test_real_world_context_is_never_invented(self):
        assert analyze_pattern("A 777 BC").to_dict()["lore"]["real_world_context"] == ""


class TestAllowedCharacters:
    """Only ASCII letters and digits are read; nothing is guessed from other scripts."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ab-12 cd", "AB12CD"),
            ("١٢٣٤", ""),  # Arabic-Indic digits are not str.isdigit()-safe here
            ("12３４", "12"),  # full-width digits
            ("ß", ""),  # str.upper() would turn this into "SS"
            ("ı", ""),  # str.upper() would turn this into "I"
            ("А777АА", "777"),  # Cyrillic letters are not Latin look-alikes
            ("AB–12", "AB12"),  # a non-ASCII dash is just a separator
            ("", ""),
        ],
    )
    def test_compaction_keeps_only_ascii_letters_and_digits(self, raw, expected):
        assert compact_identifier(raw) == expected
        assert compact_identifier(raw).isascii()

    def test_an_unreadable_letter_closes_the_run_instead_of_gluing_neighbours(self):
        assert split_identifier("К7 Х 7") == ["7", "7"]
        assert split_identifier("12-34") == ["1234"]
        assert analyze_pattern("К7 Х 7").detected_patterns == ()
        assert analyze_pattern("К7 Х 7").score == 0

    def test_ascii_separators_keep_adjacency_on_purpose(self):
        assert [p.text for p in analyze_pattern("AB-12-34").detected_patterns] == ["1234"]

    def test_cyrillic_plate_letters_do_not_break_digit_analysis(self):
        result = analyze_pattern("А 777 АА 50")
        assert [p.text for p in result.detected_patterns] == ["777"]
        assert result.score == analyze_pattern("777 50").score == 20

    def test_a_mirror_cannot_span_an_unreadable_letter_or_earn_the_whole_bonus(self):
        assert analyze_pattern("Х1221Х").score < analyze_pattern("1221").score
        assert [p.text for p in analyze_pattern("1Ж1").detected_patterns] == []

    def test_unreadable_characters_never_make_an_identifier_perfect(self):
        assert analyze_pattern("ß77ß").score < 100
        assert analyze_pattern("Ж 7777").score < 100

    def test_arbitrary_unicode_never_raises(self):
        rng = random.Random(3)
        alphabet = "ABK17 -АКх١ß٣３ı🙂\u00a0"
        for _ in range(3000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
            result = analyze_pattern(text, region_code=text[:3])
            assert 0 <= result.score <= 100
            assert compact_identifier(text).isascii()


class TestPerfectRepeat:
    @pytest.mark.parametrize("text", ["77", "777", "AA", "7777", "AAAAAA", "7-7", "a a a", "99 99 99"])
    def test_a_fully_repeated_identifier_scores_100_at_any_length(self, text):
        result = analyze_pattern(text)
        assert result.score == 100
        assert [p.family for p in result.detected_patterns] == ["repeat"]

    @pytest.mark.parametrize("text", ["7", "A", "", "77A", "A77", "7A7", "7 A"])
    def test_anything_else_is_not_perfect(self, text):
        assert analyze_pattern(text).score < 100

    def test_the_perfect_case_has_no_minimum_length_other_than_a_repeat(self):
        assert not hasattr(pattern_engine, "MIN_PERFECT")
        assert analyze_pattern("77").score == analyze_pattern("7" * 12).score == 100


class TestOverlapResolution:
    def test_containment_in_either_direction_is_one_underlying_pattern(self):
        # "12121" (mirror) sits inside "121212" (block): the same alternation.
        result = analyze_pattern("121212")
        weights = {p.family: p.weight for p in result.detected_patterns}
        assert set(weights) == {"mirror", "block"}
        assert sorted(weights.values()) == [pattern_engine.NESTED_WEIGHT, 1.0]
        mirror = next(p for p in result.detected_patterns if p.family == "mirror")
        block = next(p for p in result.detected_patterns if p.family == "block")
        assert result.score < mirror.points + block.points
        assert result.score < 100 * (1 - (1 - mirror.points / 100) * (1 - block.points / 100))

    def test_invariants_hold_for_every_resolved_result(self):
        rng = random.Random(21)
        alphabet = "ABCEHKMOPTXY0123456789 -"
        for _ in range(4000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(2, 12)))
            patterns = analyze_pattern(text).detected_patterns
            for index, first in enumerate(patterns):
                assert first.weight in (1.0, pattern_engine.PARTIAL_WEIGHT, pattern_engine.NESTED_WEIGHT)
                for second in patterns[index + 1 :]:
                    overlap = first.start < second.end and second.start < first.end
                    if first.family == second.family:
                        assert not overlap, text
                    if overlap:
                        assert min(first.weight, second.weight) < 1.0, text

    def test_per_family_cap_is_respected(self):
        patterns = analyze_pattern("11 22 33 44 55").detected_patterns
        assert sum(1 for p in patterns if p.family == "repeat") <= pattern_engine.MAX_PER_FAMILY

    def test_result_does_not_depend_on_hash_seed_or_run(self):
        corpus = ["A 777 AA 50", "121212", "AA11AA", "77AAAA77", "+372 5123 4567", "AB-121-BA", "К7 Х 7", "12３４"]
        script = (
            "import json,sys\n"
            "from app.game.pattern_engine import analyze_pattern\n"
            "print(json.dumps([analyze_pattern(t, region_code='77').to_dict() for t in json.loads(sys.argv[1])],"
            " sort_keys=True))"
        )
        outputs = set()
        for seed in ("0", "1", "4242"):
            run = subprocess.run(
                [sys.executable, "-c", script, json.dumps(corpus)],
                cwd=BACKEND_ROOT,
                env={"PYTHONHASHSEED": seed, "PYTHONPATH": str(BACKEND_ROOT), "PATH": ""},
                capture_output=True,
                text=True,
                check=True,
            )
            outputs.add(run.stdout)
        assert len(outputs) == 1


class TestRegionIsDescriptiveOnly:
    IDENTIFIERS = ["A 777 AA 50", "A 123 BC 77", "77AAAA77", "AA11AA", "B 905 XT 163", "121212", "777777", "К7 Х 7"]
    REGIONS = [None, "", "50", "77", "11", "123", "121", "163", "AB", "ВС", "999"]

    def test_region_never_changes_score_or_patterns(self):
        for identifier in self.IDENTIFIERS:
            baseline = analyze_pattern(identifier)
            for region in self.REGIONS:
                with_region = analyze_pattern(identifier, region_code=region)
                assert with_region.score == baseline.score, (identifier, region)
                assert with_region.detected_patterns == baseline.detected_patterns
                assert with_region.explanation == baseline.explanation

    def test_region_may_only_add_the_regional_tag(self):
        for identifier in self.IDENTIFIERS:
            baseline = set(analyze_pattern(identifier).collector_tags)
            for region in self.REGIONS:
                extra = set(analyze_pattern(identifier, region_code=region).collector_tags) - baseline
                assert extra <= {"REGIONAL"}, (identifier, region)

    def test_regional_tag_survives_a_full_tag_list(self):
        tags = analyze_pattern("77AAAA77", region_code="77").collector_tags
        assert "REGIONAL" in tags
        assert len(tags) <= pattern_engine.MAX_TAGS

    @pytest.mark.parametrize("region", ["77", "11", "121", "123"])
    def test_patterned_regions_are_tagged(self, region):
        assert "REGIONAL" in analyze_pattern("A 905 XT", region_code=region).collector_tags

    @pytest.mark.parametrize("region", ["50", "52", "163", "", None])
    def test_ordinary_regions_are_not_tagged(self, region):
        assert "REGIONAL" not in analyze_pattern("A 777 XT", region_code=region).collector_tags


class TestRarityIsIndependent:
    def test_the_engine_imports_nothing_about_rarity(self):
        tree = ast.parse(inspect.getsource(pattern_engine))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not [name for name in imported if "rarity" in name.lower()]
        assert not [name for name in imported if name.startswith("app.")]

    def test_the_api_takes_no_rarity_input(self):
        assert set(inspect.signature(analyze_pattern).parameters) == {"text", "region_code"}

    def test_the_result_carries_no_rarity(self):
        result = analyze_pattern("A 777 AA 50", region_code="50")
        assert not [name for name in dir(result) if "rarity" in name.lower()]
        assert "rarity" not in json.dumps(result.to_dict()).lower().replace("repeat", "")

    def test_the_score_is_a_pure_function_of_the_identifier(self):
        assert analyze_pattern("A 777 AA 50").score == analyze_pattern("A 777 AA 50").score


class TestMixedPlateAndSimIdentifiers:
    def test_georgian_style_plate_with_a_mirror(self):
        result = analyze_pattern("AB-121-BA")
        assert "PALINDROME" in result.collector_tags
        assert "SYMMETRIC" in result.collector_tags

    def test_german_style_plate_mirror_in_the_number(self):
        result = analyze_pattern("M-AB 1221")
        assert [p.text for p in result.detected_patterns if p.family == "mirror"] == ["1221"]
        assert result.score < analyze_pattern("1221").score  # no whole-identifier bonus

    def test_sim_with_calling_code_and_grouped_subscriber_digits(self):
        result = analyze_pattern("+372 5123 4567")
        assert [p.text for p in result.detected_patterns if p.family == "sequence"] == ["1234567"]
        assert "SEQUENCE" in result.collector_tags

    def test_sim_long_repeat_run_is_a_single_pattern(self):
        result = analyze_pattern("+1 555 555 5555")
        assert [(p.family, p.text) for p in result.detected_patterns] == [("repeat", "5555555555")]
        assert result.score == 80

    def test_sim_plain_number_scores_zero(self):
        assert analyze_pattern("+49 7931 468205").score == 0

    def test_plate_and_sim_share_one_scoring_scale(self):
        plate = analyze_pattern("A 777 BC")
        sim = analyze_pattern("+372 777 4915")
        assert [p.text for p in sim.detected_patterns] == ["777"]
        assert plate.score == sim.score == 20
