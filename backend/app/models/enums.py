"""String enums shared by models, services and schemas.

Stored as plain ``VARCHAR`` so the schema behaves identically on SQLite and
PostgreSQL (native ENUM types differ and complicate migrations).
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class ChallengeStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    DECLINED = "DECLINED"


class AdminCategory(StrEnum):
    """Grouping used by the admin audit log and its Telegram viewer."""

    ECONOMY = "ECONOMY"
    ROLLS = "ROLLS"
    PROGRESSION = "PROGRESSION"
    MISSIONS = "MISSIONS"
    ACHIEVEMENTS = "ACHIEVEMENTS"
    PLATES = "PLATES"
    PREMIUM = "PREMIUM"
    COSMETICS = "COSMETICS"
    REWARDS = "REWARDS"
    TEST_LAB = "TEST_LAB"
    MODERATION = "MODERATION"
    WORLD = "WORLD"
    SYSTEM = "SYSTEM"


class AdminAction(StrEnum):
    """Stable action codes written to ``admin_audit_logs.action``.

    They are part of the internal tooling contract: the Telegram panel, the audit
    viewer and future LiveOps scripts all speak these codes, never free text.
    """

    COIN_ADJUST = "ADMIN_COIN_ADJUST"
    BALANCE_SET = "ADMIN_BALANCE_SET"
    ROLL_GRANT = "ADMIN_ROLL_GRANT"
    ROLLS_RESET_DAILY = "ADMIN_ROLLS_RESET_DAILY"
    PREMIUM_GRANT = "ADMIN_PREMIUM_GRANT"
    PREMIUM_REVOKE = "ADMIN_PREMIUM_REVOKE"
    COSMETIC_GRANT = "ADMIN_COSMETIC_GRANT"
    COSMETIC_EQUIP = "ADMIN_COSMETIC_EQUIP"
    COSMETIC_UNEQUIP = "ADMIN_COSMETIC_UNEQUIP"
    TITLE_GRANT = "ADMIN_TITLE_GRANT"
    XP_CHANGE = "ADMIN_XP_CHANGE"
    LEVEL_SET = "ADMIN_LEVEL_SET"
    STREAK_SET = "ADMIN_STREAK_SET"
    PROGRESSION_RESET = "ADMIN_PROGRESSION_RESET"
    MISSION_PROGRESS = "ADMIN_MISSION_PROGRESS"
    MISSION_COMPLETE = "ADMIN_MISSION_COMPLETE"
    MISSION_RESET = "ADMIN_MISSION_RESET"
    ACHIEVEMENT_GRANT = "ADMIN_ACHIEVEMENT_GRANT"
    ACHIEVEMENT_REVOKE = "ADMIN_ACHIEVEMENT_REVOKE"
    PLATE_GRANT = "ADMIN_PLATE_GRANT"
    FIRST_DISCOVERY = "ADMIN_FIRST_DISCOVERY"
    FORCE_ROLL = "ADMIN_FORCE_ROLL"
    SIMULATE_ROLL = "ADMIN_SIMULATE_ROLL"
    FORCE_PLATE = "ADMIN_FORCE_PLATE"
    REWARD_GRANT = "ADMIN_REWARD_GRANT"
    BAN = "ADMIN_BAN"
    UNBAN = "ADMIN_UNBAN"
    SEASON_CHANGE = "ADMIN_SEASON_CHANGE"
    EVENT_CHANGE = "ADMIN_EVENT_CHANGE"
    COUNTRY_CHANGE = "ADMIN_COUNTRY_CHANGE"


class TransactionType(StrEnum):
    DAILY_REWARD = "DAILY_REWARD"
    ROLL_REWARD = "ROLL_REWARD"
    DUPLICATE_CONVERSION = "DUPLICATE_CONVERSION"
    CONTAINER_PURCHASE = "CONTAINER_PURCHASE"
    REFERRAL_REWARD = "REFERRAL_REWARD"
    ACHIEVEMENT_REWARD = "ACHIEVEMENT_REWARD"
    CHALLENGE_REWARD = "CHALLENGE_REWARD"
    PREMIUM_PURCHASE = "PREMIUM_PURCHASE"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"
    MISSION_REWARD = "MISSION_REWARD"
    ALBUM_REWARD = "ALBUM_REWARD"
    EVENT_REWARD = "EVENT_REWARD"
    SEASON_REWARD = "SEASON_REWARD"
    COSMETIC_PURCHASE = "COSMETIC_PURCHASE"
    BAD_LUCK_REWARD = "BAD_LUCK_REWARD"


class GrantType(StrEnum):
    """What a Stars purchase grants.

    Kept flat and configurable, and mirrored by
    :data:`app.game.products.GRANT_TYPES` so the catalogue and the grant
    implementation cannot drift apart. The two definitions used to disagree: the
    narrower copy below shadowed this one, which is how supporter tiers, bundles
    and the season pass ended up unfulfillable.
    """

    COINS = "COINS"
    ROLLS = "ROLLS"
    PREMIUM = "PREMIUM"
    SUPPORTER = "SUPPORTER"
    COSMETIC = "COSMETIC"
    SEASON_PASS = "SEASON_PASS"


class EntitlementTier(StrEnum):
    PRO = "PRO"
    SUPPORTER = "SUPPORTER"


class RollSource(StrEnum):
    FREE = "FREE"
    DAILY = "DAILY"
    PAID = "PAID"
    REFERRAL_BONUS = "REFERRAL_BONUS"
    ADMIN = "ADMIN"


class ReferralStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVATED = "ACTIVATED"
    REJECTED = "REJECTED"


class PaymentProvider(StrEnum):
    TELEGRAM_STARS = "TELEGRAM_STARS"
    MOCK = "MOCK"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class LeaderboardCategory(StrEnum):
    """Leaderboards reward collecting, never wallet balance."""

    COLLECTION = "COLLECTION"
    COUNTRIES = "COUNTRIES"
    FIRST_DISCOVERIES = "FIRST_DISCOVERIES"
    RARITY = "RARITY"
    SEASON = "SEASON"
    ROLLS = "ROLLS"
    # Legacy alias kept so old links keep working.
    VALUE = "COLLECTION"


class AnalyticsEventName(StrEnum):
    APP_OPEN = "app_open"
    ROLL_STARTED = "roll_started"
    ROLL_COMPLETED = "roll_completed"
    #: The product metric that matters most: how often a player rolls again.
    ROLL_AGAIN_CLICKED = "roll_again_clicked"
    ROLL_ORDINAL = "roll_ordinal"
    REVEAL_SHOWN = "reveal_shown"
    REVEAL_SKIPPED = "reveal_skipped"
    COLLECTION_OPENED = "collection_opened"
    SELL_CLICKED = "sell_clicked"
    SELL_COMPLETED = "sell_completed"
    SELL_FAILED = "sell_failed"
    SET_PROGRESS = "set_progress"
    SET_COMPLETED = "set_completed"
    OPERATOR_DISCOVERED = "operator_discovered"
    NEW_COUNTRY = "new_country"
    NEW_REGION = "new_region"
    FIRST_ROLL = "first_roll"
    ROLL = "roll"
    RARE_FOUND = "rare_found"
    LEGENDARY_FOUND = "legendary_found"
    MYTHIC_FOUND = "mythic_found"
    SECRET_FOUND = "secret_found"
    FIRST_DISCOVERY = "first_discovery"
    PLATE_COLLECTED = "plate_collected"
    PLATE_DUPLICATE = "plate_duplicate"
    PLATE_SOLD = "plate_sold"
    PLATE_FAVORITED = "plate_favorited"
    CONTAINER_OPEN = "container_open"
    SHARE_CLICKED = "share_clicked"
    SHARE = "share"
    SHARE_COMPLETED = "share_completed"
    REFERRAL_CLICK = "referral_click"
    REFERRAL_ACTIVATED = "referral_activated"
    COUNTRY_OPENED = "country_opened"
    ALBUM_COMPLETED = "album_completed"
    MISSION_COMPLETED = "mission_completed"
    DAILY_CLAIMED = "daily_claimed"
    STORE_OPENED = "store_opened"
    PRODUCT_VIEWED = "product_viewed"
    INVOICE_CREATED = "invoice_created"
    PURCHASE_SUCCESS = "purchase_success"
    SUPPORT_PURCHASE = "support_purchase"
    COSMETIC_EQUIPPED = "cosmetic_equipped"
    SEASON_PASS_OPENED = "season_pass_opened"
    PREMIUM_ACTIVATED = "premium_activated"
    CHALLENGE_CREATED = "challenge_created"
    CHALLENGE_COMPLETED = "challenge_completed"
    PREMIUM_PURCHASE = "premium_purchase"
    DAILY_CLAIM = "daily_claim"
