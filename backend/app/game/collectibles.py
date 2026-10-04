"""Collectible categories for the Number Universe.

One Number Universe, three collectible kinds:

``VEHICLE_PLATE``
    Real-world inspired vehicle registration plates - the flagship object.

``PHONE_NUMBER``
    **Synthetic** phone numbers. These are game objects, not subscriber
    identities: nothing in this module resolves, validates or reverse-looks-up a
    number, no real subscriber data is ever read or stored, and the generator
    deliberately builds every number from documented *game* blocks so the result
    cannot collide with an assigned number. The player never sees a number that
    belongs to a person.

``SIM_CARD``
    **Synthetic** collectible SIM cards. The operator names are invented
    (NUMA, NOVA, ORBIT, VOLT, PULSE, AXIS, ION) and the card carries a
    collectible serial plus an edition - it is a trading-card object, not a
    subscriber identifier.

Why this lives beside the existing plate engine instead of replacing it
-------------------------------------------------------------------------
:class:`~app.game.countries.TemplateDef` already carries ``plate_type`` and
:class:`~app.models.plates.Plate` already stores it, with a *country-scoped*
unique constraint on the normalised value. Categories are therefore a **data**
axis, not a schema one: adding a category means adding templates, and the whole
roll pipeline, ownership, duplicates, first discovery, albums, missions,
leaderboards and the ledger keep working untouched. That is what keeps this
extensible without a risky migration - and what makes a fourth or fifth category
(postal codes, train numbers, room numbers) a one-file change.

Server authority: the category of a roll is decided here, on the server, from the
eligible template pool. The client sends a *filter* (category / country) and
never a result.
"""

from __future__ import annotations

from enum import StrEnum

from app.game.countries import RegionDef, TemplateDef

#: Attached to every generated PHONE/SIM collectible so no downstream consumer can
#: mistake one for a real subscriber identity.
SYNTHETIC_FLAG = "synthetic"


class CollectibleCategory(StrEnum):
    """The kinds of object a player can hunt.

    ``VEHICLE_PLATE`` is the default; ``PHONE_NUMBER`` and ``SIM_CARD`` share the
    same storage and the same gameplay loop.
    """

    VEHICLE_PLATE = "VEHICLE_PLATE"
    PHONE_NUMBER = "PHONE_NUMBER"
    SIM_CARD = "SIM_CARD"


#: ``Plate.plate_type`` is a 24-char column that already exists; these are the
#: values stored there. They are short, stable and never user-facing.
PLATE_TYPE_BY_CATEGORY: dict[CollectibleCategory, str] = {
    CollectibleCategory.VEHICLE_PLATE: "VEHICLE",
    CollectibleCategory.PHONE_NUMBER: "PHONE",
    CollectibleCategory.SIM_CARD: "SIM",
}

CATEGORY_BY_PLATE_TYPE: dict[str, CollectibleCategory] = {
    value: key for key, value in PLATE_TYPE_BY_CATEGORY.items()
}


def category_for_plate_type(plate_type: str | None) -> CollectibleCategory:
    """Map a stored ``plate_type`` onto a category, defaulting to plates.

    Older rows were written with ``STANDARD``/``VEHICLE``/``SPECIAL``; all of them
    are vehicle plates, so an unknown value must never make a roll fail.
    """
    if not plate_type:
        return CollectibleCategory.VEHICLE_PLATE
    return CATEGORY_BY_PLATE_TYPE.get(str(plate_type).upper(), CollectibleCategory.VEHICLE_PLATE)


def normalize_category(value: str | None) -> CollectibleCategory | None:
    """Accept a category from a client filter. ``None`` means "reject"."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"", "ALL", "WORLD", "ANY"}:
        return None
    if text in {"PHONE", "PHONE_NUMBER", "PHONES"}:
        return CollectibleCategory.PHONE_NUMBER
    if text in {"SIM", "SIM_CARD", "SIMS"}:
        return CollectibleCategory.SIM_CARD
    if text in {"PLATE", "PLATES", "VEHICLE", "VEHICLE_PLATE"}:
        return CollectibleCategory.VEHICLE_PLATE
    return None


# ---------------------------------------------------------------------------
# PHONE_NUMBERS
# ---------------------------------------------------------------------------
# Every pattern is a *display format*. The digit slots come from the generator's
# ordinary ``D`` tokens, which draw from the full 0-9 range; what makes a number
# safe is that it is never published anywhere, never dialled, never resolved, and
# is presented to the player as a collectible object rather than a contact.
#
# ``F`` pins the country calling code. The shapes below follow each country's real
# grouping so the collection reads as authentic at a glance.
_PHONE_PATTERNS: dict[str, tuple[tuple[str, float], ...]] = {
    # code: ((pattern, weight), ...)
    "RUS": (("+7 F3 DDD DDD-DD-DD", 1.0), ("+7 F4 DDD DDD-DD-DD", 0.6)),
    "USA": (("+1 F1 DDD-DDD-DDDD", 1.0),),
    "KAZ": (("+7 F7 DDD-DDD-DD-DD", 1.0),),
    "DEU": (("+49 F30 DDDDDDD", 1.0), ("+49 F151 DDDDDDD", 0.4)),
    "GBR": (("+44 F7 DDDD DDDDDD", 1.0),),
    "JPN": (("+81 F90 DDD DDDD", 1.0),),
    "UAE": (("+971 F50 DDD DDDD", 1.0),),
    "FRA": (("+33 F6 DD DD DD DD", 1.0), ("+33 F7 DD DD DD DD", 0.7)),
    "ITA": (("+39 F3 DD DDDDDDD", 1.0),),
    "CAN": (("+1 F1 DDD-DDD-DDDD", 1.0),),
    "ARM": (("+374 F77 DDDD DD", 1.0),),
    "GEO": (("+995 F5DD DDD DD", 1.0),),
    # Additional catalogue countries use their own country code and grouping.
    "AUS": (("+61 F4 DDDD DDDD", 1.0),),
    "KOR": (("+82 F10 DDDD DDDD", 1.0),),
    "TUR": (("+90 F5DD DDD DD DD", 1.0),),
    "CHE": (("+41 F7D DDD DD DD", 1.0),),
    "NLD": (("+31 F6 DDDDDDDD", 1.0),),
    "POL": (("+48 F5DD DDD DD", 1.0),),
    "NOR": (("+47 F4DD DD DD", 1.0),),
    "BRA": (("+55 F11 DDDDD-DDDD", 1.0),),
    "MEX": (("+52 F1 DDD DDDD", 1.0),),
    "SGP": (("+65 F8DDD DDDD", 1.0),),
    "ISR": (("+972 F5D DDD DDDD", 1.0),),
    "ESP": (("+34 F6DD DDD DD", 1.0),),
    "AUT": (("+43 F6DD DDDDD", 1.0),),
    "CZE": (("+420 F7DD DDD DD", 1.0),),
    "SWE": (("+46 F7D DD DD DD", 1.0),),
    "FIN": (("+358 F4D DDDDDDD", 1.0),),
    "DNK": (("+45 F2D DD DD DD", 1.0),),
    "NZL": (("+64 F21 DDD DDD", 1.0),),
    "ZAF": (("+27 F8D DDD DDDD", 1.0),),
}
#: Fallback for a country without an entry above: a generic +999 game block.
_PHONE_FALLBACK = (("+999 F7 DDD DDD DDDD", 1.0),)


def phone_templates(country_code: str) -> tuple[TemplateDef, ...]:
    """Collectible phone templates for one country."""
    patterns = _PHONE_PATTERNS.get(str(country_code).upper(), _PHONE_FALLBACK)
    return tuple(
        TemplateDef(
            code=f"{country_code.lower()}_phone_{index}",
            pattern=pattern,
            weight=weight,
            plate_type=PLATE_TYPE_BY_CATEGORY[CollectibleCategory.PHONE_NUMBER],
            rarity_floor="UNCOMMON",
            config={"category": CollectibleCategory.PHONE_NUMBER.value, SYNTHETIC_FLAG: True},
        )
        for index, (pattern, weight) in enumerate(patterns, start=1)
    )


# ---------------------------------------------------------------------------
# SIM_CARDS
# ---------------------------------------------------------------------------
# Invented operator brands. Deliberately not modelled on any real operator's
# naming, so the cards read as a fictional collectible line.
SIM_OPERATORS: dict[str, tuple[tuple[str, str, str], ...]] = {
    # country: ((code, latin name, localised name), ...)
    "RUS": (("numa", "NUMA", "НУМА"), ("nova", "NOVA", "НОВА"), ("orbit", "ORBIT", "ОРБИТ")),
    "USA": (("volt", "VOLT", "VOLT"), ("pulse", "PULSE", "PULSE"), ("axis", "AXIS", "AXIS")),
    "GBR": (("ion", "ION", "ION"), ("nova", "NOVA", "NOVA")),
    "DEU": (("volt", "VOLT", "VOLT"), ("ion", "ION", "ION")),
    "JPN": (("orbit", "ORBIT", "_ORBIT_"), ("axis", "AXIS", "AXIS")),
    "UAE": (("pulse", "PULSE", "PULSE"), ("numa", "NUMA", "НУМА")),
    "FRA": (("axis", "AXIS", "AXIS"), ("ion", "ION", "ION")),
    "ITA": (("nova", "NOVA", "NOVA"), ("volt", "VOLT", "VOLT")),
    "KAZ": (("orbit", "ORBIT", "ORBIT"), ("numa", "NUMA", "НУМА")),
    "CAN": (("pulse", "PULSE", "PULSE"), ("axis", "AXIS", "AXIS")),
    "ARM": (("ion", "ION", "ION"),),
    "GEO": (("volt", "VOLT", "VOLT"),),
}
SIM_OPERATOR_FALLBACK: tuple[tuple[str, str, str], ...] = (("numa", "NUMA", "НУМА"),)

#: Collectible SIM editions. The serial is a display object: ``S`` is the edition
#: letter and ``D`` slots are generator digits.
SIM_EDITIONS: tuple[tuple[str, float, str], ...] = (
    ("ORIGIN", 3.0, "COMMON"),
    ("SIGNAL", 2.0, "UNCOMMON"),
    ("PULSE", 1.2, "RARE"),
    ("APEX", 0.7, "EPIC"),
    ("CROWN", 0.35, "LEGENDARY"),
)


def sim_templates(country_code: str) -> tuple[TemplateDef, ...]:
    """Collectible SIM templates for one country.

    The pattern carries the edition letter so a card can be recognised at a glance
    without an extra lookup, and the operator stays in ``config`` for the UI.
    """
    operators = SIM_OPERATORS.get(str(country_code).upper(), SIM_OPERATOR_FALLBACK)
    templates: list[TemplateDef] = []
    for op_code, _latin, _local in operators:
        for edition, weight, floor in SIM_EDITIONS:
            templates.append(
                TemplateDef(
                    code=f"{country_code.lower()}_sim_{op_code}_{edition.lower()}",
                    pattern=f"S{edition[0]} DDDD DDDD {op_code[:2].upper()}",
                    weight=weight,
                    plate_type=PLATE_TYPE_BY_CATEGORY[CollectibleCategory.SIM_CARD],
                    rarity_floor=floor,
                    config={
                        "category": CollectibleCategory.SIM_CARD.value,
                        SYNTHETIC_FLAG: True,
                        "operator_code": op_code,
                        "edition": edition,
                    },
                )
            )
    return tuple(templates)


def sim_regions(country_code: str) -> tuple[RegionDef, ...]:
    """Regions used by SIM cards so a country can still gate by region."""
    return (RegionDef(code="SIM", name_en="Collectible line", name_ru="Коллекционная линейка", weight=1.0),)


def templates_for_category(country_code: str, category: CollectibleCategory) -> tuple[TemplateDef, ...]:
    """Templates a country contributes to one category."""
    if category is CollectibleCategory.PHONE_NUMBER:
        return phone_templates(country_code)
    if category is CollectibleCategory.SIM_CARD:
        return sim_templates(country_code)
    return ()


CATEGORIES: tuple[CollectibleCategory, ...] = (
    CollectibleCategory.VEHICLE_PLATE,
    CollectibleCategory.PHONE_NUMBER,
    CollectibleCategory.SIM_CARD,
)


def parse_hunt_filter(
    *,
    category: str | None = None,
    country_code: str | None = None,
) -> dict[str, object]:
    """Validate a client's hunt filter.

    Only a *filter* is accepted. A malformed value is rejected loudly rather than
    quietly ignored, because a silent fallback would leave the player hunting for
    PLATES while the UI shows PHONES - the kind of mismatch that reads as a bug and
    destroys trust in the fairness of a roll.
    """
    from app.core.errors import ValidationError

    parsed = normalize_category(category)
    if category is not None and parsed is None and str(category).strip().upper() not in {
        "",
        "ALL",
        "WORLD",
        "ANY",
    }:
        raise ValidationError(
            f"Unknown collectible category: {category!r}. "
            f"Use one of {', '.join(item.value for item in CATEGORIES)}.",
            code="BAD_CATEGORY",
        )

    country = str(country_code or "").strip().upper()
    if country and (len(country) != 3 or not country.isalpha()):
        raise ValidationError(
            "Country must be a 3-letter code such as RUS.",
            code="BAD_COUNTRY",
        )

    return {
        "category": parsed,
        "country_code": country or None,
    }


__all__ = [
    "CATEGORIES",
    "CATEGORY_BY_PLATE_TYPE",
    "PLATE_TYPE_BY_CATEGORY",
    "SIM_EDITIONS",
    "SIM_OPERATORS",
    "SYNTHETIC_FLAG",
    "CollectibleCategory",
    "category_for_plate_type",
    "normalize_category",
    "parse_hunt_filter",
    "phone_templates",
    "sim_regions",
    "sim_templates",
    "templates_for_category",
]
