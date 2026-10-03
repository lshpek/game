"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, DevAuthRequest, TelegramAuthRequest
from app.services.auth import AuthService
from app.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_response(result, users: UserService) -> AuthResponse:
    return AuthResponse(
        access_token=result.token,
        expires_in=result.expires_in,
        is_new_user=result.created,
        user=users.profile(result.user),  # type: ignore[arg-type]
        start_context={
            "raw": result.context.raw,
            "referral_telegram_id": result.context.referral_telegram_id,
            "shared_number": result.context.shared_number,
            "challenge_code": result.context.challenge_code,
        },
    )


@router.post(
    "/telegram",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("auth", "rate_limit_auth"))],
    summary="Exchange verified Telegram initData for a session token",
)
def auth_telegram(
    payload: TelegramAuthRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    service = AuthService(db, settings)
    result = service.authenticate_init_data(payload.init_data)
    return _build_response(result, service.users)


@router.post(
    "/dev",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("auth", "rate_limit_auth"))],
    summary="Development-only login (disabled in production)",
)
def auth_dev(payload: DevAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    service = AuthService(db, settings)
    result = service.authenticate_dev(
        telegram_id=payload.telegram_id,
        username=payload.username,
        first_name=payload.first_name,
        start_param=payload.start_param,
    )
    return _build_response(result, service.users)


@router.get("/me", response_model=AuthResponse, summary="Refresh the current session profile")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthResponse:
    from app.core.security import create_access_token

    users = UserService(db, settings)
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expires_in=settings.access_token_ttl_seconds,
        extra_claims={"tg": user.telegram_id, "role": user.role},
    )
    return AuthResponse(
        access_token=token,
        expires_in=settings.access_token_ttl_seconds,
        is_new_user=False,
        user=users.profile(user),
        start_context={},
    )
