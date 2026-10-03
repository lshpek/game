"""Collection, number detail, duplicate conversion and sharing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.number import (
    CollectionResponse,
    ConvertAllResponse,
    DuplicateConversionResponse,
    NumberDetailResponse,
    ShareResponse,
)
from app.services.users import TOTAL_NUMBERS, UserService

router = APIRouter(tags=["collection"])


@router.get("/collection", response_model=CollectionResponse, summary="Paginated, filterable collection")
def collection(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    rarity: str | None = Query(default=None, max_length=16),
    search: str | None = Query(default=None, max_length=32),
    sort: str = Query(default="recent", pattern="^(recent|value|number|duplicates)$"),
    duplicates_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionResponse:
    service = UserService(db, settings)
    page_result = service.collection(
        user,
        page=page,
        page_size=page_size,
        rarity=rarity,
        search=search,
        sort=sort,
        only_duplicates=duplicates_only,
    )
    return CollectionResponse(
        items=page_result.items,  # type: ignore[arg-type]
        page=page_result.page,
        page_size=page_result.page_size,
        total=page_result.total,
        has_more=page_result.has_more,
        rarity_breakdown=service.rarity_breakdown(user),
        progress=round(int(user.unique_numbers_count) / TOTAL_NUMBERS, 6),
        target=TOTAL_NUMBERS,
    )


@router.get("/numbers/{value}", response_model=NumberDetailResponse, summary="Number detail card")
def number_detail(
    value: str = Path(min_length=1, max_length=4),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NumberDetailResponse:
    payload = UserService(db, settings).number_detail(user, value)
    return NumberDetailResponse(**payload)  # type: ignore[arg-type]


@router.post(
    "/numbers/{value}/convert",
    response_model=DuplicateConversionResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Convert one duplicate copy into COINS",
)
def convert_duplicate(
    value: str = Path(min_length=1, max_length=4),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DuplicateConversionResponse:
    result = UserService(db, settings).convert_duplicate(user, value)
    return DuplicateConversionResponse(**result)  # type: ignore[arg-type]


@router.post(
    "/collection/convert-all",
    response_model=ConvertAllResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Convert every duplicate copy into COINS",
)
def convert_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ConvertAllResponse:
    result = UserService(db, settings).convert_all_duplicates(user)
    return ConvertAllResponse(**result)  # type: ignore[arg-type]


@router.post(
    "/numbers/{value}/share",
    response_model=ShareResponse,
    dependencies=[Depends(rate_limit("share", "rate_limit_default"))],
    summary="Record a share and return the deep link",
)
def share_number(
    value: str = Path(min_length=1, max_length=4),
    channel: str = Query(default="telegram", max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareResponse:
    result = UserService(db, settings).record_share(user, value, channel=channel)
    return ShareResponse(**result)  # type: ignore[arg-type]


@router.get("/user/top", summary="Rarest and highest-value owned numbers")
def top_items(
    limit: int = Query(default=3, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return UserService(db, settings).top_items(user, limit=limit)


@router.get("/user/achievements", summary="Achievement progress for the current user")
def user_achievements(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    from app.services.achievements import AchievementService

    return AchievementService(db).list_for_user(user)
