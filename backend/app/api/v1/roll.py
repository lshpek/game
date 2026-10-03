"""Roll, daily allowance and roll history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, idempotency_key, rate_limit
from app.api.serializers import number_card
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import RollSource
from app.models.user import User
from app.schemas.game import DailyClaimResponse, DailyStatusResponse, RollHistoryItem, RollResponse
from app.services.achievements import AchievementService, summarize
from app.services.daily import DailyService
from app.services.rolls import RollService
from app.services.users import UserService

router = APIRouter(tags=["roll"])


@router.post(
    "/roll",
    response_model=RollResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Perform a roll - the server decides the result",
)
def perform_roll(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    key: str | None = Depends(idempotency_key),
) -> RollResponse:
    service = RollService(db, settings)
    outcome = service.perform_roll(user, source=RollSource.DAILY, idempotency_key=key)

    from app.services.referrals import ReferralService

    # First real roll activates any pending referral (reward is paid here only).
    ReferralService(db, settings).activate(user)
    db.commit()

    unlocked = AchievementService(db).evaluate(user)
    db.commit()

    card = number_card(outcome.number, value=outcome.value)
    return RollResponse(
        roll_id=outcome.roll.id,
        number=card,  # type: ignore[arg-type]
        rarity=outcome.roll.rarity,
        natural_rarity=outcome.roll.natural_rarity,
        luck_rarity=outcome.roll.luck_rarity,
        value=outcome.value,
        is_duplicate=outcome.is_duplicate,
        is_first_discovery=outcome.is_first_discovery,
        coins_awarded=outcome.coins_awarded,
        balance=outcome.balance,
        rolls_remaining=outcome.rolls_remaining,
        conversion_value=outcome.conversion_value,
        unlocked_achievements=outcome.unlocked_achievements + summarize(unlocked),
        replayed=outcome.replayed,
        share_start_param=f"number_{card['number']}",
    )


@router.get("/roll/history", response_model=list[RollHistoryItem], summary="Recent rolls")
def roll_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RollHistoryItem]:
    rolls = RollService(db, settings).history(user.id, limit=limit, offset=offset)
    return [
        RollHistoryItem(
            roll_id=roll.id,
            number=roll.number.value_str if roll.number else "----",
            rarity=roll.rarity,
            value=int(roll.value),
            coins_awarded=int(roll.coins_awarded),
            is_duplicate=bool(roll.is_duplicate),
            created_at=roll.created_at.isoformat(),
        )
        for roll in rolls
    ]


@router.get("/daily", response_model=DailyStatusResponse, summary="Daily roll allowance and streak")
def daily_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DailyStatusResponse:
    status = DailyService(db, settings).status(user)
    db.commit()
    return DailyStatusResponse(
        rolls_remaining=status.rolls_remaining,
        daily_allowance=status.daily_allowance,
        resets_at=status.resets_at,
        streak=status.streak,
        can_claim=status.can_claim,
        claim_reward_coins=status.claim_reward_coins,
    )


@router.post(
    "/daily/claim",
    response_model=DailyClaimResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Claim the daily reward (idempotent per UTC day)",
)
def claim_daily(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DailyClaimResponse:
    service = DailyService(db, settings)
    reward, coins, rolls = service.claim(user)

    from app.models.enums import AnalyticsEventName
    from app.services.analytics import AnalyticsService

    AnalyticsService(db).track(
        AnalyticsEventName.DAILY_CLAIM.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"streak": reward.streak, "coins": coins},
    )
    db.commit()

    achievements = AchievementService(db)
    unlocked = achievements.evaluate(user)
    db.commit()

    from app.services.economy import EconomyService

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
