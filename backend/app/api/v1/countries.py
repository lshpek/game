"""Country endpoints: the atlas, the selector, and the active-country context.

The selector is a first-class API rather than a dropdown over the roll endpoint:

``GET /countries``
    Searchable, paginated atlas with the playable/locked split.
``GET /countries/active``
    The player's authoritative selection plus the world totals.
``POST /countries/active``
    Validate and store the selection. The backend owns this decision.
``GET /countries/{code}``
    One country, by ISO alpha-3 or alpha-2.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.db.session import get_db
from app.models.user import User
from app.services import countries as country_service

router = APIRouter(tags=["countries"])


class ActiveCountryRequest(BaseModel):
    """Change the player's selected world. ``null`` means "the whole world"."""

    code: str | None = Field(default=None, max_length=8)


@router.get("/countries")
def list_countries(
    search: str | None = Query(default=None, max_length=64),
    region: str | None = Query(default=None, max_length=24),
    playable_only: bool = Query(default=False),
    limit: int = Query(default=60, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """The country atlas. Read-only, so it is not rate limited like a write."""
    page = country_service.list_countries(
        db,
        search=search,
        region=region,
        playable_only=playable_only,
        limit=limit,
        offset=offset,
    )
    progress = country_service.progress_map(db, user.id)
    items = []
    for raw in page.items:
        entry = dict(raw)
        entry["collected"] = progress.get(str(entry["code"]), {}).get("collected", 0)
        items.append(entry)
    active = country_service.active_country(db, user)
    return {
        "items": items,
        "total": page.total,
        "playable_total": page.playable_total,
        "locked_total": page.locked_total,
        "region_groups": page.region_groups,
        "query": page.query,
        "offset": page.offset,
        "limit": limit,
        "active_code": active.code if active else None,
    }


@router.get("/countries/active")
def get_active_country(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """The player's authoritative selection and the world totals."""
    active = country_service.active_country(db, user)
    page = country_service.list_countries(db, limit=1)
    return {
        "country": (
            country_service.card(db, active, user_id=user.id, is_active=True) if active else None
        ),
        "code": active.code if active else None,
        "playable_total": page.playable_total,
        "locked_total": page.locked_total,
    }


@router.post("/countries/active")
def set_active_country(
    payload: ActiveCountryRequest = Body(default_factory=ActiveCountryRequest),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = Depends(rate_limit("country_change", "rate_limit_rolls_per_minute")),
) -> dict[str, object]:
    """Change the active country.

    The server validates the code: an unknown or locked country is rejected with a
    clear error instead of being stored and failing later during a roll.
    """
    country = country_service.set_active_country(db, user, payload.code)
    db.commit()
    return {
        "country": (
            country_service.card(db, country, user_id=user.id, is_active=True) if country else None
        ),
        "code": country.code if country else None,
    }


@router.get("/countries/{code}")
def get_country(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """One country by ISO alpha-3 or alpha-2 code."""
    from app.core.errors import NotFoundError

    country = country_service.resolve(db, code)
    if country is None or not country.is_active:
        raise NotFoundError("Country not found.", code="COUNTRY_NOT_FOUND")
    active = country_service.active_country(db, user)
    return country_service.card(
        db, country, user_id=user.id, is_active=bool(active and active.id == country.id)
    )


__all__ = ["ActiveCountryRequest", "router"]