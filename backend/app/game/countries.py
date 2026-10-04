"""Launch country catalogue: regions, templates, currencies, albums and events.

Pure configuration. Adding a country (or region, or template) means appending
one definition - no engine, API or React code changes.

Format note: templates are a *stylised game representation* inspired by the
familiar look of each country's plates. They are intentionally simplified and
make no legal claim about real registration formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CYRILLIC = "РђР‘Р’Р“Р”Р•РЃР–Р—РР™РљР›РњРќРћРџР РЎРўРЈР¤РҐР¦Р§РЁР©РЄР«Р¬Р­Р®РЇ"
JAPANESE = "г‚ўг‚¤г‚¦г‚Ёг‚Єг‚«г‚­г‚Їг‚±г‚іг‚µг‚·г‚№г‚»г‚Ѕг‚їгѓЃгѓ„гѓ†гѓ€гѓЉгѓ‹гѓЊгѓЌгѓЋгѓЏгѓ’гѓ•гѓгѓ›гѓћгѓџгѓ гѓЎгѓўгѓ¤гѓ¦гѓЁгѓ©гѓЄгѓ«гѓ¬гѓ­гѓЇгѓІгѓі"
GEORGIAN = "бѓђбѓ‘бѓ’бѓ“бѓ”бѓ•бѓ–бѓ—бѓбѓ™бѓљбѓ›бѓњбѓќбѓћбѓџбѓ бѓЎбѓўбѓЈбѓ¤бѓҐбѓ¦бѓ§бѓЁбѓ©бѓЄбѓ«бѓ¬бѓ­бѓ®бѓЇбѓ°"
ARMENIAN = "ԱԲԳԴԵԶԷԸԹԺԻԼԽԾԿՀՁՂՃՄՅՆՇՈչՊՋՌՍՎՏՐՑՒՓՔՕՖ"

REGION_TAGS: dict[str, str] = {
    "CIS": "cis",
    "EUROPE": "europe",
    "AMERICAS": "americas",
    "ASIA": "asia",
    "MIDEAST": "middle_east",
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
    """Everything the engine needs to generate one country's plates."""

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
    regions: tuple[RegionDef, ...] = ()
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


# Region catalogues ----------------------------------------------------------
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
    RegionDef("IL", "Illinois", "РР»Р»РёРЅРѕР№СЃ", 2.4),
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
    RegionDef("IDF", "Ile-de-France", "РР»СЊ-РґРµ-Р¤СЂР°РЅСЃ", 3.2),
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
    RegionDef("NIR", "Northern Ireland", "РЎРµРІРµСЂРЅР°СЏ РСЂР»Р°РЅРґРёСЏ", 1.4),
)

# Country definitions --------------------------------------------------------
COUNTRIES: tuple[CountryDef, ...] = (
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
        visual="ru",
        sort_order=1,
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
        visual="us",
        sort_order=2,
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
        visual="kz",
        sort_order=3,
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
        visual="de",
        sort_order=4,
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
        visual="gb",
        sort_order=5,
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
        visual="fr",
        sort_order=6,
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
        visual="it",
        sort_order=7,
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
        visual="ca",
        sort_order=8,
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
        visual="jp",
        sort_order=9,
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
        visual="ae",
        sort_order=10,
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
        visual="am",
        sort_order=11,
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
        alphabet=GEORGIAN,
        letter_style="GEORGIAN",
        value_scale=0.8,
        rarity_modifier=1.05,
        visual="ge",
        sort_order=12,
        regions=GE_REGIONS,
        templates=(
            TemplateDef("ge_standard", "LL-DDD-LL", 5.0),
            TemplateDef("ge_new", "LL DDD LL", 3.0),
            TemplateDef("ge_moto", "LLL DDDD", 0.7, plate_type="MOTORCYCLE"),
        ),
    ),
)

COUNTRY_BY_CODE: dict[str, CountryDef] = {country.code: country for country in COUNTRIES}
CONTINENT_OF_COUNTRY: dict[str, str] = {c.code: c.region_group for c in COUNTRIES}


def _with_collectible_templates(country: CountryDef) -> CountryDef:
    """Attach the PHONE_NUMBER and SIM_CARD templates to a country.

    Categories are *data*, not schema: the templates join the same pool the roll
    pipeline already picks from, so ownership, duplicates, first discovery,
    albums and the ledger keep working unchanged for every category. Adding a
    fourth category later means one more call here and one more table in
    ``app.game.collectibles``.
    """
    from app.game import collectibles

    phone = collectibles.phone_templates(country.code)
    sim = collectibles.sim_templates(country.code)
    if not phone and not sim:
        return country
    # Vehicle templates keep their weights; the new categories are rarer by
    # design, so they are added at a fraction of the weight rather than in
    # proportion to the number of templates each country contributes.
    extra = tuple(
        TemplateDef(
            code=template.code,
            pattern=template.pattern,
            weight=template.weight * 0.12,
            plate_type=template.plate_type,
            rarity_floor=template.rarity_floor,
            config=dict(template.config),
        )
        for template in (*phone, *sim)
    )
    return replace(country, templates=(*country.templates, *extra))


COUNTRIES: tuple[CountryDef, ...] = tuple(_with_collectible_templates(c) for c in COUNTRIES)
COUNTRY_BY_CODE = {country.code: country for country in COUNTRIES}


def country_by_code(code: str) -> CountryDef | None:
    return COUNTRY_BY_CODE.get(code.upper())


# ---------------------------------------------------------------------------
# Albums (collection sets): themed sets resolved from plate tags plus one
# completion set per launch country.
# ---------------------------------------------------------------------------
THEME_ALBUMS: tuple[AlbumDef, ...] = (
    AlbumDef("album_europe", "EUROPE", "ЕВРОПА", "European plates", "Европейские номера", "\U0001F1EA\U0001F1FA", sort_order=1),
    AlbumDef("album_asia", "ASIA", "АЗИА", "Asian plates", "Азиатские номера", "\\U0001F1F0\\U0001F1F7", sort_order=2),
    AlbumDef("album_cis", "CIS", "СНГ", "Post-Soviet plates", "Номера СНГ", "\U0001F1F7\U0001F1FA", sort_order=3),
    AlbumDef("album_americas", "AMERICAS", "РђРњР•Р РРљРђ", "North American plates", "РЎРµРІРµСЂРѕР°РјРµСЂРёРєР°РЅСЃРєРёРµ РЅРѕРјРµСЂР°", "\U0001F1FA\U0001F1F8", sort_order=4),
    AlbumDef("album_middle_east", "MIDEAST", "Р‘Р›РР–РќРР™ Р’РћРЎРўРћРљ", "Gulf plates", "РќРѕРјРµСЂР° Р·Р°Р»РёРІР°", "\U0001F1E6\U0001F1EA", sort_order=5),
    AlbumDef("album_lucky", "LUCKY", "РЎР§РђРЎРўР›РР’Р«Р•", "Lucky digit combinations", "РЎС‡Р°СЃС‚Р»РёРІС‹Рµ РєРѕРјР±РёРЅР°С†РёРё", "\U0001F340", sort_order=6, reward_coins=800),
    AlbumDef("album_sequences", "SEQUENCES", "РџРћРЎР›Р•Р”РћР’РђРўР•Р›Р¬РќРћРЎРўР", "Ascending and descending runs", "Р СЏРґС‹ РїРѕ РїРѕСЂСЏРґРєСѓ", "\U0001F501", sort_order=7),
    AlbumDef("album_palindromes", "PALINDROMES", "РџРђР›РРќР”Р РћРњР«", "Symmetric plates", "РЎРёРјРјРµС‚СЂРёС‡РЅС‹Рµ РЅРѕРјРµСЂР°", "\U0001FA9D", sort_order=8),
    AlbumDef("album_meme", "MEME PLATES", "РњР•Рњ-РќРћРњР•Р Рђ", "Internet culture plates", "РРЅС‚РµСЂРЅРµС‚-РјРµРјС‹", "\U0001F923", sort_order=9, reward_coins=1000),
    AlbumDef("album_secret", "SECRET", "СЕКРЕТ", "The rarest discoveries", "Самые редкие находки", "✨", sort_order=10, reward_coins=5000),
    AlbumDef("album_seasonal", "SEASONAL", "СЕЗОННЫЕ", "Limited-time plates", "Сезонные номера", "\U0001F31F", sort_order=11),
    AlbumDef("album_luxury", "LUXURY", "ЛЮКС", "Premium and diplomatic plates", "Премиум-номера", "\U0001F48E", sort_order=12, reward_coins=1200),
)

THEME_TAG_MAP: dict[str, tuple[str, ...]] = {
    "album_europe": ("europe",),
    "album_asia": ("asia",),
    "album_cis": ("cis",),
    "album_americas": ("americas",),
    "album_middle_east": ("middle_east",),
    "album_lucky": ("lucky",),
    "album_sequences": ("sequence",),
    "album_palindromes": ("mirror",),
    "album_meme": ("meme",),
    "album_secret": ("secret",),
    "album_seasonal": ("seasonal",),
    "album_luxury": ("luxury",),
}

COUNTRY_ALBUM_REWARD = 2000


def country_album_defs() -> tuple[AlbumDef, ...]:
    """One completion album per launch country."""
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
    )


ALL_ALBUMS: tuple[AlbumDef, ...] = THEME_ALBUMS + country_album_defs()

# ---------------------------------------------------------------------------
# Rotating global events. Country weight modifiers are configuration, applied
# by the generator - never by the frontend.
# ---------------------------------------------------------------------------
EVENTS: tuple[EventDef, ...] = (
    EventDef("event_cis", "CIS WEEK", "НЕДЕЛЯ СНГ", "\U0001F1F7\U0001F1FA", 7, {"RUS": 3.0, "KAZ": 3.0, "ARM": 2.6, "GEO": 2.6}, 900, sort_order=1),
    EventDef("event_japan", "JAPAN DAY", "ДЕНЬ ЯПОНИИ", "\\U0001F1EF\\U0001F1F5", 3, {"JPN": 8.0}, 700, "Japan Day Hero", sort_order=2),
    EventDef("event_usa", "USA WEEK", "НЕДЕЛЯ США", "\U0001F1FA\U0001F1F8", 7, {"USA": 3.2}, 900, sort_order=3),
    EventDef("event_europe", "EUROPE WEEK", "НЕДЕЛЯ ЕВРОПЫ", "\U0001F1EA\U0001F1FA", 7, {"DEU": 3.0, "GBR": 3.0, "FRA": 3.0, "ITA": 3.0}, 1000, sort_order=4),
    EventDef("event_luxury", "LUXURY NIGHT", "ЛЮКСОВАЯ НОЧЬ", "\U0001F1E6\U0001F1EA", 2, {"ARE": 7.0, "JPN": 2.0}, 1200, "Luxury Night", sort_order=5),
)

__all__ = [
    "ALL_ALBUMS",
    "ARMENIAN",
    "CONTINENT_OF_COUNTRY",
    "COUNTRIES",
    "COUNTRY_BY_CODE",
    "CYRILLIC",
    "EVENTS",
    "GEORGIAN",
    "JAPANESE",
    "LATIN",
    "REGION_TAGS",
    "THEME_ALBUMS",
    "THEME_TAG_MAP",
    "AlbumDef",
    "CountryDef",
    "EventDef",
    "RegionDef",
    "TemplateDef",
    "country_album_defs",
    "country_by_code",
]
