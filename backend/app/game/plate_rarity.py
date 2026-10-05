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
    (120, Rarity.MYTHIC),
    (78, Rarity.LEGENDARY),
    (48, Rarity.EPIC),
    (24, Rarity.RARE),
    (10, Rarity.UNCOMMON),
)

# Secret requires an extreme number pattern plus a second independent feature.
SECRET_MIN_SCORE = 105
SECRET_REQUIRED_TRAIT = "special_run"
SECRET_COMBINATION_TRAITS = frozenset(
    {"all_same", "four_of_kind", "triple_letter", "letter_palindrome", "mirrored_letters", "symmetric_plate"}
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
    return score_rarity(sum(analysis.scores.values()))


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
    """Deterministic score in the 0-200 band from plate patterns alone.

    The keyword-only modifiers remain accepted for compatibility, but country,
    template, event, discovery and operator metadata affect value/presentation only.
    None of them may turn an ordinary registration into a high-rarity find.
    """
    return max(0, min(200, sum(analysis.scores.values())))


def resolve_final_rarity(
    *,
    natural: Rarity,
    luck: Rarity,
    score: int,
    traits: list[str],
    template_floor: str = "COMMON",
    force_secret: bool = False,
) -> Rarity:
    """Resolve rarity from intrinsic quality; ``luck`` is a target, never a promotion."""
    if force_secret or (
        score >= SECRET_MIN_SCORE
        and SECRET_REQUIRED_TRAIT in traits
        and bool(SECRET_COMBINATION_TRAITS.intersection(traits))
    ):
        return Rarity.SECRET

    return score_rarity(score)


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
