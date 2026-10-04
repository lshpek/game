"""Request/response models for ``/api/admin/bot/*``.

Strongly typed on purpose: the Telegram panel is a machine client, so every
mutation body names its target, its reason and its operation id explicitly, and
pydantic rejects anything out of range before a service is touched.

Shared conventions:

* ``operation_id`` is the idempotency key. It is mandatory on every mutation and
  becomes the unique key of the audit row, so a duplicated Telegram callback
  replays the first result instead of granting twice.
* ``reason`` is mandatory on every mutation: an admin action without a reason is
  not auditable.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Reused bounds keep the panel honest even if it is bypassed.
MAX_AMOUNT = 100_000_000
MAX_REASON = 240
MAX_LABEL = 64


class MutationBase(BaseModel):
    """Fields every admin mutation carries."""

    operation_id: str = Field(min_length=8, max_length=64)
    reason: str = Field(min_length=1, max_length=MAX_REASON)


class CoinAdjustRequest(MutationBase):
    """Signed NUMORA adjustment (``delta > 0`` credits, ``delta < 0`` debits)."""

    user_id: int = Field(gt=0)
    delta: int = Field(gt=-MAX_AMOUNT, lt=MAX_AMOUNT)


class BalanceSetRequest(MutationBase):
    user_id: int = Field(gt=0)
    target: int = Field(ge=0, le=MAX_AMOUNT)


class RollGrantRequest(MutationBase):
    user_id: int = Field(gt=0)
    amount: int = Field(gt=0, le=1000)


class RollResetRequest(MutationBase):
    user_id: int = Field(gt=0)


class XpChangeRequest(MutationBase):
    """Either a signed ``delta`` or an exact ``xp`` target, never both."""

    user_id: int = Field(gt=0)
    delta: int | None = Field(default=None, ge=-MAX_AMOUNT, lt=MAX_AMOUNT)
    xp: int | None = Field(default=None, ge=0, le=MAX_AMOUNT)


class LevelSetRequest(MutationBase):
    user_id: int = Field(gt=0)
    level: int = Field(gt=0, le=999)


class StreakSetRequest(MutationBase):
    user_id: int = Field(gt=0)
    current: int | None = Field(default=None, ge=0, le=10_000)
    longest: int | None = Field(default=None, ge=0, le=10_000)
    reset: bool = False


class ProgressionResetRequest(MutationBase):
    user_id: int = Field(gt=0)


class MissionActionRequest(MutationBase):
    user_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=48)
    action: Literal["progress", "complete", "reset"]
    amount: int = Field(default=1, ge=1, le=1000)


class AchievementActionRequest(MutationBase):
    user_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    revoke: bool = False


class CosmeticActionRequest(MutationBase):
    user_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=48)
    action: Literal["grant", "equip", "unequip"] = "grant"


class TitleGrantRequest(MutationBase):
    user_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=MAX_LABEL)


class PremiumActionRequest(MutationBase):
    user_id: int = Field(gt=0)
    days: int | None = Field(default=None, ge=1, le=3650)
    revoke: bool = False


class RewardGrantRequest(MutationBase):
    """Quick-grant menu. ``amount`` means NUMORA / rolls / XP / days."""

    user_id: int = Field(gt=0)
    kind: Literal["coins", "rolls", "xp", "premium", "cosmetic", "title", "season_pass"]
    amount: int = Field(default=0, ge=0, le=MAX_AMOUNT)
    code: str = Field(default="", max_length=MAX_LABEL)


class BanRequest(MutationBase):
    user_id: int = Field(gt=0)
    banned: bool = True


class PlateGrantRequest(MutationBase):
    user_id: int = Field(gt=0)
    plate_id: int = Field(gt=0)
    mark_first_discovery: bool = False


class FirstDiscoveryRequest(MutationBase):
    plate_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    override: bool = False


class TestRollRequest(BaseModel):
    """Shared by simulation (read-only) and the LIVE test roll."""

    country_code: str | None = Field(default=None, max_length=8)
    region_code: str | None = Field(default=None, max_length=16)
    template_code: str | None = Field(default=None, max_length=48)
    rarity: str | None = Field(default=None, max_length=16)
    preset: str | None = Field(default=None, max_length=32)
    require_trait: str | None = Field(default=None, max_length=32)


class LiveTestRollRequest(TestRollRequest, MutationBase):
    user_id: int = Field(gt=0)
    mark_first_discovery: bool = False


class ForcePlateRequest(TestRollRequest):
    plate_text: str = Field(min_length=1, max_length=32)


class ForcePlateGrantRequest(ForcePlateRequest, MutationBase):
    user_id: int | None = Field(default=None, gt=0)
    mark_first_discovery: bool = False


class CountryToggleRequest(MutationBase):
    country_id: int = Field(gt=0)
    active: bool


class EventToggleRequest(MutationBase):
    event_id: int = Field(gt=0)
    active: bool


class SeasonToggleRequest(MutationBase):
    code: str = Field(min_length=1, max_length=48)
    active: bool


class OperationResponse(BaseModel):
    """Uniform mutation envelope: enough to render the result screen."""

    success: bool = True
    replayed: bool = False
    audit_id: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AchievementActionRequest",
    "BalanceSetRequest",
    "BanRequest",
    "CoinAdjustRequest",
    "CosmeticActionRequest",
    "CountryToggleRequest",
    "EventToggleRequest",
    "FirstDiscoveryRequest",
    "ForcePlateGrantRequest",
    "ForcePlateRequest",
    "LevelSetRequest",
    "LiveTestRollRequest",
    "MissionActionRequest",
    "MutationBase",
    "OperationResponse",
    "PlateGrantRequest",
    "PremiumActionRequest",
    "ProgressionResetRequest",
    "RewardGrantRequest",
    "RollGrantRequest",
    "RollResetRequest",
    "SeasonToggleRequest",
    "StreakSetRequest",
    "TestRollRequest",
    "TitleGrantRequest",
    "XpChangeRequest",
]
