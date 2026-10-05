"""Deterministic collectible valuation.

Two outputs, produced together and always server-side:

``dealer_value_numora``
    The authoritative game-economy value. This is what the DEALER pays out.

``collector_value_local``
    A **fictional** presentation value shown in the country's display currency. It is a
    game flourish derived from the same inputs through a country scale - it is *not* a
    market price, not a real valuation, and never convertible.

The formula is pure, so identical inputs always yield identical outputs.

Bounded by design
-----------------
The product of the multipliers is clamped. Left unbounded, five factors at 1.3 each
would multiply to 3.7x and a single unlucky roll could outbid a whole country of
progress. The clamp keeps the economy legible: rarity dominates, the other factors
colour it, and no single find can explode the ledger.

    value = base(rarity)
          x pattern      (trait structure of the number itself)
          x country
          x template / region / special
          x provider     (SIM brand weight - game balance only)
          x novelty      (world discovery count)
          -> clamped to [1x, VALUE_MULTIPLIER_CAP]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.game.plate_rarity import RARITY_BASE_VALUE, Rarity
from app.game.plate_traits import PLATE_TRAITS

if TYPE_CHECKING:
    from app.game.plate_patterns import PlateAnalysis

# Discovery makes a collectible less novel; the bonus fades linearly over this window.
NOVELTY_WINDOW = 400
NOVELTY_BONUS = 0.45

SPECIAL_PATTERN_BONUS = 0.3
MIN_DUPLICATE_SALE = 3
DUPLICATE_SALE_RATE = 0.22

#: Collector's-value presentation only: how the local number is derived from the NUMORA
#: value. Purely cosmetic, never an exchange rate.
LOCAL_PER_NUMORA = 3.0

#: Hard ceiling on the combined multiplier. Rarity stays the dominant term.
VALUE_MULTIPLIER_CAP = 4.0

#: Bounds for the SIM line's operator weighting, mirroring the rarity bounds so a brand
#: can never be the reason a card is expensive.
MIN_PROVIDER_VALUE_MODIFIER = 0.85
MAX_PROVIDER_VALUE_MODIFIER = 1.20


def _trait_multiplier(traits: list[str]) -> float:
    multiplier = 1.0
    for code in traits:
        trait = PLATE_TRAITS.get(code)
        if trait is not None:
            multiplier *= trait.value_multiplier
    return multiplier


def novelty_multiplier(discovery_count: int) -> float:
    """Fewer discoveries -> higher value."""
    remaining = max(0, NOVELTY_WINDOW - max(0, discovery_count))
    return 1.0 + NOVELTY_BONUS * (remaining / NOVELTY_WINDOW)


def compute_values(
    rarity: str | Rarity,
    traits: list[str],
    *,
    discovery_count: int = 0,
    country_multiplier: float = 1.0,
    region_multiplier: float = 1.0,
    template_multiplier: float = 1.0,
    special_pattern: bool = False,
    country_value_scale: float = 1.0,
    premium_multiplier: float = 1.0,
    provider_multiplier: float = 1.0,
    collector_multiplier: float = 1.0,
) -> tuple[int, int]:
    """Return ``(dealer_value_numora, collector_value_local)``."""
    rarity_code = rarity.value if isinstance(rarity, Rarity) else str(rarity).upper()
    base = RARITY_BASE_VALUE.get(rarity_code, RARITY_BASE_VALUE[Rarity.COMMON.value])

    multiplier = _trait_multiplier(traits)
    multiplier *= max(0.25, country_multiplier)
    multiplier *= max(0.25, region_multiplier)
    multiplier *= max(0.25, template_multiplier)
    if special_pattern:
        multiplier *= 1.0 + SPECIAL_PATTERN_BONUS
    # The SIM brand's game weight, bounded so it colours the price without dominating it.
    multiplier *= max(
        MIN_PROVIDER_VALUE_MODIFIER, min(MAX_PROVIDER_VALUE_MODIFIER, provider_multiplier)
    )
    multiplier *= novelty_multiplier(discovery_count)
    multiplier = max(1.0, min(VALUE_MULTIPLIER_CAP, multiplier))

    dealer = max(1, round(base * multiplier))
    local = max(
        1,
        round(
            dealer
            * LOCAL_PER_NUMORA
            * max(0.2, country_value_scale)
            * max(1.0, min(2.5, collector_multiplier))
        ),
    )
    return dealer, local


def duplicate_sale_value(dealer_value: int, *, premium_multiplier: float = 1.0) -> int:
    """NUMORA paid by the DEALER for one duplicate copy."""
    return max(
        MIN_DUPLICATE_SALE,
        round(int(dealer_value) * DUPLICATE_SALE_RATE * max(1.0, premium_multiplier)),
    )


def value_for_analysis(
    rarity: str | Rarity,
    analysis: "PlateAnalysis",
    *,
    discovery_count: int = 0,
    country_multiplier: float = 1.0,
    region_multiplier: float = 1.0,
    template_multiplier: float = 1.0,
    country_value_scale: float = 1.0,
    provider_multiplier: float = 1.0,
    collector_multiplier: float = 1.0,
) -> tuple[int, int]:
    """Convenience wrapper deriving the multipliers from the analysis."""
    return compute_values(
        rarity,
        list(analysis.traits),
        discovery_count=discovery_count,
        country_multiplier=country_multiplier,
        region_multiplier=region_multiplier,
        template_multiplier=template_multiplier,
        special_pattern="special_run" in analysis.traits or "special_code" in analysis.traits,
        country_value_scale=country_value_scale,
        provider_multiplier=provider_multiplier,
        collector_multiplier=collector_multiplier,
    )


__all__ = [
    "DUPLICATE_SALE_RATE",
    "LOCAL_PER_NUMORA",
    "MAX_PROVIDER_VALUE_MODIFIER",
    "MIN_DUPLICATE_SALE",
    "MIN_PROVIDER_VALUE_MODIFIER",
    "NOVELTY_BONUS",
    "NOVELTY_WINDOW",
    "VALUE_MULTIPLIER_CAP",
    "compute_values",
    "duplicate_sale_value",
    "novelty_multiplier",
    "value_for_analysis",
]
