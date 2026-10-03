"""Referral endpoints (stricter rate limits)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.social import ReferralSummary
from app.services.referrals import ReferralService

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get(
    "",
    response_model=ReferralSummary,
    dependencies=[Depends(rate_limit("referral", "rate_limit_referral"))],
    summary="Referral stats, link and recent invites",
)
def referrals(
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReferralSummary:
    service = ReferralService(db, settings)
    stats = service.stats(user.id)
    start_param = f"ref_{user.telegram_id}"
    return ReferralSummary(
        referral_code=start_param,
        referral_link=settings.telegram_mini_app_link(start_param),
        total=stats.total,
        activated=stats.activated,
        pending=stats.pending,
        coins_earned=stats.coins_earned,
        reward_coins=int(settings.referral_reward_coins),
        reward_rolls=int(settings.referral_reward_rolls),
        items=service.list_referrals(user.id, limit=limit),  # type: ignore[arg-type]
    )
