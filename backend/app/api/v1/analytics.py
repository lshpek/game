"""Analytics ingestion endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.payments import AnalyticsEventRequest
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

ALLOWED_CLIENT_EVENTS = {
    "app_open",
    "share",
    "referral_click",
    "screen_view",
    "roll_button_click",
    "container_button_click",
}


@router.post(
    "/event",
    dependencies=[Depends(rate_limit("analytics", "rate_limit_default"))],
    summary="Record a client-side analytics event",
)
def track_event(
    payload: AnalyticsEventRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # Only a whitelist of non-financial events can come from the client.
    name = payload.name if payload.name in ALLOWED_CLIENT_EVENTS else "unknown_client_event"
    AnalyticsService(db).track(
        name,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props=payload.props or None,
    )
    db.commit()
    return {"success": True, "recorded": name}
