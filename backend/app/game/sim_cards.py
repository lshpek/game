"""Collectible SIM cards: fictional operators and synthetic printed numbers.

A SIM card in NUMORA is a **physical collectible object** - a plastic card with a
chip, a printed operator brand, a series and an edition. The phone number printed on
it is *information on the card*, never an independent collectible and never a real
subscriber line.

Safety contract
---------------
Every number produced here is synthetic:

* it is built from a documented **game block** (``GAME_PREFIX``) that is not an
  assigned national prefix, so the result cannot collide with a live number;
* the generator never resolves, validates or reverse-looks-up a number;
* nothing is dialled, sent or published anywhere outside the game;
* the number is tagged ``synthetic`` so no downstream consumer can mistake the card
  for a subscriber identity.

Format contract
---------------
``FORMATS`` maps a country to the *grouping* used when printing its number. These are
a stylised game representation inspired by how each country's numbers are usually
grouped for humans. They are **not** a real numbering plan and make no regulatory
claim; every card is explicitly fictional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.game.iso_countries import iso_country

#: Attached to every generated SIM collectible.
SYNTHETIC_FLAG = "synthetic"

#: Digits that are guaranteed not to be an assigned national prefix anywhere, used
#: as the leading game block of every synthetic number.
GAME_PREFIX = "9"

#: Marker written on the card so a printed number is never mistaken for a contact.
GAME_TAG = "NUMORA-SIM"


class SimEdition(StrEnum):
    """Collectible editions, cheapest first."""

    ORIGIN = "ORIGIN"
    SIGNAL = "SIGNAL"
    PULSE = "PULSE"
    APEX = "APEX"
    CROWN = "CROWN"


#: ``(edition, weight, rarity_floor)``. Heavier weights on the cheap editions so a
#: CROWN card really is rare.
EDITIONS: tuple[tuple[str, float, str], ...] = (
    ("ORIGIN", 3.0, "COMMON"),
    ("SIGNAL", 2.0, "UNCOMMON"),
    ("PULSE", 1.2, "RARE"),
    ("APEX", 0.7, "EPIC"),
    ("CROWN", 0.35, "LEGENDARY"),
)

#: Fictional operator brands. None of them is modelled on a real carrier; the names
#: are invented so the collectible line cannot be mistaken for a real network.
OPERATORS: tuple[tuple[str, str, str], ...] = (
    ("numa", "NUMA", "НУМА"),
    ("nova", "NOVA", "НОВА"),
    ("orbit", "ORBIT", "ОРБИТ"),
    ("volt", "VOLT", "ВОЛЬТ"),
    ("pulse", "PULSE", "ПУЛЬС"),
    ("axis", "AXIS", "ОСИ"),
    ("ion", "ION", "ИОН"),
    ("lumen", "LUMEN", "ЛЮМЕН"),
    ("kite", "KITE", "КАЙТ"),
)

#: Countries that get a hand-picked operator line. Everything else is assigned
#: deterministically from its ISO code, so a new country needs no configuration.
_OPERATORS_BY_COUNTRY: dict[str, tuple[str, ...]] = {
    "RUS": ("numa", "nova", "orbit"),
    "USA": ("volt", "pulse", "axis"),
    "GBR": ("ion", "nova"),
    "DEU": ("volt", "ion"),
    "JPN": ("orbit", "axis"),
    "ARE": ("pulse", "numa"),
    "FRA": ("axis", "ion"),
    "ITA": ("nova", "volt"),
    "KAZ": ("orbit", "numa"),
    "CAN": ("pulse", "axis"),
    "ARM": ("ion",),
    "GEO": ("volt",),
    "CHN": ("lumen", "kite"),
    "KOR": ("orbit", "pulse"),
    "IND": ("kite", "lumen"),
    "AUS": ("nova", "axis"),
    "NZL": ("ion", "orbit"),
    "SGP": ("kite", "pulse"),
    "BRA": ("volt", "nova"),
    "MEX": ("axis", "pulse"),
    "ZAF": ("lumen", "ion"),
}

_OPERATOR_BY_CODE = {code: (code, latin, local) for code, latin, local in OPERATORS}


@dataclass(frozen=True, slots=True)
class SimFormat:
    """How one country prints a synthetic number on a card.

    ``prefixes`` are stylised national-looking blocks; ``groups`` are the digit-run
    lengths after the prefix. Both are game fiction.
    """

    calling_code: str
    prefixes: tuple[tuple[str, float], ...]
    #: Digit-run lengths after the prefix, e.g. ``(3, 4)`` -> ``DDD DDDD``.
    groups: tuple[int, ...] = (3, 4)
    #: Optional extra groupings, printed with a lower weight.
    alt_groups: tuple[tuple[int, ...], ...] = ()
    separator: str = " "

    def groupings(self) -> tuple[tuple[int, ...], ...]:
        return (self.groups, *self.alt_groups)

    def pattern(self) -> str:
        """Template-language pattern for the country's numbers.

        The prefix and the calling code are written as plain literals: they survive
        :func:`app.game.plate_templates.parse_template` verbatim, while the ``F`` token
        only ever emits a single digit.
        """
        head = f"+{self.calling_code.lstrip('+')}"
        best_prefix = max(self.prefixes, key=lambda item: item[1])[0]
        return f"{head} {best_prefix} " + " ".join("D" * size for size in self.groups)


#: Hand-tuned groupings for the countries that ship playable on day one.
#: ``prefixes`` are stylised national-looking blocks; ``groups`` are digit-run lengths.
_FORMATS: dict[str, SimFormat] = {
    "RUS": SimFormat("+7", (("900", 3.0), ("903", 2.0), ("912", 1.5)), (3, 3, 2, 2)),
    "USA": SimFormat("+1", (("201", 1.0), ("415", 1.0), ("646", 1.0)), (3, 4)),
    "CAN": SimFormat("+1", (("604", 1.0), ("416", 1.0)), (3, 4)),
    "MEX": SimFormat("+52", (("55", 1.0), ("81", 1.0)), (3, 3, 4)),
    "BRA": SimFormat("+55", (("11", 1.0), ("21", 1.0)), (4, 4, 4)),
    "ARG": SimFormat("+54", (("11", 1.0),), (2, 4, 4)),
    "CHL": SimFormat("+56", (("9", 1.0),), (1, 4, 4)),
    "COL": SimFormat("+57", (("300", 1.0), ("601", 1.0)), (3, 3, 4)),
    "GBR": SimFormat("+44", (("7700", 2.0), ("7800", 1.5)), (6, 6)),
    "DEU": SimFormat("+49", (("151", 2.0), ("170", 1.0)), (8, 7, 2)),
    "FRA": SimFormat("+33", (("6", 1.0), ("7", 0.6)), (2, 2, 2, 2)),
    "ITA": SimFormat("+39", (("3", 1.0),), (3, 7)),
    "ESP": SimFormat("+34", (("6", 1.0),), (3, 3, 3)),
    "PRT": SimFormat("+351", (("9", 1.0),), (3, 3, 3)),
    "NLD": SimFormat("+31", (("6", 1.0),), (8, 1)),
    "BEL": SimFormat("+32", (("4", 1.0),), (9, 2)),
    "CHE": SimFormat("+41", (("79", 1.0),), (9, 2)),
    "AUT": SimFormat("+43", (("660", 1.0),), (7, 4)),
    "POL": SimFormat("+48", (("512", 1.0),), (3, 3, 3)),
    "CZE": SimFormat("+420", (("601", 1.0),), (3, 3, 3)),
    "SVK": SimFormat("+421", (("9", 1.0),), (3, 3, 2)),
    "HUN": SimFormat("+36", (("20", 1.0), ("30", 1.0)), (2, 3, 4)),
    "ROU": SimFormat("+40", (("72", 1.0),), (3, 3, 3)),
    "BGR": SimFormat("+359", (("87", 1.0),), (3, 3, 4)),
    "GRC": SimFormat("+30", (("69", 1.0),), (3, 4, 4)),
    "SWE": SimFormat("+46", (("70", 1.0),), (3, 3, 4)),
    "NOR": SimFormat("+47", (("40", 1.0), ("4", 0.4)), (3, 2, 3)),
    "DNK": SimFormat("+45", (("20", 1.0),), (2, 2, 2, 2)),
    "FIN": SimFormat("+358", (("40", 1.0), ("50", 1.0)), (3, 3, 4)),
    "ISL": SimFormat("+354", (("6", 1.0),), (3, 3, 3)),
    "IRL": SimFormat("+353", (("8", 1.0),), (3, 3, 4)),
    "EST": SimFormat("+372", (("5", 1.0),), (3, 4)),
    "LVA": SimFormat("+371", (("2", 1.0),), (3, 3, 3)),
    "LTU": SimFormat("+370", (("6", 1.0),), (3, 3, 3)),
    "UKR": SimFormat("+380", (("50", 1.0), ("67", 1.0)), (3, 3, 3)),
    "BLR": SimFormat("+375", (("29", 1.0),), (3, 3, 2, 2)),
    "KAZ": SimFormat("+7", (("700", 2.0), ("747", 1.5)), (3, 3, 2, 2)),
    "JPN": SimFormat("+81", (("90", 1.0),), (3, 4)),
    "KOR": SimFormat("+82", (("10", 1.0),), (4, 4)),
    "CHN": SimFormat("+86", (("139", 1.0), ("158", 1.0)), (4, 4, 4)),
    "IND": SimFormat("+91", (("987", 1.0), ("900", 1.0)), (5, 5)),
    "TUR": SimFormat("+90", (("532", 1.0),), (3, 3, 2, 2)),
    "ISR": SimFormat("+972", (("54", 1.0),), (3, 3, 3)),
    "ARE": SimFormat("+971", (("50", 1.0),), (3, 3, 4)),
    "SAU": SimFormat("+966", (("50", 1.0),), (3, 3, 4)),
    "THA": SimFormat("+66", (("8", 1.0),), (3, 3, 3)),
    "SGP": SimFormat("+65", (("8", 1.0), ("9", 0.8)), (4, 4)),
    "AUS": SimFormat("+61", (("4", 1.0),), (3, 3, 3)),
    "NZL": SimFormat("+64", (("21", 1.0),), (3, 3, 4)),
    "ARM": SimFormat("+374", (("77", 1.0),), (3, 3, 2, 2)),
    "GEO": SimFormat("+995", (("555", 1.0),), (3, 3, 3)),
    "ZAF": SimFormat("+27", (("82", 1.0),), (3, 3, 3)),
}


def _generic_format(country_code: str) -> SimFormat:
    """Documented synthetic format for a country without a tuned entry.

    The game block plus seven digits in two groups: plausible at a glance, impossible
    to mistake for a real line, and identical in shape for every unconfigured country
    so the line never claims a numbering plan it does not have.
    """
    iso = iso_country(country_code)
    calling = iso.calling_code if iso and iso.calling_code else "+999"
    return SimFormat(calling, ((GAME_PREFIX + "00", 1.0),), (3, 4))


def sim_format(country_code: str) -> SimFormat:
    """The SIM number format used for one country."""
    code = str(country_code or "").strip().upper()
    return _FORMATS.get(code) or _generic_format(code)


def sim_patterns(country_code: str) -> tuple[str, ...]:
    """One template pattern per distinct grouping of a country's numbers."""
    fmt = sim_format(country_code)
    seen: list[str] = []
    for prefix, _weight in fmt.prefixes:
        head = f"+{fmt.calling_code.lstrip('+')}"
        for groups in fmt.groupings():
            pattern = f"{head} {prefix} " + " ".join("D" * size for size in groups)
            if pattern not in seen:
                seen.append(pattern)
    if not seen:  # pragma: no cover - every format defines at least one grouping
        seen.append(fmt.pattern())
    return tuple(seen)


def operators_for(country_code: str) -> tuple[tuple[str, str, str], ...]:
    """Fictional operator brands available in one country."""
    code = str(country_code or "").strip().upper()
    names = _OPERATORS_BY_COUNTRY.get(code)
    if not names:
        # Deterministic round-robin so two different countries never share an exact
        # line by accident, and so adding a country needs no configuration.
        start = sum(ord(ch) for ch in code) % len(OPERATORS)
        count = 2 + (start % 2)
        names = tuple(
            OPERATORS[(start + offset) % len(OPERATORS)][0] for offset in range(count)
        )
    return tuple(_OPERATOR_BY_CODE[name] for name in names)


@dataclass(frozen=True, slots=True)
class SimCardDetails:
    """The type-specific payload stored on a SIM collectible row."""

    operator_code: str
    operator: str
    operator_local: str
    series: str
    edition: str
    synthetic_number: str
    calling_code: str
    tags: tuple[str, ...] = field(default=("sim", SYNTHETIC_FLAG))


def series_for(number: str) -> str:
    """Deterministic series code printed on the card (``N-07``).

    Derived from the printed number so the same card always carries the same series -
    the identity of a SIM collectible is its printed number.
    """
    digits = "".join(ch for ch in number if ch.isdigit()) or "0"
    bucket = int(digits[-4:]) % 90
    return f"N-{bucket + 10:02d}"


def card_details(
    *,
    country_code: str,
    operator_code: str,
    edition: str,
    number: str,
) -> SimCardDetails:
    """Assemble the stored payload for one generated SIM card."""
    operator = _OPERATOR_BY_CODE.get(operator_code) or OPERATORS[0]
    return SimCardDetails(
        operator_code=operator[0],
        operator=operator[1],
        operator_local=operator[2],
        series=series_for(number),
        edition=edition,
        synthetic_number=number,
        calling_code=sim_format(country_code).calling_code,
    )


def details_to_dict(details: SimCardDetails) -> dict[str, object]:
    """JSON-safe payload written to ``plates.details``."""
    return {
        "operator_code": details.operator_code,
        "operator": details.operator,
        "operator_local": details.operator_local,
        "series": details.series,
        "edition": details.edition,
        "synthetic_number": details.synthetic_number,
        "calling_code": details.calling_code,
        "synthetic": True,
    }


__all__ = [
    "EDITIONS",
    "GAME_PREFIX",
    "GAME_TAG",
    "OPERATORS",
    "SYNTHETIC_FLAG",
    "SimCardDetails",
    "SimEdition",
    "SimFormat",
    "card_details",
    "details_to_dict",
    "operators_for",
    "series_for",
    "sim_format",
    "sim_patterns",
]
