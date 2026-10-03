"""Container endpoints - results are always resolved server side."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, idempotency_key, rate_limit
from app.api.serializers import number_card
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.game import ContainerCard, ContainerOpenRequest, ContainerOpenResponse
from app.services.containers import ContainerService

router = APIRouter(prefix="/containers", tags=["containers"])


@router.get("", response_model=list[ContainerCard], summary="Available containers")
def list_containers(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ContainerCard]:
    rows = ContainerService(db, settings).list_containers(user)
    return [ContainerCard(**row) for row in rows]  # type: ignore[arg-type]


@router.post(
    "/open",
    response_model=ContainerOpenResponse,
    dependencies=[Depends(rate_limit("container", "rate_limit_roll"))],
    summary="Buy and open a container (atomic purchase + loot)",
)
def open_container(
    payload: ContainerOpenRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    key: str | None = Depends(idempotency_key),
) -> ContainerOpenResponse:
    outcome = ContainerService(db, settings).open_container(user, payload.code, idempotency_key=key)
    return ContainerOpenResponse(
        opening_id=outcome.opening.id,
        container=outcome.container.code,
        number=number_card(outcome.number, value=outcome.value),  # type: ignore[arg-type]
        is_duplicate=outcome.is_duplicate,
        value=outcome.value,
        balance=outcome.balance,
        conversion_value=outcome.conversion_value,
        unlocked_achievements=outcome.unlocked_achievements,
        replayed=outcome.replayed,
    )


@router.get("/history", summary="Recent container openings")
def container_history(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    rows = ContainerService(db, settings).history(user.id, limit=limit)
    return [
        {
            "opening_id": row.id,
            "container": row.container.code if row.container else "",
            "number": row.number.value_str if row.number else "",
            "rarity": row.rarity,
            "value": int(row.value),
            "price_paid": int(row.price_paid),
            "is_duplicate": bool(row.is_duplicate),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
