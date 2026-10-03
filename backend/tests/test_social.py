"""Referrals, challenges, sharing, leaderboards, achievements and seasons."""

from __future__ import annotations

import pytest


def _auth_headers(client, telegram_id: int) -> dict[str, str]:
    """Auth headers for a freshly logged-in user (Bearer scheme)."""
    token = client.post("/api/auth/dev", json={"telegram_id": telegram_id}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestReferrals:
    def test_invite_link_is_derived_from_telegram_id(self, client, authed):
        session = authed(700001, username="inviter")
        payload = client.get("/api/referrals", headers=session["headers"]).json()
        assert payload["referral_code"] == "ref_700001"
        assert payload["referral_link"].endswith("startapp=ref_700001")
        assert payload["reward_coins"] > 0

    def test_reward_is_not_paid_on_open_only(self, client, authed):
        inviter = authed(700002, username="inviter2")
        before = client.get("/api/user", headers=inviter["headers"]).json()["coins"]

        invitee = client.post(
            "/api/auth/dev", json={"telegram_id": 700003, "start_param": "ref_700002"}
        ).json()

        after_open = client.get("/api/user", headers=inviter["headers"]).json()["coins"]
        assert after_open == before
        assert invitee["start_context"]["referral_telegram_id"] == 700002

    def test_reward_is_paid_after_the_first_real_roll(self, client, authed):
        inviter = authed(700004, username="inviter3")
        invitee = client.post("/api/auth/dev", json={"telegram_id": 700005, "start_param": "ref_700004"}).json()
        headers = {"Authorization": f"Bearer {invitee['access_token']}"}

        client.post("/api/roll", headers=headers)

        profile = client.get("/api/user", headers=inviter["headers"]).json()
        assert profile["referrals_count"] == 1
        assert profile["coins"] > 0

        stats = client.get("/api/referrals", headers=inviter["headers"]).json()
        assert stats["activated"] == 1
        assert stats["pending"] == 0

    def test_self_referral_pays_nothing(self, client, authed):
        session = authed(700006)
        response = client.post(
            "/api/auth/dev", json={"telegram_id": 700006, "start_param": "ref_700006"}
        )
        assert response.status_code == 200  # authentication still succeeds
        assert client.get("/api/referrals", headers=session["headers"]).json()["activated"] == 0

    def test_unknown_referrer_does_not_break_auth(self, client):
        response = client.post("/api/auth/dev", json={"telegram_id": 700007, "start_param": "ref_999999"})
        assert response.status_code == 200
        assert response.json()["user"]["referrals_count"] == 0

    def test_a_user_can_only_be_referred_once(self, client, authed):
        client.post("/api/auth/dev", json={"telegram_id": 700008, "start_param": "ref_700002"})
        assert client.post("/api/roll", headers=_auth_headers(client, 700008)).status_code == 200
        stats = client.get("/api/referrals", headers=authed(700002)["headers"]).json()
        assert stats["activated"] == 1
        assert stats["total"] == 2  # one activated + one still pending


class TestSharing:
    def test_share_returns_a_deep_link(self, client, authed):
        session = authed(710001)
        roll = client.post("/api/roll", headers=session["headers"]).json()
        payload = client.post(f"/api/numbers/{roll['number']['number']}/share", headers=session["headers"]).json()
        assert payload["start_param"].startswith("number_")
        assert "startapp=number_" in payload["mini_app_link"]
        assert client.get("/api/user", headers=session["headers"]).json()["shares_count"] >= 1

    def test_shared_number_deep_link_is_parsed_on_login(self, client):
        response = client.post("/api/auth/dev", json={"telegram_id": 710002, "start_param": "number_1337"})
        assert response.json()["start_context"]["shared_number"] == "1337"


class TestChallenges:
    def test_challenge_requires_a_number_first(self, client, authed):
        session = authed(720001)
        response = client.post("/api/challenges", headers=session["headers"], json={})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "NO_NUMBERS"

    def test_friend_can_accept_and_a_result_is_stored(self, client, authed):
        challenger = authed(720002)
        client.post("/api/roll", headers=challenger["headers"])
        challenge = client.post("/api/challenges", headers=challenger["headers"], json={}).json()
        assert challenge["status"] == "PENDING"
        assert "startapp=challenge_" in challenge["link"]

        opponent = authed(720003)
        client.post("/api/roll", headers=opponent["headers"])
        accepted = client.post(f"/api/challenges/{challenge['code']}/accept", headers=opponent["headers"]).json()

        assert accepted["status"] == "COMPLETED"
        assert accepted["opponent_number"] is not None
        assert accepted["challenger_rarity"] and accepted["opponent_rarity"]

    def test_self_acceptance_is_rejected(self, client, authed):
        session = authed(720004)
        client.post("/api/roll", headers=session["headers"])
        challenge = client.post("/api/challenges", headers=session["headers"], json={}).json()
        response = client.post(f"/api/challenges/{challenge['code']}/accept", headers=session["headers"])
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CHALLENGE_SELF"

    def test_unknown_code_is_not_found(self, client, authed):
        session = authed(720005)
        assert client.get("/api/challenges/doesnotexist", headers=session["headers"]).status_code == 404


class TestLeaderboards:
    def test_boards_are_returned_for_every_category(self, client, authed):
        session = authed(730001)
        client.post("/api/roll", headers=session["headers"])
        payload = client.get("/api/leaderboard/all?period=alltime", headers=session["headers"]).json()
        assert set(payload["boards"]) == {"VALUE", "RARITY", "COLLECTION", "ROLLS"}
        assert payload["boards"]["ROLLS"]["entries"]

    @pytest.mark.parametrize("period", ["daily", "weekly", "alltime"])
    def test_periods_are_supported(self, client, authed, period):
        session = authed(730002)
        response = client.get(f"/api/leaderboard?period={period}&category=VALUE", headers=session["headers"])
        assert response.status_code == 200
        assert response.json()["period"] == period


class TestAchievementsAndSeasons:
    def test_achievements_report_progress(self, client, authed):
        session = authed(740001)
        payload = client.get("/api/achievements", headers=session["headers"]).json()
        assert any(row["code"] == "FIRST_ROLL" for row in payload)

        client.post("/api/roll", headers=session["headers"])
        updated = {row["code"]: row for row in client.get("/api/achievements", headers=session["headers"]).json()}
        assert updated["FIRST_ROLL"]["unlocked"] is True

    def test_seasons_are_listed_with_exactly_one_active(self, client, authed):
        session = authed(740002)
        payload = client.get("/api/seasons", headers=session["headers"]).json()
        assert payload
        assert sum(1 for row in payload if row["is_active"]) == 1
        assert client.get("/api/seasons/active", headers=session["headers"]).json() is not None

