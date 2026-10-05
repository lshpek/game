"""Telegram Stars products and entitlement tiers.

Monetisation is deliberately restrained:

* **NUMORA PRO** - convenience perks only; the free game stays fair.
* **SUPPORT NUMORA** - badge, frame and title, and nothing else.
* **Season pass / bundles** - fixed content with disclosed contents.

There is no paid random-loot product: money never buys a surprise plate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductDefinition:
    """A purchasable product granted through Telegram Stars (or the mock)."""

    code: str
    name: str
    name_ru: str
    description: str
    description_ru: str
    stars_price: int
    grant_type: str  # COINS | PREMIUM | SUPPORTER | COSMETIC | SEASON_PASS
    grant_payload: dict[str, object]
    category: str = "PRO"
    sort_order: int = 0


PRODUCT_DEFINITIONS: tuple[ProductDefinition, ...] = (
    # --- NUMORA (the in-game currency; buyable, never required)
    ProductDefinition(
        "numora_5000", "5 000 NUMORA", "5 000 NUMORA",
        "A balance boost for the DEALER and the cosmetic shop.",
        "Пополнение баланса для дилера и магазина косметики.",
        150, "COINS", {"amount": 5000}, category="NUMORA", sort_order=1,
    ),
    ProductDefinition(
        "numora_25000", "25 000 NUMORA", "25 000 NUMORA",
        "A larger balance boost for serious collectors.",
        "Большее пополнение для серьёзных коллекционеров.",
        600, "COINS", {"amount": 25000}, category="NUMORA", sort_order=2,
    ),
    ProductDefinition(
        "numora_100000", "100 000 NUMORA", "100 000 NUMORA",
        "The largest NUMORA top-up.",
        "Самое большое пополнение NUMORA.",
        2000, "COINS", {"amount": 100000}, category="NUMORA", sort_order=3,
    ),
    # --- fixed roll bundles ---------------------------------------------
    # Fully disclosed, fixed contents. These grant a flat number of rolls and nothing
    # else: no guaranteed rarity, no altered odds, no hidden RNG. The rolls land in the
    # bonus bank above the normal cap, so they are never consumed by passive
    # regeneration and cannot be lost to it.
    ProductDefinition(
        "rolls_5", "5 Rolls", "5 прокруток",
        "Exactly 5 extra rolls. Fixed contents, unchanged odds.",
        "Ровно 5 дополнительных прокруток. Фиксированное содержимое, шансы прежние.",
        60, "ROLLS", {"rolls": 5}, category="ROLLS", sort_order=5,
    ),
    ProductDefinition(
        "rolls_15", "15 Rolls", "15 прокруток",
        "Exactly 15 extra rolls. Fixed contents, unchanged odds.",
        "Ровно 15 дополнительных прокруток. Фиксированное содержимое, шансы прежние.",
        150, "ROLLS", {"rolls": 15}, category="ROLLS", sort_order=6,
    ),
    ProductDefinition(
        "rolls_40", "40 Rolls", "40 прокруток",
        "Exactly 40 extra rolls. Fixed contents, unchanged odds.",
        "Ровно 40 дополнительных прокруток. Фиксированное содержимое, шансы прежние.",
        350, "ROLLS", {"rolls": 40}, category="ROLLS", sort_order=7,
    ),
    # --- PRO subscription
    ProductDefinition(
        "pro_30d", "NUMORA PRO - 30 days", "NUMORA PRO - 30 дней",
        "More daily rolls, a better DEALER rate and Pro cosmetics.",
        "Больше прокруток, выгодный курс дилера и Pro-косметика.",
        750, "PREMIUM", {"tier": "PRO", "days": 30}, category="PRO", sort_order=10,
    ),
    ProductDefinition(
        "pro_90d", "NUMORA PRO - 90 days", "NUMORA PRO - 90 дней",
        "Three months of Pro perks.",
        "Три месяца Pro-возможностей.",
        1900, "PREMIUM", {"tier": "PRO", "days": 90}, category="PRO", sort_order=11,
    ),
    ProductDefinition(
        "supporter_25", "Supporter 25", "Поддержка 25",
        "Supporter badge, frame and title. No gameplay power.",
        "Значок, рамка и титул поддержки. Без влияния на игру.",
        25, "SUPPORTER", {"tier": "SUPPORTER_25", "cosmetic": "frame_supporter"},
        category="SUPPORT", sort_order=20,
    ),
    ProductDefinition(
        "supporter_100", "Supporter 100", "Поддержка 100",
        "Supporter badge, frame and title. No gameplay power.",
        "Значок, рамка и титул поддержки. Без влияния на игру.",
        100, "SUPPORTER", {"tier": "SUPPORTER_100", "cosmetic": "frame_supporter"},
        category="SUPPORT", sort_order=21,
    ),
    ProductDefinition(
        "supporter_250", "Supporter 250", "Поддержка 250",
        "Supporter badge, frame and title. No gameplay power.",
        "Значок, рамка и титул поддержки. Без влияния на игру.",
        250, "SUPPORTER", {"tier": "SUPPORTER_250", "cosmetic": "frame_supporter"},
        category="SUPPORT", sort_order=22,
    ),
    ProductDefinition(
        "supporter_500", "Supporter 500", "Поддержка 500",
        "Supporter badge, frame and title. No gameplay power.",
        "Значок, рамка и титул поддержки. Без влияния на игру.",
        500, "SUPPORTER", {"tier": "SUPPORTER_500", "cosmetic": "frame_supporter"},
        category="SUPPORT", sort_order=23,
    ),
    # --- fixed-content bundles (contents fully disclosed)
    ProductDefinition(
        "bundle_starter", "Starter Bundle", "Стартовый набор",
        "Chrome finish, steel frame and 5 000 NUMORA. Fixed contents.",
        "Хром, стальная рамка и 5 000 NUMORA. Фиксированное содержимое.",
        400, "COSMETIC", {"cosmetics": ["finish_chrome", "frame_steel"], "numora": 5000},
        category="BUNDLE", sort_order=30,
    ),
    ProductDefinition(
        "bundle_garage", "Garage Bundle", "Набор для гаража",
        "Night garage background, gold finish and neon edge. Fixed contents.",
        "Ночной гараж, золотая отделка и неон. Фиксированное содержимое.",
        600, "COSMETIC", {"cosmetics": ["garage_night", "finish_gold", "finish_neon"]},
        category="BUNDLE", sort_order=31,
    ),
    ProductDefinition(
        "season_pass_1", "Season Pass", "Сезонный пропуск",
        "The full season reward track: cosmetics, titles and NUMORA.",
        "Полная награда сезона: косметика, титулы и NUMORA.",
        900, "SEASON_PASS", {"season": "current"}, category="SEASON", sort_order=40,
    ),
)

PREMIUM_TIERS: dict[str, dict[str, object]] = {
    "PRO": {
        "label": "NUMORA PRO",
        "daily_rolls_bonus": 15,
        # A better DEALER rate is a convenience, not a power ceiling.
        "duplicate_coin_multiplier": 1.25,
        "unlocked_containers": ["pro"],
        "perks_en": [
            "+15 daily rolls",
            "+25% NUMORA from duplicates",
            "Pro cosmetic drops",
            "Extended statistics",
            "Priority event rewards",
        ],
        "perks_ru": [
            "+15 прокруток в день",
            "+25% NUMORA за дубликаты",
            "Pro-косметика",
            "Расширенная статистика",
            "Приоритетные награды событий",
        ],
    },
}

SUPPORTER_TIERS: dict[str, dict[str, object]] = {
    "SUPPORTER_25": {"label": "Supporter", "title": "Supporter"},
    "SUPPORTER_100": {"label": "Supporter", "title": "Patron"},
    "SUPPORTER_250": {"label": "Supporter", "title": "Benefactor"},
    "SUPPORTER_500": {"label": "Supporter", "title": "NUMORA Patron"},
}


def product_by_code(code: str) -> ProductDefinition | None:
    return next((item for item in PRODUCT_DEFINITIONS if item.code == code), None)


#: Declared here, next to the catalogue that uses it, so the seeder, the admin
#: catalogue and :meth:`PaymentService._grant` cannot drift apart. A product whose
#: grant type is not listed here is a purchase the backend cannot fulfil, and
#: ``tests/test_payments.py`` asserts the two sets are identical.
GRANT_TYPES: tuple[str, ...] = (
    "COINS",
    "ROLLS",
    "PREMIUM",
    "SUPPORTER",
    "COSMETIC",
    "SEASON_PASS",
)


def premium_tier_config(tier: str) -> dict[str, object]:
    return PREMIUM_TIERS.get((tier or "").upper(), {})
