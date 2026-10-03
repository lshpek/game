"""Rarity definitions, weights and special-number tables.

Every probability lives here (optionally overridable through the
``RARITY_WEIGHTS_OVERRIDE`` environment variable as JSON) so tuning the game
never requires touching the roll logic.
"""

from __future__ import annotations

import json
from enum import StrEnum

from app.core.errors import ValidationError


class Rarity(StrEnum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"
    MYTHIC = "MYTHIC"
    SECRET = "SECRET"


# Ascending order of prestige. Rank comparisons drive "rarest" calculations.
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

# Percentages must sum to 100; the RNG normalises defensively anyway.
DEFAULT_RARITY_WEIGHTS: dict[str, float] = {
    Rarity.COMMON.value: 70.0,
    Rarity.UNCOMMON.value: 20.0,
    Rarity.RARE.value: 7.0,
    Rarity.EPIC.value: 2.0,
    Rarity.LEGENDARY.value: 0.8,
    Rarity.MYTHIC.value: 0.19,
    Rarity.SECRET.value: 0.01,
}

RARITY_BASE_VALUE: dict[str, int] = {
    Rarity.COMMON.value: 10,
    Rarity.UNCOMMON.value: 45,
    Rarity.RARE.value: 180,
    Rarity.EPIC.value: 900,
    Rarity.LEGENDARY.value: 4200,
    Rarity.MYTHIC.value: 25000,
    Rarity.SECRET.value: 120000,
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

# --- Special numbers ---------------------------------------------------
SECRET_NUMBERS: frozenset[str] = frozenset({"1337", "8008", "4200", "6969"})
MYTHIC_NUMBERS: frozenset[str] = frozenset({"7777", "0000", "1234", "6666", "9999", "1111"})
LEGENDARY_NUMBERS: frozenset[str] = frozenset(
    {
        "4321",
        "8888",
        "2222",
        "5555",
        "3333",
        "4444",
        "0007",
        "0777",
        "1000",
        "5000",
        "2048",
        "2024",
    }
)

SPECIAL_NUMBER_RARITY: dict[str, Rarity] = {
    **dict.fromkeys(SECRET_NUMBERS, Rarity.SECRET),
    **dict.fromkeys(MYTHIC_NUMBERS, Rarity.MYTHIC),
    **dict.fromkeys(LEGENDARY_NUMBERS, Rarity.LEGENDARY),
}


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


def max_rarity(*rarities: str | Rarity) -> Rarity:
    """Return the most prestigious rarity of the arguments."""
    best = Rarity.COMMON
    for rarity in rarities:
        if rarity_rank(rarity) > rarity_rank(best):
            best = Rarity(rarity)
    return best
