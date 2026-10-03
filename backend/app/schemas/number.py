"""Number-related response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NumberCard(BaseModel):
    """Canonical representation of a number shown across the app."""

    number: str = Field(min_length=4, max_length=4, description="Zero-padded 4-digit value.")
    rarity: str
    value: int
    traits: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    story: str = ""
    is_special: bool = False
    discovery_count: int = 0
    duplicate_count: int = 0
    owned: bool = False
    acquired_at: str | None = None
    first_discovered_at: str | None = None
    undiscovered: bool = False


class CollectionResponse(BaseModel):
    items: list[NumberCard]
    page: int
    page_size: int
    total: int
    has_more: bool
    rarity_breakdown: dict[str, int] = Field(default_factory=dict)
    progress: float = 0.0
    target: int = 10_000


class DuplicateConversionResponse(BaseModel):
    number: str
    coins_gained: int
    duplicates_left: int
    balance: int


class ConvertAllResponse(BaseModel):
    coins_gained: int
    converted: int
    balance: int


class ShareResponse(BaseModel):
    number: str
    rarity: str
    value: int
    start_param: str
    mini_app_link: str


class NumberDetailResponse(NumberCard):
    pass
