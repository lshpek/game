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
    """What a Stars purchase grants. Kept flat and configurable."""

    COINS = "COINS"
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


class GrantType(StrEnum):
    COINS = "COINS"
    PREMIUM = "PREMIUM"


class EntitlementTier(StrEnum):
    PRO = "PRO"


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
    FIRST_ROLL = "first_roll"
    ROLL = "roll"
    RARE_FOUND = "rare_found"
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
