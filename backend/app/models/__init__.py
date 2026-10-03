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
from app.models.plates import (
    Album,
    Country,
    Plate,
    PlateAlbum,
    PlateChallenge,
    PlateDiscovery,
    PlateTemplate,
    Region,
    UserPlate,
)
from app.models.progression import Achievement, DailyReward, Season, UserAchievement
from app.models.roll import Roll
from app.models.social import Challenge, Referral, ShareEvent
from app.models.user import User, Wallet, WalletTransaction

__all__ = [
    "Achievement",
    "Album",
    "AnalyticsEvent",
    "AnalyticsEventName",
    "Challenge",
    "ChallengeStatus",
    "Container",
    "ContainerOpening",
    "Country",
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
    "Plate",
    "PlateAlbum",
    "PlateChallenge",
    "PlateDiscovery",
    "PlateTemplate",
    "PremiumEntitlement",
    "Product",
    "Referral",
    "ReferralStatus",
    "Region",
    "Roll",
    "RollSource",
    "Season",
    "ShareEvent",
    "TransactionType",
    "User",
    "UserAchievement",
    "UserNumber",
    "UserPlate",
    "UserRole",
    "Wallet",
    "WalletTransaction",
]
