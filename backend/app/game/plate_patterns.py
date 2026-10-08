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
from dataclasses import dataclass
from itertools import pairwise

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


__all__ = [
    "FAMILIES",
    "DetectedPattern",
    "PatternResult",
    "analyze_pattern",
    "compact_identifier",
    "split_identifier",
]
