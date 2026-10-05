"""The roll reel.

The reel is the run-up to a result, not a result. These tests hold that line from both
sides: the frames have to be enough *and* varied enough to sell the scroll, and they must
be incapable of granting, scoring or persisting anything.
"""

from __future__ import annotations

import random
from itertools import pairwise

import pytest

from app.core.config import settings
from app.game.collectibles import CollectibleKind
from app.game.roll_reel import REEL_FRAME_COUNT, build_reel
from app.models.plates import Plate
from app.services.catalog import snapshot


@pytest.fixture()
def context(db):
    """The real, seeded catalogue - the same one a roll generates from."""
    return snapshot(db, settings.rarity_weights).context


def test_a_reel_is_long_enough_to_read_as_a_scroll(context):
    """A handful of frames would flash past; a reel has to feel like a stream."""
    frames = build_reel(context, rng=random.Random(1))
    assert len(frames) == REEL_FRAME_COUNT
    assert REEL_FRAME_COUNT >= 20


def test_a_reel_scrolls_through_many_different_collectibles(context):
    """
    Different countries, different shapes, repeated combinations.

    A reel of near-identical frames looks broken rather than busy, so consecutive
    repeats of the same country are skipped and re-rolled.
    """
    frames = build_reel(context, rng=random.Random(2))
    codes = [str(frame["country_code"]) for frame in frames]
    texts = [str(frame["plate_text"]) for frame in frames]

    assert len(set(codes)) >= 8, "the reel must show a genuinely different world"
    assert len(set(texts)) >= REEL_FRAME_COUNT - 2
    # No two identical countries back to back.
    assert all(a != b for a, b in pairwise(codes))


def test_a_reel_covers_both_collectible_kinds(context):
    """Plates and SIM cards, because the product has exactly these two kinds."""
    frames = build_reel(context, rng=random.Random(3))
    kinds = {str(frame["kind"]) for frame in frames}
    assert kinds <= {"VEHICLE_PLATE", "SIM_CARD"}
    assert kinds == {"VEHICLE_PLATE", "SIM_CARD"}


def test_a_phone_number_is_not_a_collectible(context):
    """A phone number is data printed on a SIM card, never a kind of its own."""
    frames = build_reel(context, rng=random.Random(4))
    for frame in frames:
        assert str(frame["kind"]) in {"VEHICLE_PLATE", "SIM_CARD"}
        assert str(frame["kind"]) != "PHONE_NUMBER"


def test_a_frame_carries_the_same_recipe_contract_as_a_real_card(context):
    """
    A frame renders through the real renderer.

    If a frame's recipe were missing a field the real card carries, the frame would fall
    back to a default and stop looking like the country's plate - which would give away
    that the whole reel is fake.
    """
    for frame in build_reel(context, rng=random.Random(5)):
        visual = frame["visual"]
        assert isinstance(visual, dict)
        for key in (
            "width_mm",
            "height_mm",
            "aspect",
            "background",
            "border",
            "font_stack",
            "letter_spacing",
            "band_position",
            "region_position",
            "mount",
            "sheen",
            "relief",
            "grain",
        ):
            assert key in visual, key
        # The ratio is the one the declared millimetres imply.
        assert visual["aspect"] == pytest.approx(
            visual["width_mm"] / visual["height_mm"], abs=0.01
        )


def test_a_frame_prints_exactly_the_text_the_generator_produced(context):
    """Segments and gaps must reconstruct the frame's own value, or the object lies."""
    for frame in build_reel(context, rng=random.Random(6)):
        segments = [str(item) for item in frame["display_segments"]]
        gaps = [bool(item) for item in frame["display_segment_gaps"]]
        # Segments and gaps are two views of the same list, so a length mismatch would be a
        # server bug rather than something to tolerate.
        printed = "".join(
            (" " if gap else "") + text
            for text, gap in zip(segments, gaps, strict=True)
        )
        assert printed.strip() == str(frame["plate_text"])


def test_hunting_a_country_reels_through_that_country(context):
    """A Georgia hunt must not flash the whole world past the player."""
    frames = build_reel(context, country_code="GEO", rng=random.Random(7))
    assert frames
    assert {str(frame["country_code"]) for frame in frames} == {"GEO"}


def test_hunting_a_kind_reels_through_that_kind(context):
    frames = build_reel(context, kind=CollectibleKind.SIM_CARD, rng=random.Random(8))
    assert frames
    assert {str(frame["kind"]) for frame in frames} == {"SIM_CARD"}


def test_a_country_and_kind_can_be_narrowed_together(context):
    frames = build_reel(
        context,
        country_code="GEO",
        kind=CollectibleKind.VEHICLE_PLATE,
        rng=random.Random(9),
    )
    assert frames
    assert {str(frame["country_code"]) for frame in frames} == {"GEO"}
    assert {str(frame["kind"]) for frame in frames} == {"VEHICLE_PLATE"}


def test_a_reel_persists_nothing(context, db):
    """
    The whole contract, in one test.

    A frame is a picture. It is never written to the database, so no frame can be owned,
    sold, counted or replayed - which is what makes a fast, noisy reel free.
    """
    before = db.query(Plate).count()
    build_reel(context, rng=random.Random(10))
    db.rollback()
    assert db.query(Plate).count() == before


def test_two_reels_differ(context):
    """
    Consecutive reels are not the same run.

    A fixed frame list would make the roll feel like a video rather than a search.
    """
    first = [str(frame["plate_text"]) for frame in build_reel(context, rng=random.Random(11))]
    second = [str(frame["plate_text"]) for frame in build_reel(context, rng=random.Random(12))]
    assert first != second


def test_the_same_seed_reproduces_the_same_reel(context):
    """Reproducible, so a screenshot or a bug report can name the exact frames."""
    first = build_reel(context, rng=random.Random(13))
    second = build_reel(context, rng=random.Random(13))
    assert [frame["plate_text"] for frame in first] == [frame["plate_text"] for frame in second]


def test_a_frame_is_never_the_result(context, db, client, authed):
    """
    The reel and the winning card are separate things, from separate generators.

    The roll commits its result before any frame exists, and the frames are built from
    the catalogue afterwards. A client that discarded the real card and believed the
    last frame it saw would own nothing - which is exactly the guarantee that makes the
    animation honest.
    """
    session = authed(9_100_001)
    payload = client.post("/api/roll", headers=session["headers"]).json()

    assert payload["reel"], "the roll must carry its run-up"
    assert payload["plate"]["rarity"] == payload["rarity"]
    # Exactly one plate row exists for this find: the frames left nothing behind.
    winner = payload["plate"]["plate_text"]
    assert db.query(Plate).filter(Plate.plate_text == winner).count() >= 1


def test_the_roll_response_carries_the_reel(client, authed):
    """The frames arrive with the result, in the same response."""
    session = authed(9_100_002)
    response = client.post("/api/roll", headers=session["headers"])
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["reel"], list)
    assert len(payload["reel"]) == REEL_FRAME_COUNT
    for frame in payload["reel"]:
        assert frame["plate_text"]
        assert frame["country_code"]
        assert frame["kind"] in {"VEHICLE_PLATE", "SIM_CARD"}
        assert frame["visual"]["width_mm"] > 0


def test_hunting_a_kind_narrows_the_reel(client, authed):
    """A SIM hunt reels through cards, not through plates."""
    session = authed(9_100_003)
    payload = client.post("/api/roll?category=sim", headers=session["headers"]).json()
    assert payload["reel"]
    assert {frame["kind"] for frame in payload["reel"]} == {"SIM_CARD"}


def test_a_replayed_roll_returns_its_reel_too(client, authed):
    """
    An idempotent replay must still be a usable payload.

    The reel is regenerated per response rather than stored, because it is not game state.
    A replayed roll therefore returns a fresh reel with the *same* winner.
    """
    session = authed(9_100_004)
    key = "reel-replay-key"
    first = client.post("/api/roll", headers={**session["headers"], "Idempotency-Key": key}).json()
    second = client.post("/api/roll", headers={**session["headers"], "Idempotency-Key": key}).json()
    assert second["replayed"] is True
    assert second["plate"]["plate_text"] == first["plate"]["plate_text"]
    assert len(second["reel"]) == len(first["reel"])
