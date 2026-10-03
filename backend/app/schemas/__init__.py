"""Pydantic request/response schemas."""

from app.schemas.auth import AuthResponse, DevAuthRequest, TelegramAuthRequest, UserSummary
from app.schemas.common import (
    AchievementBadge,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    MessageResponse,
    PageMeta,
)
from app.schemas.game import (
    ContainerCard,
    ContainerOpenRequest,
    ContainerOpenResponse,
    DailyClaimResponse,
    DailyStatusResponse,
    RollResponse,
)
from app.schemas.number import (
    CollectionResponse,
    ConvertAllResponse,
    DuplicateConversionResponse,
    NumberCard,
    ShareResponse,
)
from app.schemas.payments import (
    AnalyticsEventRequest,
    InvoiceRequest,
    InvoiceResponse,
    PaymentItem,
    PremiumStatusResponse,
    ProductItem,
)
from app.schemas.social import (
    AchievementItem,
    ChallengeCreateRequest,
    ChallengeItem,
    LeaderboardBundle,
    LeaderboardResponse,
    ReferralItem,
    ReferralSummary,
    SeasonItem,
)

__all__ = [
    "AchievementBadge",
    "AchievementItem",
    "AnalyticsEventRequest",
    "AuthResponse",
    "ChallengeCreateRequest",
    "ChallengeItem",
    "CollectionResponse",
    "ContainerCard",
    "ContainerOpenRequest",
    "ContainerOpenResponse",
    "ConvertAllResponse",
    "DailyClaimResponse",
    "DailyStatusResponse",
    "DevAuthRequest",
    "DuplicateConversionResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "InvoiceRequest",
    "InvoiceResponse",
    "LeaderboardBundle",
    "LeaderboardResponse",
    "MessageResponse",
    "NumberCard",
    "PageMeta",
    "PaymentItem",
    "PremiumStatusResponse",
    "ProductItem",
    "ReferralItem",
    "ReferralSummary",
    "RollResponse",
    "SeasonItem",
    "ShareResponse",
    "TelegramAuthRequest",
    "UserSummary",
]
