"""The country catalogue: regions, plate layouts, currencies, albums and events.

Pure configuration built on the complete ISO 3166-1 list in
:mod:`app.game.iso_countries`. Adding a country - or a region, or a plate layout -
means appending one definition; no engine, API or React code changes.

Playability
-----------
Every ISO 3166-1 country and territory is seeded, but only countries with a complete
generation and presentation setup are **playable**. The rest are seeded as
``is_playable = False`` so the WORLD screen can list them as *locked / coming soon*
and a later release can flip one flag and add layouts - no schema change.

Format honesty
---------------
Country layouts are a *stylised game representation* inspired by the familiar look of
each country's plates and numbers. They are deliberately simplified and make no legal
or regulatory claim about real registration formats or numbering plans. Countries
that ship on the generic families are explicitly synthetic placeholders, not attempts
to reproduce a real scheme.

Identifiers
-----------
``code`` is the ISO 3166-1 **alpha-3** code and is the engine's stable key.
``iso_alpha2`` carries the two-letter form for deep links and share payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from app.game.iso_countries import ISO_COUNTRIES, IsoCountry, iso_country
from app.game.plate_formats import COUNTRY_FORMATS

LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CYRILLIC = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
JAPANESE = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヰヱヲン"
GEORGIAN = "აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ"
ARMENIAN = "ԱԲԳԴԵԶԷԸԹԺԻԼԽԾԿՀՁՂՃՄՅՆՇՈՉՊՋՌՍՎՏՐՑՒՓՔՕՖ"

REGION_TAGS: dict[str, str] = {
    "CIS": "cis",
    "EUROPE": "europe",
    "AMERICAS": "americas",
    "ASIA": "asia",
    "MIDEAST": "middle_east",
    "AFRICA": "africa",
    "OCEANIA": "oceania",
    "ANTARCTIC": "polar",
}


@dataclass(frozen=True, slots=True)
class RegionDef:
    """One region/state/canton of a country."""

    code: str
    name_en: str
    name_ru: str
    weight: float = 1.0
    config: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TemplateDef:
    """One plate layout for a country."""

    code: str
    pattern: str
    weight: float = 1.0
    plate_type: str = "STANDARD"
    rarity_floor: str = "COMMON"
    config: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CountryDef:
    """Everything the engine needs to generate one country's collectibles."""

    code: str
    name_en: str
    name_ru: str
    flag: str
    region_group: str
    currency_code: str
    currency_symbol: str
    weight: float
    alphabet: str
    letter_style: str = "LATIN"
    value_scale: float = 1.0
    rarity_modifier: float = 1.0
    visual: str = "european"
    sort_order: int = 0
    #: ISO 3166-1 alpha-2 code; empty only if the ISO list has none.
    iso_alpha2: str = ""
    #: Assigned calling code, printed on the country's SIM cards.
    calling_code: str = ""
    #: Whether the country is playable today. Locked countries are listed by the
    #: WORLD screen and rejected by the roll.
    playable: bool = False
    regions: tuple[RegionDef, ...] = ()
    #: Vehicle-plate layouts for this country. SIM card layouts live in
    #: :mod:`app.game.sim_cards` and are merged in by the catalogue, so a new kind
    #: never has to be threaded through the country tables.
    templates: tuple[TemplateDef, ...] = ()
    config: dict[str, object] = field(default_factory=dict)

    @property
    def tag(self) -> str:
        return REGION_TAGS.get(self.region_group, self.region_group.lower())


@dataclass(frozen=True, slots=True)
class AlbumDef:
    """A collectible set: a country completion set or a themed set."""

    code: str
    name_en: str
    name_ru: str
    description_en: str
    description_ru: str
    icon: str
    kind: str = "THEME"
    country_code: str | None = None
    sort_order: int = 0
    reward_coins: int = 500
    reward_title: str | None = None


@dataclass(frozen=True, slots=True)
class EventDef:
    """A rotating global event that re-weights country chances."""

    code: str
    name_en: str
    name_ru: str
    flag: str
    duration_days: int
    country_multipliers: dict[str, float]
    reward_coins: int
    reward_title: str | None = None
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class PlateFamily:
    """A stylised plate layout family shared by several countries.

    Families exist so the catalogue can ship every ISO country without inventing a
    real numbering plan for each one. They are clearly marked as game layouts.
    """

    key: str
    visual: str
    #: ``(code suffix, pattern, weight, plate_type)``
    layouts: tuple[tuple[str, str, float, str], ...]


#: Documented synthetic layout families. ``STANDARD`` layouts are the everyday plate;
#: the second layout is the rarer, non-standard variant.
PLATE_FAMILIES: dict[str, PlateFamily] = {
    "cis": PlateFamily(
        "cis",
        "ru",
        (
            ("std", "LDDD LL DD", 5.0, "STANDARD"),
            ("long", "DDDLLL DD", 1.4, "COMMERCIAL"),
            ("moto", "L DDDD DD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "euro_long": PlateFamily(
        "euro_long",
        "european",
        (
            ("std", "LL DDD LL", 5.0, "STANDARD"),
            ("long", "LLL DDDDD", 1.5, "COMMERCIAL"),
            ("moto", "LLLLLL", 0.7, "MOTORCYCLE"),
        ),
    ),
    "euro_compact": PlateFamily(
        "euro_compact",
        "fr",
        (
            ("std", "LLL DDDD", 5.0, "STANDARD"),
            ("alt", "LL DDD LL", 2.0, "STANDARD"),
            ("moto", "LLL DDD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "britain": PlateFamily(
        "britain",
        "gb",
        (
            ("std", "LL DD LLL", 5.0, "STANDARD"),
            ("prefix", "LLL DD LLL", 1.8, "STANDARD"),
            ("moto", "LLL DD DDD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "nordic": PlateFamily(
        "nordic",
        "nordic",
        (
            ("std", "LL DDD DD", 5.0, "STANDARD"),
            ("alt", "LLL DD DD", 1.6, "STANDARD"),
            ("moto", "LL DDDD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "americas": PlateFamily(
        "americas",
        "us",
        (
            ("std", "LLL DDDD", 5.0, "STANDARD"),
            ("alt", "LLL-DDD", 1.8, "STANDARD"),
            ("moto", "DDDDD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "americas_south": PlateFamily(
        "americas_south",
        "latam",
        (
            ("std", "LLL DD DD", 5.0, "STANDARD"),
            ("alt", "LLL DDDD", 1.8, "STANDARD"),
            ("moto", "LLLLLL", 0.7, "MOTORCYCLE"),
        ),
    ),
    "asia_compact": PlateFamily(
        "asia_compact",
        "jp",
        (
            ("std", "DD LL DD", 5.0, "STANDARD"),
            ("long", "L DDD DD DD", 1.8, "COMMERCIAL"),
            ("moto", "DDD LL DD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "asia_wide": PlateFamily(
        "asia_wide",
        "seasia",
        (
            ("std", "DDD LLL DD", 5.0, "STANDARD"),
            ("alt", "LL DD DDDD", 1.8, "STANDARD"),
            ("moto", "L DDDDD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "mideast": PlateFamily(
        "mideast",
        "ae",
        (
            ("std", "L DDD L", 5.0, "STANDARD"),
            ("alt", "DDD L L", 2.0, "STANDARD"),
            ("lux", "L DDDDD", 0.8, "SPECIAL"),
        ),
    ),
    "oceania": PlateFamily(
        "oceania",
        "oceania",
        (
            ("std", "LLL DD L", 5.0, "STANDARD"),
            ("alt", "LLL-DDD", 1.8, "STANDARD"),
            ("moto", "LLLL D", 0.7, "MOTORCYCLE"),
        ),
    ),
    "africa": PlateFamily(
        "africa",
        "africa",
        (
            ("std", "DD LLL DD", 5.0, "STANDARD"),
            ("alt", "LL DDD DD", 1.8, "STANDARD"),
            ("moto", "L DDDDD", 0.7, "MOTORCYCLE"),
        ),
    ),
    "generic": PlateFamily(
        "generic",
        "european",
        (
            ("std", "LL DDD LL", 5.0, "STANDARD"),
            ("alt", "LLL DDDD", 2.0, "STANDARD"),
            ("moto", "LLLLLL", 0.7, "MOTORCYCLE"),
        ),
    ),
}

#: Default family per continent.
FAMILY_BY_REGION: dict[str, str] = {
    "CIS": "cis",
    "EUROPE": "euro_compact",
    "AMERICAS": "americas",
    "ASIA": "asia_wide",
    "MIDEAST": "mideast",
    "AFRICA": "africa",
    "OCEANIA": "oceania",
    "ANTARCTIC": "generic",
}

#: Latin America uses its own family; North America the ``americas`` one.
_LATAM = frozenset(
    {
        "MEX", "BRA", "ARG", "CHL", "COL", "PER", "VEN", "ECU", "BOL", "PRY",
        "URY", "PAN", "CRI", "GTM", "HND", "SLV", "NIC", "JAM", "HTI", "DOM",
        "CUB", "TTO",
    }
)


# ---------------------------------------------------------------------------
# Playable country order
# ---------------------------------------------------------------------------
#: The twelve original launch countries keep their historical order and weights so
#: an existing player's roll distribution does not shift on upgrade.
ORIGINAL_ORDER: tuple[str, ...] = (
    "RUS", "USA", "KAZ", "DEU", "GBR", "FRA", "ITA", "CAN", "JPN", "ARE", "ARM", "GEO",
)

#: Additional countries that ship playable in the first global release.
PRIORITY_ORDER: tuple[str, ...] = (
    "MEX", "BRA", "ARG", "CHL", "COL",
    "ESP", "PRT", "NLD", "BEL", "CHE", "AUT", "POL", "CZE", "SVK", "HUN", "ROU",
    "BGR", "GRC", "SWE", "NOR", "DNK", "FIN", "ISL", "IRL", "EST", "LVA", "LTU",
    "UKR", "BLR",
    "KOR", "CHN", "IND", "TUR", "ISR", "SAU", "THA", "SGP", "AUS", "NZL",
    "ZAF",
)

#: Every country mapped to the physical plate format it actually uses.
#:
#: A country does not need a *layout family* of its own - several genuinely share one
#: standard - but it does need a physical *format*, and that is what decides the
#: millimetres, the border, the identifier band and the mounting hardware. The rows
#: resolve through :mod:`app.game.plate_formats.COUNTRY_FORMATS`, so there is one place
#: that knows what the world's plates look like.
#:
#: The curated launch countries carry their format key inline on the ``CountryDef``; this
#: table is what every derived country uses, and it is also consulted for the curated ones
#: so that a curated row can never drift away from the shared source of truth.
COUNTRY_VISUAL_OVERRIDES: dict[str, str] = dict(COUNTRY_FORMATS)


def visual_theme_for(code: str, family_visual: str) -> str:
    """The physical format for a country, else the family it was grouped under.

    A derived country is grouped by *layout family* for generation - that is a statement
    about the shape of its registration - but its presentation is a statement about its
    physical plate, and the two are not the same thing. That is why Spain is grouped with
    the compact European layouts and still renders as a 520x110 EU plate.
    """
    return COUNTRY_VISUAL_OVERRIDES.get(code) or family_visual


#: ``code -> (family, weight, value_scale, rarity_modifier)`` for the playable
#: countries that use a shared layout family.
PLAYABLE_TUNING: dict[str, tuple[str, float, float, float]] = {
    "MEX": ("americas_south", 3.2, 0.95, 1.04),
    "BRA": ("americas_south", 3.6, 1.0, 1.05),
    "ARG": ("americas_south", 2.6, 0.9, 1.03),
    "CHL": ("americas_south", 2.2, 0.92, 1.03),
    "COL": ("americas_south", 2.4, 0.9, 1.04),
    "ESP": ("euro_compact", 4.2, 1.05, 1.0),
    "PRT": ("euro_compact", 2.6, 1.0, 1.0),
    "NLD": ("euro_compact", 3.0, 1.08, 1.0),
    "BEL": ("euro_compact", 2.6, 1.08, 1.0),
    "CHE": ("euro_compact", 2.8, 1.25, 1.06),
    "AUT": ("euro_compact", 2.6, 1.08, 1.0),
    "POL": ("euro_compact", 3.0, 0.92, 1.02),
    "CZE": ("euro_compact", 2.2, 0.95, 1.0),
    "SVK": ("euro_compact", 2.0, 0.95, 1.0),
    "HUN": ("euro_compact", 2.0, 0.9, 1.0),
    "ROU": ("euro_compact", 2.0, 0.88, 1.0),
    "BGR": ("euro_compact", 1.8, 0.85, 1.0),
    "GRC": ("euro_compact", 2.0, 0.95, 1.0),
    "SWE": ("nordic", 2.4, 1.1, 1.0),
    "NOR": ("nordic", 2.0, 1.15, 1.0),
    "DNK": ("nordic", 2.0, 1.1, 1.0),
    "FIN": ("nordic", 1.9, 1.1, 1.0),
    "ISL": ("nordic", 1.5, 1.1, 1.02),
    "IRL": ("britain", 2.0, 1.05, 1.0),
    "EST": ("nordic", 1.4, 0.95, 1.0),
    "LVA": ("nordic", 1.4, 0.95, 1.0),
    "LTU": ("nordic", 1.5, 0.95, 1.0),
    "UKR": ("cis", 3.0, 0.75, 1.04),
    "BLR": ("cis", 2.2, 0.8, 1.04),
    "TUR": ("mideast", 3.0, 1.0, 1.02),
    "ISR": ("mideast", 1.8, 1.1, 1.04),
    "KOR": ("asia_compact", 2.6, 1.2, 1.06),
    "CHN": ("asia_compact", 4.0, 0.9, 1.08),
    "IND": ("asia_wide", 3.6, 0.75, 1.05),
    "SAU": ("mideast", 2.6, 1.35, 1.08),
    "THA": ("asia_wide", 2.2, 0.85, 1.04),
    "SGP": ("asia_compact", 2.0, 1.3, 1.08),
    "NZL": ("oceania", 1.8, 1.05, 1.02),
    "AUS": ("oceania", 2.6, 1.1, 1.04),
    "ZAF": ("africa", 2.2, 0.9, 1.04),
}

#: Countries whose English name differs from the ISO short name.
NAME_OVERRIDES: dict[str, tuple[str, str]] = {
    "USA": ("United States", "США"),
    "GBR": ("United Kingdom", "Великобритания"),
    "ARE": ("United Arab Emirates", "ОАЭ"),
    "CZE": ("Czechia", "Чехия"),
    "KOR": ("South Korea", "Южная Корея"),
    "RUS": ("Russia", "Россия"),
    "IRN": ("Iran", "Иран"),
    "SYR": ("Syria", "Сирия"),
    "LAO": ("Laos", "Лаос"),
    "VNM": ("Vietnam", "Вьетнам"),
    "TZA": ("Tanzania", "Танзания"),
    "BOL": ("Bolivia", "Боливия"),
    "VEN": ("Venezuela", "Венесуэла"),
    "BRN": ("Brunei", "Бруней"),
    "COD": ("DR Congo", "ДР Конго"),
    "COG": ("Congo", "Конго"),
    "CAF": ("Central African Republic", "ЦАР"),
    "DOM": ("Dominican Republic", "Доминикана"),
    "PRK": ("North Korea", "Северная Корея"),
    "CIV": ("Ivory Coast", "Кот-д'Ивуар"),
    "CPV": ("Cape Verde", "Кабо-Верде"),
    "SWZ": ("Eswatini", "Эсватини"),
    "TLS": ("Timor-Leste", "Восточный Тимор"),
    "MKD": ("North Macedonia", "Северная Македония"),
    "MDA": ("Moldova", "Молдова"),
    "BHS": ("Bahamas", "Багамы"),
    "GBR2": ("United Kingdom", "Великобритания"),
    "TTO": ("Trinidad and Tobago", "Тринидад и Тобаго"),
    "VUT": ("Vanuatu", "Вануату"),
    "WSM": ("Samoa", "Самоа"),
    "KIR": ("Kiribati", "Кирибати"),
    "FSM": ("Micronesia", "Микронезия"),
    "MHL": ("Marshall Islands", "Маршалловы Острова"),
    "PLW": ("Palau", "Палау"),
    "NRU": ("Nauru", "Науру"),
    "TUV": ("Tuvalu", "Тувалу"),
}


def _family_for(code: str, region_group: str) -> str:
    if code in _LATAM:
        return "americas_south"
    return FAMILY_BY_REGION.get(region_group, "generic")


# ---------------------------------------------------------------------------
# Region catalogues
# ---------------------------------------------------------------------------
RU_REGIONS = (
    RegionDef("77", "Moscow", "Москва", 4.0),
    RegionDef("50", "Moscow Oblast", "Московская область", 3.0),
    RegionDef("78", "Saint Petersburg", "Санкт-Петербург", 3.4),
    RegionDef("23", "Krasnodar", "Краснодар", 2.6),
    RegionDef("16", "Tatarstan", "Татарстан", 2.2),
    RegionDef("40", "Kaluga", "Калуга", 1.4),
    RegionDef("66", "Sverdlovsk", "Свердловская область", 2.0),
    RegionDef("52", "Nizhny Novgorod", "Нижегородская область", 2.0),
    RegionDef("63", "Samara", "Самарская область", 2.0),
    RegionDef("61", "Rostov", "Ростовская область", 1.8),
    RegionDef("54", "Novosibirsk", "Новосибирская область", 1.8),
    RegionDef("02", "Bashkortostan", "Башкортостан", 1.6),
)

US_REGIONS = (
    RegionDef("CA", "California", "Калифорния", 5.0),
    RegionDef("TX", "Texas", "Техас", 4.0),
    RegionDef("FL", "Florida", "Флорида", 3.6),
    RegionDef("NY", "New York", "Нью-Йорк", 3.6),
    RegionDef("NV", "Nevada", "Невада", 2.0),
    RegionDef("AZ", "Arizona", "Аризона", 2.0),
    RegionDef("WA", "Washington", "Вашингтон", 2.4),
    RegionDef("NJ", "New Jersey", "Нью-Джерси", 2.2),
    RegionDef("IL", "Illinois", "Иллинойс", 2.4),
    RegionDef("GA", "Georgia", "Джорджия", 2.2),
    RegionDef("CO", "Colorado", "Колорадо", 2.0),
    RegionDef("MI", "Michigan", "Мичиган", 2.0),
    RegionDef("MA", "Massachusetts", "Массачусетс", 1.8),
    RegionDef("AK", "Alaska", "Аляска", 1.2),
    RegionDef("HI", "Hawaii", "Гавайи", 1.2),
)

DE_REGIONS = (
    RegionDef("B", "Berlin", "Берлин", 3.0),
    RegionDef("M", "Munich", "Мюнхен", 3.0),
    RegionDef("HH", "Hamburg", "Гамбург", 2.4),
    RegionDef("HE", "Frankfurt", "Франкфурт", 2.2),
    RegionDef("S", "Stuttgart", "Штутгарт", 2.0),
    RegionDef("K", "Cologne", "Кёльн", 2.0),
    RegionDef("D", "Dusseldorf", "Дюссельдорф", 1.9),
    RegionDef("DD", "Dresden", "Дрезден", 1.8),
    RegionDef("L", "Leipzig", "Лейпциг", 1.6),
    RegionDef("H", "Hanover", "Ганновер", 1.7),
)

KZ_REGIONS = (
    RegionDef("02", "Almaty", "Алматы", 4.0),
    RegionDef("01", "Astana", "Астана", 3.4),
    RegionDef("03", "Shymkent", "Шымкент", 2.6),
    RegionDef("10", "Karaganda", "Караганда", 2.0),
    RegionDef("05", "Aktobe", "Актобе", 1.8),
    RegionDef("04", "Atyrau", "Атырау", 1.4),
    RegionDef("07", "Pavlodar", "Павлодар", 1.6),
)

AM_REGIONS = (
    RegionDef("01", "Yerevan", "Ереван", 4.0),
    RegionDef("02", "Ararat", "Арарат", 1.8),
    RegionDef("03", "Armavir", "Армавир", 1.6),
    RegionDef("04", "Gegharkunik", "Гегаркуник", 1.6),
    RegionDef("05", "Lori", "Лори", 1.8),
    RegionDef("06", "Shirak", "Ширак", 1.4),
    RegionDef("07", "Syunik", "Сюник", 1.4),
    RegionDef("08", "Tavush", "Тавуш", 1.3),
)

GE_REGIONS = (
    RegionDef("TB", "Tbilisi", "Тбилиси", 4.0),
    RegionDef("BT", "Batumi", "Батуми", 2.4),
    RegionDef("KL", "Kutaisi", "Кутаиси", 2.2),
    RegionDef("RL", "Rustavi", "Рустави", 1.8),
    RegionDef("GQ", "Gori", "Гори", 1.6),
    RegionDef("OZ", "Ozurgeti", "Озургети", 1.6),
    RegionDef("TK", "Telavi", "Телави", 1.4),
    RegionDef("SN", "Senaki", "Сенаки", 1.3),
)

FR_REGIONS = (
    RegionDef("IDF", "Ile-de-France", "Иль-де-Франс", 3.2),
    RegionDef("ARA", "Auvergne-Rhone-Alpes", "Овернь-Рона-Альп", 2.4),
    RegionDef("PAC", "Provence-Alpes-Cote d'Azur", "Прованс", 2.2),
    RegionDef("OCC", "Occitanie", "Окситания", 2.0),
    RegionDef("NAQ", "Nouvelle-Aquitaine", "Новая Аквитания", 1.8),
    RegionDef("BRE", "Brittany", "Бретань", 1.8),
)

IT_REGIONS = (
    RegionDef("MI", "Lombardy", "Ломбардия", 3.0),
    RegionDef("RM", "Lazio", "Лацио", 2.6),
    RegionDef("TO", "Piedmont", "Пьемонт", 2.2),
    RegionDef("VE", "Veneto", "Венето", 2.2),
    RegionDef("NA", "Campania", "Кампания", 2.0),
    RegionDef("FI", "Tuscany", "Тоскана", 1.9),
)

CA_REGIONS = (
    RegionDef("ON", "Ontario", "Онтарио", 4.0),
    RegionDef("QC", "Quebec", "Квебек", 3.0),
    RegionDef("BC", "British Columbia", "Британская Колумбия", 2.4),
    RegionDef("AB", "Alberta", "Алберта", 2.2),
    RegionDef("MB", "Manitoba", "Манитоба", 1.6),
    RegionDef("NS", "Nova Scotia", "Новая Шотландия", 1.6),
)

JP_REGIONS = (
    RegionDef("13", "Tokyo", "Токио", 4.0),
    RegionDef("27", "Osaka", "Осака", 3.0),
    RegionDef("01", "Hokkaido", "Хоккайдо", 2.0),
    RegionDef("40", "Fukuoka", "Фукуока", 2.0),
    RegionDef("23", "Aichi", "Айти", 2.2),
    RegionDef("14", "Kanagawa", "Канагава", 2.2),
)

AE_REGIONS = (
    RegionDef("DXB", "Dubai", "Дубай", 4.0),
    RegionDef("AZ", "Abu Dhabi", "Абу-Даби", 3.0),
    RegionDef("SH", "Sharjah", "Шарджа", 2.2),
    RegionDef("AJ", "Ajman", "Аджман", 1.8),
    RegionDef("UQ", "Umm Al Quwain", "Умм-Аль-Каввайн", 1.5),
    RegionDef("RK", "Ras Al Khaimah", "Рас-Аль-Хайма", 1.5),
)

GB_REGIONS = (
    RegionDef("ENG", "England", "Англия", 4.0),
    RegionDef("SCT", "Scotland", "Шотландия", 2.2),
    RegionDef("WLS", "Wales", "Уэльс", 2.0),
    RegionDef("NIR", "Northern Ireland", "Северная Ирландия", 1.4),
)

#: Optional region sets for a few more playable countries.
EXTRA_REGIONS: dict[str, tuple[RegionDef, ...]] = {
    "ESP": (
        RegionDef("MD", "Madrid", "Мадрид", 3.0),
        RegionDef("CT", "Catalonia", "Каталония", 2.4),
        RegionDef("AN", "Andalusia", "Андалусия", 2.2),
        RegionDef("PV", "Basque Country", "Страна басков", 1.8),
    ),
    "POL": (
        RegionDef("MZ", "Mazovia", "Мазовия", 3.0),
        RegionDef("SL", "Silesia", "Силезия", 2.2),
        RegionDef("PM", "Pomerania", "Поморье", 1.8),
        RegionDef("PMK", "Greater Poland", "Великая Польша", 1.8),
        RegionDef("LB", "Lublin", "Люблин", 1.6),
        RegionDef("OP", "Opole", "Ополе", 1.4),
    ),
    "UKR": (
        RegionDef("KV", "Kyiv", "Киев", 3.4),
        RegionDef("OD", "Odesa", "Одесса", 2.4),
        RegionDef("LV", "Lviv", "Львов", 2.2),
        RegionDef("DN", "Dnipro", "Днепр", 1.8),
    ),
    "BRA": (
        RegionDef("SP", "Sao Paulo", "Сан-Паулу", 3.4),
        RegionDef("RJ", "Rio de Janeiro", "Рио-де-Жанейро", 2.6),
        RegionDef("MG", "Minas Gerais", "Минас-Жерайс", 2.0),
    ),
    "IND": (
        RegionDef("MH", "Maharashtra", "Махараштра", 3.0),
        RegionDef("KA", "Karnataka", "Карнатака", 2.4),
        RegionDef("DL", "Delhi", "Дели", 2.2),
    ),
    "CHN": (
        RegionDef("GD", "Guangdong", "Гуандун", 3.0),
        RegionDef("SH2", "Shanghai", "Шанхай", 2.8),
        RegionDef("BJ", "Beijing", "Пекин", 2.8),
    ),
    "AUS": (
        RegionDef("NSW", "New South Wales", "Новый Южный Уэльс", 3.0),
        RegionDef("VIC", "Victoria", "Виктория", 2.4),
        RegionDef("QLD", "Queensland", "Квинсленд", 2.2),
    ),
    "MEX": (
        RegionDef("CMX", "Mexico City", "Мехико", 3.0),
        RegionDef("JAL", "Jalisco", "Халиско", 2.0),
        RegionDef("NLE", "Nuevo Leon", "Нуево-Леон", 1.8),
    ),
    "ZAF": (
        RegionDef("WC", "Western Cape", "Западный Кап", 2.6),
        RegionDef("GT", "Gauteng", "Гаутенг", 2.4),
        RegionDef("KZ", "KwaZulu-Natal", "КваЗулу-Натал", 1.8),
    ),
    "ARE": AE_REGIONS,
}

# ---------------------------------------------------------------------------
# Curated country definitions (the original twelve launch countries)
# ---------------------------------------------------------------------------
CURATED: tuple[CountryDef, ...] = (
    CountryDef(
        code="RUS",
        name_en="Russia",
        name_ru="Россия",
        flag="\U0001F1F7\U0001F1FA",
        region_group="CIS",
        currency_code="RUB",
        currency_symbol="₽",
        weight=18.0,
        alphabet=CYRILLIC,
        letter_style="CYRILLIC",
        visual="cis_right_region",
        sort_order=1,
        playable=True,
        regions=RU_REGIONS,
        templates=(
            TemplateDef("ru_standard", "LDDD LL DD", 6.0),
            TemplateDef("ru_moscow", "LDDDLLL DD", 2.0),
            TemplateDef("ru_truck", "LDDD LLL DD", 1.0, plate_type="COMMERCIAL"),
            TemplateDef("ru_moto", "L DDDD DD", 0.8, plate_type="MOTORCYCLE"),
            TemplateDef("ru_special", "X[6789] DDD LL DD", 0.6, plate_type="SPECIAL", rarity_floor="UNCOMMON"),
            TemplateDef("ru_gov", "DDD LLL DD", 0.3, plate_type="GOVERNMENT_STYLE", rarity_floor="RARE"),
        ),
    ),
    CountryDef(
        code="USA",
        name_en="United States",
        name_ru="США",
        flag="\U0001F1FA\U0001F1F8",
        region_group="AMERICAS",
        currency_code="USD",
        currency_symbol="$",
        weight=17.0,
        alphabet=LATIN,
        value_scale=1.35,
        rarity_modifier=1.05,
        visual="north_america",
        sort_order=2,
        playable=True,
        regions=US_REGIONS,
        templates=(
            TemplateDef("us_cali", "LDDDLDDD", 5.0),
            TemplateDef("us_generic", "LLL DDDD", 5.0),
            TemplateDef("us_texas", "LLL DDDD", 2.0),
            TemplateDef("us_fl", "LLL DDD", 1.6),
            TemplateDef("us_ny", "LLL-DDDD", 1.6),
            TemplateDef("us_moto", "DDDDD", 0.8, plate_type="MOTORCYCLE"),
            TemplateDef("us_commercial", "LLL LLL DDD", 1.0, plate_type="COMMERCIAL"),
            TemplateDef("us_historic", "LLD DDDD", 0.4, plate_type="HISTORICAL", rarity_floor="RARE"),
        ),
    ),
    CountryDef(
        code="KAZ",
        name_en="Kazakhstan",
        name_ru="Казахстан",
        flag="\U0001F1F0\U0001F1FF",
        region_group="CIS",
        currency_code="KZT",
        currency_symbol="₸",
        weight=11.0,
        alphabet=CYRILLIC,
        letter_style="CYRILLIC",
        value_scale=0.8,
        rarity_modifier=1.08,
        visual="cis_right_kaz",
        sort_order=3,
        playable=True,
        regions=KZ_REGIONS,
        templates=(
            TemplateDef("kz_standard", "DDD LLL DD", 5.0),
            TemplateDef("kz_region", "DDD LLL R", 4.0),
            TemplateDef("kz_truck", "DDD LLL DD", 0.9, plate_type="COMMERCIAL"),
            TemplateDef("kz_moto", "L LLL DD", 0.7, plate_type="MOTORCYCLE"),
        ),
    ),
    CountryDef(
        code="DEU",
        name_en="Germany",
        name_ru="Германия",
        flag="\U0001F1E9\U0001F1EA",
        region_group="EUROPE",
        currency_code="EUR",
        currency_symbol="€",
        weight=10.0,
        alphabet=LATIN,
        value_scale=1.1,
        visual="eu_long",
        sort_order=4,
        playable=True,
        regions=DE_REGIONS,
        templates=(
            TemplateDef("de_standard", "R LL DDDD", 6.0),
            TemplateDef("de_compact", "R LL DDD", 2.0),
            TemplateDef("de_moto", "L LL DDD", 0.8, plate_type="MOTORCYCLE"),
            TemplateDef("de_long", "R LL DDDDD", 1.0, plate_type="COMMERCIAL"),
            TemplateDef("de_sealed", "R LL DD DD", 0.5, plate_type="SPECIAL", rarity_floor="UNCOMMON"),
        ),
    ),
    CountryDef(
        code="GBR",
        name_en="United Kingdom",
        name_ru="Великобритания",
        flag="\U0001F1EC\U0001F1E7",
        region_group="EUROPE",
        currency_code="GBP",
        currency_symbol="£",
        weight=9.0,
        alphabet=LATIN,
        value_scale=1.15,
        visual="uk_rear",
        sort_order=5,
        playable=True,
        regions=GB_REGIONS,
        templates=(
            TemplateDef("gb_standard", "LL DD LLL", 6.0),
            TemplateDef("gb_prefix", "LLL DD LLL", 2.0),
            TemplateDef("gb_dateless", "LLLL DDD", 1.0, plate_type="HISTORICAL"),
            TemplateDef("gb_moto", "LLL DD DDD", 0.7, plate_type="MOTORCYCLE"),
        ),
    ),
    CountryDef(
        code="FRA",
        name_en="France",
        name_ru="Франция",
        flag="\U0001F1EB\U0001F1F7",
        region_group="EUROPE",
        currency_code="EUR",
        currency_symbol="€",
        weight=8.0,
        alphabet=LATIN,
        value_scale=1.05,
        visual="eu_long",
        sort_order=6,
        playable=True,
        regions=FR_REGIONS,
        templates=(
            TemplateDef("fr_standard", "LL-DDD-LL", 6.0),
            TemplateDef("fr_new", "LL DDD LL", 3.0),
            TemplateDef("fr_moto", "LLD DDD", 0.7, plate_type="MOTORCYCLE"),
            TemplateDef("fr_vintage", "DDDDD LL", 0.4, plate_type="HISTORICAL", rarity_floor="UNCOMMON"),
        ),
    ),
    CountryDef(
        code="ITA",
        name_en="Italy",
        name_ru="Италия",
        flag="\U0001F1EE\U0001F1F9",
        region_group="EUROPE",
        currency_code="EUR",
        currency_symbol="€",
        weight=7.0,
        alphabet=LATIN,
        visual="eu_long",
        sort_order=7,
        playable=True,
        regions=IT_REGIONS,
        templates=(
            TemplateDef("it_standard", "LL DDD LL", 6.0),
            TemplateDef("it_province", "L DDD LL", 2.0),
            TemplateDef("it_moto", "LLLLLL", 0.7, plate_type="MOTORCYCLE"),
            TemplateDef("it_diplomatic", "LL DDD LL", 0.3, plate_type="DIPLOMATIC_STYLE", rarity_floor="RARE"),
        ),
    ),
    CountryDef(
        code="CAN",
        name_en="Canada",
        name_ru="Канада",
        flag="\U0001F1E8\U0001F1E6",
        region_group="AMERICAS",
        currency_code="CAD",
        currency_symbol="C$",
        weight=6.0,
        alphabet=LATIN,
        value_scale=1.1,
        visual="canada",
        sort_order=8,
        playable=True,
        regions=CA_REGIONS,
        templates=(
            TemplateDef("ca_ontario", "ABCD 123", 4.0),
            TemplateDef("ca_standard", "LLLL DDD", 4.0),
            TemplateDef("ca_quebec", "LLL DDD", 1.5),
            TemplateDef("ca_moto", "LLL DDD", 0.7, plate_type="MOTORCYCLE"),
        ),
    ),
    CountryDef(
        code="JPN",
        name_en="Japan",
        name_ru="Япония",
        flag="\U0001F1EF\U0001F1F5",
        region_group="ASIA",
        currency_code="JPY",
        currency_symbol="¥",
        weight=6.0,
        alphabet=JAPANESE,
        letter_style="KANJI",
        value_scale=1.6,
        rarity_modifier=1.15,
        visual="japan",
        sort_order=9,
        playable=True,
        regions=JP_REGIONS,
        templates=(
            TemplateDef("jp_standard", "LL DD LL DD", 5.0),
            TemplateDef("jp_business", "L DDD DD DD", 2.0, plate_type="COMMERCIAL"),
            TemplateDef("jp_kei", "LL DD DD LLL L", 1.0),
            TemplateDef("jp_heavy", "DD LL DD", 0.8, plate_type="COMMERCIAL", rarity_floor="UNCOMMON"),
            TemplateDef("jp_diplomatic", "DD LL DD DD", 0.25, plate_type="DIPLOMATIC_STYLE", rarity_floor="RARE"),
        ),
    ),
    CountryDef(
        code="ARE",
        name_en="United Arab Emirates",
        name_ru="ОАЭ",
        flag="\U0001F1E6\U0001F1EA",
        region_group="MIDEAST",
        currency_code="AED",
        currency_symbol="AED",
        weight=5.0,
        alphabet=LATIN,
        value_scale=1.5,
        rarity_modifier=1.12,
        visual="gulf",
        sort_order=10,
        playable=True,
        regions=AE_REGIONS,
        templates=(
            TemplateDef("ae_dubai", "L DDD L", 4.0),
            TemplateDef("ae_standard", "DDD L L", 4.0),
            TemplateDef("ae_abudhabi", "L DDD L", 2.0),
            TemplateDef("ae_luxury", "L DDD L", 1.2, plate_type="SPECIAL", rarity_floor="UNCOMMON"),
            TemplateDef("ae_classic", "L DDDDD", 0.8, plate_type="HISTORICAL"),
        ),
    ),
    CountryDef(
        code="POL",
        name_en="Poland",
        name_ru="Польша",
        flag="\U0001F1F5\U0001F1F1",
        region_group="EUROPE",
        currency_code="PLN",
        currency_symbol="zł",
        weight=3.0,
        alphabet=LATIN,
        value_scale=0.92,
        rarity_modifier=1.02,
        visual="eu_long",
        sort_order=13,
        playable=True,
        regions=EXTRA_REGIONS["POL"],
        templates=(
            TemplateDef("pl_standard", "LL DDDDD", 6.0),
            TemplateDef("pl_three_letters", "LLL DDDDD", 2.4),
            TemplateDef("pl_moto", "LLL LL", 0.8, plate_type="MOTORCYCLE"),
            TemplateDef("pl_diplomatic", "LL DDDD DD", 0.4, plate_type="DIPLOMATIC_STYLE", rarity_floor="RARE"),
        ),
    ),
    CountryDef(
        code="ARM",
        name_en="Armenia",
        name_ru="Армения",
        flag="\U0001F1F2\U0001F1EA",
        region_group="CIS",
        currency_code="AMD",
        currency_symbol="֏",
        weight=5.0,
        alphabet=ARMENIAN,
        letter_style="ARMENIAN",
        value_scale=0.75,
        rarity_modifier=1.05,
        visual="eu_long",
        sort_order=11,
        playable=True,
        regions=AM_REGIONS,
        templates=(
            TemplateDef("am_standard", "DD LL DDD", 5.0),
            TemplateDef("am_new", "LL DDD DD", 3.0),
            TemplateDef("am_moto", "L DDDDD", 0.7, plate_type="MOTORCYCLE"),
            TemplateDef("am_gov", "DD LL DDD", 0.3, plate_type="GOVERNMENT_STYLE", rarity_floor="RARE"),
        ),
    ),
    CountryDef(
        code="GEO",
        name_en="Georgia",
        name_ru="Грузия",
        flag="\U0001F1EC\U0001F1EA",
        region_group="CIS",
        currency_code="GEL",
        currency_symbol="₾",
        weight=5.0,
        # Latin, not Georgian script. Georgian registration plates are printed in Latin
        # letters - `AB-123-CD` - and a plate rendered in the Georgian alphabet would be
        # the single most obviously wrong collectible in the atlas: it looks like a
        # novelty keycap rather than a number anyone has ever seen on a car.
        alphabet=LATIN,
        letter_style="LATIN",
        value_scale=0.8,
        rarity_modifier=1.05,
        visual="ge",
        sort_order=12,
        playable=True,
        regions=GE_REGIONS,
        templates=(
            # The current Georgian format: two letters, three digits, two letters.
            TemplateDef("ge_standard", "LL-DDD-LL", 6.0),
            # A slightly older shape that is still widely seen on the road.
            TemplateDef("ge_legacy", "LL DDDD LL", 2.0),
            TemplateDef("ge_moto", "LLL DDDD", 0.7, plate_type="MOTORCYCLE"),
        ),
    ),
)


def _family_templates(country: IsoCountry, family: PlateFamily) -> tuple[TemplateDef, ...]:
    """Turn a shared layout family into per-country template rows."""
    prefix = country.alpha3.lower()
    return tuple(
        TemplateDef(
            code=f"{prefix}_{family.key}_{suffix}",
            pattern=pattern,
            weight=weight,
            plate_type=plate_type,
        )
        for suffix, pattern, weight, plate_type in family.layouts
    )


def _generic_country(iso: IsoCountry, sort_order: int) -> CountryDef:
    """A locked country: listed in the atlas, not playable, no generated layouts."""
    name_en, name_ru = NAME_OVERRIDES.get(iso.alpha3, (iso.name_en, iso.name_ru))
    family = _family_for(iso.alpha3, iso.region_group)
    return CountryDef(
        code=iso.alpha3,
        name_en=name_en,
        name_ru=name_ru,
        flag=iso.flag,
        region_group=iso.region_group,
        currency_code=iso.currency_code,
        currency_symbol=iso.currency_symbol,
        weight=0.0,
        alphabet=LATIN,
        value_scale=1.0,
        rarity_modifier=1.0,
        visual=visual_theme_for(iso.alpha3, PLATE_FAMILIES[family].visual),
        sort_order=sort_order,
        iso_alpha2=iso.alpha2,
        calling_code=iso.calling_code,
        playable=False,
        config={"family": family, "locked": True, "un_member": iso.un_member},
    )


def _playable_country(iso: IsoCountry, sort_order: int) -> CountryDef:
    """A playable country built on a shared, documented layout family."""
    family_key, weight, value_scale, rarity_modifier = PLAYABLE_TUNING[iso.alpha3]
    family = PLATE_FAMILIES[family_key]
    name_en, name_ru = NAME_OVERRIDES.get(iso.alpha3, (iso.name_en, iso.name_ru))
    return CountryDef(
        code=iso.alpha3,
        name_en=name_en,
        name_ru=name_ru,
        flag=iso.flag,
        region_group=iso.region_group,
        currency_code=iso.currency_code,
        currency_symbol=iso.currency_symbol,
        weight=weight,
        alphabet=LATIN,
        value_scale=value_scale,
        rarity_modifier=rarity_modifier,
        visual=visual_theme_for(iso.alpha3, family.visual),
        sort_order=sort_order,
        iso_alpha2=iso.alpha2,
        calling_code=iso.calling_code,
        playable=True,
        regions=EXTRA_REGIONS.get(iso.alpha3, ()),
        templates=_family_templates(iso, family),
        config={"family": family_key, "locked": False, "un_member": iso.un_member},
    )


def _with_iso_identity(country: CountryDef) -> CountryDef:
    """Fill the ISO identifiers of a curated country from the ISO table."""
    iso = iso_country(country.code)
    if iso is None:  # pragma: no cover - every curated code is a valid ISO code
        return country
    return replace(
        country,
        iso_alpha2=iso.alpha2,
        calling_code=iso.calling_code,
        currency_code=country.currency_code or iso.currency_code,
        currency_symbol=country.currency_symbol or iso.currency_symbol,
    )


def _build_catalogue() -> tuple[CountryDef, ...]:
    curated_by_code = {country.code: _with_iso_identity(country) for country in CURATED}
    order: list[str] = [code for code in ORIGINAL_ORDER if code in curated_by_code]
    # A country may be both curated (its own layouts and regions) and listed in the
    # priority order (its position in the atlas), so the curated set is not filtered
    # out here - it simply wins over the shared family when the row is built.
    order += [
        code
        for code in PRIORITY_ORDER
        if code in PLAYABLE_TUNING and code not in order
    ]

    built: dict[str, CountryDef] = {}
    for index, code in enumerate(order, start=1):
        iso = iso_country(code)
        if iso is None:  # pragma: no cover - guarded by the tables above
            continue
        built[code] = (
            curated_by_code[code] if code in curated_by_code else _playable_country(iso, index)
        )

    playable_codes = set(order)
    remaining = [
        iso for iso in ISO_COUNTRIES if iso.alpha3 not in playable_codes and iso.alpha3 not in curated_by_code
    ]
    remaining.sort(key=lambda iso: iso.alpha3)
    next_order = len(order)
    for iso in remaining:
        next_order += 1
        built[iso.alpha3] = _generic_country(iso, next_order)

    return tuple(sorted(built.values(), key=lambda country: country.sort_order))


COUNTRIES: tuple[CountryDef, ...] = _build_catalogue()
COUNTRY_BY_CODE: dict[str, CountryDef] = {country.code: country for country in COUNTRIES}
PLAYABLE_CODES: frozenset[str] = frozenset(c.code for c in COUNTRIES if c.playable)
LOCKED_CODES: frozenset[str] = frozenset(c.code for c in COUNTRIES if not c.playable)
CONTINENT_OF_COUNTRY: dict[str, str] = {c.code: c.region_group for c in COUNTRIES}

#: The country a new player starts in when they have not chosen one.
DEFAULT_COUNTRY = "RUS"


def country_by_code(code: str | None) -> CountryDef | None:
    """Resolve an ISO 3166-1 alpha-3 or alpha-2 code to a catalogue entry."""
    if not code:
        return None
    text = str(code).strip().upper()
    found = COUNTRY_BY_CODE.get(text)
    if found is not None:
        return found
    iso = iso_country(text)
    return COUNTRY_BY_CODE.get(iso.alpha3) if iso else None


def is_playable(code: str | None) -> bool:
    """Whether a code names a country a roll may produce."""
    country = country_by_code(code)
    return bool(country and country.playable)


def playable_countries() -> tuple[CountryDef, ...]:
    return tuple(country for country in COUNTRIES if country.playable)


# ---------------------------------------------------------------------------
# Albums (collection sets): themed sets resolved from plate tags plus one
# completion set per playable country.
# ---------------------------------------------------------------------------
THEME_ALBUMS: tuple[AlbumDef, ...] = (
    AlbumDef("album_europe", "EUROPE", "ЕВРОПА", "European plates", "Европейские номера", "\U0001F1EA\U0001F1FA", sort_order=1),
    AlbumDef("album_asia", "ASIA", "АЗИЯ", "Asian plates", "Азиатские номера", "\U0001F1F0\U0001F1F7", sort_order=2),
    AlbumDef("album_cis", "CIS", "СНГ", "Post-Soviet plates", "Номера СНГ", "\U0001F1F7\U0001F1FA", sort_order=3),
    AlbumDef("album_americas", "AMERICAS", "АМЕРИКИ", "North American plates", "Американские номера", "\U0001F1FA\U0001F1F8", sort_order=4),
    AlbumDef("album_middle_east", "MIDEAST", "БЛИЖНИЙ ВОСТОК", "Gulf plates", "Номера залива", "\U0001F1E6\U0001F1EA", sort_order=5),
    AlbumDef("album_africa", "AFRICA", "АФРИКА", "African plates", "Африканские номера", "\U0001F1FF\U0001F1E6", sort_order=6),
    AlbumDef("album_oceania", "OCEANIA", "ОКЕАНИЯ", "Oceania plates", "Номера Океании", "\U0001F1F0\U0001F1FA", sort_order=7),
    AlbumDef("album_lucky", "LUCKY", "УДАЧИВЫЕ", "Lucky digit combinations", "Счастливые комбинации", "\U0001F340", sort_order=8, reward_coins=800),
    AlbumDef("album_sequences", "SEQUENCES", "ПОСЛЕДОВАТЕЛЬНОСТИ", "Ascending and descending runs", "Ряды по порядку", "\U0001F501", sort_order=9),
    AlbumDef("album_palindromes", "PALINDROMES", "ПАЛИНДРОМЫ", "Symmetric plates", "Симметричные номера", "\U0001FA9D", sort_order=10),
    AlbumDef("album_meme", "MEME PLATES", "МЕМ-НОМЕРА", "Internet culture plates", "Интернет-мемы", "\U0001F923", sort_order=11, reward_coins=1000),
    AlbumDef("album_secret", "SECRET", "СЕКРЕТ", "The rarest discoveries", "Самые редкие находки", "✨", sort_order=12, reward_coins=5000),
    AlbumDef("album_seasonal", "SEASONAL", "СЕЗОННЫЕ", "Limited-time plates", "Сезонные номера", "\U0001F31F", sort_order=13),
    AlbumDef("album_luxury", "LUXURY", "ЛЮКС", "Premium and diplomatic plates", "Премиум-номера", "\U0001F48E", sort_order=14, reward_coins=1200),
    AlbumDef("album_sim", "SIM LINE", "ЛИНЕЙКА SIM", "Collectible SIM cards", "Коллекционные SIM-карты", "\U0001F4F7", sort_order=15, reward_coins=1500),
)

THEME_TAG_MAP: dict[str, tuple[str, ...]] = {
    "album_europe": ("europe",),
    "album_asia": ("asia",),
    "album_cis": ("cis",),
    "album_americas": ("americas",),
    "album_middle_east": ("middle_east",),
    "album_africa": ("africa",),
    "album_oceania": ("oceania",),
    "album_lucky": ("lucky",),
    "album_sequences": ("sequence",),
    "album_palindromes": ("mirror",),
    "album_meme": ("meme",),
    "album_secret": ("secret",),
    "album_seasonal": ("seasonal",),
    "album_luxury": ("luxury",),
    "album_sim": ("sim",),
}

COUNTRY_ALBUM_REWARD = 2000


def country_album_defs() -> tuple[AlbumDef, ...]:
    """One completion album per playable country."""
    return tuple(
        AlbumDef(
            code=f"country_{country.code.lower()}",
            name_en=country.name_en.upper(),
            name_ru=country.name_ru.upper(),
            description_en=f"Complete the {country.name_en} collection",
            description_ru=f"Завершите коллекцию «{country.name_ru}»",
            icon=country.flag,
            kind="COUNTRY",
            country_code=country.code,
            sort_order=100 + country.sort_order,
            reward_coins=COUNTRY_ALBUM_REWARD,
            reward_title=f"{country.name_en} Collector",
        )
        for country in COUNTRIES
        if country.playable
    )


ALL_ALBUMS: tuple[AlbumDef, ...] = THEME_ALBUMS + country_album_defs()

# ---------------------------------------------------------------------------
# Rotating global events. Country weight modifiers are configuration, applied
# by the generator - never by the frontend.
# ---------------------------------------------------------------------------
EVENTS: tuple[EventDef, ...] = (
    EventDef("event_cis", "CIS WEEK", "НЕДЕЛЯ СНГ", "\U0001F1F7\U0001F1FA", 7, {"RUS": 3.0, "KAZ": 3.0, "ARM": 2.6, "GEO": 2.6, "BLR": 2.4, "UKR": 2.4}, 900, sort_order=1),
    EventDef("event_japan", "JAPAN DAY", "ДЕНЬ ЯПОНИИ", "\U0001F1EF\U0001F1F5", 3, {"JPN": 8.0, "KOR": 3.0}, 700, "Japan Day Hero", sort_order=2),
    EventDef("event_usa", "USA WEEK", "НЕДЕЛЯ США", "\U0001F1FA\U0001F1F8", 7, {"USA": 3.2, "CAN": 2.4}, 900, sort_order=3),
    EventDef("event_europe", "EUROPE WEEK", "НЕДЕЛЯ ЕВРОПЫ", "\U0001F1EA\U0001F1FA", 7, {"DEU": 3.0, "GBR": 3.0, "FRA": 3.0, "ITA": 3.0, "ESP": 2.6, "POL": 2.4}, 1000, sort_order=4),
    EventDef("event_asia", "ASIA WEEK", "НЕДЕЛЯ АЗИИ", "\U0001F1F0\U0001F1F7", 7, {"CHN": 3.0, "IND": 3.0, "JPN": 2.2, "KOR": 2.2, "THA": 2.0}, 900, sort_order=5),
    EventDef("event_latin_america", "LATAM WEEK", "НЕДЕЛЯ ЛАТИНОЙ", "\U0001F1E7\U0001F1F7", 7, {"BRA": 4.0, "MEX": 4.0, "ARG": 3.4, "CHL": 3.0, "COL": 3.0}, 900, sort_order=6),
    EventDef("event_luxury", "LUXURY NIGHT", "ЛЮКСОВАЯ НОЧЬ", "\U0001F1E6\U0001F1EA", 2, {"ARE": 7.0, "JPN": 2.0, "SAU": 3.0}, 1200, "Luxury Night", sort_order=7),
)

__all__ = [
    "ALL_ALBUMS",
    "ARMENIAN",
    "CONTINENT_OF_COUNTRY",
    "COUNTRIES",
    "COUNTRY_ALBUM_REWARD",
    "COUNTRY_BY_CODE",
    "COUNTRY_VISUAL_OVERRIDES",
    "CYRILLIC",
    "DEFAULT_COUNTRY",
    "EVENTS",
    "FAMILY_BY_REGION",
    "GEORGIAN",
    "JAPANESE",
    "LATIN",
    "LOCKED_CODES",
    "ORIGINAL_ORDER",
    "PLATE_FAMILIES",
    "PLAYABLE_CODES",
    "PLAYABLE_TUNING",
    "PRIORITY_ORDER",
    "REGION_TAGS",
    "THEME_ALBUMS",
    "THEME_TAG_MAP",
    "AlbumDef",
    "CountryDef",
    "EventDef",
    "PlateFamily",
    "RegionDef",
    "TemplateDef",
    "country_album_defs",
    "country_by_code",
    "is_playable",
    "playable_countries",
    "visual_theme_for",
]
