"""Authentication, initData verification and token security."""

from __future__ import annotations

import json
import time

import pytest

from app.core.errors import InvalidInitDataError, ValidationError
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    parse_challenge_start_param,
    parse_number_start_param,
    parse_referral_start_param,
    sign_init_data,
    verify_init_data,
)

BOT_TOKEN = "123456:test-bot-token"


def build_init_data(telegram_id: int = 42, **extra: str) -> str:
    payload = {
        "auth_date": str(int(time.time())),
        "query_id": "AAH123",
        "user": json.dumps({"id": telegram_id, "first_name": "Ada", "username": "ada", "language_code": "en"}),
    }
    payload.update(extra)
    return sign_init_data(payload, BOT_TOKEN)


class TestInitDataVerification:
    def test_valid_payload_is_accepted(self):
        result = verify_init_data(build_init_data(777), bot_token=BOT_TOKEN)
        assert result.user.id == 777
        assert result.user.username == "ada"
        assert result.user.first_name == "Ada"

    def test_tampered_user_id_is_rejected(self):
        raw = build_init_data(1).replace('"id": 1', '"id": 2')
        with pytest.raises(InvalidInitDataError):
            verify_init_data(raw, bot_token=BOT_TOKEN)

    def test_wrong_bot_token_is_rejected(self):
        with pytest.raises(InvalidInitDataError):
            verify_init_data(build_init_data(), bot_token="999:another-token")

    def test_forged_hash_is_rejected(self):
        with pytest.raises(InvalidInitDataError):
            verify_init_data(build_init_data() + "&hash=deadbeef", bot_token=BOT_TOKEN)

    def test_missing_hash_is_rejected(self):
        with pytest.raises(InvalidInitDataError):
            verify_init_data("auth_date=1&user=%7B%7D", bot_token=BOT_TOKEN)

    def test_empty_payload_is_rejected(self):
        with pytest.raises(InvalidInitDataError):
            verify_init_data("", bot_token=BOT_TOKEN)

    def test_unconfigured_bot_token_is_rejected(self):
        with pytest.raises(InvalidInitDataError):
            verify_init_data(build_init_data(), bot_token="CHANGE_ME")

    def test_expired_init_data_is_rejected(self):
        stale = sign_init_data(
            {"auth_date": str(int(time.time()) - 100_000), "user": json.dumps({"id": 5})},
            BOT_TOKEN,
        )
        with pytest.raises(InvalidInitDataError):
            verify_init_data(stale, bot_token=BOT_TOKEN, ttl_seconds=86400)

    def test_start_param_is_extracted(self):
        result = verify_init_data(build_init_data(9, start_param="ref_777"), bot_token=BOT_TOKEN)
        assert result.start_param == "ref_777"


class TestAccessTokens:
    def test_roundtrip(self):
        token = create_access_token("7", secret_key="s" * 32, extra_claims={"tg": 5})
        payload = decode_access_token(token, secret_key="s" * 32)
        assert payload["sub"] == "7"
        assert payload["tg"] == 5

    def test_tampered_payload_is_rejected(self):
        token = create_access_token("7", secret_key="s" * 32)
        header, body, signature = token.split(".")
        with pytest.raises(TokenError):
            decode_access_token(f"{header}.{body[:-2]}XY.{signature}", secret_key="s" * 32)

    def test_wrong_secret_is_rejected(self):
        token = create_access_token("7", secret_key="s" * 32)
        with pytest.raises(TokenError):
            decode_access_token(token, secret_key="x" * 32)

    def test_expired_token_is_rejected(self):
        token = create_access_token("7", secret_key="s" * 32, expires_in=-10)
        with pytest.raises(TokenError):
            decode_access_token(token, secret_key="s" * 32)

    def test_malformed_token_is_rejected(self):
        with pytest.raises(TokenError):
            decode_access_token("not-a-token", secret_key="s" * 32)

    def test_unsupported_algorithm_is_rejected(self):
        with pytest.raises(ValueError):
            create_access_token("7", secret_key="s" * 32, algorithm="RS256")


class TestStartParamParsing:
    def test_referral(self):
        assert parse_referral_start_param("ref_12345") == 12345
        assert parse_referral_start_param("number_1234") is None

    def test_referral_rejects_non_numeric(self):
        with pytest.raises(ValidationError):
            parse_referral_start_param("ref_abc")

    def test_number(self):
        assert parse_number_start_param("number_1337") == "1337"

    @pytest.mark.parametrize("value", ["number_12", "number_abcde", "number_"])
    def test_number_rejects_malformed(self, value):
        with pytest.raises(ValidationError):
            parse_number_start_param(value)

    def test_challenge(self):
        assert parse_challenge_start_param("challenge_abc123") == "abc123"

    def test_challenge_rejects_bad_length(self):
        with pytest.raises(ValidationError):
            parse_challenge_start_param("challenge_ab")

class TestAuthEndpoints:
    def test_protected_route_requires_a_token(self, client):
        response = client.get("/api/user")
        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_garbage_token_is_rejected(self, client):
        response = client.get("/api/user", headers={"Authorization": "Bearer garbage"})
        assert response.status_code == 401

    def test_forged_init_data_is_rejected(self, client):
        response = client.post("/api/auth/telegram", json={"init_data": "auth_date=1&user=%7B%7D&hash=x"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_INIT_DATA"

    def test_dev_login_creates_a_session(self, client):
        response = client.post("/api/auth/dev", json={"telegram_id": 515151, "username": "dev"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["token_type"] == "bearer"
        assert payload["user"]["username"] == "dev"
        assert payload["user"]["coins"] == 0

    def test_session_works_for_protected_routes(self, client, authed):
        session = authed(515152)
        assert client.get("/api/user", headers=session["headers"]).status_code == 200

    def test_me_endpoint_refreshes_the_profile(self, client, authed):
        session = authed(515153)
        response = client.get("/api/auth/me", headers=session["headers"])
        assert response.status_code == 200
        assert response.json()["access_token"]


class TestTelegramLogin:
    """The real Telegram login path: verified initData -> session JWT.

    These tests exist because the production outage was a *login* outage:
    every normal Telegram user hit "Network unavailable" while an admin
    with a cached localStorage token kept working through ``/auth/me``.
    A forged-initData test alone cannot catch that - the happy path must
    be exercised too.
    """

    def test_valid_init_data_logs_a_normal_user_in(self, client):
        """A genuine, correctly-signed initData must authenticate."""
        init_data = build_init_data(777_001)
        response = client.post("/api/auth/telegram", json={"init_data": init_data})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["access_token"]
        assert payload["token_type"] == "bearer"
        assert payload["is_new_user"] is True
        assert payload["user"]["telegram_id"] == 777_001
        # A brand-new player is a normal user, never an admin.
        assert payload["user"]["role"] == "USER"
        assert payload["user"]["is_admin"] is False

    def test_telegram_login_is_idempotent_for_returning_users(self, client):
        init_data = build_init_data(777_002)
        first = client.post("/api/auth/telegram", json={"init_data": init_data})
        second = client.post("/api/auth/telegram", json={"init_data": init_data})
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["is_new_user"] is False
        assert second.json()["user"]["id"] == first.json()["user"]["id"]

    def test_telegram_login_token_accesses_protected_routes(self, client):
        init_data = build_init_data(777_003)
        response = client.post("/api/auth/telegram", json={"init_data": init_data})
        token = response.json()["access_token"]
        me = client.get("/api/user", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["telegram_id"] == 777_003

    def test_telegram_login_does_not_grant_admin_to_normal_users(self, client):
        """Only telegram ids in ADMIN_TELEGRAM_IDS may become admins."""
        init_data = build_init_data(777_004)
        response = client.post("/api/auth/telegram", json={"init_data": init_data})
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        # Admin-only surface must stay forbidden for a normal player.
        assert client.get("/api/admin/stats", headers=headers).status_code == 403

    def test_admin_telegram_id_is_promoted_on_login(self, client):
        from tests.conftest import TEST_ADMIN_TELEGRAM_ID

        init_data = build_init_data(TEST_ADMIN_TELEGRAM_ID)
        response = client.post("/api/auth/telegram", json={"init_data": init_data})
        assert response.status_code == 200
        payload = response.json()
        assert payload["user"]["role"] == "ADMIN"
        assert payload["user"]["is_admin"] is True

    def test_stale_init_data_is_rejected(self, client):
        stale = sign_init_data(
            {
                "auth_date": str(int(time.time()) - 100_000),
                "user": json.dumps({"id": 777_005, "first_name": "Stale"}),
            },
            BOT_TOKEN,
        )
        response = client.post("/api/auth/telegram", json={"init_data": stale})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_INIT_DATA"

    def test_init_data_signed_with_wrong_token_is_rejected(self, client):
        init_data = build_init_data(777_006)
        # Re-sign the same payload with a different bot token.
        forged = sign_init_data(
            {
                "auth_date": str(int(time.time())),
                "query_id": "AAH123",
                "user": json.dumps({"id": 777_006, "first_name": "Ada"}),
            },
            "999:attacker-token",
        )
        response = client.post("/api/auth/telegram", json={"init_data": forged})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_INIT_DATA"
        # The correctly-signed one still works (sanity check).
        ok = client.post("/api/auth/telegram", json={"init_data": init_data})
        assert ok.status_code == 200


class TestCorsConfiguration:
    """The Mini App origin must always be allowed by CORS.

    A deployment that forgets CORS_ORIGINS leaves the default
    localhost-only allow-list, so the browser fails the preflight and
    the client reports "Network unavailable" even though the API is up.
    """

    def test_frontend_url_is_always_in_cors_origins(self):
        from app.core.config import Settings

        settings = Settings(
            frontend_url="https://mini.example.com",
            cors_origins=["http://localhost:5173"],
        )
        assert "https://mini.example.com" in settings.cors_origins
        assert settings.cors_allows_frontend is True

    def test_explicit_cors_origins_are_preserved(self):
        from app.core.config import Settings

        settings = Settings(
            frontend_url="https://mini.example.com",
            cors_origins=["https://mini.example.com", "https://other.example.com"],
        )
        assert settings.cors_origins == [
            "https://mini.example.com",
            "https://other.example.com",
        ]

    def test_loopback_only_cors_is_detected(self):
        from app.core.config import Settings

        settings = Settings(frontend_url="http://localhost:5173")
        assert settings.cors_is_local_only is True

        settings = Settings(
            frontend_url="https://mini.example.com",
            cors_origins=["https://mini.example.com"],
        )
        assert settings.cors_is_local_only is False

    def test_default_settings_allow_localhost(self):
        from app.core.config import settings

        assert "http://localhost:5173" in settings.cors_origins
        assert settings.cors_allows_frontend is True


class TestAdminProtection:
    """Admin-only endpoints must stay protected after the auth fix."""

    def test_admin_stats_requires_admin_role(self, client, authed):
        session = authed(777_010)
        response = client.get("/api/admin/stats", headers=session["headers"])
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_admin_stats_allows_admins(self, client, admin_authed):
        response = client.get("/api/admin/stats", headers=admin_authed["headers"])
        assert response.status_code == 200

    def test_admin_bot_surface_requires_service_token(self, client, authed):
        """The internal admin panel uses a separate service-token path."""
        session = authed(777_011)
        response = client.get(
            "/api/admin/bot/users",
            headers={**session["headers"], "X-Admin-Telegram-Id": "777011"},
        )
        assert response.status_code == 401

    def test_admin_bot_surface_rejects_non_admin_telegram_id(self, client):
        from tests.conftest import TEST_SERVICE_TOKEN

        response = client.get(
            "/api/admin/bot/users",
            headers={
                "X-Service-Token": TEST_SERVICE_TOKEN,
                "X-Admin-Telegram-Id": "777012",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ADMIN_REQUIRED"
