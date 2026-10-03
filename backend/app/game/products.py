"""Telegram Stars products and premium entitlement tiers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductDefinition:
    """A purchasable product granted through Telegram Stars (or the mock)."""

    code: str
    name: str
    description: str
    stars_price: int
    grant_type: str  # "coins" | "premium"
    grant_payload: dict[str, object]
    sort_order: int = 0


PRODUCT_DEFINITIONS: tuple[ProductDefinition, ...] = (
    ProductDefinition("coins_1000", "1 000 Coins", "A small boost for the collection.", 50, "coins", {"amount": 1000}, 1),
    ProductDefinition("coins_5000", "5 000 Coins", "Enough for a handful of Premium Boxes.", 200, "coins", {"amount": 5000}, 2),
    ProductDefinition("coins_25000", "25 000 Coins", "Serious capital for serious collectors.", 800, "coins", {"amount": 25000}, 3),
    ProductDefinition("pro_30d", "Pro - 30 days", "More daily rolls, Pro Boxes and full statistics.", 1000, "premium", {"tier": "PRO", "days": 30}, 4),
    ProductDefinition("pro_90d", "Pro - 90 days", "Three months of Pro perks.", 2500, "premium", {"tier": "PRO", "days": 90}, 5),
)

PREMIUM_TIERS: dict[str, dict[str, object]] = {
    "PRO": {
        "label": "Pro",
        "daily_rolls_bonus": 15,
        "duplicate_coin_multiplier": 1.25,
        "unlocked_containers": ["pro"],
        "perks": [
            "More daily rolls",
            "Access to the Pro Box",
            "+25% coins from duplicates",
            "Extended statistics",
        ],
    }
}


def product_by_code(code: str) -> ProductDefinition | None:
    return next((item for item in PRODUCT_DEFINITIONS if item.code == code), None)


def premium_tier_config(tier: str) -> dict[str, object]:
    return PREMIUM_TIERS.get(tier.upper(), {})
