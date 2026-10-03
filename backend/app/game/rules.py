"""Rule detectors used by the number analyzer.

Each rule is a pure predicate over the padded 4-digit string so behaviour is
trivially unit-testable and composable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

from app.game.constants import MIN_SEQUENCE_LENGTH_FOR_TRAIT

# Explicit internet-culture patterns kept in one place.
MEME_NUMBERS: frozenset[str] = frozenset({"1337", "8008", "0420", "1338", "6969", "9001", "1010"})
LUCKY_DIGITS: frozenset[str] = frozenset({"7", "8"})

Detector = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class Rule:
    """A named predicate over a number string."""

    code: str
    detector: Detector

    def matches(self, number: str) -> bool:
        return self.detector(number)


# --- helpers -----------------------------------------------------------
def longest_consecutive_run(number: str) -> int:
    """Longest run of adjacent digits where each differs from the previous by 1."""
    best = 1
    current = 1
    for previous, digit in pairwise(number):
        if int(digit) == int(previous) + 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def is_strictly_ascending(number: str) -> bool:
    return all(int(a) < int(b) for a, b in pairwise(number))


def is_strictly_descending(number: str) -> bool:
    return all(int(a) > int(b) for a, b in pairwise(number))


def digit_counts(number: str) -> Counter[str]:
    return Counter(number)


# --- detectors ---------------------------------------------------------
def _counts_and_shape(number: str) -> tuple[Counter[str], list[int]]:
    counts = digit_counts(number)
    return counts, sorted(counts.values(), reverse=True)


def detect_all_same(number: str) -> bool:
    return len(set(number)) == 1


detect_four_of_kind = detect_all_same


def detect_triple(number: str) -> bool:
    counts, _ = _counts_and_shape(number)
    return sorted(counts.values(), reverse=True)[0] == 3


def detect_two_pairs(number: str) -> bool:
    _, shape = _counts_and_shape(number)
    return shape == [2, 2]


def detect_pair(number: str) -> bool:
    _, shape = _counts_and_shape(number)
    return shape[0] == 2


def detect_palindrome(number: str) -> bool:
    return number == number[::-1]


def detect_repeated_pattern(number: str) -> bool:
    return number[:2] == number[2:]


def detect_contains_777(number: str) -> bool:
    return "777" in number


def detect_contains_666(number: str) -> bool:
    return "666" in number


def detect_contains_123(number: str) -> bool:
    return "123" in number


def detect_contains_000(number: str) -> bool:
    return "000" in number


def detect_round_number(number: str) -> bool:
    return number.endswith("00")


def detect_year_like(number: str) -> bool:
    """Looks like a calendar year (1000-2099)."""
    return 1000 <= int(number) <= 2099


def detect_lucky_pattern(number: str) -> bool:
    digits = set(number)
    if digits <= LUCKY_DIGITS and len(digits) > 0:
        return True
    return digit_counts(number)["7"] >= 2


def detect_meme_pattern(number: str) -> bool:
    return number in MEME_NUMBERS


def detect_low_number(number: str) -> bool:
    return int(number) < 100


def detect_sequence(number: str) -> bool:
    return longest_consecutive_run(number) >= MIN_SEQUENCE_LENGTH_FOR_TRAIT


ALL_RULES: tuple[Rule, ...] = (
    Rule("all_same", detect_all_same),
    Rule("four_of_kind", detect_four_of_kind),
    Rule("triple", detect_triple),
    Rule("two_pairs", detect_two_pairs),
    Rule("pair", detect_pair),
    Rule("ascending", is_strictly_ascending),
    Rule("descending", is_strictly_descending),
    Rule("palindrome", detect_palindrome),
    Rule("repeated_pattern", detect_repeated_pattern),
    Rule("contains_777", detect_contains_777),
    Rule("contains_666", detect_contains_666),
    Rule("contains_123", detect_contains_123),
    Rule("contains_000", detect_contains_000),
    Rule("round_number", detect_round_number),
    Rule("year_like", detect_year_like),
    Rule("lucky_pattern", detect_lucky_pattern),
    Rule("meme_pattern", detect_meme_pattern),
    Rule("low_number", detect_low_number),
    Rule("sequence", detect_sequence),
)
