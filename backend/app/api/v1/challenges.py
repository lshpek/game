"""Plate challenge endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.plate_challenges import PlateChallengeService

router = APIRouter(prefix="/challenges", tags=["challenges"])


class ChallengeCreateRequest(BaseModel):
    """Only an optional plate id - never a value, rarity or score."""

    plate_id: int | None = Field(default=None, ge=1)


class ChallengeItem(BaseModel):
    code: str
    status: str
    challenger: dict[str, Any] | None = None
    opponent: dict[str, Any] | None = None
    challenger_plate_id: int | None = None
    challenger_plate_text: str | None = None
    challenger_rarity: str | None = None
    challenger_score: int = 0
    opponent_plate_id: int | None = None
    opponent_plate_text: str | None = None
    opponent_rarity: str | None = None
    opponent_score: int | None = None
    winner_id: int | None = None
    reward_coins: int = 0
    expires_at: str | None = None
    completed_at: str | None = None
    link: str = ""


def _with_link(payload: dict[str, object]) -> ChallengeItem:
    code = str(payload["code"])
    payload["link"] = settings.telegram_mini_app_link(f"challenge_{code}")
    return ChallengeItem(**payload)  # type: ignore[arg-type]


@router.get("", response_model=list[ChallengeItem], summary="Challenge history")
def list_challenges(
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChallengeItem]:
    service = PlateChallengeService(db, settings)
    rows = service.list_for_user(user.id, limit=limit)
    db.commit()
    return [_with_link(service.serialize(row)) for row in rows]


@router.post(
    "",
    response_model=ChallengeItem,
    dependencies=[Depends(rate_limit("referral", "rate_limit_referral"))],
    summary="Create a challenge deep link",
)
def create_challenge(
    payload: ChallengeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeItem:
    service = PlateChallengeService(db, settings)
    challenge = service.create(user, plate_id=payload.plate_id)
    return _with_link(service.serialize(challenge))


@router.get("/{code}", response_model=ChallengeItem, summary="Public view of a challenge")
def get_challenge(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeItem:
    service = PlateChallengeService(db, settings)
    challenge = service.get_by_code(code)
    db.commit()
    if challenge.opponent_id is None and challenge.challenger_id != user.id:
        return _with_link(service.serialize_public(challenge))
    return _with_link(service.serialize(challenge))


@router.post(
    "/{code}/accept",
    response_model=ChallengeItem,
    dependencies=[Depends(rate_limit("referral", "rate_limit_referral"))],
    summary="Accept a challenge with your latest plate",
)
def accept_challenge(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeItem:
    service = PlateChallengeService(db, settings)
    challenge = service.accept(user, code)
    return _with_link(service.serialize(challenge))