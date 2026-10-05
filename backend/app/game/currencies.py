"""Display currencies.

NUMORA's economy is denominated in one thing: **NUMORA**. A roll, a sale, a balance, a
reward - all of it is NUMORA, and that is what the database stores. Everything else in
this module is *presentation*.

The rule this module exists to enforce
--------------------------------------
**Switching the displayed currency changes no game state.** Not a stored value, not a
rarity, not a dealer or collector value, not a balance, not a reward, not ownership. It
changes the unit a number is printed in, and nothing else. That is why the conversion
lives in exactly one place: a scattered per-screen formula is how a display concern
accidentally starts behaving like an economic one.

Where the numbers come from
---------------------------
The currency list is **derived from the country catalogue**, not written out here. A
currency only appears in the picker if a playable country actually uses it, so the list
can never drift from the world, and a country added tomorrow brings its currency with it
without touching this file.

Rates are deliberately fixed and clearly labelled
------------------------------------------------
These are presentation rates, not a market. They exist so a player can read a collectible
in a currency they recognise, and they are stored here as one table so that there is
exactly one number to change if they ever need to be. The game never pays out in them,
never stores them, and never rounds a stored value by them.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.game.countries import COUNTRIES, PLAYABLE_CODES

#: The one currency the economy is actually denominated in.
GAME_CURRENCY = "NUMORA"

#: Its display code. Three letters, because the picker is a list of ISO-style codes and
#: a two-letter slot would read as a country rather than as a currency.
GAME_CURRENCY_CODE = "NMR"

# ---------------------------------------------------------------------------
# Presentation rates
# ---------------------------------------------------------------------------
#
# Units of a currency per 1 NUMORA. Fixed, documented, and used for display only.
# A rate of 0.0092 means one NUMORA reads as about 0.0092 euro.
#
# These are not exchange rates and must not be presented as current market values.
RATES: dict[str, float] = {
    "NUMORA": 1.0,
    "RUB": 92.0,
    "KZT": 51.0,
    "GEL": 3.05,
    "AMD": 390.0,
    "UAH": 40.0,
    "BYN": 3.15,
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CHF": 0.88,
    "PLN": 3.95,
    "CZK": 23.1,
    "SEK": 10.6,
    "NOK": 10.7,
    "DKK": 6.85,
    "ISK": 137.0,
    "CAD": 1.36,
    "MXN": 18.2,
    "BRL": 5.4,
    "ARS": 890.0,
    "CLP": 940.0,
    "COP": 3900.0,
    "JPY": 152.0,
    "CNY": 7.25,
    "KRW": 1340.0,
    "INR": 83.5,
    "SGD": 1.35,
    "THB": 35.5,
    "TRY": 33.0,
    "ILS": 3.7,
    "AED": 3.67,
    "SAR": 3.75,
    "AUD": 1.52,
    "NZD": 1.64,
    "ZAR": 18.4,
    "HUF": 360.0,
    "RON": 4.6,
    "BGN": 1.8,
}

#: Currencies with no minor unit, so a fractional amount is never printed.
#:
#: NUMORA is here because a game's own currency has no minor unit at all: a value of
#: ``1250.37 NUMORA`` would be nonsense in an economy that pays whole units.
WHOLE_UNITS = {"NUMORA", "JPY", "KRW", "ISK", "CLP", "COP", "HUF", "VND", "IDR"}

#: How many minor digits a currency's conventional form uses.
FRACTION_DIGITS: dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "ISK": 0,
    "CLP": 0,
    "COP": 0,
    "HUF": 0,
}

#: Display names. Only for the codes the catalogue can produce; anything else falls back to
#: the code itself, which is what an ISO list does.
CURRENCY_NAMES: dict[str, str] = {
    "NUMORA": "NUMORA",
    "AED": "UAE dirham",
    "AMD": "Armenian dram",
    "ARS": "Argentine peso",
    "AUD": "Australian dollar",
    "BGN": "Bulgarian lev",
    "BRL": "Brazilian real",
    "BYN": "Belarusian ruble",
    "CAD": "Canadian dollar",
    "CHF": "Swiss franc",
    "CLP": "Chilean peso",
    "CNY": "Chinese yuan",
    "COP": "Colombian peso",
    "CZK": "Czech koruna",
    "DKK": "Danish krone",
    "EUR": "Euro",
    "GBP": "Pound sterling",
    "GEL": "Georgian lari",
    "HUF": "Hungarian forint",
    "ILS": "Israeli shekel",
    "INR": "Indian rupee",
    "ISK": "Icelandic krona",
    "JPY": "Japanese yen",
    "KZT": "Kazakhstani tenge",
    "KRW": "South Korean won",
    "MXN": "Mexican peso",
    "NOK": "Norwegian krone",
    "NZD": "New Zealand dollar",
    "PLN": "Polish zloty",
    "RON": "Romanian leu",
    "RUB": "Russian ruble",
    "SAR": "Saudi riyal",
    "SEK": "Swedish krona",
    "SGD": "Singapore dollar",
    "THB": "Thai baht",
    "TRY": "Turkish lira",
    "UAH": "Ukrainian hryvnia",
    "USD": "US dollar",
    "ZAR": "South African rand",
}

#: One representative country per currency, for the flag preview in the picker.
#: Filled from the catalogue at build time; kept as a field so the client can render a
#: flag without a second request.
FLAG_BY_CURRENCY: dict[str, str] = {}


@dataclass(frozen=True, slots=True)
class DisplayCurrency:
    """One selectable display currency."""

    code: str
    name: str
    #: A representative country flag, so the row is recognisable at a glance.
    flag: str
    #: Units of this currency per 1 NUMORA.
    rate: float
    #: Minor digits to print, 0 for a whole-unit currency.
    fraction_digits: int

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name": self.name,
            "flag": self.flag,
            "rate": self.rate,
            "fraction_digits": self.fraction_digits,
        }


def _fraction_digits(code: str) -> int:
    """Minor digits for a currency, defaulting to 2 like the overwhelming majority."""
    if code in WHOLE_UNITS:
        return 0
    return FRACTION_DIGITS.get(code, 2)


def build_catalog() -> list[DisplayCurrency]:
    """Every currency a playable country actually uses, deduplicated, plus the game's own.

    Derived from :mod:`app.game.countries` rather than written out, so the picker can only
    ever offer a currency that exists somewhere in the world. A currency used by fifteen
    countries appears once, carrying one representative flag.
    """
    playable = set(PLAYABLE_CODES)
    by_currency: dict[str, str] = {}
    for country in COUNTRIES:
        if country.code not in playable:
            continue
        code = (country.currency_code or "").strip().upper()
        if not code or code in by_currency:
            continue
        by_currency[code] = country.flag

    FLAG_BY_CURRENCY.clear()
    FLAG_BY_CURRENCY.update(by_currency)

    catalog = [
        DisplayCurrency(
            code="NUMORA",
            name=CURRENCY_NAMES["NUMORA"],
            # No country owns the game currency, so the picker shows a neutral mark
            # rather than borrowing a flag that would imply otherwise.
            flag="\N{CONFETTI BALL}",
            rate=RATES["NUMORA"],
            fraction_digits=0,
        )
    ]
    for code in sorted(by_currency):
        rate = RATES.get(code)
        if rate is None:
            # A country in the catalogue with no display rate is still a real currency;
            # a missing rate is a data gap, not a reason to hide the country.
            continue
        catalog.append(
            DisplayCurrency(
                code=code,
                name=CURRENCY_NAMES.get(code, code),
                flag=by_currency[code],
                rate=rate,
                fraction_digits=_fraction_digits(code),
            )
        )
    return catalog


def catalog() -> list[DisplayCurrency]:
    return build_catalog()


def is_known(code: str) -> bool:
    return (code or "").strip().upper() in RATES


def convert(amount: float, to_currency: str) -> float:
    """Convert a NUMORA amount into a display currency.

    The *only* place a conversion happens. Nothing else in the codebase multiplies by a
    rate, which is what guarantees that a display change cannot leak into game state.
    """
    rate = RATES.get((to_currency or "").strip().upper())
    if rate is None:
        return float(amount)
    return float(amount) * rate


def fraction_digits_for(code: str) -> int:
    return _fraction_digits((code or "").strip().upper())


__all__ = [
    "CURRENCY_NAMES",
    "GAME_CURRENCY",
    "GAME_CURRENCY_CODE",
    "RATES",
    "DisplayCurrency",
    "build_catalog",
    "catalog",
    "convert",
    "fraction_digits_for",
    "is_known",
]
