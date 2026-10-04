"""Leaderboard, achievement and season endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.achievements import AchievementService
from app.services.leaderboards import PlateLeaderboardService
from app.services.seasons import SeasonService

router = APIRouter(tags=["ranking"])

# Boards reward collecting; none of them ranks by wallet balance.
CATEGORIES = ("COLLECTION", "COUNTRIES", "FIRST_DISCOVERIES", "RARITY", "ROLLS")


class LeaderboardEntry(BaseModel):
    user_id: int
    display_name: str
    username: str | None = None
    photo_url: str | None = None
    score: int
    metric: str = "COLLECTION"


class LeaderboardResponse(BaseModel):
    category: str
    period: str
    label: str
    entries: list[LeaderboardEntry]
    you: int | None = None


class LeaderboardBundle(BaseModel):
    boards: dict[str, LeaderboardResponse]


class AchievementItem(BaseModel):
    code: str
    name: str
    description: str = ""
    icon: str = "star"
    threshold: int
    progress: int
    reward_coins: int
    unlocked: bool
    unlocked_at: str | None = None


class SeasonItem(BaseModel):
    code: str
    name: str
    description: str = ""
    start_date: str | None = None
    end_date: str | None = None
    is_active: bool
    is_over: bool
    special_numbers: list[str] = Field(default_factory=list)
    rewards: dict[str, Any] = Field(default_factory=dict)


@router.get("/leaderboard", response_model=LeaderboardResponse, summary="Single leaderboard")
def leaderboard(
    category: str = Query(default="COLLECTION"),
    period: str = Query(default="daily", pattern="^(daily|weekly|alltime)$"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardResponse:
    service = PlateLeaderboardService(db)
    resolved = category.upper() if category.upper() in CATEGORIES else "COLLECTION"
    data = service.leaderboard(category=resolved, period=period, limit=limit)
    return LeaderboardResponse(
        **data,  # type: ignore[arg-type]
        you=service.rank_of(user.id, category=resolved, period=period),
    )


@router.get("/leaderboard/all", response_model=LeaderboardBundle, summary="All boards")
def leaderboard_all(
    period: str = Query(default="daily", pattern="^(daily|weekly|alltime)$"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardBundle:
    service = PlateLeaderboardService(db)
    boards: dict[str, LeaderboardResponse] = {}
    for category in CATEGORIES:
        data = service.leaderboard(category=category, period=period, limit=limit)
        boards[category] = LeaderboardResponse(
            **data,  # type: ignore[arg-type]
            you=service.rank_of(user.id, category=category, period=period),
        )
    return LeaderboardBundle(boards=boards)


@router.get("/achievements", response_model=list[AchievementItem], summary="Achievements")
def achievements(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AchievementItem]:
    rows = AchievementService(db).list_for_user(user)
    db.commit()
    return [AchievementItem(**row) for row in rows]  # type: ignore[misc]


@router.get("/seasons", response_model=list[SeasonItem], summary="All seasons")
def seasons(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[SeasonItem]:
    service = SeasonService(db)
    return [SeasonItem(**service.serialize(row)) for row in service.list_all()]  # type: ignore[misc]


@router.get("/seasons/active", response_model=SeasonItem | None, summary="Active season")
def active_season(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SeasonItem | None:
    service = SeasonService(db)
    season = service.active()
    if season is None:
        return None
    return SeasonItem(**service.serialize(season))  # type: ignore[misc]