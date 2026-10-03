"""Deterministic in-game valuation.

Never describes real money: the currency is the in-game ``COINS`` value.
The formula is pure and depends only on persisted inputs, so identical state
always yields an identical value.
"""

from __future__ import annotations

from app.game.rarity import RARITY_BASE_VALUE, SPECIAL_NUMBER_RARITY, Rarity
from app.game.traits import TRAITS

# Discovery makes a number less novel; the bonus fades linearly over this range.
NOVELTY_WINDOW = 1000
NOVELTY_BONUS = 0.5

SPECIAL_NUMBER_BONUS = 0.35
DUPLICATE_CONVERSION_RATE = 0.25
MIN_DUPLICATE_CONVERSION = 5


def _trait_multiplier(traits: list[str]) -> float:
    multiplier = 1.0
    for code in traits:
        trait = TRAITS.get(code)
        if trait is not None:
            multiplier *= trait.value_multiplier
    return multiplier


def novelty_multiplier(discovery_count: int) -> float:
    """Fewer discoveries -> higher value."""
    remaining = max(0, NOVELTY_WINDOW - max(0, discovery_count))
    return 1.0 + NOVELTY_BONUS * (remaining / NOVELTY_WINDOW)


def compute_value(
    rarity: str | Rarity,
    traits: list[str],
    number: str,
    discovery_count: int = 0,
) -> int:
    """Compute the authoritative COINS value of a number."""
    rarity_code = rarity.value if isinstance(rarity, Rarity) else str(rarity).upper()
    base = RARITY_BASE_VALUE.get(rarity_code, RARITY_BASE_VALUE[Rarity.COMMON.value])
    multiplier = _trait_multiplier(traits)
    if number in SPECIAL_NUMBER_RARITY:
        multiplier *= 1.0 + SPECIAL_NUMBER_BONUS
    value = base * multiplier * novelty_multiplier(discovery_count)
    return max(1, round(value))


def duplicate_conversion_reward(value: int) -> int:
    """COINS granted when a duplicate number is converted."""
    return max(MIN_DUPLICATE_CONVERSION, round(value * DUPLICATE_CONVERSION_RATE))


def rarity_sort_key(rarity: str | Rarity) -> int:
    from app.game.rarity import rarity_rank

    return rarity_rank(rarity)
