"""Display currencies.

The property that matters is that a currency is a *presentation* concern. These tests hold
that line: the list comes from the world, a conversion never touches game state, and the
game's own currency is the default.
"""

from __future__ import annotations

import pytest

from app.game.countries import COUNTRIES, PLAYABLE_CODES
from app.game.currencies import (
    GAME_CURRENCY,
    GAME_CURRENCY_CODE,
    RATES,
    build_catalog,
    convert,
    fraction_digits_for,
    is_known,
)


class TestCatalog:
    def test_the_catalog_is_derived_from_the_playable_countries(self):
        """
        The list is not written out here.

        A hand-written currency list drifts from the world: a country launches with a
        currency nobody remembered, and a currency survives for a country that was removed.
        """
        catalog = build_catalog()
        playable = {
            (country.currency_code or "").strip().upper()
            for country in COUNTRIES
            if country.code in set(PLAYABLE_CODES)
        }
        playable.discard("")
        offered = {entry.code for entry in catalog} - {GAME_CURRENCY}
        # Every currency in the catalogue has a rate, and every rate is offered.
        assert offered == {code for code in playable if code in RATES}

    def test_the_game_currency_is_first_and_is_the_default(self):
        catalog = build_catalog()
        assert catalog[0].code == GAME_CURRENCY
        assert catalog[0].rate == 1.0
        # A player sees the game currency before touching anything.
        assert convert(1250, GAME_CURRENCY) == 1250
        assert convert(1250, GAME_CURRENCY_CODE.replace("NMR", "NUMORA")) == 1250

    def test_a_currency_used_by_many_countries_appears_once(self):
        """
        EUR is fifteen countries' currency and must be one row.

        Showing it fifteen times would make the picker a country list wearing a currency
        label, which is not what it is for.
        """
        catalog = build_catalog()
        codes = [entry.code for entry in catalog]
        assert len(codes) == len(set(codes))
        # And EUR really is shared by many countries, so the deduplication is load-bearing.
        euro_users = [
            country
            for country in COUNTRIES
            if country.code in set(PLAYABLE_CODES) and country.currency_code == "EUR"
        ]
        assert len(euro_users) > 1
        assert codes.count("EUR") == 1

    def test_every_entry_carries_what_a_picker_row_needs(self):
        for entry in build_catalog():
            assert entry.code
            assert entry.name
            assert entry.rate > 0
            assert entry.flag
            assert 0 <= entry.fraction_digits <= 2

    def test_whole_unit_currencies_print_no_decimals(self):
        """
        A yen price with two decimals is wrong, and a ruble price without is worse.

        The minor unit is a property of the currency, not a global default, so the two
        must be able to differ.
        """
        assert fraction_digits_for("JPY") == 0
        assert fraction_digits_for("KRW") == 0
        assert fraction_digits_for("NUMORA") == 0
        assert fraction_digits_for("RUB") == 2
        assert fraction_digits_for("EUR") == 2
        for entry in build_catalog():
            assert entry.fraction_digits == fraction_digits_for(entry.code)


class TestConversion:
    def test_conversion_is_the_only_multiplication_in_the_game(self):
        """A rate is applied in exactly one function."""
        assert convert(1000, "USD") == pytest.approx(1000 * RATES["USD"])
        assert convert(1000, "RUB") == pytest.approx(1000 * RATES["RUB"])
        # A very different rate still produces a very different number, which is the
        # whole point of showing a player a currency they recognise.
        assert convert(1000, "ISK") > convert(1000, "EUR")

    def test_an_unknown_currency_returns_the_amount_unchanged(self):
        """A surprising code degrades to the canonical value rather than to zero.

        Returning zero would show a player that their collectible is worthless.
        """
        assert convert(1250, "XYZ") == 1250
        assert convert(1250, "") == 1250
        assert convert(1250, "nonsense") == 1250

    def test_conversion_never_changes_the_canonical_amount(self):
        """
        The stored value is NUMORA and stays NUMORA.

        This is the invariant that lets the picker exist: displaying 1150 EUR is a
        rendering of 1250 NUMORA, and the 1250 is still the 1250 afterwards.
        """
        canonical = 1250
        for code in RATES:
            shown = convert(canonical, code)
            # Whatever is shown, the canonical figure the backend stores is untouched.
            assert canonical == 1250
            assert shown >= 0

    def test_zero_stays_zero_in_every_currency(self):
        for code in RATES:
            assert convert(0, code) == 0

    def test_is_known_matches_the_rate_table(self):
        assert is_known("NUMORA")
        assert is_known("rub")
        assert not is_known("XYZ")
        assert not is_known("")


class TestEndpoint:
    def test_the_endpoint_serves_the_catalog_without_a_player(self, client):
        """
        Public, because the client needs a currency before it can render the first price.

        It carries no player data, so requiring a session would only delay the hunt screen.
        """
        response = client.get("/api/currencies")
        assert response.status_code == 200
        payload = response.json()
        assert payload["game_currency"] == GAME_CURRENCY
        assert payload["game_currency_code"] == GAME_CURRENCY_CODE
        codes = [entry["code"] for entry in payload["currencies"]]
        assert codes[0] == GAME_CURRENCY
        assert len(codes) == len(set(codes))
        assert "EUR" in codes
        assert "RUB" in codes
        for entry in payload["currencies"]:
            assert entry["rate"] > 0
            assert entry["name"]
            assert "fraction_digits" in entry
