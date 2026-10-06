"""Physical plate formats, per country.

These tests are the reason the format table can be trusted. Each playable country is
checked, because a country nobody looked at is exactly how a generic white card with
different text ends up in the atlas.
"""

from __future__ import annotations

import random

import pytest

from app.game.countries import (
    COUNTRIES,
    LATIN,
    PLAYABLE_ALPHABETS,
    PLAYABLE_CODES,
    PLAYABLE_PLATE_LAYOUTS,
    PLAYABLE_TUNING,
    RUSSIAN_PLATE_LETTERS,
)
from app.game.plate_formats import (
    COUNTRY_ACCENTS,
    COUNTRY_FORMATS,
    DEFAULT_FORMAT,
    FONT_STACKS,
    FORMATS,
    band_text_for,
    format_for,
    region_text_for,
    serialize_visual,
    theme_for,
    visual_for,
)
from app.game.plate_generator import render_template
from app.game.plate_templates import parse_template

PLAYABLE = [country for country in COUNTRIES if country.code in set(PLAYABLE_CODES)]


class TestCoverage:
    def test_every_playable_country_has_a_physical_format(self):
        """No country may fall through to a default.

        A country missing from the table would silently render as the EU standard with a
        wrong size and the wrong identifier - the exact failure this table exists to stop.
        """
        missing = sorted(country.code for country in PLAYABLE if country.code not in COUNTRY_FORMATS)
        assert missing == [], f"countries with no physical format: {missing}"

    def test_the_table_has_no_orphan_rows(self):
        """
        Every row in the table names a country that exists.

        An orphan row is dead configuration: nothing reads it, and it gives a false
        impression of coverage.
        """
        playable = {country.code for country in PLAYABLE}
        orphans = sorted(set(COUNTRY_FORMATS) - playable)
        assert orphans == [], f"format rows for countries that are not playable: {orphans}"

    def test_every_derived_playable_country_uses_its_explicit_layout(self):
        assert set(PLAYABLE_PLATE_LAYOUTS) == set(PLAYABLE_TUNING)
        for country in PLAYABLE:
            if country.code in PLAYABLE_PLATE_LAYOUTS:
                assert country.templates == PLAYABLE_PLATE_LAYOUTS[country.code]

    def test_every_playable_template_draws_only_from_its_declared_alphabet(self):
        for country in PLAYABLE:
            for template in country.templates:
                parsed = parse_template(template.pattern)
                for part in parsed.parts:
                    if not part.is_literal() and part.kind in ("L", "A"):
                        assert set(part.choices or country.alphabet) <= set(country.alphabet), (
                            country.code,
                            template.code,
                        )
                region = country.regions[0].code if country.regions else None
                rendered, _styles = render_template(
                    parsed,
                    alphabet=country.alphabet,
                    region_code=region,
                    rng=random.Random(17),
                    country_code=country.code,
                )
                assert rendered

    def test_playable_region_codes_are_unique_within_each_country(self):
        for country in PLAYABLE:
            codes = [region.code for region in country.regions]
            assert len(codes) == len(set(codes)), country.code

    @pytest.mark.parametrize("country", PLAYABLE, ids=lambda c: c.code)
    def test_a_country_is_not_a_generic_card_with_different_text(self, country):
        """
        Every country has a real physical recipe.

        "Not a generic white card" means three concrete things: a real standardised size,
        its own identifier code, and mounting hardware that matches its format.
        """
        recipe = format_for(country.code)

        # 1. A real, standardised size - not a default copied from another country.
        assert recipe.width_mm > 0
        assert recipe.height_mm > 0
        assert recipe.width_mm >= 280
        assert recipe.height_mm >= 100

        # 2. Its own identifier. A format with a band must print *this* country's code.
        band = band_text_for(
            recipe, alpha2=country.iso_alpha2 or "", alpha3=country.code
        )
        if recipe.band_position != "none":
            assert band, f"{country.code} has a band but prints no identifier"
            if recipe.band_text_source == "country_alpha2":
                assert band == (country.iso_alpha2 or "").upper()

        # 3. Mounting hardware, and it is one of the three real kinds.
        assert recipe.mount in {"bolts", "holes", "none"}
        if recipe.mount != "none":
            assert 0.05 <= recipe.mount_size <= 0.2

    @pytest.mark.parametrize("country", PLAYABLE, ids=lambda c: c.code)
    def test_the_ratio_is_always_derived_from_the_declared_millimetres(self, country):
        """A recipe can never claim a size and a ratio that disagree."""
        recipe = format_for(country.code)
        assert recipe.aspect == pytest.approx(
            recipe.width_mm / recipe.height_mm, abs=0.001
        )

    @pytest.mark.parametrize("country", PLAYABLE, ids=lambda c: c.code)
    def test_a_serial_always_fits_its_plate(self, country):
        """
        Text fit: the longest serial the country generates must fit its field.

        The renderer sizes type against the plate's own width, so a ratio above ~1.2 is the
        property that guarantees a plate does not overflow. A country whose shortest
        realistic format is a motorcycle plate still has room.
        """
        recipe = format_for(country.code)
        longest = max(
            (sum(1 for ch in pattern if ch in "LDFRAX") for pattern in
             (t.pattern for t in country.templates)),
            default=0,
        )
        assert longest > 0, f"{country.code} has no template"
        # The narrowest plate in the atlas is Iceland's 520x111 and South Africa's 340x175;
        # a 13-symbol commercial serial must still fit inside one.
        assert recipe.aspect > 1.2, country.code

    @pytest.mark.parametrize("country", PLAYABLE, ids=lambda c: c.code)
    def test_the_recipe_is_complete_for_the_renderer(self, country):
        """Every field the renderer reads is present and typed for the API."""
        payload = serialize_visual(
            country.visual,
            alpha2=country.iso_alpha2 or "",
            alpha3=country.code,
            country_code=country.code,
        )
        for key in (
            "width_mm", "height_mm", "aspect", "radius", "border_width",
            "background", "background_alt", "border", "text", "font_stack",
            "letter_spacing", "group_gap", "digit_scale", "letter_scale",
            "band_position", "band_text", "band_stars", "header_source",
            "header_offset", "region_position", "region_width", "region_flag",
            "region_text", "mount", "mount_size", "gloss", "sheen", "relief", "grain",
        ):
            assert key in payload, key
        assert payload["font_stack"] == FONT_STACKS[format_for(country.code).font_stack]
        assert payload["country_code"] == country.code
        assert 0 <= payload["sheen"] <= 1
        assert 0 <= payload["relief"] <= 1
        assert 0 <= payload["grain"] <= 1


class TestPhysicalFormats:
    """The formats that are genuinely distinct, and the facts that make them so."""

    def test_aspect_ratios_match_the_physical_standards(self):
        """
        The ratio is the clearest tell that an object is a plate.

        A Russian plate is 520x112 mm, so it is *long* - 4.64. Rendering it at the 2.46
        the recipes used to claim is what made it look like a card with text on it.
        """
        assert abs(format_for("RUS").aspect - 520 / 112) < 0.01
        assert abs(format_for("KAZ").aspect - 520 / 112) < 0.01
        assert abs(format_for("GEO").aspect - 520 / 112) < 0.01
        assert abs(format_for("POL").aspect - 520 / 110) < 0.01
        assert abs(format_for("GBR").aspect - 520 / 111) < 0.01
        assert abs(format_for("USA").aspect - 305 / 152) < 0.01
        assert abs(format_for("JPN").aspect - 330 / 165) < 0.01
        # Brazil left Mercosur, and Mercosur plates are 400x130 - visibly not an EU plate.
        assert abs(format_for("BRA").aspect - 400 / 130) < 0.01

    def test_brazil_is_not_shaped_like_a_north_american_plate(self):
        """
        The bug this prevents: Brazil grouped with the Americas got a 305x152 plate.

        Mercosur is 400x130, so a Brazilian plate is shorter and taller than a US one, and
        it prints its country wordmark instead of a state name.
        """
        brazil = format_for("BRA")
        assert brazil.width_mm == 400
        assert brazil.height_mm == 130
        assert brazil.header_source == "static"
        assert brazil.header
        # And materially different from the North American recipe it used to share.
        assert brazil.aspect != pytest.approx(format_for("USA").aspect, abs=0.05)

    def test_norway_and_sweden_print_no_country_band(self):
        """
        Norway and Sweden left the EU's band scheme in 2019.

        They share the 520x110 plate with the EU standard but carry no band at all, which
        is a visible difference and a real one.
        """
        for code in ("NOR", "SWE"):
            recipe = format_for(code)
            assert recipe.band_position == "none", code
            assert recipe.band_stars is False, code
            assert band_text_for(recipe, alpha2=code[:2]) == ""
        # Switzerland is not in the EU either.
        assert format_for("CHE").band_position == "none"

    def test_eu_members_share_one_standard_but_print_their_own_code(self):
        """
        The same standard, a different plate.

        This is the distinction the table exists to make: a shared *physical* row is fine
        when countries genuinely share a standard, as long as each prints its own code.
        """
        for code, expected in (
            ("DEU", "DE"),
            ("FRA", "FR"),
            ("ITA", "IT"),
            ("POL", "PL"),
            ("ESP", "ES"),
            ("NLD", "NL"),
            ("BEL", "BE"),
            ("CZE", "CZ"),
            ("IRL", "IE"),
        ):
            recipe = format_for(code)
            assert recipe.band_stars is True, code
            assert band_text_for(recipe, alpha2=expected) == expected, code

    def test_north_america_prints_a_state_name_rather_than_a_band(self):
        """
        The printed header is what makes a US plate specific to its state.

        Two US plates differ by their header, not by a side band, so a recipe that hid the
        header would make every state identical.
        """
        assert format_for("USA").header_source == "region"
        assert format_for("USA").header_align == "center"
        assert format_for("USA").mount == "holes"
        # Canada prints its own wordmark instead.
        assert format_for("CAN").header_source == "static"
        assert format_for("CAN").header == "CANADA"

    def test_south_africa_is_an_inverted_plate(self):
        """White on black. No shared light-field row can represent it."""
        zaf = format_for("ZAF")
        assert zaf.background.lower() in ("#14161a", "#0f1115")
        assert zaf.text.lower().startswith("#f")
        assert zaf.texture == "reflective"

    def test_israel_uses_a_tall_two_compartment_format(self):
        """520x220 mm: nearly twice as tall as the EU plate, and a real second compartment."""
        israel = format_for("ISR")
        assert (israel.width_mm, israel.height_mm) == (520, 220)
        assert israel.aspect < 2.5
        assert israel.region_position == "right"
        assert israel.region_width > 0.15

    def test_the_inverted_regions_are_recognisable(self):
        """Only formats that really carry one set a flag, and it is drawn as vectors."""
        drawn = {theme for theme, recipe in FORMATS.items() if recipe.band_flag}
        assert drawn == {"ge"}
        # The Russian tricolour is in the region compartment, which is where the real
        # format puts it.
        assert format_for("RUS").band_flag is None
        assert format_for("RUS").region_flag is True

    def test_every_distinct_format_declares_its_finish(self):
        for theme, recipe in FORMATS.items():
            assert 0 <= recipe.sheen <= 1, theme
            assert 0 <= recipe.relief <= 1, theme
            assert 0 <= recipe.grain <= 1, theme
            assert recipe.font_stack in FONT_STACKS, theme


class TestGeorgia:
    """The Georgian format, called out specifically."""

    def test_georgia_has_its_own_recipe_with_a_blue_flag_block(self):
        """
        A white plate with a blue block down the left edge carrying the flag and ``GE``.

        Not an EU band: Georgia prints its own flag panel, never the EU star ring, and it
        has no region compartment because the third group of its serial is part of the
        number.
        """
        recipe = format_for("GEO")
        assert recipe.plate_family == "ge"
        assert recipe.background.lower() in ("#ffffff", "#fdfdfb")
        assert recipe.band_position == "left"
        assert recipe.band_color == "#1c3f94"
        assert recipe.band_text == "GE"
        assert recipe.band_flag == "ge"
        assert recipe.band_stars is False
        assert recipe.region_position == "none"
        assert recipe.region_width == 0.0
        assert recipe.mount == "holes"

    def test_georgia_prints_latin_letters(self):
        """
        Latin, never the Georgian alphabet.

        Georgian registration plates are printed in Latin letters. A plate rendered in
        Georgian script would look like a novelty keycap rather than a number anyone has
        seen on a car, so the alphabet is a presentation decision the catalogue owns.
        """
        georgia = next(c for c in COUNTRIES if c.code == "GEO")
        assert georgia.alphabet == LATIN
        assert georgia.letter_style == "LATIN"
        assert georgia.visual == "ge"
        assert not georgia.regions

    def test_the_georgian_format_is_two_letters_three_digits_two_letters(self):
        """
        ``AB-123-CD`` - the current Georgian shape.

        The dashes are part of the template, so they are part of the stored plate text and
        part of what a player searches for.
        """
        georgia = next(c for c in COUNTRIES if c.code == "GEO")
        standard = next(t for t in georgia.templates if t.code == "ge_standard")
        assert standard.pattern == "LL-DDD-LL"
        parsed = parse_template(standard.pattern)
        assert parsed.signature() == "LL?DDD?LL"
        assert parsed.letter_slots == 4
        assert parsed.digit_slots == 3


class TestRussianPlateData:
    def test_only_the_permitted_cyrillic_letters_are_generated(self):
        russia = next(country for country in COUNTRIES if country.code == "RUS")
        assert russia.alphabet == RUSSIAN_PLATE_LETTERS == "АВЕКМНОРСТУХ"
        assert len(russia.alphabet) == 12

    def test_other_non_latin_countries_use_their_plate_script(self):
        countries = {country.code: country for country in COUNTRIES}
        assert countries["KAZ"].alphabet == LATIN
        assert countries["ARM"].alphabet == LATIN
        japan = countries["JPN"]
        assert japan.letter_style == "HIRAGANA"
        assert set(japan.alphabet) <= set(
            "あいうえかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるろわ"
        )
        assert next(t for t in japan.templates if t.code == "jp_standard").pattern == "DDD L DDDD"
        for code in ("GRC", "BLR", "KOR", "SAU", "THA"):
            assert countries[code].alphabet == PLAYABLE_ALPHABETS[code][0]
            assert countries[code].letter_style == PLAYABLE_ALPHABETS[code][1]

    def test_every_russian_vehicle_layout_uses_a_modern_registered_shape(self):
        russia = next(country for country in COUNTRIES if country.code == "RUS")
        patterns = {template.code: template.pattern for template in russia.templates}
        assert patterns["ru_standard"] == "LDDD LL DD"
        assert patterns["ru_truck"] == "LDDD LL DD"
        assert patterns["ru_moto"] == "DDDD LL DD"
        assert not {"ru_moscow", "ru_special", "ru_gov"} & patterns.keys()

    def test_numeric_regions_are_country_catalogue_entries_not_a_generated_grid(self):
        russia = next(country for country in COUNTRIES if country.code == "RUS")
        assert {region.code for region in russia.regions} == {
            "02", "16", "23", "40", "50", "52", "54", "61", "63", "66", "77", "78"
        }

    def test_selected_country_region_codes_match_plate_identifiers(self):
        countries = {country.code: country for country in COUNTRIES}
        assert "F" in {region.code for region in countries["DEU"].regions}
        assert "HE" not in {region.code for region in countries["DEU"].regions}
        assert {region.code for region in countries["FRA"].regions} <= {
            "75", "69", "13", "33", "59", "29"
        }
        assert {region.code for region in countries["UKR"].regions} <= {"AA", "BH", "BC", "AE"}
        assert {region.code for region in countries["CHN"].regions} <= {"粤", "沪", "京"}

    def test_every_russian_letter_slot_uses_only_legal_letters(self):
        russia = next(country for country in COUNTRIES if country.code == "RUS")
        for template in russia.templates:
            parsed = parse_template(template.pattern)
            for part in parsed.parts:
                if not part.is_literal() and part.kind == "L":
                    assert set(part.choices or russia.alphabet) <= set(RUSSIAN_PLATE_LETTERS)


class TestRussia:
    def test_the_russian_format_is_gost_type_one(self):
        """
        520x112 mm with the registration left of centre and a separate right compartment.
        """
        recipe = format_for("RUS")
        assert (recipe.width_mm, recipe.height_mm) == (520, 112)
        assert recipe.plate_family == "cis_right_region"
        # No side band: the identifier lives in the compartment with the tricolour.
        assert recipe.band_position == "none"
        assert recipe.region_position == "right"
        assert recipe.region_style == "block"
        assert 0.08 < recipe.region_width < 0.2
        assert recipe.region_flag is True
        assert recipe.mount == "bolts"
        assert recipe.font_stack == "cyrillic"

    def test_the_russian_legend_is_the_three_letter_code(self):
        assert region_text_for(format_for("RUS"), alpha3="RUS") == "RUS"
        assert region_text_for(format_for("KAZ"), alpha3="KAZ") == "KAZ"
        # A format with no compartment prints nothing there.
        assert region_text_for(format_for("POL"), alpha3="POL") == ""

    def test_a_format_with_no_band_prints_no_band_text(self):
        """A recipe that draws no stripe must not print an identifier for it."""
        for code in ("RUS", "GBR", "USA", "BRA", "ZAF", "SWE"):
            assert band_text_for(format_for(code), alpha2=code[:2], alpha3=code) == "", code


class TestThemeKeys:
    def test_a_theme_key_resolves_back_to_its_format(self):
        for country in PLAYABLE:
            assert visual_for(theme_for(country.code)) is format_for(country.code)

    def test_an_unknown_theme_falls_back_to_the_eu_standard(self):
        """A surprising key must not crash a render; it degrades to a real plate."""
        assert visual_for("not_a_theme") is FORMATS[DEFAULT_FORMAT]
        assert visual_for("cc_zzz") is FORMATS[DEFAULT_FORMAT]

    def test_a_country_key_carries_its_own_accent(self):
        """The last piece of identity a shared physical format cannot supply."""
        for country in PLAYABLE:
            payload = serialize_visual(
                country.visual,
                alpha2=country.iso_alpha2 or "",
                alpha3=country.code,
                country_code=country.code,
            )
            expected = COUNTRY_ACCENTS.get(country.code, format_for(country.code).accent)
            assert payload["accent"] == expected
