"""Shared response envelopes and pagination metadata."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable explanation.")
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Uniform error envelope returned for every failure."""

    success: bool = False
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str
    timestamp: str
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    has_more: bool


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class AchievementBadge(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    reward_coins: int
