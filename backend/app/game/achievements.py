"""Achievement catalogue.

``metric`` values are resolved by
:data:`app.services.achievements.METRIC_RESOLVERS`, so new achievements only
need an entry here plus - if the metric is new - one resolver function.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    code: str
    name: str
    description: str
    metric: str
    threshold: int
    reward_coins: int
    icon: str = "star"
    sort_order: int = 0
    meta: dict[str, str] = field(default_factory=dict)


ACHIEVEMENT_DEFINITIONS: tuple[AchievementDefinition, ...] = (
    # --- getting started
    AchievementDefinition("FIRST_PLATE", "First Plate", "Collect your first plate.", "plates", 1, 40, "sparkles", 1),
    AchievementDefinition("FIRST_COUNTRY", "First Country", "Collect a plate from any country.", "countries", 1, 80, "globe", 2),
    AchievementDefinition("WORLD_TRAVELER", "World Traveler", "Collect plates from 3 countries.", "countries", 3, 250, "globe", 3),
    AchievementDefinition("TEN_COUNTRIES", "Ten Countries", "Collect plates from 10 countries.", "countries", 10, 1500, "globe", 4),
    # --- country collectors
    AchievementDefinition("RUS_COLLECTOR", "Russia Collector", "Collect 10 Russian plates.", "country_rus", 10, 400, "box", 5),
    AchievementDefinition("USA_COLLECTOR", "USA Collector", "Collect 10 US plates.", "country_usa", 10, 400, "box", 6),
    AchievementDefinition("JPN_COLLECTOR", "Japan Collector", "Collect 5 Japanese plates.", "country_jpn", 5, 500, "box", 7),
    # --- pattern hunters
    AchievementDefinition("TRIPLE_SEVEN", "Triple Seven", "Find a plate containing 777.", "trait_777", 1, 200, "flame", 8),
    AchievementDefinition("PALINDROME_HUNTER", "Palindrome Hunter", "Find 5 palindrome plates.", "trait_palindrome", 5, 600, "mirror", 9),
    AchievementDefinition("REPEATED_PATTERN", "Pattern Reader", "Find 5 plates with repeated patterns.", "trait_repeat", 5, 600, "repeat", 10),
    # --- rarity hunters
    AchievementDefinition("RARE_HUNTER", "Rare Hunter", "Collect 5 Rare plates.", "rarity_rare", 5, 400, "gem", 11),
    AchievementDefinition("EPIC_HUNTER", "Epic Hunter", "Collect 3 Epic plates.", "rarity_epic", 3, 1200, "gem", 12),
    AchievementDefinition("LEGENDARY_HUNTER", "Legendary Hunter", "Collect your first Legendary plate.", "rarity_legendary", 1, 4000, "crown", 13),
    AchievementDefinition("MYTHIC_HUNTER", "Mythic Hunter", "Collect your first Mythic plate.", "rarity_mythic", 1, 15000, "crown", 14),
    AchievementDefinition("SECRET_FINDER", "Secret Finder", "Discover a Secret plate.", "secret", 1, 50000, "eye", 15),
    # --- collection size
    AchievementDefinition("PLATES_100", "Century", "Collect 100 unique plates.", "plates", 100, 2500, "stack", 16),
    AchievementDefinition("PLATES_500", "Plate Hoarder", "Collect 500 unique plates.", "plates", 500, 12000, "stack", 17),
    AchievementDefinition("PLATES_1000", "NUMORA Vault", "Collect 1000 unique plates.", "plates", 1000, 40000, "stack", 18),
    # --- first discoveries
    AchievementDefinition("FIRST_DISCOVERY", "World First", "Be the first to discover a plate.", "first_discoveries", 1, 300, "star", 19),
    AchievementDefinition("DISCOVERIES_10", "Pioneer", "Make 10 world-first discoveries.", "first_discoveries", 10, 6000, "star", 20),
    # --- activity
    AchievementDefinition("ROLL_100", "Roller I", "Perform 100 rolls.", "total_rolls", 100, 500, "dice", 21),
    AchievementDefinition("ROLL_1000", "Roller II", "Perform 1000 rolls.", "total_rolls", 1000, 5000, "dice", 22),
    AchievementDefinition("OPEN_10_PACKS", "Pack Opener", "Open 10 packs.", "packs_opened", 10, 400, "package", 23),
    AchievementDefinition("STREAK_7", "Week Streak", "Claim daily rewards 7 days in a row.", "streak", 7, 1000, "flame", 24),
    AchievementDefinition("INVITE_1", "Recruiter", "Activate your first referral.", "referrals", 1, 300, "users", 25),
    AchievementDefinition("INVITE_10", "Ambassador", "Activate 10 referrals.", "referrals", 10, 3000, "users", 26),
    AchievementDefinition("CHALLENGE_5", "Duelist", "Complete 5 challenges.", "challenges_completed", 5, 900, "swords", 27),
    AchievementDefinition("SHARE_5", "Show Off", "Share 5 results.", "shares", 5, 200, "share", 28),
)


def achievement_by_code(code: str) -> AchievementDefinition | None:
    return next((item for item in ACHIEVEMENT_DEFINITIONS if item.code == code), None)
