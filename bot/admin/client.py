"""Typed client for the backend's internal control API.

The only place in the bot that performs admin HTTP calls. It attaches the
service-to-service headers, enforces a timeout, and turns the backend's error
envelope into a short human-readable message so a handler never has to know how
the API reports problems.

The service token is held here and never rendered, logged or passed in a URL.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("bot.admin.client")

# Backend error code -> short operator-facing message (English is fine for a
# technical error line; the surrounding screen stays Russian).
ERROR_MESSAGES: dict[str, str] = {
    "USER_NOT_FOUND": "Player not found.",
    "PLATE_NOT_FOUND": "Plate not found.",
    "PLATE_ALREADY_EXISTS": "Plate already exists.",
    "COUNTRY_NOT_FOUND": "Country not found.",
    "MISSION_NOT_FOUND": "Mission not found.",
    "ACHIEVEMENT_NOT_FOUND": "Achievement not found.",
    "EVENT_NOT_FOUND": "Event not found.",
    "PRESET_NOT_FOUND": "Preset not found.",
    "BAD_PLATE_TEMPLATE": "That plate text does not fit the country templates.",
    "PLATE_SHAPE_MISMATCH": "Plate text does not match any template.",
    "PLATE_TEXT_EMPTY": "Plate text is empty.",
    "PLATE_TEXT_INVALID": "Plate text has no usable characters.",
    "COUNTRY_INACTIVE": "Country is inactive.",
    "INVALID_AMOUNT": "Invalid amount.",
    "INVALID_BALANCE": "Balance cannot be negative.",
    "INVALID_DURATION": "Invalid duration.",
    "INVALID_TITLE": "Title is empty.",
    "BALANCE_UNCHANGED": "Balance already equals the target.",
    "INSUFFICIENT_FUNDS": "Insufficient balance.",
    "FIRST_DISCOVERY_TAKEN": "This plate already has a first discoverer.",
    "PROTECTED_ADMIN": "Configured admins cannot be banned here.",
    "SELF_BAN": "You cannot ban yourself.",
    "ADMIN_REQUIRED": "Administrator access required.",
    "SERVICE_UNAUTHORIZED": "Service credentials rejected by the backend.",
    "RATE_LIMITED": "Too many requests - slow down.",
    "PERMISSION_DENIED": "Permission denied.",
    "VALIDATION_ERROR": "Validation failed.",
    "CONFLICT": "Conflict - the state already changed.",
    "INTERNAL_ERROR": "Temporary server error.",
}


class AdminAPIError(Exception):
    """A backend error, already reduced to something showable to an admin."""

    def __init__(self, message: str, *, code: str = "ERROR", status: int = 0, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.details = details or {}

    def display(self) -> str:
        return f"⚠️ {self.message}\n<code>{self.code}</code>"


class AdminAPIUnavailable(AdminAPIError):
    """The backend could not be reached at all."""


def _error_message(status: int, code: str, message: str) -> str:
    if code in ERROR_MESSAGES:
        return ERROR_MESSAGES[code]
    if status >= 500:
        return ERROR_MESSAGES["INTERNAL_ERROR"]
    return message or "Request failed."


class AdminBotClient:
    """Thin, typed wrapper around ``/api/admin/bot/*``."""

    def __init__(self, base_url: str, service_token: str, *, timeout: float = 20.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout = timeout

    # --- transport ------------------------------------------------------
    def _headers(self, admin_telegram_id: int, operation_id: str | None = None) -> dict[str, str]:
        headers = {
            "X-Service-Token": self._service_token,
            "X-Admin-Telegram-Id": str(admin_telegram_id),
        }
        if operation_id:
            # Also the correlation id used by the backend's structured logs.
            headers["X-Request-ID"] = operation_id
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        admin_telegram_id: int,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/api/admin/bot{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=self._headers(admin_telegram_id, operation_id),
                )
        except httpx.TimeoutException as exc:
            raise AdminAPIUnavailable("Backend timed out.", code="TIMEOUT") from exc
        except httpx.HTTPError as exc:
            # Never log the URL *with* credentials - headers are not in the URL.
            logger.warning("admin backend unreachable: %s", type(exc).__name__)
            raise AdminAPIUnavailable("Backend unreachable.", code="UNREACHABLE") from exc

        if response.status_code == 204:
            return {}

        try:
            payload = response.json()
        except ValueError as exc:
            raise AdminAPIError(
                "Backend returned an unreadable response.",
                code="BAD_RESPONSE",
                status=response.status_code,
            ) from exc

        if response.status_code >= 400:
            error = payload.get("error") or {}
            raise AdminAPIError(
                _error_message(
                    response.status_code,
                    str(error.get("code") or "ERROR"),
                    str(error.get("message") or ""),
                ),
                code=str(error.get("code") or "ERROR"),
                status=response.status_code,
                details=error.get("details"),
            )
        return payload if isinstance(payload, dict) else {"data": payload}

    async def get(self, path: str, *, admin_telegram_id: int, **kwargs: Any) -> dict[str, Any]:
        return await self.request("GET", path, admin_telegram_id=admin_telegram_id, **kwargs)

    async def post(self, path: str, *, admin_telegram_id: int, **kwargs: Any) -> dict[str, Any]:
        return await self.request("POST", path, admin_telegram_id=admin_telegram_id, **kwargs)

    # --- reads ----------------------------------------------------------
    async def dashboard(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/dashboard", admin_telegram_id=telegram_id)

    async def catalog(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/catalog", admin_telegram_id=telegram_id)

    async def search_users(self, telegram_id: int, query: str | None, page: int = 1) -> dict[str, Any]:
        return await self.get(
            "/users",
            admin_telegram_id=telegram_id,
            params={"query": query or "", "page": page},
        )

    async def user_detail(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}", admin_telegram_id=telegram_id)

    async def user_economy(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/economy", admin_telegram_id=telegram_id)

    async def user_missions(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/missions", admin_telegram_id=telegram_id)

    async def user_achievements(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/achievements", admin_telegram_id=telegram_id)

    async def user_premium(self, telegram_id: int, user_id: int) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}/premium", admin_telegram_id=telegram_id)

    async def cosmetics(self, telegram_id: int, query: str | None = None) -> dict[str, Any]:
        return await self.get("/cosmetics", admin_telegram_id=telegram_id, params={"query": query or ""})

    async def plates(self, telegram_id: int, **params: Any) -> dict[str, Any]:
        return await self.get("/plates", admin_telegram_id=telegram_id, params=params)

    async def plate(self, telegram_id: int, plate_id: int) -> dict[str, Any]:
        return await self.get(f"/plates/{plate_id}", admin_telegram_id=telegram_id)

    async def ranks(self, telegram_id: int, category: str, period: str) -> dict[str, Any]:
        return await self.get(
            "/ranks",
            admin_telegram_id=telegram_id,
            params={"category": category, "period": period},
        )

    async def countries(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/countries", admin_telegram_id=telegram_id)

    async def events(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/events", admin_telegram_id=telegram_id)

    async def analytics(self, telegram_id: int, period: str) -> dict[str, Any]:
        return await self.get("/analytics", admin_telegram_id=telegram_id, params={"period": period})

    async def system(self, telegram_id: int) -> dict[str, Any]:
        return await self.get("/system", admin_telegram_id=telegram_id)

    async def errors(self, telegram_id: int, limit: int = 10) -> dict[str, Any]:
        return await self.get("/errors", admin_telegram_id=telegram_id, params={"limit": limit})

    async def transactions(self, telegram_id: int, **params: Any) -> dict[str, Any]:
        return await self.get("/transactions", admin_telegram_id=telegram_id, params=params)

    async def audit(self, telegram_id: int, **params: Any) -> dict[str, Any]:
        return await self.get("/audit", admin_telegram_id=telegram_id, params=params)

    # --- mutations ------------------------------------------------------
    async def mutate(
        self,
        path: str,
        *,
        admin_telegram_id: int,
        operation_id: str,
        reason: str,
        **body: Any,
    ) -> dict[str, Any]:
        """POST a mutation.

        ``operation_id`` doubles as the idempotency key *and* the request id, so a
        duplicated Telegram callback replays instead of granting twice.
        """
        payload = {"operation_id": operation_id, "reason": reason, **body}
        response = await self.post(
            path,
            admin_telegram_id=admin_telegram_id,
            json=payload,
            operation_id=operation_id,
        )
        data = response.get("data")
        return data if isinstance(data, dict) else response


__all__ = [
    "ERROR_MESSAGES",
    "AdminAPIError",
    "AdminAPIUnavailable",
    "AdminBotClient",
]
