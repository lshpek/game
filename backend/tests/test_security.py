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
