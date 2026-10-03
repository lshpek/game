"""Challenge endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.social import ChallengeCreateRequest, ChallengeItem
from app.services.challenges import ChallengeService

router = APIRouter(prefix="/challenges", tags=["challenges"])


def _with_link(payload: dict[str, object]) -> ChallengeItem:
    code = str(payload["code"])
    payload["link"] = settings.telegram_mini_app_link(f"challenge_{code}")
    return ChallengeItem(**payload)  # type: ignore[arg-type]


@router.get("", response_model=list[ChallengeItem], summary="Challenge history for the current user")
def list_challenges(
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChallengeItem]:
    service = ChallengeService(db, settings)
    db.commit()
    return [_with_link(service.serialize(row)) for row in service.list_for_user(user.id, limit=limit)]


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
    service = ChallengeService(db, settings)
    challenge = service.create(user, number_value=payload.number)
    return _with_link(service.serialize(challenge))


@router.get("/{code}", response_model=ChallengeItem, summary="Public view of a challenge")
def get_challenge(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeItem:
    service = ChallengeService(db, settings)
    challenge = service.get_by_code(code)
    db.commit()
    if challenge.opponent_id is None and challenge.challenger_id != user.id:
        return _with_link(service.serialize_public(challenge))
    return _with_link(service.serialize(challenge))


@router.post(
    "/{code}/accept",
    response_model=ChallengeItem,
    dependencies=[Depends(rate_limit("referral", "rate_limit_referral"))],
    summary="Accept a challenge with your latest roll",
)
def accept_challenge(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeItem:
    service = ChallengeService(db, settings)
    challenge = service.accept(user, code)
    return _with_link(service.serialize(challenge))
