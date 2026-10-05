"""Daily allowance and daily-claim endpoints.

The roll itself now lives in :mod:`app.api.v1.plates`, which produces a real
license plate instead of a bare 4-digit number. The legacy ``RollService``
(number domain) is still exercised through ``/api/legacy/collection``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.game import DailyClaimResponse, DailyStatusResponse
from app.services.achievements import AchievementService, summarize
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.users import UserService

router = APIRouter(tags=["roll"])


@router.get("/daily", response_model=DailyStatusResponse, summary="Daily roll allowance and streak")
def daily_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DailyStatusResponse:
    """The authoritative roll balance.

    The client renders the roll button straight from this payload - the normal bank, the
    bonus bank and the countdown to the next passive roll - and keeps no economy of its
    own.
    """
    status = DailyService(db, settings).status(user)
    db.commit()
    return DailyStatusResponse(
        rolls_remaining=status.rolls_remaining,
        daily_allowance=status.daily_allowance,
        resets_at=status.resets_at,
        streak=status.streak,
        can_claim=status.can_claim,
        claim_reward_coins=status.claim_reward_coins,
        normal_rolls=status.normal_rolls,
        bonus_rolls=status.bonus_rolls,
        next_roll_at=status.next_roll_at,
        seconds_to_next_roll=status.seconds_to_next_roll,
        regen_minutes=status.regen_minutes,
    )


@router.post(
    "/daily/claim",
    response_model=DailyClaimResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Claim the daily reward (idempotent per UTC day)",
)
def claim_daily(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DailyClaimResponse:
    """Claim today's reward.

    Idempotent in two independent ways: a unique constraint on
    ``(user_id, claimed_on)`` rejects a second claim in the same UTC day, and the coin
    grant carries its own ledger idempotency key. A double tap therefore cannot pay out
    twice, and the player keeps whatever bonus rolls the reward granted.
    """
    service = DailyService(db, settings)
    reward, coins, rolls = service.claim(user)

    from app.models.enums import AnalyticsEventName
    from app.services.analytics import AnalyticsService

    AnalyticsService(db).track(
        AnalyticsEventName.DAILY_CLAIMED,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"streak": reward.streak, "coins": coins, "rolls": rolls},
    )
    db.commit()

    achievements = AchievementService(db)
    unlocked = achievements.evaluate(user)
    db.commit()

    return DailyClaimResponse(
        coins_granted=coins,
        rolls_granted=rolls,
        streak=reward.streak,
        balance=EconomyService(db).balance(user.id),
        unlocked_achievements=summarize(unlocked),
    )


@router.get("/user", summary="Current user profile")
def current_user_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return UserService(db, settings).profile(user)
