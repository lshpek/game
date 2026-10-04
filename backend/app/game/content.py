"""Mission and cosmetic catalogues.

Separate from the seed module so the content can grow without touching
persistence code.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MissionDefinition:
    code: str
    name_en: str
    name_ru: str
    description_en: str
    description_ru: str
    metric: str
    target: int
    reward_coins: int = 0
    reward_rolls: int = 0
    reward_xp: int = 0
    icon: str = "target"
    sort_order: int = 0


MISSION_DEFINITIONS: tuple[MissionDefinition, ...] = (
    MissionDefinition(
        "mission_roll_5", "Roll 5 plates", "Крутите 5 номеров",
        "Roll any 5 plates.", "Прокрутите любые 5 номеров.",
        "ROLL", 5, reward_coins=150, reward_xp=20, icon="dice", sort_order=1,
    ),
    MissionDefinition(
        "mission_rare_1", "Find 1 Rare+", "Найдите 1 Rare+",
        "Collect one Rare or better plate.", "Соберите один номер Rare или выше.",
        "FIND_RARE", 1, reward_coins=250, icon="gem", sort_order=2,
    ),
    MissionDefinition(
        "mission_countries_3", "Find 3 countries", "Найдите 3 страны",
        "Collect plates from three different countries.", "Соберите номера из трёх стран.",
        "NEW_COUNTRY", 3, reward_coins=400, reward_rolls=1, icon="globe", sort_order=3,
    ),
    MissionDefinition(
        "mission_pattern_1", "Repeated pattern", "Повторяющийся паттерн",
        "Find a plate with a repeated pattern.", "Найдите номер с повторяющимся паттерном.",
        "REPEATED_PATTERN", 1, reward_coins=200, icon="repeat", sort_order=4,
    ),
    MissionDefinition(
        "mission_777", "Find a 777", "Найдите 777",
        "Find a plate containing triple seven.", "Найдите номер с тройной семёркой.",
        "FIND_777", 1, reward_coins=300, icon="flame", sort_order=5,
    ),
    MissionDefinition(
        "mission_palindrome", "Palindrome hunter", "Охотник за палиндромами",
        "Find a palindrome plate.", "Найдите палиндромный номер.",
        "FIND_PALINDROME", 1, reward_coins=250, icon="mirror", sort_order=6,
    ),
    MissionDefinition(
        "mission_japan", "Japanese plate", "Японский номер",
        "Find a plate from Japan.", "Найдите номер из Японии.",
        "COUNTRY_PLATE", 1, reward_coins=400, icon="star", sort_order=7,
    ),
    MissionDefinition(
        "mission_duplicates", "Two duplicates", "Два дубликата",
        "Roll the same plate twice.", "Прокрутите один и тот же номер дважды.",
        "DUPLICATE", 2, reward_coins=200, icon="copy", sort_order=8,
    ),
    MissionDefinition(
        "mission_share", "Share a result", "Поделитесь находкой",
        "Share one of your plates.", "Поделитесь одним из своих номеров.",
        "SHARE", 1, reward_coins=150, reward_xp=15, icon="share", sort_order=9,
    ),
    MissionDefinition(
        "mission_challenge", "Accept a challenge", "Примите вызов",
        "Complete one plate challenge.", "Завершите один вызов номеров.",
        "CHALLENGE", 1, reward_coins=300, icon="swords", sort_order=10,
    ),
)


@dataclass(frozen=True, slots=True)
class CosmeticDefinition:
    code: str
    kind: str
    name_en: str
    name_ru: str
    description_en: str
    description_ru: str
    config: dict[str, object] = field(default_factory=dict)
    price_stars: int = 0
    price_numora: int = 0
    rarity_code: str = "COMMON"
    sort_order: int = 0


COSMETIC_DEFINITIONS: tuple[CosmeticDefinition, ...] = (
    # --- plate finishes
    CosmeticDefinition(
        "finish_stock", "PLATE_FINISH", "Stock", "Стандарт",
        "The factory finish.", "Стандартная заводская отделка.",
        {"style": "metal", "colors": ["#f4f6fb", "#e2e8f0"], "gradient": False},
        sort_order=1,
    ),
    CosmeticDefinition(
        "finish_chrome", "PLATE_FINISH", "Chrome", "Хром",
        "Mirror chrome finish.", "Зеркальный хром.",
        {"style": "chrome", "colors": ["#e5e7eb", "#9ca3af"], "gradient": True},
        price_numora=4000, rarity_code="RARE", sort_order=2,
    ),
    CosmeticDefinition(
        "finish_carbon", "PLATE_FINISH", "Carbon", "Карбон",
        "Carbon-fibre weave.", "Углеволокно.",
        {"style": "carbon", "colors": ["#1f2937", "#0f172a"], "texture": "weave"},
        price_numora=6500, rarity_code="EPIC", sort_order=3,
    ),
    CosmeticDefinition(
        "finish_gold", "PLATE_FINISH", "Gold", "Золото",
        "Brushed gold finish.", "Золотая отделка.",
        {"style": "gold", "colors": ["#fbbf24", "#b45309"], "gradient": True},
        price_stars=250, rarity_code="LEGENDARY", sort_order=4,
    ),
    CosmeticDefinition(
        "finish_holographic", "PLATE_FINISH", "Holographic", "Голографический",
        "Shifting holographic skin.", "Переливающаяся голографическая плёнка.",
        {"style": "holographic", "colors": ["#22d3ee", "#a855f7", "#f43f5e"], "animated": True},
        price_stars=500, rarity_code="MYTHIC", sort_order=5,
    ),
    CosmeticDefinition(
        "finish_neon", "PLATE_FINISH", "Neon", "Неон",
        "Night-city neon edge.", "Неоновая кромка ночного города.",
        {"style": "neon", "colors": ["#22d3ee", "#7c5cff"], "glow": True},
        price_numora=5000, rarity_code="RARE", sort_order=6,
    ),
    CosmeticDefinition(
        "finish_matte_black", "PLATE_FINISH", "Matte Black", "Матовый чёрный",
        "Stealthy matte black.", "Матовый чёрный.",
        {"style": "matte", "colors": ["#111827", "#0b1220"], "gradient": False},
        price_numora=3000, rarity_code="UNCOMMON", sort_order=7,
    ),
    # --- plate glows
    CosmeticDefinition(
        "glow_gold", "PLATE_GLOW", "Gold Glow", "Золотое свечение",
        "A warm gold glow on rare finds.", "Тёплое золотое свечение редких находок.",
        {"glow": "#fbbf24", "intensity": 0.8},
        price_stars=150, rarity_code="LEGENDARY", sort_order=10,
    ),
    CosmeticDefinition(
        "glow_cyan", "PLATE_GLOW", "Cyan Glow", "Голубое свечение",
        "Secret teal glow.", "Голубое свечение для секретов.",
        {"glow": "#22d3ee", "intensity": 1.0},
        price_stars=300, rarity_code="MYTHIC", sort_order=11,
    ),
    # --- profile frames
    CosmeticDefinition(
        "frame_steel", "PROFILE_FRAME", "Steel Frame", "Стальная рамка",
        "Brushed steel profile frame.", "Стальная рамка профиля.",
        {"border": "#94a3b8", "style": "solid"},
        price_numora=2000, rarity_code="UNCOMMON", sort_order=20,
    ),
    CosmeticDefinition(
        "frame_supporter", "PROFILE_FRAME", "Supporter Frame", "Рамка поддержки",
        "Earned by supporting NUMORA.", "Награда за поддержку NUMORA.",
        {"border": "#fbbf24", "style": "gradient"},
        price_stars=100, rarity_code="LEGENDARY", sort_order=21,
    ),
    # --- garage backgrounds
    CosmeticDefinition(
        "garage_night", "GARAGE_BACKGROUND", "Night Garage", "Ночной гараж",
        "A dark garage backdrop.", "Тёмный гараж.",
        {"background": "garage-night"},
        price_numora=3500, rarity_code="RARE", sort_order=30,
    ),
    CosmeticDefinition(
        "garage_sunset", "GARAGE_BACKGROUND", "Sunset Garage", "Закатный гараж",
        "A warm sunset backdrop.", "Тёплый закатный фон.",
        {"background": "garage-sunset"},
        price_stars=120, rarity_code="EPIC", sort_order=31,
    ),
)


__all__ = [
    "COSMETIC_DEFINITIONS",
    "CosmeticDefinition",
    "MISSION_DEFINITIONS",
    "MissionDefinition",
]