"""Payment, premium and analytics request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProductItem(BaseModel):
    code: str
    name: str
    description: str
    stars_price: int
    grant_type: str


class InvoiceRequest(BaseModel):
    product_code: str = Field(min_length=1, max_length=48)


class InvoiceResponse(BaseModel):
    success: bool = True
    payment_id: int
    provider: str
    product_code: str
    amount: int
    currency: str
    status: str
    invoice_link: str | None = None
    mock_confirm_url: str | None = None


class MockConfirmRequest(BaseModel):
    payment_id: int = Field(gt=0)


class PaymentItem(BaseModel):
    id: int
    provider: str
    product_code: str
    amount: int
    currency: str
    status: str
    granted: bool
    created_at: str | None = None
    paid_at: str | None = None


class PremiumStatusResponse(BaseModel):
    active: bool
    tier: str | None = None
    expires_at: str | None = None
    perks: list[str] = Field(default_factory=list)
    daily_rolls_bonus: int = 0
    duplicate_multiplier: float = 1.0
    unlocked_containers: list[str] = Field(default_factory=list)


class AnalyticsEventRequest(BaseModel):
    name: str = Field(min_length=1, max_length=48)
    props: dict[str, Any] = Field(default_factory=dict)


class PremiumGrantRequest(BaseModel):
    user_id: int = Field(gt=0)
    days: int = Field(default=30, gt=0, le=3650)
    tier: str = Field(default="PRO", max_length=16)


class AdminCoinAdjustRequest(BaseModel):
    user_id: int = Field(gt=0)
    delta: int = Field(description="Signed COINS adjustment.")
    reason: str = Field(default="manual adjustment", max_length=255)


class AdminUserItem(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    display_name: str
    role: str
    is_banned: bool
    coins: int
    total_rolls: int
    unique_numbers: int
    best_value: int
    created_at: str | None = None


class AdminStatsResponse(BaseModel):
    users_total: int
    users_new_today: int
    rolls_total: int
    rolls_today: int
    numbers_discovered: int
    coins_in_circulation: int
    payments_paid: int
    revenue_stars: int
    active_season: str | None = None
    rarity_distribution: dict[str, int] = Field(default_factory=dict)


class AdminSeasonToggleRequest(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    active: bool = True


class AdminRarityConfigResponse(BaseModel):
    weights: dict[str, float]
    source: str
