"""Roll, container and daily response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import AchievementBadge
from app.schemas.number import NumberCard


class RollResponse(BaseModel):
    success: bool = True
    roll_id: int
    number: NumberCard
    rarity: str
    natural_rarity: str
    luck_rarity: str
    value: int = Field(description="Server-computed COINS value of the rolled number.")
    is_duplicate: bool
    is_first_discovery: bool
    coins_awarded: int
    balance: int
    rolls_remaining: int
    conversion_value: int
    unlocked_achievements: list[AchievementBadge] = Field(default_factory=list)
    replayed: bool = False
    share_start_param: str


class RollHistoryItem(BaseModel):
    roll_id: int
    number: str
    rarity: str
    value: int
    coins_awarded: int
    is_duplicate: bool
    created_at: str


class DailyStatusResponse(BaseModel):
    rolls_remaining: int
    daily_allowance: int
    resets_at: str
    streak: int
    can_claim: bool
    claim_reward_coins: int


class DailyClaimResponse(BaseModel):
    success: bool = True
    coins_granted: int
    rolls_granted: int
    streak: int
    balance: int
    unlocked_achievements: list[AchievementBadge] = Field(default_factory=list)


class ContainerCard(BaseModel):
    code: str
    name: str
    description: str
    price: int
    minimum_rarity: str
    rarity_weights: dict[str, float] = Field(default_factory=dict)
    accent: str
    animation: str
    premium_only: bool = False
    locked: bool = False
    affordable: bool = False
    granted_by_premium: bool = False


class ContainerOpenRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class ContainerOpenResponse(BaseModel):
    success: bool = True
    opening_id: int
    container: str
    number: NumberCard
    is_duplicate: bool
    value: int
    balance: int
    conversion_value: int
    unlocked_achievements: list[AchievementBadge] = Field(default_factory=list)
    replayed: bool = False
