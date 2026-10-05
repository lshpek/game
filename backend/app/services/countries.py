"""Country catalogue service: listing, search and the active-country context.

This is the single authoritative place a country's identity is read or changed.

Why the active country lives on the server
-------------------------------------------
``User.active_country_code`` is the one authoritative selection. It drives the roll,
the collection filters, the country statistics and the progression, and the backend
validates every change: a client may only pick a country that exists and is playable.
The frontend keeps a mirror for instant rendering, but it never decides.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.game import sim_cards
from app.models.plates import Country, Plate, Region, UserPlate
from app.models.user import User
from app.services import catalog


@dataclass(frozen=True, slots=True)
class CountryPage:
    """One page of the country atlas plus the totals the selector needs."""

    items: list[dict[str, object]]
    total: int
    playable_total: int
    locked_total: int
    active_code: str | None
    region_groups: list[str]
    query: str | None
    offset: int


def resolve(db: Session, code: str | None) -> Country | None:
    """Resolve an ISO 3166-1 alpha-3 *or* alpha-2 code to a country row."""
    return catalog.country_by_code(db, code or "")


def require_playable(db: Session, code: str | None) -> Country:
    """Resolve a country the roll is allowed to produce.

    Raises :class:`ValidationError` for an unknown or locked country instead of
    silently falling back: the client asked for a specific world, and quietly rolling
    somewhere else is exactly the kind of mismatch that looks like a cheat.
    """
    text = (code or "").strip().upper()
    if not text:
        raise ValidationError("Country code is required.", code="BAD_COUNTRY")
    country = resolve(db, text)
    if country is None:
        raise ValidationError(f"Unknown country code: {text}.", code="BAD_COUNTRY")
    if not country.is_active or not country.is_playable:
        raise ValidationError(
            f"{country.name_en} is not available yet.",
            code="COUNTRY_LOCKED",
        )
    return country


def list_countries(
    db: Session,
    *,
    search: str | None = None,
    region: str | None = None,
    playable_only: bool = False,
    limit: int = 60,
    offset: int = 0,
) -> CountryPage:
    """Searchable, paginated country atlas.

    ``search`` matches the code, the alpha-2 code and both display names, so
    "ru", "rus", "russia" and "россия" all find Russia.
    """
    limit = max(1, min(int(limit or 60), 250))
    offset = max(0, int(offset or 0))

    conditions = [Country.is_active.is_(True)]
    if playable_only:
        conditions.append(Country.is_playable.is_(True))
    if region:
        conditions.append(Country.region_group == str(region).strip().upper())

    term = (search or "").strip()
    if term:
        # One lower-cased blob per country keeps the match portable: SQLite's
        # ``lower()`` is ASCII-only, so "россия" would never match a Cyrillic name.
        conditions.append(Country.search_text.contains(term.lower()))

    base = select(Country).where(*conditions)
    rows = list(db.execute(base.order_by(Country.sort_order, Country.id)).scalars().all())
    total = len(rows)

    playable_total = int(
        db.execute(
            select(func.count(Country.id)).where(
                Country.is_active.is_(True), Country.is_playable.is_(True)
            )
        ).scalar_one()
    )
    locked_total = int(
        db.execute(
            select(func.count(Country.id)).where(
                Country.is_active.is_(True), Country.is_playable.is_(False)
            )
        ).scalar_one()
    )

    return CountryPage(
        items=[catalog.country_card(row) for row in rows[offset : offset + limit]],
        total=total,
        playable_total=playable_total,
        locked_total=locked_total,
        active_code=None,
        region_groups=sorted({row.region_group for row in rows if row.region_group}),
        query=term or None,
        offset=offset,
    )


def progress_map(db: Session, user_id: int) -> dict[str, dict[str, int]]:
    """Per-country collection progress for one player.

    Two aggregate queries instead of one per country, so the atlas stays cheap even
    with the full ISO list.
    """
    owned = (
        select(
            Plate.country_code.label("country_code"),
            func.count(func.distinct(Plate.id)).label("collected"),
        )
        .join(UserPlate, UserPlate.plate_id == Plate.id)
        .where(UserPlate.user_id == user_id)
        .group_by(Plate.country_code)
    )
    result: dict[str, dict[str, int]] = {}
    for row in db.execute(owned).all():
        result[row.country_code] = {"collected": int(row.collected or 0)}
    return result


def card(
    db: Session,
    country: Country,
    *,
    user_id: int | None = None,
    is_active: bool = False,
) -> dict[str, object]:
    """Full country payload: identity, presentation, SIM format and progress."""
    payload = dict(catalog.country_card(country))
    payload["is_active_country"] = is_active
    payload["sim"] = sim_card_config(country)
    # The country card doubles as the source of the collection's region filter, so the
    # client can offer "every region in Japan" without a second request.
    payload["regions"] = region_options(db, country)
    if user_id is not None:
        payload["collected"] = progress_map(db, user_id).get(country.code, {}).get("collected", 0)
    return payload


def region_options(db: Session, country: Country) -> list[dict[str, object]]:
    """The country's regions, in catalogue order, for the collection's region filter."""
    rows = (
        db.execute(
            select(Region.code, Region.name_en, Region.name_ru, Region.sort_order)
            .where(Region.country_id == country.id)
            .order_by(Region.sort_order, Region.code)
        )
        .all()
    )
    return [
        {"code": code, "name_en": name_en, "name_ru": name_ru, "sort_order": sort_order}
        for code, name_en, name_ru, sort_order in rows
    ]


def sim_card_config(country: Country) -> dict[str, object]:
    """SIM presentation configuration for the frontend to render the physical card.

    Providers are the real, current operators a country's cards may print, with their
    **game** rarity/value modifiers so the client can show why a card is worth more
    without ever implying a real-world tariff or market claim.
    """
    config = country.sim_config or {}
    fmt = sim_cards.sim_format(country.code)
    providers = sim_cards.operators_for(country.code)
    items = [
        {
            "code": provider.code,
            "brand": provider.brand,
            "local_name": provider.local_name,
            "rarity_modifier": provider.rarity_modifier,
            "value_modifier": provider.value_modifier,
            "visual": provider.visual,
            "accent": provider.accent,
            "is_real_brand": provider.real_brand,
        }
        for provider in providers
    ]
    return {
        "calling_code": config.get("calling_code") or fmt.calling_code,
        "groups": config.get("groups") or list(fmt.groups),
        "providers": items,
        # Compatibility alias for clients built against the previous key.
        "operators": [
            {"code": item["code"], "name": item["brand"], "name_local": item["local_name"]}
            for item in items
        ],
        "editions": config.get("editions") or [edition for edition, _w, _f in sim_cards.EDITIONS],
        "synthetic": True,
    }


def set_active_country(db: Session, user: User, code: str | None) -> Country | None:
    """Validate and persist the player's selected country.

    ``None`` (or an empty string) clears the selection and returns the player to the
    world-wide hunt, which is the default mode.
    """
    text = (code or "").strip()
    if not text or text.upper() in {"WORLD", "ALL", "ANY"}:
        user.active_country_code = None
        db.flush()
        return None
    country = require_playable(db, text)
    user.active_country_code = country.code
    db.flush()
    return country


def active_country(db: Session, user: User) -> Country | None:
    """The player's currently selected country, if it is still valid."""
    code = user.active_country_code
    if not code:
        return None
    country = resolve(db, code)
    if country is None or not country.is_active or not country.is_playable:
        # A country that was locked or removed must not leave the player stuck on a
        # world the backend can no longer generate.
        user.active_country_code = None
        db.flush()
        return None
    return country


def roll_country(db: Session, user: User, requested: str | None) -> str | None:
    """Resolve the country a roll must use.

    An explicit request wins - but it is still validated server-side. Otherwise the
    active country decides. ``None`` means "the whole world".
    """
    text = (requested or "").strip()
    if text:
        return require_playable(db, text).code
    country = active_country(db, user)
    return country.code if country else None


__all__ = [
    "CountryPage",
    "active_country",
    "card",
    "list_countries",
    "progress_map",
    "require_playable",
    "resolve",
    "roll_country",
    "set_active_country",
    "sim_card_config",
]
