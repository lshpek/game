"""Authentication primitives.

* Telegram WebApp ``initData`` signature verification (HMAC-SHA256).
* A dependency-free HS256 JWT implementation for our own session tokens.

The frontend is *never* trusted: a Telegram user id is only accepted after the
signature produced with the bot token has been verified server side.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

from app.core.errors import InvalidInitDataError, ValidationError

_INIT_DATA_SECRET_LABEL = b"WebAppData"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TokenError(Exception):
    """Raised when a JWT is malformed, tampered with or expired."""


def create_access_token(
    subject: str,
    *,
    secret_key: str,
    algorithm: str = "HS256",
    expires_in: int = 3600,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed HS256 JWT."""
    if algorithm != "HS256":
        raise ValueError(f"Unsupported JWT algorithm: {algorithm}")

    now = int(time.time())
    payload: dict[str, Any] = {"sub": subject, "iat": now, "exp": now + expires_in}
    if extra_claims:
        payload.update(extra_claims)

    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret_key.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode_access_token(token: str, *, secret_key: str, algorithm: str = "HS256") -> dict[str, Any]:
    """Verify and decode a JWT produced by :func:`create_access_token`."""
    if algorithm != "HS256":
        raise ValueError(f"Unsupported JWT algorithm: {algorithm}")

    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise TokenError("Malformed token") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected = hmac.new(secret_key.encode(), signing_input, hashlib.sha256).digest()
    try:
        provided = _b64url_decode(signature_segment)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise TokenError("Malformed signature") from exc

    if not hmac.compare_digest(expected, provided):
        raise TokenError("Invalid signature")

    try:
        payload = json.loads(_b64url_decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Malformed payload") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("Token expired")
    if not payload.get("sub"):
        raise TokenError("Token subject missing")
    return payload


@dataclass(slots=True)
class TelegramUser:
    """Trusted Telegram user profile extracted from verified ``initData``."""

    id: int
    first_name: str = ""
    last_name: str = ""
    username: str | None = None
    language_code: str | None = None
    is_premium: bool = False
    allows_write_to_pm: bool = False
    photo_url: str | None = None

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or (f"@{self.username}" if self.username else f"id{self.id}")


@dataclass(slots=True)
class VerifiedInitData:
    """Result of a successful ``initData`` verification."""

    user: TelegramUser
    auth_date: int
    query_id: str | None = None
    start_param: str | None = None
    raw: dict[str, str] = field(default_factory=dict)


def hash_secret(secret: str, *, length: int = 32) -> str:
    """Non-reversible fingerprint of a secret.

    Used by internal tooling that must prove a credential *is configured* (and
    that two services agree) without ever revealing the credential itself.
    """
    import hashlib

    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()[: max(8, min(length, 64))]


def _build_data_check_string(pairs: dict[str, str]) -> str:
    return "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs) if key != "hash")


def compute_init_data_hash(raw_init_data: str, bot_token: str) -> str:
    """Compute the expected ``hash`` for a raw initData query string (tests)."""
    secret_key = hmac.new(_INIT_DATA_SECRET_LABEL, bot_token.encode(), hashlib.sha256).digest()
    pairs = dict(parse_qsl(raw_init_data, keep_blank_values=True))
    return hmac.new(secret_key, _build_data_check_string(pairs).encode(), hashlib.sha256).hexdigest()


def sign_init_data(pairs: dict[str, str], bot_token: str) -> str:
    """Produce a valid ``initData`` query string (used by tests and the mock bot)."""
    secret_key = hmac.new(_INIT_DATA_SECRET_LABEL, bot_token.encode(), hashlib.sha256).digest()
    data_check_string = _build_data_check_string(pairs)
    digest = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    body = "&".join(f"{key}={value}" for key, value in pairs.items())
    return f"{body}&hash={digest}"


def verify_init_data(
    raw_init_data: str,
    *,
    bot_token: str,
    ttl_seconds: int = 86400,
    now: int | None = None,
) -> VerifiedInitData:
    """Cryptographically validate Telegram WebApp ``initData``.

    Raises :class:`InvalidInitDataError` when the payload is missing, stale or
    the signature does not match.
    """
    if not raw_init_data:
        raise InvalidInitDataError("Telegram init data is missing.")
    if not bot_token or bot_token == "CHANGE_ME":
        raise InvalidInitDataError("Bot token is not configured; set BOT_TOKEN before Telegram auth.")

    pairs = dict(parse_qsl(raw_init_data, keep_blank_values=True))
    provided_hash = pairs.pop("hash", None)
    if not provided_hash:
        raise InvalidInitDataError("Telegram init data has no signature.")

    secret_key = hmac.new(_INIT_DATA_SECRET_LABEL, bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, _build_data_check_string(pairs).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, provided_hash):
        raise InvalidInitDataError("Telegram init data signature is invalid.")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise InvalidInitDataError("Invalid auth_date in init data.") from exc

    current = now if now is not None else int(time.time())
    if auth_date <= 0 or current - auth_date > ttl_seconds:
        raise InvalidInitDataError("Telegram init data has expired.")

    user_payload = pairs.get("user")
    if not user_payload:
        raise InvalidInitDataError("Telegram init data contains no user.")

    try:
        user_json = json.loads(user_payload)
        telegram_id = int(user_json["id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise InvalidInitDataError("Telegram user payload is malformed.") from exc

    user = TelegramUser(
        id=telegram_id,
        first_name=str(user_json.get("first_name") or "")[:128],
        last_name=str(user_json.get("last_name") or "")[:128],
        username=(str(user_json["username"])[:64] if user_json.get("username") else None),
        language_code=(str(user_json["language_code"])[:16] if user_json.get("language_code") else None),
        is_premium=bool(user_json.get("is_premium", False)),
        allows_write_to_pm=bool(user_json.get("allows_write_to_pm", False)),
        photo_url=(str(user_json["photo_url"])[:512] if user_json.get("photo_url") else None),
    )

    return VerifiedInitData(
        user=user,
        auth_date=auth_date,
        query_id=pairs.get("query_id"),
        start_param=pairs.get("start_param") or None,
        raw=pairs,
    )


def parse_referral_start_param(start_param: str | None) -> int | None:
    """Extract a Telegram user id from a ``ref_<id>`` deep-link parameter."""
    if not start_param or not start_param.startswith("ref_"):
        return None
    raw = start_param[len("ref_"):]
    if not raw.isdigit():
        raise ValidationError("Referral parameter is not a valid Telegram id.", code="INVALID_REFERRAL")
    return int(raw)


def parse_number_start_param(start_param: str | None) -> str | None:
    """Extract a 4-digit number from a ``number_1234`` deep-link parameter."""
    if not start_param or not start_param.startswith("number_"):
        return None
    raw = start_param[len("number_"):]
    if not (raw.isdigit() and len(raw) == 4):
        raise ValidationError("Shared number parameter is invalid.", code="INVALID_NUMBER_PARAM")
    return raw


def parse_plate_start_param(start_param: str | None) -> int | None:
    """Extract a plate id from a ``plate_<id>`` deep-link parameter.

    Only digits are accepted, so a crafted link can never smuggle content.
    """
    if not start_param or not start_param.startswith("plate_"):
        return None
    raw = start_param[len("plate_") :]
    if not raw.isdigit() or len(raw) > 12:
        raise ValidationError("Shared plate parameter is invalid.", code="INVALID_PLATE_PARAM")
    return int(raw)


def parse_country_start_param(start_param: str | None) -> str | None:
    """Extract a country code from a ``country_<CODE>`` deep-link parameter."""
    if not start_param or not start_param.startswith("country_"):
        return None
    raw = start_param[len("country_") :]
    if not raw.isalnum() or not (2 <= len(raw) <= 4):
        raise ValidationError("Country parameter is invalid.", code="INVALID_COUNTRY_PARAM")
    return raw.upper()


def parse_season_start_param(start_param: str | None) -> str | None:
    """Extract a season code from a ``season_<code>`` deep-link parameter."""
    if not start_param or not start_param.startswith("season_"):
        return None
    raw = start_param[len("season_") :]
    if not raw.isalnum() or not (2 <= len(raw) <= 32):
        raise ValidationError("Season parameter is invalid.", code="INVALID_SEASON_PARAM")
    return raw


def parse_challenge_start_param(start_param: str | None) -> str | None:
    """Extract a challenge code from a ``challenge_<code>`` deep-link parameter."""
    if not start_param or not start_param.startswith("challenge_"):
        return None
    code = start_param[len("challenge_"):]
    if not code.isalnum() or not (4 <= len(code) <= 32):
        raise ValidationError("Challenge parameter is invalid.", code="INVALID_CHALLENGE_PARAM")
    return code
