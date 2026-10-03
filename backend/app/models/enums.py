"""String enums shared by models, services and schemas.

Stored as plain ``VARCHAR`` so the schema behaves identically on SQLite and
PostgreSQL (native ENUM types differ and complicate migrations).
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


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


class ChallengeStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    DECLINED = "DECLINED"


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
    VALUE = "VALUE"
    RARITY = "RARITY"
    COLLECTION = "COLLECTION"
    ROLLS = "ROLLS"


class AnalyticsEventName(StrEnum):
    APP_OPEN = "app_open"
    FIRST_ROLL = "first_roll"
    ROLL = "roll"
    RARE_FOUND = "rare_found"
    CONTAINER_OPEN = "container_open"
    SHARE = "share"
    REFERRAL_CLICK = "referral_click"
    REFERRAL_ACTIVATED = "referral_activated"
    CHALLENGE_CREATED = "challenge_created"
    CHALLENGE_COMPLETED = "challenge_completed"
    PREMIUM_PURCHASE = "premium_purchase"
    DAILY_CLAIM = "daily_claim"
