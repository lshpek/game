"""Leaderboard, achievements and season endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.social import AchievementItem, LeaderboardBundle, LeaderboardResponse, SeasonItem
from app.services.achievements import AchievementService
from app.services.leaderboards import LeaderboardService
from app.services.seasons import SeasonService

router = APIRouter(tags=["ranking"])


@router.get("/leaderboard", response_model=LeaderboardResponse, summary="Single leaderboard board")
def leaderboard(
    category: str = Query(default="VALUE", pattern="^(VALUE|RARITY|COLLECTION|ROLLS)$"),
    period: str = Query(default="daily", pattern="^(daily|weekly|alltime)$"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardResponse:
    service = LeaderboardService(db)
    data = service.leaderboard(category=category, period=period, limit=limit)
    return LeaderboardResponse(**data, you=service.rank_of(user.id, category=category, period=period))  # type: ignore[arg-type]


@router.get("/leaderboard/all", response_model=LeaderboardBundle, summary="All boards for one period")
def leaderboard_all(
    period: str = Query(default="daily", pattern="^(daily|weekly|alltime)$"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardBundle:
    service = LeaderboardService(db)
    boards: dict[str, LeaderboardResponse] = {}
    for category in ("VALUE", "RARITY", "COLLECTION", "ROLLS"):
        data = service.leaderboard(category=category, period=period, limit=limit)
        boards[category] = LeaderboardResponse(
            **data,
            you=service.rank_of(user.id, category=category, period=period),  # type: ignore[arg-type]
        )
    return LeaderboardBundle(boards=boards)


@router.get("/achievements", response_model=list[AchievementItem], summary="Achievement catalogue with progress")
def achievements(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AchievementItem]:
    rows = AchievementService(db).list_for_user(user)
    db.commit()
    return [AchievementItem(**row) for row in rows]  # type: ignore[arg-type]


@router.get("/seasons", response_model=list[SeasonItem], summary="All seasons")
def seasons(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[SeasonItem]:
    service = SeasonService(db)
    return [SeasonItem(**service.serialize(row)) for row in service.list_all()]  # type: ignore[arg-type]


@router.get("/seasons/active", response_model=SeasonItem | None, summary="Currently active season")
def active_season(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SeasonItem | None:
    service = SeasonService(db)
    season = service.active()
    if season is None:
        return None
    return SeasonItem(**service.serialize(season))  # type: ignore[arg-type]
