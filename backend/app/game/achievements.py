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
    AchievementDefinition("FIRST_ROLL", "First Roll", "Perform your very first roll.", "total_rolls", 1, 25, "sparkles", 1),
    AchievementDefinition("FIRST_RARE", "Rare Find", "Find a Rare number.", "rarity_rare", 1, 100, "gem", 2),
    AchievementDefinition("FIRST_EPIC", "Epic Find", "Find an Epic number.", "rarity_epic", 1, 300, "gem", 3),
    AchievementDefinition("FIRST_LEGENDARY", "Legendary Find", "Find a Legendary number.", "rarity_legendary", 1, 1000, "crown", 4),
    AchievementDefinition("FIRST_MYTHIC", "Mythic Find", "Find a Mythic number.", "rarity_mythic", 1, 5000, "crown", 5),
    AchievementDefinition("DISCOVER_SECRET", "Secret Discovered", "Be the first to uncover a Secret number.", "secret_first_discovery", 1, 25000, "eye", 6),
    AchievementDefinition("COLLECT_10", "Collector I", "Own 10 unique numbers.", "unique_numbers", 10, 150, "box", 7),
    AchievementDefinition("COLLECT_50", "Collector II", "Own 50 unique numbers.", "unique_numbers", 50, 800, "box", 8),
    AchievementDefinition("COLLECT_100", "Collector III", "Own 100 unique numbers.", "unique_numbers", 100, 2500, "box", 9),
    AchievementDefinition("ROLL_100", "Roller I", "Perform 100 rolls.", "total_rolls", 100, 500, "dice", 10),
    AchievementDefinition("ROLL_1000", "Roller II", "Perform 1000 rolls.", "total_rolls", 1000, 5000, "dice", 11),
    AchievementDefinition("OPEN_10_BOXES", "Box Opener", "Open 10 containers.", "containers_opened", 10, 400, "package", 12),
    AchievementDefinition("STREAK_7", "Week Streak", "Claim daily rewards 7 days in a row.", "streak", 7, 1000, "flame", 13),
    AchievementDefinition("INVITE_1", "Recruiter", "Activate your first referral.", "referrals", 1, 300, "users", 14),
    AchievementDefinition("INVITE_10", "Ambassador", "Activate 10 referrals.", "referrals", 10, 3000, "users", 15),
    AchievementDefinition("CHALLENGE_5", "Duelist", "Complete 5 challenges.", "challenges_completed", 5, 900, "swords", 16),
    AchievementDefinition("SHARE_5", "Show Off", "Share 5 results.", "shares", 5, 200, "share", 17),
)


def achievement_by_code(code: str) -> AchievementDefinition | None:
    return next((item for item in ACHIEVEMENT_DEFINITIONS if item.code == code), None)
