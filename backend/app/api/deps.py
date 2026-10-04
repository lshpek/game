"""FastAPI dependencies: authentication, rate limiting, idempotency."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import AuthError, PermissionDeniedError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.admin import AdminActor

bearer_scheme = HTTPBearer(auto_error=False)
rate_limiter = SlidingWindowRateLimiter(enabled=settings.rate_limit_enabled)


def get_settings_dep() -> Settings:
    return settings


def client_ip(request: Request) -> str:
    """Best-effort client address, honouring the reverse proxy header."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from our own session JWT."""
    if credentials is None or not credentials.credentials:
        raise AuthError("Authentication required.")

    try:
        payload = decode_access_token(
            credentials.credentials,
            secret_key=settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except TokenError as exc:
        raise AuthError(f"Invalid session: {exc}") from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("Malformed session token.") from exc

    user = db.get(User, user_id)
    if user is None:
        raise AuthError("Account no longer exists.", code="USER_NOT_FOUND")
    if user.is_banned:
        raise PermissionDeniedError("This account has been suspended.", code="ACCOUNT_BANNED")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Admin-only dependency; the role is resolved from the environment list."""
    if not user.is_admin:
        raise PermissionDeniedError("Administrator access required.")
    return user


def _identity_from_token(authorization: str | None) -> str | None:
    """Resolve a stable identity for rate limiting without touching the DB."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = decode_access_token(
            authorization.split(" ", 1)[1],
            secret_key=settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except TokenError:
        return None
    return f"user:{payload.get('sub')}"


def rate_limit(scope: str, limit_setting: str) -> Callable[..., None]:
    """Build a dependency enforcing one named rate-limit bucket.

    Identity resolution is token-first (stable per player) with an IP fallback
    for unauthenticated routes, so a shared NAT cannot exhaust a user's quota.
    """

    def dependency(request: Request, authorization: str | None = Header(default=None)) -> None:
        if not settings.rate_limit_enabled:
            return
        limit = int(getattr(settings, limit_setting, settings.rate_limit_default))
        identity = _identity_from_token(authorization) or f"ip:{client_ip(request)}"
        rate_limiter.check(f"{scope}:{identity}", limit, int(settings.rate_limit_window_seconds))

    return dependency


def idempotency_key(header: str | None = Header(default=None, alias="Idempotency-Key")) -> str | None:
    """Optional replay-protection key supplied by the client."""
    if header is None:
        return None
    cleaned = header.strip()
    if not cleaned:
        return None
    if len(cleaned) > 128:
        raise AuthError("Idempotency-Key is too long.", code="BAD_IDEMPOTENCY_KEY")
    return cleaned


def verify_service_token(provided: str | None) -> None:
    """Constant-time check of the internal service token.

    Rejects placeholders so a deployment that forgot to rotate ``SERVICE_TOKEN``
    cannot be reached with a publicly known value.
    """
    configured = settings.service_token
    if not provided or not configured or configured == "CHANGE_ME":
        raise AuthError("Invalid service credentials.", code="SERVICE_UNAUTHORIZED")
    if not hmac.compare_digest(str(provided), str(configured)):
        raise AuthError("Invalid service credentials.", code="SERVICE_UNAUTHORIZED")


@dataclass(frozen=True, slots=True)
class AdminBotContext:
    """A verified service-to-service admin caller."""

    actor: AdminActor
    request_id: str | None


def get_admin_bot_context(
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    x_admin_telegram_id: str | None = Header(default=None, alias="X-Admin-Telegram-Id"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> AdminBotContext:
    """Authorise an internal admin-tool request.

    Two independent checks, both mandatory:

    1. a valid internal service token (constant-time comparison);
    2. the claimed Telegram id must appear in ``settings.admin_telegram_ids``.

    The id in the header is never trusted on its own - it is *verified* against
    the server-side allow list, so neither a leaked token nor a spoofed header can
    grant admin access.
    """
    verify_service_token(x_service_token)

    raw = (x_admin_telegram_id or "").strip()
    if not raw.isdigit():
        raise PermissionDeniedError("Administrator access required.", code="ADMIN_REQUIRED")
    telegram_id = int(raw)
    allowed = {int(value) for value in settings.admin_telegram_ids}
    if telegram_id not in allowed:
        raise PermissionDeniedError("Administrator access required.", code="ADMIN_REQUIRED")

    admin_user = db.execute(select(User).where(User.telegram_id == telegram_id)).scalar_one_or_none()
    return AdminBotContext(
        actor=AdminActor(
            telegram_id=telegram_id,
            user_id=int(admin_user.id) if admin_user is not None else None,
        ),
        request_id=(x_request_id or None),
    )
