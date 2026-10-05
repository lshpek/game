"""The roll economy: 20 rolls, 45-minute regeneration, bonus rolls, reset.

Everything here is server authority. The tests drive time explicitly rather than
sleeping, so they are deterministic and fast.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import NoRollsAvailableError
from app.core.timeutils import as_aware, next_utc_midnight, utcnow
from app.db.session import SessionLocal
from app.models.user import User
from app.services.daily import DailyService


@pytest.fixture
def user(db) -> User:
    row = User(telegram_id=880_100_001, first_name="Roll")
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def service(db) -> DailyService:
    return DailyService(db, settings)


class TestBankSize:
    def test_a_new_player_starts_with_twenty_rolls(self, db, user, service):
        assert settings.default_daily_rolls == 20
        state = service.sync(user)
        assert state.bank_cap == 20
        assert state.normal_remaining == 20
        assert state.bonus_rolls == 0
        assert state.rolls_remaining == 20

    def test_a_full_bank_has_no_pending_regeneration(self, db, user, service):
        state = service.sync(user)
        assert state.next_roll_at is None
        assert state.seconds_to_next_roll == 0
        assert user.roll_regen_at is None

    def test_a_spent_roll_is_taken_from_the_normal_bank(self, db, user, service):
        assert service.consume_roll(user) == "normal"
        assert service.sync(user).normal_remaining == 19
        assert service.sync(user).bonus_rolls == 0

    def test_the_bank_is_refilled_from_the_day_boundary(self, db, user, service):
        service.sync(user)
        user.daily_rolls_used = 17
        user.bonus_rolls = 4
        user.roll_regen_at = utcnow() + timedelta(minutes=5)
        db.flush()

        tomorrow = next_utc_midnight(utcnow()) + timedelta(seconds=1)
        assert service.sync(user, now=tomorrow).normal_remaining == 20

        state = service.sync(user)
        # The reset refills the normal bank and nothing else: bonus rolls are never
        # deleted, and the clock starts idle again.
        assert state.normal_remaining == 20
        assert state.bonus_rolls == 4
        assert state.next_roll_at is None

    def test_a_reset_before_the_boundary_changes_nothing(self, db, user, service):
        service.sync(user)
        user.daily_rolls_used = 5
        db.flush()
        assert service.ensure_reset(user) is False
        assert service.sync(user).normal_remaining == 15


class TestPassiveRegeneration:
    def test_the_interval_is_forty_five_minutes(self, db, user, service):
        assert settings.roll_regen_minutes == 45

    def test_the_clock_starts_when_the_bank_drops_below_the_cap(self, db, user, service):
        service.consume_roll(user)
        state = service.sync(user)
        assert state.next_roll_at is not None
        assert 44 * 60 <= state.seconds_to_next_roll <= 45 * 60 + 5

    def test_nothing_regenerates_before_the_interval_elapses(self, db, user, service):
        service.consume_roll(user)
        service.sync(user)
        due = as_aware(user.roll_regen_at)
        state = service.sync(user, now=due - timedelta(seconds=1))
        assert state.normal_remaining == 19
        assert state.seconds_to_next_roll == 1
        # One second later the roll is there: the countdown the client renders is the
        # same clock the server settles.
        assert service.sync(user, now=due).normal_remaining == 20

    def test_one_roll_regenerates_after_the_interval(self, db, user, service):
        service.consume_roll(user)
        service.sync(user)
        due = as_aware(user.roll_regen_at)
        # ``roll_regen_at`` is the moment the roll becomes available, so it lands on time.
        state = service.sync(user, now=due)
        assert state.normal_remaining == 20
        # Full bank: the clock goes idle rather than accumulating a surplus.
        assert state.next_roll_at is None

    def test_a_long_absence_is_capped_by_the_bank(self, db, user, service):
        for _ in range(12):
            service.consume_roll(user)
        service.sync(user)
        assert service.normal_remaining(user) == 8

        due = as_aware(user.roll_regen_at)
        state = service.sync(user, now=due + timedelta(days=3))
        assert state.normal_remaining == 20
        assert state.rolls_remaining == 20
        assert state.next_roll_at is None

    def test_catch_up_is_exact_not_rounded_up(self, db, user, service):
        for _ in range(5):
            service.consume_roll(user)
        service.sync(user)
        assert service.normal_remaining(user) == 15
        due = as_aware(user.roll_regen_at)
        # Three whole intervals after the pending slot: three rolls, no more.
        state = service.sync(user, now=due + timedelta(minutes=45 * 2, seconds=30))
        assert state.normal_remaining == 18
        assert state.seconds_to_next_roll > 0

    def test_regeneration_never_consumes_bonus_rolls(self, db, user, service):
        service.grant_bonus_rolls(user, 5)
        for _ in range(3):
            service.consume_roll(user)
        service.sync(user)
        due = as_aware(user.roll_regen_at)
        state = service.sync(user, now=due + timedelta(days=2))
        assert state.bonus_rolls == 5
        assert state.rolls_remaining == 25


class TestBonusRolls:
    def test_bonus_rolls_sit_above_the_normal_bank(self, db, user, service):
        service.grant_bonus_rolls(user, 3)
        state = service.sync(user)
        assert state.normal_remaining == 20
        assert state.bonus_rolls == 3
        assert state.rolls_remaining == 23

    def test_the_normal_bank_is_spent_before_the_bonus_bank(self, db, user, service):
        service.grant_bonus_rolls(user, 2)
        for _ in range(20):
            assert service.consume_roll(user) == "normal"
        assert service.consume_roll(user) == "bonus"
        assert service.consume_roll(user) == "bonus"
        with pytest.raises(NoRollsAvailableError):
            service.consume_roll(user)

    def test_a_full_normal_bank_does_not_consume_bonus(self, db, user, service):
        service.grant_bonus_rolls(user, 4)
        service.consume_roll(user)
        state = service.sync(user)
        # The bank regrew from the cap, so the bonus rolls are still there.
        due = as_aware(user.roll_regen_at)
        state = service.sync(user, now=due + timedelta(minutes=46))
        assert state.normal_remaining == 20
        assert state.bonus_rolls == 4

    def test_a_non_positive_grant_is_a_no_op(self, db, user, service):
        service.grant_bonus_rolls(user, 3)
        assert service.grant_bonus_rolls(user, 0) == 3
        assert service.grant_bonus_rolls(user, -5) == 3


class TestExhaustion:
    def test_an_empty_bank_raises_a_typed_error(self, db, user, service):
        service.grant_bonus_rolls(user, 1)
        for _ in range(20):
            assert service.consume_roll(user) == "normal"
        assert service.consume_roll(user) == "bonus"
        with pytest.raises(NoRollsAvailableError):
            service.consume_roll(user)

    def test_the_error_carries_the_times_a_client_needs(self, db, user, service):
        for _ in range(20):
            service.consume_roll(user)
        with pytest.raises(NoRollsAvailableError) as info:
            service.consume_roll(user)
        details = getattr(info.value, "details", {})
        assert "resets_at" in details
        assert "next_roll_at" in details


class TestStatePayload:
    def test_the_payload_is_complete_for_the_roll_button(self, db, user, service):
        service.grant_bonus_rolls(user, 2)
        service.consume_roll(user)
        payload = service.sync(user).to_dict()
        assert payload == {
            "rolls_remaining": 21,
            "normal_rolls": 19,
            "bonus_rolls": 2,
            "daily_allowance": 20,
            "bank_cap": 20,
            "resets_at": payload["resets_at"],
            "next_roll_at": payload["next_roll_at"],
            "seconds_to_next_roll": payload["seconds_to_next_roll"],
            "regen_minutes": 45,
        }
        assert payload["next_roll_at"] is not None
        assert payload["seconds_to_next_roll"] > 0


class TestDailyEndpoint:
    def test_the_api_reports_the_whole_economy(self, client, authed):
        session = authed(880_100_002)
        response = client.get("/api/daily", headers=session["headers"])
        assert response.status_code == 200
        data = response.json()
        assert data["daily_allowance"] == 20
        assert data["normal_rolls"] == 20
        assert data["bonus_rolls"] == 0
        assert data["next_roll_at"] is None
        assert data["regen_minutes"] == 45

    def test_a_roll_spends_from_the_normal_bank_and_reports_the_clock(
        self, client, authed
    ):
        session = authed(880_100_003)
        rolled = client.post("/api/roll", headers=session["headers"], json={})
        assert rolled.status_code == 200, rolled.text
        rolls = rolled.json()["rolls"]
        assert rolls["normal_rolls"] == 19
        assert rolls["bonus_rolls"] == 0
        assert rolls["regen_minutes"] == 45
        assert rolls["next_roll_at"] is not None
        assert 0 < rolls["seconds_to_next_roll"] <= 45 * 60 + 5

    def test_a_regenerated_roll_is_visible_without_a_roll(self, client, authed, db):
        session = authed(880_100_004)
        client.post("/api/roll", headers=session["headers"], json={})

        with SessionLocal() as session_db:
            row = session_db.execute(
                select(User).where(User.telegram_id == 880_100_004)
            ).scalar_one()
            row.roll_regen_at = utcnow() - timedelta(minutes=46)
            session_db.commit()

        data = client.get("/api/daily", headers=session["headers"]).json()
        assert data["normal_rolls"] == 20

    def test_the_daily_claim_fills_the_bank_without_creating_a_surplus(self, client, authed):
        session = authed(880_100_005)
        client.post("/api/roll", headers=session["headers"], json={})
        claim = client.post("/api/daily/claim", headers=session["headers"], json={})
        assert claim.status_code == 200, claim.text
        data = client.get("/api/daily", headers=session["headers"]).json()
        assert data["normal_rolls"] == 20

    def test_a_second_claim_the_same_day_is_refused(self, client, authed):
        session = authed(880_100_006)
        first = client.post("/api/daily/claim", headers=session["headers"], json={})
        assert first.status_code == 200
        second = client.post("/api/daily/claim", headers=session["headers"], json={})
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "DAILY_ALREADY_CLAIMED"
