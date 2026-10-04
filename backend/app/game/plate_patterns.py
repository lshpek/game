"""Plate pattern engine.

Detects number, letter and plate-level characteristics of a generated plate.
Everything is a pure function over the plate's own text, so a given plate always
produces exactly the same traits - which keeps rarity scoring deterministic and
replayable.

Trait *definitions* (label, score weight, rarity hint) live in
:mod:`app.game.plate_traits`; this module only implements detectors.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise

from app.game.phone_patterns import PHONE_TRAIT_WEIGHTS, detect_phone_traits

# Digit-run patterns that carry an extra "recognisable" bonus.
SPECIAL_NUMBER_RUNS: dict[str, str] = {
    "0001": "double_zero_one",
    "0007": "double_oh_seven",
    "1337": "leet",
    "2026": "year_like",
    "2027": "year_like",
    "2048": "power_of_two",
    "6969": "sixty_nine",
    "7777": "quad_seven",
    "8888": "quad_eight",
    "9999": "quad_nine",
    "420": "meme_pattern",
    "911": "nine_eleven",
    "8008": "boobies",
    "1234": "ascending_run",
    "4321": "descending_run",
}

LUCKY_DIGITS = frozenset("78")
MEME_RUNS = frozenset({"1337", "8008", "420", "6969", "911", "9119"})


def split_plate(text: str) -> tuple[list[str], list[str]]:
    """Split a rendered plate into (digit runs, letter runs)."""
    digits: list[str] = []
    letters: list[str] = []
    current_kind: str | None = None
    for char in text or "":
        if char.isdigit():
            kind = "digit"
        elif char.isalpha():
            kind = "letter"
        else:
            current_kind = None
            continue
        if kind == current_kind:
            (digits if kind == "digit" else letters)[-1] += char
        else:
            (digits if kind == "digit" else letters).append(char)
            current_kind = kind
    return digits, letters


def _digits_only(core: str) -> str:
    return "".join(ch for ch in core if ch.isdigit())


def _compact(core: str) -> str:
    return "".join(ch for ch in core if ch.isalnum())


def letter_signature(letters: list[str]) -> str:
    """Structural signature of the letters, e.g. ``ABBA`` -> ``ABBA``."""
    return "".join(letters)


@dataclass(slots=True)
class PlateAnalysis:
    """Deterministic analysis of one generated plate."""

    plate_text: str
    digits: list[str]
    letters: list[str]
    numeric_core: str
    traits: list[str]
    scores: dict[str, int]
    tags: list[str]
    letter_pattern: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def numbers(self) -> str:
        return self.numeric_core

    def to_dict(self) -> dict[str, object]:
        return {
            "plate_text": self.plate_text,
            "digits": self.digits,
            "letters": self.letters,
            "numbers": self.numeric_core,
            "traits": self.traits,
            "scores": self.scores,
            "tags": self.tags,
            "letter_pattern": self.letter_pattern,
        }


# --- numeric detectors -----------------------------------------------------
def detect_all_same(core: str) -> bool:
    digits = _digits_only(core)
    return len(digits) >= 3 and len(set(digits)) == 1


def detect_four_of_kind(core: str) -> bool:
    digits = _digits_only(core)
    return len(digits) >= 4 and len(set(digits)) == 1


def detect_triple(core: str) -> bool:
    counts = Counter(_digits_only(core)).values()
    return bool(counts) and max(counts) >= 3


def detect_pair(core: str) -> bool:
    counts = Counter(_digits_only(core)).values()
    return bool(counts) and max(counts) == 2


def detect_two_pairs(core: str) -> bool:
    counts = sorted(Counter(_digits_only(core)).values(), reverse=True)
    return counts[:2] == [2, 2]


def _longest_consecutive_run(digits: str) -> int:
    best = current = 1
    for a, b in pairwise(digits):
        if abs(int(b) - int(a)) == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def detect_ascending(core: str) -> bool:
    digits = _digits_only(core)
    return len(digits) >= 3 and all(int(b) > int(a) for a, b in pairwise(digits))


def detect_descending(core: str) -> bool:
    digits = _digits_only(core)
    return len(digits) >= 3 and all(int(b) < int(a) for a, b in pairwise(digits))


def detect_palindrome(core: str) -> bool:
    compact = _compact(core)
    return len(compact) >= 3 and compact == compact[::-1]


def detect_repeated_pattern(core: str) -> bool:
    compact = _compact(core)
    half = len(compact) // 2
    return len(compact) >= 4 and len(compact) % 2 == 0 and compact[:half] == compact[half:]


def detect_sequence(core: str) -> bool:
    return _longest_consecutive_run(_digits_only(core)) >= 3


def detect_contains_777(core: str) -> bool:
    return "777" in _digits_only(core)


def detect_contains_666(core: str) -> bool:
    return "666" in _digits_only(core)


def detect_contains_123(core: str) -> bool:
    return "123" in _digits_only(core)


def detect_contains_007(core: str) -> bool:
    return "007" in _digits_only(core)


def detect_contains_000(core: str) -> bool:
    return "000" in _digits_only(core)


def detect_leading_zeros(core: str) -> bool:
    digits = _digits_only(core)
    return len(digits) >= 3 and digits.startswith("0")


def detect_round_number(core: str) -> bool:
    digits = _digits_only(core)
    return digits.endswith("00") or digits.endswith("000")


def detect_year_like(core: str) -> bool:
    digits = _digits_only(core)
    windows = [digits[i : i + 4] for i in range(max(0, len(digits) - 3))]
    return any(len(w) == 4 and w.isdigit() and 1990 <= int(w) <= 2099 for w in windows)


def detect_lucky_pattern(core: str) -> bool:
    digits = _digits_only(core)
    if not digits:
        return False
    return set(digits) <= LUCKY_DIGITS or digits.count("7") >= 2


def detect_meme_pattern(core: str) -> bool:
    digits = _digits_only(core)
    return any(run in digits for run in MEME_RUNS)


def detect_special_run(core: str) -> bool:
    digits = _digits_only(core)
    return any(run in digits for run in SPECIAL_NUMBER_RUNS)


def detect_special_code(core: str) -> bool:
    digits = _digits_only(core)
    return any(digits.startswith(run) for run in SPECIAL_NUMBER_RUNS)


# --- letter detectors ------------------------------------------------------
def detect_triple_letter(letters: list[str]) -> bool:
    joined = "".join(letters)
    return bool(joined) and max(Counter(joined).values(), default=0) >= 3


def detect_pair_letter(letters: list[str]) -> bool:
    joined = "".join(letters)
    counts = Counter(joined).values()
    return bool(counts) and max(counts) >= 2


def detect_letter_palindrome(letters: list[str]) -> bool:
    joined = "".join(letters)
    return len(joined) >= 3 and joined == joined[::-1]


def detect_letter_ascending(letters: list[str]) -> bool:
    joined = "".join(letters)
    return len(joined) >= 3 and all(a < b for a, b in pairwise(joined))


def detect_repeated_letter_prefix(letters: list[str]) -> bool:
    return bool(letters) and len(letters[0]) >= 2 and len(set(letters[0])) == 1


def detect_repeated_letter_suffix(letters: list[str]) -> bool:
    return bool(letters) and len(letters[-1]) >= 2 and len(set(letters[-1])) == 1


def detect_mirrored_letters(letters: list[str]) -> bool:
    joined = "".join(letters)
    return len(joined) >= 4 and joined == joined[::-1]


def detect_alphabetical_run(letters: list[str]) -> bool:
    """Letters form a strictly ordered run, e.g. ABC or XYZ."""
    joined = "".join(letters)
    return len(joined) >= 3 and all(a < b for a, b in pairwise(joined))


# --- plate-level detectors -------------------------------------------------
def detect_region_match(plate_text: str, region_code: str | None) -> bool:
    """The region code repeats inside the plate body (e.g. region 77, plate 777)."""
    if not region_code:
        return False
    return region_code in _digits_only(plate_text)


def detect_number_mirrors_region(plate_text: str, region_code: str | None) -> bool:
    """The digit core is exactly the region code (or its reverse)."""
    if not region_code:
        return False
    digits = _digits_only(plate_text)
    return digits in (region_code, region_code[::-1])


def detect_symmetric_plate(plate_text: str) -> bool:
    compact = _compact(plate_text)
    return len(compact) >= 5 and compact == compact[::-1]


def detect_rare_template(rarity_floor: str) -> bool:
    return str(rarity_floor).upper() not in ("", "COMMON", "UNCOMMON")


def detect_same_number_and_letters(digits: list[str], letters: list[str]) -> bool:
    """A digit run and a letter run are internally identical (ABAB / 1212)."""
    return any(d.isalnum() and len(d) >= 2 and len(set(d)) == 1 for d in digits) and any(
        len(s) >= 2 and len(set(s)) == 1 for s in letters
    )


NUMERIC_DETECTORS: tuple[tuple[str, object], ...] = (
    ("all_same", detect_all_same),
    ("four_of_kind", detect_four_of_kind),
    ("triple", detect_triple),
    ("two_pairs", detect_two_pairs),
    ("pair", detect_pair),
    ("ascending", detect_ascending),
    ("descending", detect_descending),
    ("palindrome", detect_palindrome),
    ("repeated_pattern", detect_repeated_pattern),
    ("sequence", detect_sequence),
    ("contains_777", detect_contains_777),
    ("contains_666", detect_contains_666),
    ("contains_123", detect_contains_123),
    ("contains_007", detect_contains_007),
    ("contains_000", detect_contains_000),
    ("leading_zeros", detect_leading_zeros),
    ("round_number", detect_round_number),
    ("year_like", detect_year_like),
    ("lucky_pattern", detect_lucky_pattern),
    ("meme_pattern", detect_meme_pattern),
    ("special_run", detect_special_run),
    ("special_code", detect_special_code),
)

LETTER_DETECTORS: tuple[tuple[str, object], ...] = (
    ("triple_letter", detect_triple_letter),
    ("pair_letter", detect_pair_letter),
    ("letter_palindrome", detect_letter_palindrome),
    ("letter_ascending", detect_letter_ascending),
    ("alphabetical_run", detect_alphabetical_run),
    ("repeated_letter_prefix", detect_repeated_letter_prefix),
    ("repeated_letter_suffix", detect_repeated_letter_suffix),
    ("mirrored_letters", detect_mirrored_letters),
)

#: ``Plate.plate_type`` values that are judged purely on their digits. A synthetic
#: number printed on a SIM card has no letters to reward and no region to mirror, so
#: the vehicle detectors would call every one of them ordinary - which is how a 777
#: number used to come out as an unremarkable plate.
_DIGIT_JUDGED_TYPES: frozenset[str] = frozenset({"PHONE", "SIM"})


def build_tags(
    traits: list[str],
    *,
    country_tag: str,
    plate_type: str,
    is_secret: bool,
    season_code: str | None,
) -> list[str]:
    """Human-facing tags used by collection filters and album membership."""
    tags: list[str] = [country_tag]
    if {"palindrome", "symmetric_plate", "letter_palindrome", "mirrored_letters"} & set(traits):
        tags.append("mirror")
    if {"sequence", "ascending", "descending", "alphabetical_run", "letter_ascending"} & set(traits):
        tags.append("sequence")
    if {"lucky_pattern", "contains_777", "contains_666", "contains_123"} & set(traits):
        tags.append("lucky")
    if {"triple_repeat", "quad_repeat", "lucky_run", "repeated_digits"} & set(traits):
        tags.append("lucky")
    if {"low_entropy", "alternating"} & set(traits):
        tags.append("pattern")
    if "meme_pattern" in traits:
        tags.append("meme")
    if is_secret:
        tags.append("secret")
    if season_code:
        tags.append("seasonal")
    if plate_type in {"DIPLOMATIC_STYLE", "GOVERNMENT_STYLE", "SPECIAL", "HISTORICAL"}:
        tags.append("luxury")
    if plate_type in _DIGIT_JUDGED_TYPES:
        # Every synthetic collectible is tagged, so a player can filter the whole SIM
        # line out of a mixed collection.
        tags.append("sim")
        tags.append("synthetic")
    return sorted(set(tags))


def analyze_plate(
    plate_text: str,
    *,
    region_code: str | None = None,
    rarity_floor: str = "COMMON",
    plate_type: str = "STANDARD",
    country_tag: str = "",
    is_secret: bool = False,
    season_code: str | None = None,
) -> PlateAnalysis:
    """Run every detector over a plate and return its traits and scores."""
    from app.game.plate_traits import PLATE_TRAITS

    digits, letters = split_plate(plate_text)
    # The region code is context, not part of the serial. When the plate ends
    # with the region code we strip it from the core so ``A777AA 77`` is judged
    # on its serial 777 rather than on the combined 77777.
    numeric_core = "".join(digits)
    if (
        region_code
        and region_code.isdigit()
        and len(numeric_core) > len(region_code)
        and numeric_core.endswith(region_code)
    ):
        numeric_core = numeric_core[: -len(region_code)]
    scores: dict[str, int] = {}
    traits: list[str] = []

    def _record(code: str) -> None:
        trait = PLATE_TRAITS.get(code)
        if trait is None:
            return
        scores[code] = trait.score
        traits.append(code)

    for code, detector in NUMERIC_DETECTORS:
        if detector(numeric_core):  # type: ignore[operator]
            _record(code)

    for code, detector in LETTER_DETECTORS:
        if detector(letters):  # type: ignore[operator]
            _record(code)

    if detect_region_match(plate_text, region_code):
        _record("region_match")
    if detect_number_mirrors_region(plate_text, region_code):
        _record("number_mirrors_region")
    if detect_symmetric_plate(plate_text):
        _record("symmetric_plate")
    if detect_rare_template(rarity_floor):
        _record("rare_template")

    # SIM cards are judged on the digits printed on them. A synthetic number has no
    # letters worth rewarding and no region to mirror, so the vehicle detectors above
    # would report almost nothing for one - which is exactly how a 777 number used to
    # come out as an ordinary plate. These detectors read the digit structure
    # directly, so rarity is a property of the number itself.
    if plate_type in _DIGIT_JUDGED_TYPES:
        for code in detect_phone_traits(plate_text):
            if code not in scores:
                scores[code] = PHONE_TRAIT_WEIGHTS.get(code, 4)
                traits.append(code)

    # Order traits deterministically by score (desc) then code, so the strongest
    # reasons always come first for the result UI.
    traits.sort(key=lambda code: (-scores.get(code, 0), code))
    scores_dict = {code: scores[code] for code in traits}
    reasons = list(traits[:4])

    return PlateAnalysis(
        plate_text=plate_text,
        digits=digits,
        letters=letters,
        numeric_core=numeric_core,
        traits=traits,
        scores=scores_dict,
        tags=build_tags(
            traits,
            country_tag=country_tag,
            plate_type=plate_type,
            is_secret=is_secret,
            season_code=season_code,
        ),
        letter_pattern=letter_signature(letters),
        reasons=reasons,
    )


__all__ = [
    "LETTER_DETECTORS",
    "MEME_RUNS",
    "NUMERIC_DETECTORS",
    "SPECIAL_NUMBER_RUNS",
    "PlateAnalysis",
    "analyze_plate",
    "build_tags",
    "split_plate",
]
