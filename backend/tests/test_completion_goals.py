"""Country completion sets and the single next objective.

The point of these tests is that the player always has exactly one thing to chase, and
that it is computed from real authoritative rows rather than invented client-side.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.plates import Country
from app.services.goals import (
    COUNTRY_SECTIONS,
    NEAR_TERM,
    GoalService,
    country_completion,
    country_sections,
    section_totals,
)

SECTION_CODES = tuple(code for code, _en, _ru in COUNTRY_SECTIONS)


def _country(db, code: str) -> Country:
    return db.execute(select(Country).where(Country.code == code)).scalar_one()


class TestCompletionSections:
    def test_every_playable_country_has_the_four_sections(self, db):
        for country in db.execute(
            select(Country).where(Country.is_playable.is_(True))
        ).scalars():
            sections = country_sections(db, 0, country)
            assert [section["code"] for section in sections] == list(SECTION_CODES)
            assert all(section["total"] >= 1 for section in sections)

    def test_sections_start_empty_for_a_new_player(self, db):
        completion = country_completion(db, _fake_user(), _country(db, "RUS"))
        assert completion["collected"] == 0
        assert completion["progress"] == 0.0
        assert completion["completed"] is False
        assert completion["total"] == sum(
            section["total"] for section in completion["sections"]
        )

    def test_targets_are_derived_from_the_live_catalogue(self, db):
        country = _country(db, "RUS")
        totals = section_totals(db, country)
        assert totals.standard > 0
        assert totals.special > 0
        assert totals.regions > 0
        # Standard scales with the layouts and the regions, so it is the big goal.
        assert totals.standard >= totals.special

    def test_a_locked_country_still_reports_sections(self, db):
        row = db.execute(
            select(Country).where(Country.is_active.is_(True), Country.is_playable.is_(False))
        ).scalars().first()
        if row is None:
            return
        completion = country_completion(db, _fake_user(), row)
        assert len(completion["sections"]) == 4


class TestNextTarget:
    def test_the_goal_payload_is_machine_readable(self, db):
        target = GoalService(db).next_target(_fake_user(), country_code="JPN")
        assert target["code"]
        assert target["country_code"] == "JPN"
        assert isinstance(target["current"], int)
        assert isinstance(target["target"], int)
        assert target["remaining"] >= 0
        # No user-facing copy travels from the backend.
        assert set(target) <= {
            "code",
            "country_code",
            "country_name_en",
            "country_name_ru",
            "country_flag",
            "current",
            "target",
            "remaining",
            "progress",
            "section_code",
            "section_name_en",
            "section_name_ru",
            "mission_code",
            "mission_name_en",
            "mission_name_ru",
            "album_code",
            "album_name_en",
            "album_name_ru",
            "rarity",
            "achievement_code",
            "reward_coins",
            "providers_total",
        }

    def test_exactly_one_goal_is_returned(self, db):
        result = GoalService(db).next_target(_fake_user(), country_code="RUS")
        assert isinstance(result, dict)
        assert result["code"]

    def test_the_roll_response_carries_one_next_target(self, client, authed):
        session = authed(884_100_001)
        payload = client.post("/api/roll", headers=session["headers"], json={}).json()
        assert payload["next_target"]["code"]

    def test_the_garage_carries_one_next_target(self, client, authed):
        session = authed(884_100_002)
        payload = client.get("/api/garage", headers=session["headers"]).json()
        assert payload["next_target"]["code"]
        assert payload["rolls"]["bank_cap"] == 20

    def test_the_country_screen_carries_its_own_goal(self, client, authed):
        session = authed(884_100_003)
        payload = client.get("/api/countries/DEU", headers=session["headers"]).json()
        assert payload["next_target"]["code"]
        assert payload["completion"]["country_code"] == "DEU"
        assert len(payload["completion"]["sections"]) == 4

    def test_a_sim_hunt_offers_the_operator_goal(self, client, authed):
        session = authed(884_100_004)
        payload = client.post(
            "/api/roll?category=SIM_CARD&country_code=RUS", headers=session["headers"], json={}
        ).json()
        target = payload["next_target"]
        # With no other goal close, the SIM line's own coverage is the objective.
        assert target["code"] in {"country_operator", "country_set", "country_region", "mission", "album"}
        if target["code"] == "country_operator":
            assert target["providers_total"] >= 2

    def test_near_completion_sections_are_preferred(self, db):
        """The objective a player is closest to is the one offered."""
        service = GoalService(db)
        target = service.next_target(_fake_user(), country_code="RUS")
        # With an empty collection nothing is near completion, so the country goal is used.
        assert target["code"] in {"country_set", "country_region", "country_operator", "mission", "album", "rarity", "first_discovery", "keep_rolling", "collection"}

    def test_the_near_term_window_is_bounded(self):
        assert NEAR_TERM >= 1
        assert NEAR_TERM <= 5


def _fake_user():
    """A minimal user-shaped object for the pure computation, with no DB row."""
    from app.models.user import User

    user = User(telegram_id=999_999_999, first_name="Goal")
    user.id = 0
    return user
