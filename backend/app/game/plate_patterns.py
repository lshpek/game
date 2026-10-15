"""Pattern Engine - deterministic collector metadata for plates and SIM cards.

The engine reads the *complete visible identifier* and answers one question:
"how collectible does this combination look?". The answer is a **Pattern Score**
(0-100) plus structured details. It is purely descriptive:

* it is deterministic - the same text always yields the same result, no RNG;
* it never feeds back into rarity (rarity is rolled independently);
* the generator never steers towards it - patterns occur naturally.

Model
-----
The identifier is flattened into ``compact`` (ASCII letters and digits, separators
dropped). A non-ASCII letter or digit is not guessed at: it becomes a *boundary*, so
no pattern is ever invented across a character the engine cannot read. Detectors propose *candidates*, each belonging to one **family**:

``repeat``    runs of one character (``77``, ``777``, ``AAAA``)
``sequence``  +1/-1 runs inside one character class (``1234``, ``4321``, ``ABC``)
``mirror``    palindromes that are not plain repeats (``1221``, ``ABBA``, ``AB1BA``)
``block``     a block written twice or more (``1212``, ``ABAB``, ``123123``)

Candidates are resolved so one underlying pattern is never paid twice:

* inside a family only the strongest ``MAX_PER_FAMILY`` candidates survive;
* a candidate that overlaps an accepted one of the *same* family is dropped;
* a candidate nested inside an accepted span of another family - or containing one -
  keeps only ``NESTED_WEIGHT`` of its points (``22`` inside ``1221`` is part of the
  mirror; a block that wraps a mirror is the same alternation);
* a partial overlap keeps ``PARTIAL_WEIGHT``.

Independent patterns combine with a saturating formula
``100 * (1 - prod(1 - weighted_points / 100))``, so the score is bounded by 100,
grows with every additional independent pattern, and a plain plate stays low.
A compact identifier made of one repeated character (two or more of it, nothing
else) is the perfect case: 100.

``region_code`` is descriptive only: it may add the ``REGIONAL`` tag and never
touches the score.
"""

from __future__ import annotations

import string
from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise

from app.game.phone_patterns import PHONE_TRAIT_WEIGHTS, detect_phone_traits

# Digit-run patterns that carry an extra "recognisable" bonus. Feeds the
# ``special_run`` / ``special_code`` traits, which are rarity inputs.
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

# --- tuning -------------------------------------------------------------------
#: The only characters the engine reads: ASCII letters and digits. Anything else
#: is either a separator (dropped, adjacency kept) or a *boundary* (see
#: :func:`split_identifier`).
ALLOWED_CHARACTERS = frozenset(string.ascii_uppercase + string.digits)

MIN_REPEAT = 2
MIN_SEQUENCE = 3
MIN_MIRROR = 4
MIN_BLOCK_TOTAL = 4
MAX_PER_FAMILY = 2
NESTED_WEIGHT = 0.35
PARTIAL_WEIGHT = 0.6
WHOLE_MIRROR_BONUS = 8
MAX_TAGS = 4

_REPEAT_POINTS = {2: 6, 3: 20, 4: 36, 5: 50, 6: 62, 7: 72}
_REPEAT_POINTS_MAX = 80  # 8 or more
_SEQUENCE_POINTS = {3: 12, 4: 24, 5: 36, 6: 48, 7: 58}
_SEQUENCE_POINTS_MAX = 68  # 8 or more
_MIRROR_POINTS = {4: 20, 5: 26, 6: 34, 7: 40, 8: 50}
_MIRROR_POINTS_MAX = 58  # 9 or more
_BLOCK_POINTS = {4: 14, 5: 18, 6: 24, 7: 28, 8: 34, 9: 38}
_BLOCK_POINTS_MAX = 44  # 10 or more

FAMILIES = ("repeat", "sequence", "mirror", "block")

TAG_DOUBLE = "DOUBLE"
TAG_TRIPLE = "TRIPLE"
TAG_REPEATED = "REPEATED"
TAG_SEQUENCE = "SEQUENCE"
TAG_PALINDROME = "PALINDROME"
TAG_SYMMETRIC = "SYMMETRIC"
TAG_REGIONAL = "REGIONAL"


@dataclass(frozen=True, slots=True)
class DetectedPattern:
    """One accepted pattern: where it sits and what it is worth."""

    family: str
    text: str
    start: int
    end: int
    charset: str  # "digit", "letter" or "mixed"
    points: int  # raw points before overlap weighting
    weight: float  # 1.0 for an independent pattern, lower when it overlaps another
    descending: bool = False

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def contribution(self) -> float:
        return self.points * self.weight

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "text": self.text,
            "charset": self.charset,
            "length": self.length,
            "points": self.points,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class PatternResult:
    """Structured, deterministic outcome of one analysis."""

    identifier: str
    score: int
    detected_patterns: tuple[DetectedPattern, ...]
    collector_tags: tuple[str, ...]
    explanation: str
    title: str
    short_description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "identifier": self.identifier,
            "score": self.score,
            "detected_patterns": [pattern.to_dict() for pattern in self.detected_patterns],
            "collector_tags": list(self.collector_tags),
            "explanation": self.explanation,
            "lore": {
                "title": self.title,
                "short_description": self.short_description,
                "real_world_context": "",
                "patterns": [pattern.family for pattern in self.detected_patterns],
                "collector_tags": list(self.collector_tags),
            },
        }


@dataclass(frozen=True, slots=True)
class _Candidate:
    family: str
    start: int
    end: int
    points: int
    descending: bool = False


def _scan(text: str) -> tuple[list[str], bool]:
    """Runs of readable characters, and whether any unreadable letter/digit was seen."""
    runs: list[str] = []
    current: list[str] = []
    unreadable = False
    for character in text or "":
        upper = character.upper() if character.isascii() else ""
        if upper in ALLOWED_CHARACTERS:
            current.append(upper)
        elif not character.isascii() and character.isalnum():
            unreadable = True
            if current:
                runs.append("".join(current))
                current = []
    if current:
        runs.append("".join(current))
    return runs, unreadable


def split_identifier(text: str) -> list[str]:
    """Split an identifier into runs of readable characters.

    Only ASCII letters and digits are kept (upper-cased). ASCII separators, spaces
    and punctuation are dropped, so ``12-34`` still reads as ``1234``. A non-ASCII
    letter or digit (a Cyrillic plate letter, Thai script, ...) is *not* silently
    deleted - that would glue its neighbours together and invent a pair such as the
    ``77`` in ``К7 Х 7`` - it closes the current run instead. Other non-ASCII
    symbols (dashes, no-break spaces) behave like separators.

    ``str.isalnum`` is deliberately avoided for the ASCII test: it accepts
    arbitrary Unicode letters and digits.
    """
    return _scan(text)[0]


def compact_identifier(text: str) -> str:
    """The readable characters of ``text``: ASCII letters and digits, upper-cased."""
    return "".join(split_identifier(text))


def _charset(value: str) -> str:
    if value.isascii() and value.isdigit():
        return "digit"
    if value.isascii() and value.isalpha():
        return "letter"
    return "mixed"


def _table_points(table: dict[int, int], ceiling: int, length: int) -> int:
    if length in table:
        return table[length]
    return ceiling if length > max(table) else 0


# --- detectors ----------------------------------------------------------------
def _detect_repeats(compact: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    index = 0
    while index < len(compact):
        end = index
        while end + 1 < len(compact) and compact[end + 1] == compact[index]:
            end += 1
        length = end - index + 1
        if length >= MIN_REPEAT:
            points = _table_points(_REPEAT_POINTS, _REPEAT_POINTS_MAX, length)
            found.append(_Candidate("repeat", index, end + 1, points))
        index = end + 1
    return found


def _detect_sequences(compact: str) -> list[_Candidate]:
    found: list[_Candidate] = []
    index = 0
    while index < len(compact) - 1:
        step = _step(compact[index], compact[index + 1])
        if step == 0:
            index += 1
            continue
        end = index + 1
        while end + 1 < len(compact) and _step(compact[end], compact[end + 1]) == step:
            end += 1
        length = end - index + 1
        if length >= MIN_SEQUENCE:
            points = _table_points(_SEQUENCE_POINTS, _SEQUENCE_POINTS_MAX, length)
            found.append(_Candidate("sequence", index, end + 1, points, descending=step < 0))
        index = end
    return found


def _step(left: str, right: str) -> int:
    """+1 or -1 when ``right`` follows ``left`` inside one character class, else 0."""
    if left in string.digits and right in string.digits:
        delta = int(right) - int(left)
    elif left in string.ascii_uppercase and right in string.ascii_uppercase:
        delta = ord(right) - ord(left)
    else:
        return 0
    return delta if delta in (-1, 1) else 0


def _is_real_mirror(compact: str, start: int, end: int) -> bool:
    """Reject accidental symmetry: a triple (or longer run) wrapped by one layer.

    ``A777A`` is just a triple with an equal character on each side, not a mirror
    anyone would collect, and counting it would also demote the real triple.
    A long central run needs at least two symmetric layers around it.
    """
    middle = (start + end - 1) // 2
    run_start = middle
    while run_start > start and compact[run_start - 1] == compact[middle]:
        run_start -= 1
    run_end = middle + 1
    while run_end < end and compact[run_end] == compact[middle]:
        run_end += 1
    centre_run = run_end - run_start
    layers = ((end - start) - centre_run) // 2
    return centre_run <= 2 or layers >= 2


def _detect_mirrors(compact: str, *, whole_identifier: bool) -> list[_Candidate]:
    """Maximal palindromes of length >= 4 that are not a plain repeat."""
    spans: set[tuple[int, int]] = set()
    size = len(compact)
    for center in range(size):
        for left, right in ((center, center), (center, center + 1)):
            while left >= 0 and right < size and compact[left] == compact[right]:
                left -= 1
                right += 1
            start, end = left + 1, right
            if end - start >= MIN_MIRROR and len(set(compact[start:end])) > 1 and _is_real_mirror(compact, start, end):
                spans.add((start, end))
    maximal = [
        span
        for span in spans
        if not any(other != span and other[0] <= span[0] and span[1] <= other[1] for other in spans)
    ]
    found: list[_Candidate] = []
    for start, end in sorted(maximal):
        points = _table_points(_MIRROR_POINTS, _MIRROR_POINTS_MAX, end - start)
        if whole_identifier and start == 0 and end == size:
            points = min(100, points + WHOLE_MIRROR_BONUS)
        found.append(_Candidate("mirror", start, end, points))
    return found


def _detect_blocks(compact: str) -> list[_Candidate]:
    """A block of >= 2 distinct characters written at least twice in a row."""
    best: dict[int, _Candidate] = {}
    size = len(compact)
    for start in range(size):
        for block_len in range(2, (size - start) // 2 + 1):
            block = compact[start : start + block_len]
            if len(set(block)) == 1:
                continue
            copies = 1
            while compact[start + copies * block_len : start + (copies + 1) * block_len] == block:
                copies += 1
            total = copies * block_len
            if copies >= 2 and total >= MIN_BLOCK_TOTAL:
                points = _table_points(_BLOCK_POINTS, _BLOCK_POINTS_MAX, total)
                current = best.get(start)
                if current is None or total > current.end - current.start:
                    best[start] = _Candidate("block", start, start + total, points)
    return [best[start] for start in sorted(best)]


# --- resolution ---------------------------------------------------------------
def _overlap(a: _Candidate, b: _Candidate) -> bool:
    return a.start < b.end and b.start < a.end


def _nested_in(inner: _Candidate, outer: _Candidate) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


def _resolve(compact: str, candidates: list[_Candidate]) -> list[DetectedPattern]:
    ordered = sorted(candidates, key=lambda c: (-c.points, c.start, -(c.end - c.start), c.family))
    accepted: list[tuple[_Candidate, float]] = []
    per_family: dict[str, int] = dict.fromkeys(FAMILIES, 0)
    for candidate in ordered:
        if per_family[candidate.family] >= MAX_PER_FAMILY:
            continue
        weight = 1.0
        rejected = False
        for other, _ in accepted:
            if not _overlap(candidate, other):
                continue
            if candidate.family == other.family:
                rejected = True
                break
            nested = _nested_in(candidate, other) or _nested_in(other, candidate)
            weight = min(weight, NESTED_WEIGHT if nested else PARTIAL_WEIGHT)
        if rejected:
            continue
        accepted.append((candidate, weight))
        per_family[candidate.family] += 1
    accepted.sort(key=lambda item: (item[0].start, item[0].end, item[0].family))
    return [
        DetectedPattern(
            family=candidate.family,
            text=compact[candidate.start : candidate.end],
            start=candidate.start,
            end=candidate.end,
            charset=_charset(compact[candidate.start : candidate.end]),
            points=candidate.points,
            weight=weight,
            descending=candidate.descending,
        )
        for candidate, weight in accepted
    ]


def _combine(patterns: list[DetectedPattern]) -> int:
    remaining = 1.0
    for pattern in patterns:
        remaining *= 1.0 - min(100.0, pattern.contribution) / 100.0
    return max(0, min(100, round(100.0 * (1.0 - remaining))))


# --- tags and wording -----------------------------------------------------------
def _tags(patterns: list[DetectedPattern], compact: str, region_code: str | None) -> tuple[str, ...]:
    ranked = sorted(patterns, key=lambda p: (-p.contribution, p.start))
    tags: list[str] = []

    def add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    for pattern in ranked:
        if pattern.family == "repeat":
            add(TAG_DOUBLE if pattern.length == 2 else TAG_TRIPLE if pattern.length == 3 else TAG_REPEATED)
        elif pattern.family == "sequence":
            add(TAG_SEQUENCE)
        elif pattern.family == "mirror":
            add(TAG_PALINDROME)
            if pattern.length >= 5 or pattern.length == len(compact):
                add(TAG_SYMMETRIC)
        elif pattern.family == "block":
            add(TAG_REPEATED)
    region = compact_identifier(region_code or "")
    if len(region) >= 2 and _is_pattern_text(region):
        tags = tags[: MAX_TAGS - 1]
        add(TAG_REGIONAL)
    return tuple(tags[:MAX_TAGS])


def _is_pattern_text(value: str) -> bool:
    """A region written as a double/triple, a run or a palindrome (``77``, ``121``, ``123``)."""
    if len(set(value)) == 1:
        return True
    if len(value) >= 3 and value == value[::-1]:
        return True
    return len(value) >= 3 and all(_step(a, b) == _step(value[0], value[1]) != 0 for a, b in pairwise(value))


_REPEAT_NAMES = {2: "Double", 3: "Triple", 4: "Quadruple"}
_KIND_NOUN = {"digit": "number", "letter": "letter", "mixed": "character"}


def _describe(pattern: DetectedPattern) -> str:
    noun = _KIND_NOUN[pattern.charset]
    if pattern.family == "repeat":
        name = _REPEAT_NAMES.get(pattern.length, f"{pattern.length}x repeated")
        return f"{name} {pattern.text} - a clean repeating-{noun} pattern."
    if pattern.family == "sequence":
        direction = "descending" if pattern.descending else "ascending"
        return f"{pattern.text} - an {direction} {noun} sequence."
    if pattern.family == "mirror":
        return f"{pattern.text} - a palindrome with strong visual symmetry."
    return f"{pattern.text} - a repeating block."


def _wording(patterns: list[DetectedPattern], score: int) -> tuple[str, str, str]:
    if not patterns:
        return ("", "No standout pattern.", "A plain combination without a notable pattern.")
    lead = max(patterns, key=lambda p: (p.contribution, -p.start))
    lead_text = _describe(lead)
    title = lead_text.split(" - ")[0]
    others = [p for p in patterns if p is not lead]
    extra = f" Also: {', '.join(p.text for p in others)}." if others else ""
    return (lead_text + extra, title, lead_text)


# --- public API -----------------------------------------------------------------
def analyze_pattern(text: str, *, region_code: str | None = None) -> PatternResult:
    """Analyse one visible identifier. Pure and deterministic.

    ``region_code`` is descriptive: it can only add the ``REGIONAL`` tag. It is never
    read by the detectors or the score, so two identifiers that differ only in their
    region code always score the same.
    """
    runs, unreadable = _scan(text)
    compact = "".join(runs)
    if not compact:
        return PatternResult(text or "", 0, (), (), "No standout pattern.", "", "")

    if not unreadable and len(runs) == 1 and len(compact) >= MIN_REPEAT and len(set(compact)) == 1:
        # The whole identifier is one repeated character: nothing else to weigh.
        perfect = DetectedPattern("repeat", compact, 0, len(compact), _charset(compact), 100, 1.0)
        patterns = [perfect]
        score = 100
    else:
        candidates: list[_Candidate] = []
        offset = 0
        for run in runs:
            found = (
                _detect_repeats(run)
                + _detect_sequences(run)
                + _detect_mirrors(run, whole_identifier=len(runs) == 1 and not unreadable)
                + _detect_blocks(run)
            )
            candidates.extend(
                _Candidate(c.family, c.start + offset, c.end + offset, c.points, c.descending)
                for c in found
            )
            offset += len(run)
        patterns = _resolve(compact, candidates)
        score = _combine(patterns)

    explanation, title, short = _wording(patterns, score)
    return PatternResult(
        identifier=text,
        score=score,
        detected_patterns=tuple(patterns),
        collector_tags=_tags(patterns, compact, region_code),
        explanation=explanation,
        title=title,
        short_description=short,
    )


# =============================================================================
# Compatibility adapter: the trait/detector contract the rest of the game reads
# =============================================================================
#
# Commit 2ef42b2 replaced the *trait* engine in this file with the deterministic
# Pattern Engine above (PatternResult / analyze_pattern) but left every consumer
# - rarity, valuation, generation, status/lore, admin tools - importing
# PlateAnalysis and analyze_plate. This section restores that contract:
#
# * analyze_plate runs the original trait detectors. Trait codes are the input
#   to app.game.plate_rarity.compute_rarity_score and to the value multipliers,
#   so keeping them identical keeps every score, tier and price exactly as it
#   was before the Pattern Engine landed.
# * PatternResult is attached read-only as PlateAnalysis.pattern: descriptive
#   metadata (Pattern Score, lore) for tools. Neither the rarity resolver nor
#   the valuation reads it, so pattern scoring cannot move a tier or a price.
#
# The Pattern Engine keeps its own contract (analyze_pattern(text, *,
# region_code)) and is not re-exported from here.
# -----------------------------------------------------------------------------


def split_plate(text: str) -> tuple[list[str], list[str]]:
    """Split a rendered plate into ``(digit runs, letter runs)``.

    Runs are maximal and in reading order: ``"A777AA 77"`` gives the digits
    ``["777", "77"]`` and the letters ``["A", "AA"]``. Separators reset a run and
    non-ASCII letters/digits are kept, so Cyrillic and Japanese plates analyse.
    """
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
    """Structural signature of the letters, e.g. ``["A", "BC"]`` -> ``"ABC"``."""
    return "".join(letters)


@dataclass(slots=True)
class PlateAnalysis:
    """Deterministic trait analysis of one generated plate.

    Read by the generator, the rarity resolver, the valuation, the status/lore
    layer and the admin tools. ``pattern`` carries the Pattern Engine result
    alongside it; it is informational and has no bearing on traits, scores,
    rarity or value.
    """

    plate_text: str
    digits: list[str]
    letters: list[str]
    numeric_core: str
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
    """The region code repeats inside the plate body (region 77, plate 777)."""
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
        # Every synthetic collectible is tagged, so a player can filter the whole
        # SIM line out of a mixed collection.
        tags.append("sim")
        tags.append("synthetic")
    return sorted(set(tags))



def analyze_plate(
    plate_text: str,
    *,
    region_code: str | None = None,
    quality_digits: str | None = None,
    rarity_floor: str = "COMMON",
    plate_type: str = "STANDARD",
    country_tag: str = "",
    is_secret: bool = False,
    season_code: str | None = None,
) -> PlateAnalysis:
    """Run every trait detector over a plate and return traits and scores.

    This is the rarity-facing analysis: ``traits`` and ``scores`` feed
    :func:`app.game.plate_rarity.compute_rarity_score`, whose output decides the
    tier and the price. The Pattern Engine result is attached alongside it as
    ``pattern`` for descriptive use only - it is never read by rarity or value.
    """
    from app.game.plate_traits import PLATE_TRAITS

    digits, letters = split_plate(plate_text)
    # The region code is context, not part of the serial. When the plate ends
    # with the region code we strip it from the core so ``A777AA 77`` is judged
    # on its serial 777 rather than on the combined 77777.
    numeric_core = (
        "".join(char for char in quality_digits if char.isdigit())
        if plate_type in _DIGIT_JUDGED_TYPES and quality_digits is not None
        else "".join(digits)
    )
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

    # SIM cards are judged on the digits printed on them. A synthetic number has
    # no letters worth rewarding and no region to mirror, so the vehicle
    # detectors above would report almost nothing for one - which is exactly how
    # a 777 number used to come out as an ordinary plate. These detectors read
    # the digit structure directly, so rarity is a property of the number itself.
    if plate_type in _DIGIT_JUDGED_TYPES:
        pattern_text = quality_digits if quality_digits is not None else plate_text
        for code in detect_phone_traits(pattern_text):
            if code not in scores:
                scores[code] = PHONE_TRAIT_WEIGHTS.get(code, 4)
                traits.append(code)

    # Order traits deterministically by score (desc) then code, so the strongest
    # reasons always come first for the result UI.
    traits.sort(key=lambda code: (-scores.get(code, 0), code))
    scores_dict = {code: scores[code] for code in traits}
    reasons = list(traits[:4])

    # Attach the Pattern Engine result. `analyze_pattern` is pure, deterministic
    # and knows nothing about rarity, so it cannot move a tier or a price.
    pattern_result = analyze_pattern(plate_text, region_code=region_code)

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
        region_code=region_code,
        pattern=pattern_result,
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

#: ``Plate.plate_type`` values judged purely on their digits. A synthetic number
#: printed on a SIM card has no letters to reward and no region to mirror.
_DIGIT_JUDGED_TYPES: frozenset[str] = frozenset({"PHONE", "SIM"})




__all__ = [
    "FAMILIES",
    "LETTER_DETECTORS",
    "LUCKY_DIGITS",
    "MEME_RUNS",
    "NUMERIC_DETECTORS",
    "SPECIAL_NUMBER_RUNS",
    "DetectedPattern",
    "PatternResult",
    "PlateAnalysis",
    "analyze_pattern",
    "analyze_plate",
    "build_tags",
    "compact_identifier",
    "detect_alphabetical_run",
    "detect_ascending",
    "detect_contains_000",
    "detect_contains_007",
    "detect_contains_123",
    "detect_contains_666",
    "detect_contains_777",
    "detect_descending",
    "detect_four_of_kind",
    "detect_letter_ascending",
    "detect_letter_palindrome",
    "detect_lucky_pattern",
    "detect_meme_pattern",
    "detect_mirrored_letters",
    "detect_number_mirrors_region",
    "detect_pair",
    "detect_pair_letter",
    "detect_palindrome",
    "detect_rare_template",
    "detect_region_match",
    "detect_repeated_letter_prefix",
    "detect_repeated_letter_suffix",
    "detect_repeated_pattern",
    "detect_round_number",
    "detect_same_number_and_letters",
    "detect_sequence",
    "detect_special_code",
    "detect_special_run",
    "detect_symmetric_plate",
    "detect_triple",
    "detect_triple_letter",
    "detect_two_pairs",
    "detect_year_like",
    "letter_signature",
    "split_identifier",
    "split_plate",
]
