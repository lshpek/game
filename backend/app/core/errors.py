"""Typed application errors and the uniform error envelope.

Every failure returned to the client uses the shape:

    {"success": false, "error": {"code": "...", "message": "..."}}
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, user-facing failures."""

    status_code: int = 400
    code: str = "BAD_REQUEST"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.code.replace("_", " ").capitalize()
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class InvalidInitDataError(AuthError):
    code = "INVALID_INIT_DATA"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMITED"


class NoRollsAvailableError(AppError):
    status_code = 409
    code = "NO_ROLLS_AVAILABLE"


class InsufficientFundsError(AppError):
    status_code = 409
    code = "INSUFFICIENT_FUNDS"


class ContainerUnavailableError(AppError):
    status_code = 409
    code = "CONTAINER_UNAVAILABLE"


class PaymentError(AppError):
    status_code = 402
    code = "PAYMENT_FAILED"


class ReferralAbuseError(AppError):
    status_code = 409
    code = "REFERRAL_ABUSE"
