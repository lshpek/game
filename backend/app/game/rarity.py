"""Rarity definitions, weights and special-number tables.

The **chance table** lives here and nowhere else: :data:`RARITY_WEIGHT_HUNDREDTHS`
declares the game's fixed chances as integer hundredths of a percent (so 0.01%
Secret is exactly representable and the total is exactly 100%), and
:data:`DEFAULT_RARITY_WEIGHTS` is derived from it in percent. Every roll's
server-side luck draw reads that table, and
:mod:`app.game.plate_rarity` re-exports it rather than keeping a second copy.

An optional ``RARITY_WEIGHTS_OVERRIDE`` environment variable (JSON) can replace
the table for a tuning session, validated by :func:`load_rarity_weights`.
"""

from __future__ import annotations

import json
from enum import StrEnum

from app.core.errors import ValidationError

# The chance table is declared once, in integer hundredths of a percent, right here.


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

#: The game's fixed presentation chances, in percent. Authoritative: every roll's
#: server-side luck draw reads this table and nothing else.
#:
#: Expressed as integer **basis-point-like hundredths of a percent** (1/100 of 1%)
#: so that the tiny tiers are exact in binary floating point: Secret at 0.01% is
#: ``1`` hundredth-unit, Mythic at 0.09% is ``9``, and the whole table sums to
#: ``10_000`` hundredth-units = exactly 100%. A float table such as 0.01 would not
#: be exactly representable and repeated normalisation could drift.
#:
#: ```text
#: Common 54% | Uncommon 30% | Rare 13% | Epic 2.5% | Legendary 0.4%
#: Mythic 0.09% | Secret 0.01%        total = 100.00%
#: ```
#: The game's fixed presentation chances, in percent, as the ONE authoritative
#: table. Every roll's server-side luck draw reads this and nothing else.
#:
#: Stored as integer **hundredths of a percent** so the tiny tiers are exact in
#: binary floating point: Secret at 0.01% is ``1`` unit, Mythic at 0.09% is ``9``,
#: and the table sums to ``10_000`` units = exactly 100%. A hand-written float
#: table would not be exactly representable, and repeated normalisation of
#: ``0.01`` could drift.
#:
#: ```text
#: Common 54% | Uncommon 30% | Rare 13% | Epic 2.5% | Legendary 0.4%
#: Mythic 0.09% | Secret 0.01%        total = 100.00%
#: ```
RARITY_WEIGHT_HUNDREDTHS: dict[str, int] = {
    Rarity.COMMON.value: 5_400,
    Rarity.UNCOMMON.value: 3_000,
    Rarity.RARE.value: 1_300,
    Rarity.EPIC.value: 250,
    Rarity.LEGENDARY.value: 40,
    Rarity.MYTHIC.value: 9,
    Rarity.SECRET.value: 1,
}

#: The same table in percent, derived rather than duplicated, so the figure the
#: admin panel shows and the figure the RNG uses can never disagree.
DEFAULT_RARITY_WEIGHTS: dict[str, float] = {
    code: units / 100.0 for code, units in RARITY_WEIGHT_HUNDREDTHS.items()
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
    """Return validated rarity weights, honouring an optional JSON override.

    The default table is returned **as declared** - never renormalised - so its
    total is exactly ``100.0`` percent and the declared 0.01% Secret is the
    rolled 0.01% Secret. An override must itself sum to exactly 100%: silently
    rescaling a typo'd table would hide it, and a table that does not total 100
    is a configuration error, not a rounding problem.
    """
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

    # Exact for any table written in hundredths (54.0 + 30.0 + ... is exact in
    # binary), and tolerant of one ulp for a table that used repeating fractions.
    total = sum(weights.values())
    if abs(total - 100.0) > 1e-9:
        raise ValidationError(
            "Rarity weights must sum to exactly 100%.",
            code="BAD_RARITY_CONFIG",
        )
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
