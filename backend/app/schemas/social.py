"""Social (referral, challenge, leaderboard) response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlayerRef(BaseModel):
    display_name: str
    username: str | None = None
    photo_url: str | None = None


class ReferralItem(BaseModel):
    status: str
    username: str | None = None
    display_name: str
    photo_url: str | None = None
    reward_coins: int = 0
    created_at: str
    activated_at: str | None = None


class ReferralSummary(BaseModel):
    referral_code: str
    referral_link: str
    total: int
    activated: int
    pending: int
    coins_earned: int
    reward_coins: int
    reward_rolls: int
    items: list[ReferralItem] = Field(default_factory=list)


class ChallengeCreateRequest(BaseModel):
    number: str | None = Field(default=None, min_length=1, max_length=4)


class ChallengeItem(BaseModel):
    code: str
    status: str
    challenger: PlayerRef | None = None
    opponent: PlayerRef | None = None
    challenger_number: str | None = None
    challenger_rarity: str | None = None
    challenger_value: int | None = None
    opponent_number: str | None = None
    opponent_rarity: str | None = None
    opponent_value: int | None = None
    winner_id: int | None = None
    expires_at: str | None = None
    completed_at: str | None = None
    link: str | None = None


class LeaderboardEntry(BaseModel):
    user_id: int
    display_name: str
    username: str | None = None
    photo_url: str | None = None
    score: int
    rolls: int = 0


class LeaderboardResponse(BaseModel):
    category: str
    period: str
    label: str
    entries: list[LeaderboardEntry] = Field(default_factory=list)
    you: int | None = None


class LeaderboardBundle(BaseModel):
    """Every category for the requested period (each board carries its own period)."""

    boards: dict[str, LeaderboardResponse]


class AchievementItem(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    threshold: int
    progress: int
    reward_coins: int
    unlocked: bool
    unlocked_at: str | None = None


class SeasonItem(BaseModel):
    code: str
    name: str
    description: str
    start_date: str | None = None
    end_date: str | None = None
    is_active: bool
    is_over: bool
    special_numbers: list[str] = Field(default_factory=list)
    rewards: dict[str, object] = Field(default_factory=dict)
