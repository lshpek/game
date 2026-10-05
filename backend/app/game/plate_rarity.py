"""Rarity engine for plates.

Rarity is never a random label: it is derived from the plate's own patterns.

* **natural rarity** - the highest rarity floor implied by its traits;
* **luck rarity** - a server-side roll that can only *lift* a plate, and whose
  weights are softened by bad-luck protection;
* **final rarity** - the more prestigious of the two, then clamped by the
  template floor and the season/event modifiers.

Every declared probability lives in :mod:`app.game.rarity` - one table, in exact
integer hundredths of a percent - and is re-exported here so the plate engine
has a single import. ``RARITY_WEIGHTS_OVERRIDE`` may replace it for a session;
scoring, floors and pity logic stay in this module.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING

from app.core.errors import ValidationError
from app.game.rarity import DEFAULT_RARITY_WEIGHTS as _RARITY_WEIGHTS

if TYPE_CHECKING:
    from app.game.plate_patterns import PlateAnalysis


class Rarity(StrEnum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"
    MYTHIC = "MYTHIC"
    SECRET = "SECRET"


RARITY_ORDER: tuple[Rarity, ...] = (
    Rarity.COMMON,
    Rarity.UNCOMMON,
    Rarity.RARE,
    Rarity.EPIC,
    Rarity.LEGENDARY,
    Rarity.MYTHIC,
    Rarity.SECRET,
)

RARITY_RANK: dict[str, int] = {r.value: index for index, r in enumerate(RARITY_ORDER)}

# The game's fixed presentation chances, mirroring
# :data:`app.game.rarity.DEFAULT_RARITY_WEIGHTS` exactly. The table lives there
# (as integer hundredths of a percent, so 0.01% Secret is representable and the
# total is exactly 100%) and is re-exported here, because the plate engine reads
# its weights from this module and two *different* tables would be a bug.
DEFAULT_RARITY_WEIGHTS: dict[str, float] = dict(_RARITY_WEIGHTS)

# Base dealer value (in NUMORA) per rarity. Collector Value is a separate,
# purely cosmetic local-currency presentation derived from this.
RARITY_BASE_VALUE: dict[str, int] = {
    Rarity.COMMON.value: 12,
    Rarity.UNCOMMON.value: 55,
    Rarity.RARE.value: 240,
    Rarity.EPIC.value: 1100,
    Rarity.LEGENDARY.value: 4800,
    Rarity.MYTHIC.value: 26000,
    Rarity.SECRET.value: 140000,
}

RARITY_LABEL: dict[str, str] = {
    Rarity.COMMON.value: "Common",
    Rarity.UNCOMMON.value: "Uncommon",
    Rarity.RARE.value: "Rare",
    Rarity.EPIC.value: "Epic",
    Rarity.LEGENDARY.value: "Legendary",
    Rarity.MYTHIC.value: "Mythic",
    Rarity.SECRET.value: "Secret",
}

RARITY_COLOR: dict[str, str] = {
    Rarity.COMMON.value: "#8b93a7",
    Rarity.UNCOMMON.value: "#4ade80",
    Rarity.RARE.value: "#38bdf8",
    Rarity.EPIC.value: "#a855f7",
    Rarity.LEGENDARY.value: "#fbbf24",
    Rarity.MYTHIC.value: "#f43f5e",
    Rarity.SECRET.value: "#22d3ee",
}

# Score thresholds map intrinsic pattern quality onto a rarity.
SCORE_THRESHOLDS: tuple[tuple[int, Rarity], ...] = (
    (100, Rarity.MYTHIC),
    (78, Rarity.LEGENDARY),
    (55, Rarity.EPIC),
    (28, Rarity.RARE),
    (12, Rarity.UNCOMMON),
)

SECRET_MIN_SCORE = 130
SECRET_DIGIT_TRAITS = frozenset({"all_same", "four_of_kind", "quad_repeat"})
SECRET_LETTER_TRAITS = frozenset(
    {"triple_letter", "letter_palindrome", "mirrored_letters", "perfect_symmetry"}
)

# Bad-luck protection thresholds (consecutive rolls without a tier).
PITY_RARE_AFTER = 14
PITY_EPIC_AFTER = 34
PITY_LEGENDARY_AFTER = 120
PITY_LUCK_MULTIPLIER = 2.6

# Bounds for the SIM line's operator weighting. Narrow on purpose: a provider colours a
# card, it never manufactures a tier. See :func:`compute_rarity_score`.
MIN_PROVIDER_SCORE_MODIFIER = 0.85
MAX_PROVIDER_SCORE_MODIFIER = 1.20


def load_rarity_weights(override_json: str | None = None) -> dict[str, float]:
    """Return validated rarity weights, honouring an optional JSON override."""
    if not override_json:
        return dict(DEFAULT_RARITY_WEIGHTS)

    try:
        parsed = json.loads(override_json)
    except json.JSONDecodeError as exc:
        raise ValidationError("RARITY_WEIGHTS_OVERRIDE is not valid JSON.", code="BAD_RARITY_CONFIG") from exc

    if not isinstance(parsed, dict):
        raise ValidationError("Rarity weights must be a JSON object.", code="BAD_RARITY_CONFIG")

    weights: dict[str, float] = {}
    for code, value in parsed.items():
        key = str(code).upper()
        if key not in RARITY_RANK:
            raise ValidationError(f"Unknown rarity code: {key}", code="BAD_RARITY_CONFIG")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Weight for {key} must be numeric.", code="BAD_RARITY_CONFIG") from exc
        if weight < 0:
            raise ValidationError(f"Weight for {key} cannot be negative.", code="BAD_RARITY_CONFIG")
        weights[key] = weight

    for code in RARITY_ORDER:
        weights.setdefault(code.value, 0.0)

    if sum(weights.values()) <= 0:
        raise ValidationError("Rarity weights must sum to a positive value.", code="BAD_RARITY_CONFIG")
    return weights


def rarity_rank(rarity: str | Rarity) -> int:
    value = rarity.value if isinstance(rarity, Rarity) else str(rarity).upper()
    return RARITY_RANK.get(value, 0)


def rarity_case(column):
    """SQL ``CASE`` mapping a rarity column onto its numeric rank.

    Lets a single aggregate query sort or bucket by rarity without pulling rows
    into Python. Unknown codes fall back to ``COMMON``.
    """
    from sqlalchemy import case

    return case(RARITY_RANK, value=column, else_=0)


def max_rarity(*rarities: str | Rarity) -> Rarity:
    """Return the most prestigious rarity of the arguments."""
    best = Rarity.COMMON
    for rarity in rarities:
        if rarity_rank(rarity) > rarity_rank(best):
            best = Rarity(rarity)
    return best


def natural_rarity(analysis: "PlateAnalysis") -> Rarity:
    """Rarity implied by intrinsic patterns, without luck or template labels."""
    return _quality_rarity(compute_rarity_score(analysis), analysis.traits)


def _secret_eligible(score: int, traits: list[str]) -> bool:
    trait_set = set(traits)
    has_exceptional_mix = bool(SECRET_DIGIT_TRAITS & trait_set) and bool(
        SECRET_LETTER_TRAITS & trait_set
    )
    has_perfect_number = "perfect_symmetry" in trait_set and bool(
        {"quad_repeat", "all_same", "four_of_kind"} & trait_set
    )
    return score >= SECRET_MIN_SCORE and (has_exceptional_mix or has_perfect_number)


def _quality_rarity(score: int, traits: list[str]) -> Rarity:
    if _secret_eligible(score, traits):
        return Rarity.SECRET
    candidate = score_rarity(score)
    return Rarity.MYTHIC if candidate is Rarity.SECRET else candidate


def score_rarity(score: int) -> Rarity:
    """Map a numeric rarity score onto a rarity band."""
    for threshold, rarity in SCORE_THRESHOLDS:
        if score >= threshold:
            return rarity
    return Rarity.COMMON


def compute_rarity_score(
    analysis: "PlateAnalysis",
    *,
    country_modifier: float = 1.0,
    template_multiplier: float = 1.0,
    event_modifier: float = 1.0,
    novelty_bonus: float = 0.0,
    provider_modifier: float = 1.0,
) -> int:
    """Score independent number/letter pattern families without stacking aliases.

    The keyword-only modifiers remain accepted for compatibility, but country,
    template, event, discovery and operator metadata affect value/presentation only.
    None of them may turn an ordinary registration into a high-rarity find. Within
    each family, only its strongest feature counts; a triple, lucky label and special
    code describing the same run do not add together.
    """
    digits = "".join(character for character in analysis.numeric_core if character.isdigit())
    letters = "".join(character for group in analysis.letters for character in group)
    region_code = str(getattr(analysis, "region_code", "") or "")
    if region_code and not region_code.isdigit():
        if letters.startswith(region_code):
            letters = letters[len(region_code):]
        elif letters.endswith(region_code):
            letters = letters[:-len(region_code)]

    digit_score = max(
        _repeat_quality(digits),
        _sequence_quality(digits),
        _mirror_quality(digits),
        _repeated_block_quality(digits),
        26 if {"special_run", "special_code", "contains_007", "contains_777", "contains_123"}
        & set(analysis.traits) else 0,
    )
    letter_score = max(
        _repeat_quality(letters),
        _sequence_quality(letters),
        _mirror_quality(letters),
        _repeated_block_quality(letters),
    )

    if digit_score >= 28 and letter_score >= 28:
        score = digit_score + letter_score + (18 if digit_score >= 50 and letter_score >= 45 else 12)
    else:
        score = max(digit_score, letter_score)
    return max(0, min(200, score))


def _repeat_quality(value: str) -> int:
    longest = current = 0
    previous = ""
    for character in value:
        current = current + 1 if character == previous else 1
        previous = character
        longest = max(longest, current)
    if longest >= 10:
        return 130
    if longest >= 8:
        return 108
    if longest >= 7:
        return 96
    if longest >= 6:
        return 82
    if longest >= 5:
        return 68
    if longest >= 4:
        return 52
    if longest >= 3:
        return 28
    return 8 if longest == 2 else 0


def _sequence_quality(value: str) -> int:
    longest = current = 1 if value else 0
    direction = 0
    for left, right in zip(value, value[1:]):
        if left.isdigit() and right.isdigit():
            step = int(right) - int(left)
        else:
            step = ord(right) - ord(left)
        if step in (-1, 1) and direction in (0, step):
            current += 1
            direction = step
        else:
            current = 1
            direction = 0
        longest = max(longest, current)
    if longest >= 9:
        return 96
    if longest >= 7:
        return 86
    if longest >= 6:
        return 76
    if longest >= 5:
        return 64
    if longest >= 4:
        return 48
    if longest >= 3:
        return 22
    return 0


def _mirror_quality(value: str) -> int:
    if len(value) >= 10 and value == value[::-1]:
        return 96
    if len(value) >= 8 and value == value[::-1]:
        return 80
    if len(value) >= 6 and value == value[::-1]:
        return 64
    if len(value) >= 4 and value == value[::-1]:
        return 42
    return 0


def _repeated_block_quality(value: str) -> int:
    if len(value) >= 8 and len(value) % 2 == 0 and value[: len(value) // 2] == value[len(value) // 2 :]:
        return 68
    if len(value) >= 6 and len(value) % 2 == 0 and value[: len(value) // 2] == value[len(value) // 2 :]:
        return 55
    if len(value) >= 4 and len(value) % 2 == 0 and value[: len(value) // 2] == value[len(value) // 2 :]:
        return 34
    return 0


def resolve_final_rarity(
    *,
    natural: Rarity,
    luck: Rarity,
    score: int,
    traits: list[str],
    template_floor: str = "COMMON",
    force_secret: bool = False,
) -> Rarity:
    """Resolve rarity from intrinsic quality; targets and overrides cannot promote it."""
    return _quality_rarity(score, traits)


def pity_weights(
    base_weights: dict[str, float],
    *,
    rare_streak: int = 0,
    epic_streak: int = 0,
    legendary_streak: int = 0,
) -> dict[str, float]:
    """Lift rare-tier weights when a player is on a long unlucky streak.

    Bad-luck protection only ever *helps*: it never removes a weight and never
    manufactures Mythic/Secret, it just makes them less unlikely to be absent.
    """
    weights = dict(base_weights)
    factor = 1.0

    if rare_streak >= PITY_RARE_AFTER:
        factor += PITY_LUCK_MULTIPLIER * min(3.0, (rare_streak - PITY_RARE_AFTER + 1) / 8.0)
    if epic_streak >= PITY_EPIC_AFTER:
        factor += PITY_LUCK_MULTIPLIER * min(2.0, (epic_streak - PITY_EPIC_AFTER + 1) / 12.0)
    if legendary_streak >= PITY_LEGENDARY_AFTER:
        factor += 1.0

    if factor <= 1.0:
        return weights

    for code in (Rarity.RARE.value, Rarity.EPIC.value, Rarity.LEGENDARY.value):
        weights[code] = weights.get(code, 0.0) * factor
    # Mythic/Secret get a very small, bounded nudge only on extreme streaks.
    if epic_streak >= PITY_EPIC_AFTER * 2:
        weights[Rarity.MYTHIC.value] = weights.get(Rarity.MYTHIC.value, 0.0) * 1.25
    if legendary_streak >= PITY_LEGENDARY_AFTER * 2:
        weights[Rarity.SECRET.value] = weights.get(Rarity.SECRET.value, 0.0) * 1.2
    return weights


__all__ = [
    "DEFAULT_RARITY_WEIGHTS",
    "MAX_PROVIDER_SCORE_MODIFIER",
    "MIN_PROVIDER_SCORE_MODIFIER",
    "PITY_EPIC_AFTER",
    "PITY_LEGENDARY_AFTER",
    "PITY_RARE_AFTER",
    "RARITY_BASE_VALUE",
    "RARITY_COLOR",
    "RARITY_LABEL",
    "RARITY_ORDER",
    "RARITY_RANK",
    "SCORE_THRESHOLDS",
    "Rarity",
    "compute_rarity_score",
    "load_rarity_weights",
    "max_rarity",
    "natural_rarity",
    "pity_weights",
    "rarity_case",
    "rarity_rank",
    "resolve_final_rarity",
    "score_rarity",
]
