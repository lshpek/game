"""Authentication request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TelegramAuthRequest(BaseModel):
    """Payload sent by the Mini App after ``Telegram.WebApp.initData`` is read."""

    init_data: str = Field(min_length=1, max_length=8192)

    @field_validator("init_data")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("init_data must not be blank")
        return value


class DevAuthRequest(BaseModel):
    """Local development login (rejected outside development/test)."""

    telegram_id: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=64)
    first_name: str = Field(default="Dev", max_length=128)
    start_param: str | None = Field(default=None, max_length=64)


class PremiumState(BaseModel):
    active: bool = False
    tier: str | None = None
    expires_at: str | None = None
    perks: list[str] = Field(default_factory=list)


class CollectorLevelState(BaseModel):
    level: int = 1
    title_en: str = "Rookie"
    title_ru: str = "Новичок"
    xp: int = 0
    xp_into_level: int = 0
    xp_for_level: int = 0
    progress: float = 0.0


class UserSummary(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    first_name: str = ""
    last_name: str = ""
    display_name: str
    photo_url: str | None = None
    language_code: str | None = None
    role: str
    is_admin: bool = False
    is_banned: bool = False

    # --- economy (user-facing name is NUMORA) ---
    coins: int = 0
    total_earned: int = 0
    total_spent: int = 0

    # --- activity ---
    total_rolls: int = 0
    containers_opened: int = 0

    # --- collection ---
    plates_count: int = 0
    countries_count: int = 0
    regions_count: int = 0
    first_discoveries_count: int = 0
    duplicates_sold_count: int = 0
    collection_progress: float = 0.0
    collection_target: int = 0
    collector_level: CollectorLevelState = Field(default_factory=CollectorLevelState)

    # --- best find ---
    best_value: int = 0
    best_rarity: str | None = None
    best_collector_value: int = 0
    best_plate_id: int | None = None

    # --- social ---
    referrals_count: int = 0
    shares_count: int = 0
    challenges_completed: int = 0

    # --- daily ---
    current_streak: int = 0
    longest_streak: int = 0
    rolls_remaining: int = 0
    daily_allowance: int = 0
    daily_resets_at: str | None = None
    can_claim_daily: bool = False

    # --- entitlements and cosmetics ---
    premium: PremiumState = Field(default_factory=PremiumState)
    supporter: bool = False
    season_pass_active: bool = False
    equipped_title: str | None = None
    equipped_cosmetics: dict[str, str] = Field(default_factory=dict)

    created_at: str | None = None
    last_seen_at: str | None = None

    # --- legacy aliases kept for older clients ---
    unique_numbers: int = 0
    best_plate_text: str = ""


class AuthResponse(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_new_user: bool
    user: UserSummary
    start_context: dict[str, object] = Field(default_factory=dict)
