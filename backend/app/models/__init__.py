"""ORM model package - importing it registers every table on ``Base.metadata``."""

from app.models.analytics import AnalyticsEvent, IdempotencyRecord
from app.models.container import Container, ContainerOpening
from app.models.enums import (
    AnalyticsEventName,
    ChallengeStatus,
    EntitlementTier,
    GrantType,
    LeaderboardCategory,
    PaymentProvider,
    PaymentStatus,
    ReferralStatus,
    RollSource,
    TransactionType,
    UserRole,
)
from app.models.number import Discovery, Number, UserNumber
from app.models.payment import Payment, PremiumEntitlement, Product
from app.models.progression import Achievement, DailyReward, Season, UserAchievement
from app.models.roll import Roll
from app.models.social import Challenge, Referral, ShareEvent
from app.models.user import User, Wallet, WalletTransaction

__all__ = [
    "Achievement",
    "AnalyticsEvent",
    "AnalyticsEventName",
    "Challenge",
    "ChallengeStatus",
    "Container",
    "ContainerOpening",
    "DailyReward",
    "Discovery",
    "EntitlementTier",
    "GrantType",
    "IdempotencyRecord",
    "LeaderboardCategory",
    "Number",
    "Payment",
    "PaymentProvider",
    "PaymentStatus",
    "PremiumEntitlement",
    "Product",
    "Referral",
    "ReferralStatus",
    "Roll",
    "RollSource",
    "Season",
    "ShareEvent",
    "TransactionType",
    "User",
    "UserAchievement",
    "UserNumber",
    "UserRole",
    "Wallet",
    "WalletTransaction",
]
