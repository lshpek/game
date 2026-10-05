"""Synthetic reel frames for the roll animation.

A roll is not "press, the number appears". It is a reel: a stream of collectibles that
scrolls past and settles on one. This module produces what the reel scrolls through.

The contract that matters
------------------------

**The reel never decides anything.** The result of a roll is generated, scored and
persisted by :class:`~app.services.plate_rolls.PlateRollService` *before* a single frame is
built. These frames are generated afterwards, from the same catalogue, with a **separate
RNG stream**, and are:

* never written to the database;
* never scored, valued, granted or counted;
* never returned as a result - the API sends the real :class:`PlateCard` separately.

So a frame is exactly what it claims to be: a picture of a plate, and nothing more. Even
if a client discarded the final card and believed the last frame it saw, the player would
own nothing and the economy would be unchanged - the frames are not a result, they are the
run-up to one.

Why the server builds them
--------------------------

The client could have permuted the winning plate's own text, but that would print a
Georgian-shaped serial on a United States plate. Frames here are generated through the real
engine - real country weights, real templates, real regional alphabets, real physical
formats - so every frame is a collectible that *could* have come out. That is what makes
the reel read as genuine rather than as noise.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.game.collectibles import CollectibleKind, kind_for_plate_type
from app.game.plate_formats import serialize_visual
from app.game.plate_generator import (
    GenerationContext,
    display_segments,
    pick_country,
    pick_region,
    pick_template,
    render_template,
    segment_gaps,
    segment_kinds,
)
from app.game.plate_templates import parse_template
from app.game.rng import Rng

#: How many frames the reel runs through.
#:
#: Long enough to read as a real search - a player sees a genuine stream of different
#: countries passing - and short enough that every frame stays a cheap compositor layer.
#: Above roughly thirty the browser drops frames on a mid-range Android anyway.
REEL_FRAME_COUNT = 26


@dataclass(frozen=True, slots=True)
class ReelFrame:
    """One synthetic collectible shown while the reel is spinning.

    ``visual`` is the same recipe contract the real card carries, so the reel renders
    through exactly the same component as the result: a frame is indistinguishable from the
    real thing except that it is not real.
    """

    plate_text: str
    display_segments: list[str]
    display_segment_gaps: list[bool]
    display_segment_kinds: list[str]
    visual: dict[str, object]
    kind: str
    country_code: str
    country_name_en: str
    country_flag: str

    def to_dict(self) -> dict[str, object]:
        return {
            "plate_text": self.plate_text,
            "display_segments": list(self.display_segments),
            "display_segment_gaps": list(self.display_segment_gaps),
            "display_segment_kinds": list(self.display_segment_kinds),
            "visual": self.visual,
            "kind": self.kind,
            "country_code": self.country_code,
            "country_name_en": self.country_name_en,
            "country_flag": self.country_flag,
        }


def build_reel(
    context: GenerationContext,
    *,
    count: int = REEL_FRAME_COUNT,
    country_code: str | None = None,
    kind: CollectibleKind | None = None,
    rng: Rng | None = None,
) -> list[dict[str, object]]:
    """Build the frame list for one reel.

    ``country_code`` and ``kind`` narrow the frames the way they narrow a real roll, so
    hunting one country reels through that country's plates rather than flashing the whole
    world past the player.

    ``rng`` is injected so a test gets a reproducible reel; in production the caller passes
    the roll's own generator, which means consecutive reels differ.
    """
    source = rng or random.Random()
    frames: list[ReelFrame] = []
    attempts = 0
    # Bounded: a template that cannot render must not spin here forever.
    limit = max(count, 1) * 6

    while len(frames) < count and attempts < limit:
        attempts += 1
        frame = _one_frame(context, source, country_code=country_code, kind=kind)
        if frame is None:
            continue
        # Two identical countries in a row make the reel look broken rather than busy, so
        # an immediate repeat of the previous frame is skipped and re-rolled.
        if frames and frames[-1].country_code == frame.country_code and attempts < limit - 1:
            continue
        frames.append(frame)

    if not frames:
        return []
    if kind is None and len(frames) > 1:
        wanted_country = str(country_code or "").strip().upper() or None
        available: set[CollectibleKind] = set()
        for code, options in context.templates_by_country.items():
            if wanted_country is not None and code != wanted_country:
                continue
            available.update(kind_for_plate_type(option.plate_type) for option in options)
        present = {CollectibleKind(frame.kind) for frame in frames}
        for missing in sorted(available - present, key=lambda item: item.value):
            replacement_index = next(
                (
                    index
                    for index in range(len(frames) - 1, -1, -1)
                    if sum(item.kind == frames[index].kind for item in frames) > 1
                ),
                len(frames) - 1,
            )
            for _ in range(24):
                candidate = _one_frame(
                    context, source, country_code=country_code, kind=missing
                )
                if candidate is None:
                    continue
                previous = frames[replacement_index - 1] if replacement_index else None
                if country_code or previous is None or previous.country_code != candidate.country_code:
                    frames[replacement_index] = candidate
                    present.add(missing)
                    break
    if len(frames) == 1:
        # A reel needs at least a couple of frames to scroll.
        frames = frames * 2
    return [frame.to_dict() for frame in frames[:count]]


def _one_frame(
    context: GenerationContext,
    rng: Rng,
    *,
    country_code: str | None,
    kind: CollectibleKind | None,
) -> ReelFrame | None:
    """One synthetic frame, or ``None`` when the requested shape has no candidates."""
    pool = _narrow(context, country_code=country_code, kind=kind)
    country = pick_country(pool, rng)
    if country_code and country.code != country_code:
        # The narrow pool did not contain the requested country, so skip rather than
        # showing the player a frame from somewhere else.
        return None
    region = pick_region(pool, country, rng)
    template = pick_template(pool, country, region, rng)
    if kind is not None and kind_for_plate_type(template.plate_type) is not kind:
        return None

    plate_text, styles = render_template(
        parse_template(template.pattern),
        alphabet=country.alphabet,
        region_code=region.code if region else None,
        rng=rng,
        country_code=country.code,
    )
    segments = display_segments(styles)
    return ReelFrame(
        plate_text=plate_text,
        display_segments=segments,
        display_segment_gaps=segment_gaps(styles),
        display_segment_kinds=segment_kinds(segments, region.code if region else None),
        visual=serialize_visual(
            country.visual,
            alpha2=country.iso_alpha2 or "",
            alpha3=country.code,
            country_code=country.code,
        ),
        kind=kind_for_plate_type(template.plate_type).value,
        country_code=country.code,
        country_name_en=country.name_en,
        country_flag=country.flag,
    )


def _narrow(
    context: GenerationContext,
    *,
    country_code: str | None,
    kind: CollectibleKind | None,
) -> GenerationContext:
    """Restrict the catalogue the way the real generator does.

    Reusing the real narrowing rules keeps a "hunt SIM cards" reel made of SIM cards and
    a "hunt Georgia" reel made of Georgian plates. An over-narrow request falls back to the
    whole world rather than producing nothing to scroll.
    """
    countries = context.countries
    templates = context.templates_by_country
    regions = context.regions_by_country
    if country_code:
        scoped = tuple(item for item in countries if item.code == country_code)
        if scoped:
            countries = scoped
            regions = {item.code: regions.get(item.code, ()) for item in scoped}
    if kind is not None:
        templates = {
            code: tuple(
                option for option in options if kind_for_plate_type(option.plate_type) is kind
            )
            for code, options in templates.items()
        }
        templates = {code: options for code, options in templates.items() if options}
        # A country can legitimately have no layout of the requested kind.
        # Keep only the countries that do, so pick_country never lands on a
        # country whose template pool is now empty (which would raise in
        # pick_template instead of scrolling past it).
        countries = tuple(item for item in countries if item.code in templates)
        regions = {code: regions.get(code, ()) for code in templates}
    if not templates:
        return context
    return GenerationContext(
        countries=countries,
        regions_by_country=regions,
        templates_by_country=templates,
        rarity_weights=context.rarity_weights,
        event_multipliers=context.event_multipliers,
        season_code=context.season_code,
    )


__all__ = [
    "REEL_FRAME_COUNT",
    "ReelFrame",
    "build_reel",
]
