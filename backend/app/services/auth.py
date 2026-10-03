"""Authentication: verify Telegram ``initData`` and mint our own session JWT."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import AuthError, PermissionDeniedError
from app.core.logging import get_logger
from app.core.security import (
    TelegramUser,
    create_access_token,
    parse_challenge_start_param,
    parse_number_start_param,
    parse_referral_start_param,
    verify_init_data,
)
from app.models.enums import AnalyticsEventName
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.services.referrals import ReferralService
from app.services.users import UserService

logger = get_logger(__name__)


@dataclass(slots=True)
class StartContext:
    """Deep-link context extracted from the verified start parameter."""

    raw: str | None = None
    referral_telegram_id: int | None = None
    shared_number: str | None = None
    challenge_code: str | None = None


@dataclass(slots=True)
class AuthResult:
    user: User
    token: str
    expires_in: int
    created: bool
    context: StartContext


class AuthService:
    """Turn a verified Telegram payload into a session."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.users = UserService(db, self.settings)
        self.referrals = ReferralService(db, self.settings)
        self.analytics = AnalyticsService(db)

    # --- helpers --------------------------------------------------------
    def _parse_context(self, start_param: str | None) -> StartContext:
        context = StartContext(raw=start_param)
        if not start_param:
            return context
        context.referral_telegram_id = parse_referral_start_param(start_param)
        context.shared_number = parse_number_start_param(start_param)
        context.challenge_code = parse_challenge_start_param(start_param)
        return context

    def _issue(self, user: User, created: bool, context: StartContext) -> AuthResult:
        if user.is_banned:
            raise PermissionDeniedError("This account has been suspended.", code="ACCOUNT_BANNED")

        token = create_access_token(
            subject=str(user.id),
            secret_key=self.settings.secret_key,
            algorithm=self.settings.jwt_algorithm,
            expires_in=self.settings.access_token_ttl_seconds,
            extra_claims={"tg": user.telegram_id, "role": user.role},
        )
        self.db.commit()
        return AuthResult(
            user=user,
            token=token,
            expires_in=self.settings.access_token_ttl_seconds,
            created=created,
            context=context,
        )

    def _apply_referral(self, user: User, created: bool, context: StartContext) -> None:
        """Bind a referral only for genuinely new users (anti-abuse)."""
        if not context.referral_telegram_id:
            return
        from app.core.errors import AppError

        try:
            self.referrals.bind(user, context.referral_telegram_id, context.raw)
        except AppError as exc:
            # A referral problem must never block authentication.
            logger.warning("Referral binding rejected: %s", exc.message, extra={"user_id": user.id})

    # --- entry points ---------------------------------------------------
    def authenticate_init_data(self, raw_init_data: str) -> AuthResult:
        verified = verify_init_data(
            raw_init_data,
            bot_token=self.settings.bot_token,
            ttl_seconds=self.settings.telegram_init_data_ttl_seconds,
        )
        user, created = self.users.upsert_from_telegram(verified.user)
        context = self._parse_context(verified.start_param)
        self._apply_referral(user, created, context)

        self.analytics.track(
            AnalyticsEventName.APP_OPEN.value,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={"created": created, "start_param": verified.start_param},
        )
        return self._issue(user, created, context)

    def authenticate_dev(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str = "Dev",
        start_param: str | None = None,
    ) -> AuthResult:
        """Local development login. Disabled outside ``development``/``test``."""
        if self.settings.is_production or not self.settings.allow_dev_login:
            raise AuthError("Developer login is disabled.", code="DEV_LOGIN_DISABLED")

        profile = TelegramUser(
            id=int(telegram_id),
            first_name=first_name,
            username=username,
        )
        user, created = self.users.upsert_from_telegram(profile)
        context = self._parse_context(start_param)
        self._apply_referral(user, created, context)
        self.analytics.track(
            AnalyticsEventName.APP_OPEN.value,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={"created": created, "dev": True},
        )
        return self._issue(user, created, context)
