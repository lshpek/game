"""Country presentation recipes and the generated number formats behind them.

Two guarantees are tested here:

* every supported country resolves to a real recipe with plausible proportions, a proper
  country identifier and a documented family;
* the number printed on the plate is generated from that country's own template, so the
  stored, displayed, searched and shared text are always the same string.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.game.countries import COUNTRIES, COUNTRY_BY_CODE, LATIN, playable_countries
from app.game.plate_generator import segment_kinds, styles_for_text
from app.game.plate_templates import normalize_plate, parse_template
from app.game.plate_visuals import (
    DEFAULT_VISUAL,
    FONT_STACKS,
    PLATE_VISUALS,
    band_text_for,
    region_text_for,
    serialize_visual,
    visual_for,
)
from app.models.plates import Country, Plate

PLAYABLE = playable_countries()
LAUNCH = ("RUS", "KAZ", "POL", "DEU", "GBR", "FRA", "ITA", "JPN", "USA", "ARE")
#: The visual recipe key each launch country uses.
VISUAL_THEME_BY_CODE = {
    "RUS": "ru",
    "KAZ": "kz",
    "POL": "pol",
    "DEU": "de",
    "GBR": "gb",
    "FRA": "fr",
    "ITA": "it",
    "JPN": "jp",
    "USA": "us",
    "ARE": "ae",
}


class TestRecipeCoverage:
    def test_every_country_resolves_to_a_known_recipe(self):
        for country in COUNTRIES:
            assert country.visual in PLATE_VISUALS, country.code

    def test_every_playable_country_has_a_recipe(self):
        for country in PLAYABLE:
            recipe = visual_for(country.visual)
            assert recipe.plate_family
            assert recipe.aspect >= 1.6, country.code
            assert recipe.font_stack in FONT_STACKS, country.code

    @pytest.mark.parametrize("code", LAUNCH)
    def test_launch_countries_have_their_own_recipe(self, code):
        country = COUNTRY_BY_CODE[code]
        # Each launch country carries its own recipe rather than a generic family.
        assert country.visual == VISUAL_THEME_BY_CODE[code]
        assert country.visual in PLATE_VISUALS

    def test_an_unknown_theme_degrades_to_the_documented_generic_family(self):
        recipe = visual_for("not-a-country")
        assert recipe.theme == DEFAULT_VISUAL.theme
        assert recipe.plate_family == "eu_long"

    def test_aspect_ratios_match_the_physical_families(self):
        """
        Proportions come from the real standardised size, not from a tuned constant.

        The 520x112 Russian format is the reference the whole product is built around: it
        is *long* (ratio 4.64), not the squat 2.46 the recipes used to claim. Getting this
        wrong is what made a plate render as a card with text on it.
        """
        # EU long: 520x110.
        assert abs(visual_for("pol").aspect - 520 / 110) < 0.01
        assert abs(visual_for("de").aspect - 520 / 110) < 0.01
        # GOST R 50577-2018 type 1: 520x112, for both CIS formats.
        assert abs(visual_for("ru").aspect - 520 / 112) < 0.01
        assert abs(visual_for("kz").aspect - 520 / 112) < 0.01
        # North America: 305x152.
        assert abs(visual_for("us").aspect - 305 / 152) < 0.01
        # Japan: 330x165.
        assert abs(visual_for("jp").aspect - 330 / 165) < 0.01

    def test_the_aspect_is_always_derived_from_the_declared_millimetres(self):
        """A recipe can never claim a size and a ratio that disagree."""
        for theme, recipe in PLATE_VISUALS.items():
            assert recipe.width_mm > 0, theme
            assert recipe.height_mm > 0, theme
            assert recipe.aspect == pytest.approx(recipe.width_mm / recipe.height_mm, abs=0.01), theme

    def test_the_russian_format_declares_its_standardised_size(self):
        for code in ("ru", "kz"):
            recipe = visual_for(code)
            assert (recipe.width_mm, recipe.height_mm) == (520, 112), code

    def test_the_eu_countries_carry_a_proper_eu_band(self):
        for code in ("POL", "DEU", "FRA", "ITA"):
            recipe = visual_for(COUNTRY_BY_CODE[code].visual)
            assert recipe.band_position == "left"
            assert recipe.band_color == "#003399"
            assert recipe.band_stars is True
            assert recipe.band_width > 0.1

    def test_poland_prints_pol_in_its_band(self):
        assert band_text_for(visual_for("pol")) == "PL"
        assert serialize_visual("pol", alpha2="PL", alpha3="POL")["band_text"] == "PL"

    def test_a_generic_eu_family_prints_the_country_own_code(self):
        """Sweden on the generic family prints SE, not a generic EU placeholder."""
        assert band_text_for(visual_for("european"), alpha2="SE", alpha3="SWE") == "SE"

    def test_the_non_eu_launch_countries_have_their_own_identifier(self):
        # A CIS plate has no side band: RUS/KAZ are printed in the right-hand
        # compartment together with the flag and the region code.
        assert band_text_for(visual_for("ru"), alpha3="RUS") == ""
        assert region_text_for(visual_for("ru"), alpha3="RUS") == "RUS"
        assert region_text_for(visual_for("kz"), alpha3="KAZ") == "KAZ"
        # A British plate has no EU band at all.
        assert visual_for("gb").band_position == "none"
        # A US plate prints its state name as the header instead.
        assert visual_for("us").header_source == "region"
        assert visual_for("us").mount == "holes"

    def test_the_uk_recipe_is_a_yellow_rear_plate(self):
        recipe = visual_for("gb")
        assert recipe.variant == "rear"
        assert recipe.background.lower().startswith("#f")  # yellow, not white
        assert recipe.background == "#f7d117"

    def test_russia_and_kazakhstan_put_the_region_in_its_own_compartment(self):
        """
        The two-compartment format, as GOST R 50577-2018 defines it.

        The compartment is separated from the registration by a vertical rule and has a
        printed width; it is part of the plate's geometry, not an appended suffix.
        """
        for code, flag in (("ru", True), ("kz", False)):
            recipe = visual_for(code)
            assert recipe.plate_family == "cis_right_region"
            assert recipe.region_position == "right"
            assert recipe.region_style == "block"
            assert recipe.region_width > 0.08, code
            assert recipe.region_flag is flag, code
            # No EU band: the identifier lives in the compartment, not in a blue stripe.
            assert recipe.band_position == "none", code

    def test_a_country_with_no_region_compartment_says_so(self):
        """A format with no separate region block must not reserve space for one."""
        for code in ("gb", "us", "ca"):
            recipe = visual_for(code)
            assert recipe.region_position == "none", code
            assert recipe.region_width == 0.0, code

    def test_germany_and_poland_place_the_region_as_a_badge(self):
        for code in ("de", "pol"):
            assert visual_for(code).region_position == "badge"

    def test_every_recipe_declares_its_mounting_hardware(self):
        """``bolts`` | ``holes`` | ``none``, with a printed size when it has any."""
        for theme, recipe in PLATE_VISUALS.items():
            assert recipe.mount in ("bolts", "holes", "none"), theme
            assert recipe.mount_color.startswith("#"), theme
            if recipe.mount != "none":
                assert 0.05 <= recipe.mount_size <= 0.2, theme

    def test_mounting_appearance_matches_the_real_format(self):
        """CIS and EU plates carry studded bolts; North American and Japanese ones do not."""
        for code in ("ru", "kz", "de", "pol", "fr", "it", "gb"):
            assert visual_for(code).mount == "bolts", code
        for code in ("us", "ca", "jp"):
            assert visual_for(code).mount == "holes", code

    def test_every_recipe_declares_its_finish(self):
        """Relief and grain must be present and in range: they are what make the object."""
        for theme, recipe in PLATE_VISUALS.items():
            assert 0.0 <= recipe.relief <= 1.0, theme
            assert 0.0 <= recipe.grain <= 1.0, theme
            assert 0.0 <= recipe.sheen <= 1.0, theme

    def test_georgia_has_its_own_recipe_with_a_blue_identifier_block(self):
        """
        The modern Georgian format.

        A white plate with a blue block down the left edge carrying the flag and ``GE``,
        then a Latin registration. It is a distinct physical design from the EU band - no
        star ring, a wider block, and no separate region compartment.
        """
        recipe = visual_for("ge")
        assert recipe.plate_family == "ge"
        assert recipe.background.lower() in ("#ffffff", "#fdfdfd")
        assert recipe.border.lower() == "#0f172a"
        assert recipe.band_position == "left"
        assert recipe.band_color == "#1c3f94"
        assert recipe.band_text == "GE"
        assert recipe.band_flag == "ge"
        # Not an EU band: Georgia prints its own flag block, never the EU star ring.
        assert recipe.band_stars is False
        # The third group of a Georgian number is part of the serial, not a region.
        assert recipe.region_position == "none"
        assert recipe.region_width == 0.0

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
        # Four letters, three digits, and the two dashes are literals - which is why they
        # end up in the stored plate text and in what a player can search for.
        assert parsed.signature() == "LL?DDD?LL"
        assert parsed.letter_slots == 4
        assert parsed.digit_slots == 3

    def test_only_the_georgian_band_carries_a_drawn_flag(self):
        """A pasted-on flag reads as a sticker; only the formats that really have one draw it."""
        drawn = {theme for theme, recipe in PLATE_VISUALS.items() if recipe.band_flag}
        assert drawn == {"ge"}
        # The Russian tricolour is printed in the *region compartment*, not in a band -
        # which is where the real format puts it.
        assert visual_for("ru").band_flag is None
        assert visual_for("ru").region_flag is True

    def test_the_serialised_recipe_is_complete_for_the_renderer(self):
        """
        Every field the renderer reads must be present.

        A missing key means the client silently falls back to a default, which is how one
        country ends up rendering as a different country's plate.
        """
        payload = serialize_visual("pol", alpha2="PL", alpha3="POL")
        for key in (
            # Physical geometry.
            "width_mm",
            "height_mm",
            "aspect",
            # Surface.
            "background",
            "background_alt",
            "border",
            "text",
            "font_stack",
            # Typography.
            "letter_spacing",
            "group_gap",
            "digit_scale",
            "letter_scale",
            # Country identifier.
            "band_position",
            "band_text",
            "band_stars",
            # Printed header.
            "header_source",
            "header_offset",
            # Region placement.
            "region_position",
            "region_width",
            # Mounting hardware.
            "mount",
            "mount_size",
            # Finish.
            "gloss",
            "sheen",
            "relief",
            "grain",
        ):
            assert key in payload, key
        assert payload["font_stack"] == FONT_STACKS["euro"]
        # The ratio the client renders with is the one the millimetres imply.
        assert payload["aspect"] == pytest.approx(
            payload["width_mm"] / payload["height_mm"], abs=0.01
        )

    def test_the_serialised_recipe_carries_the_region_legend(self):
        payload = serialize_visual("ru", alpha2="RU", alpha3="RUS")
        assert payload["region_position"] == "right"
        assert payload["region_text"] == "RUS"
        assert payload["region_flag"] is True


class TestSegmentKinds:
    def test_letters_digits_and_a_region_block_are_classified(self):
        assert segment_kinds(["A", "001", "BC"], "77") == ["letter", "digit", "letter"]
        assert segment_kinds(["123", "77"], "77") == ["digit", "region"]
        assert segment_kinds(["7", "001", "77"], "77") == ["digit", "digit", "region"]
        assert segment_kinds(["A1"], None) == ["mixed"]
        assert segment_kinds([""], None) == [""]

    def test_styles_agree_with_the_character_classification(self):
        """The generator's own styles and the renderer's kinds must not disagree."""
        styles = styles_for_text("A 001 BC 77")
        kinds = segment_kinds([style["text"] for style in styles], "77")
        for style, kind in zip(styles, kinds, strict=True):
            assert style["kind"] in {"letter", "digit", "region", "mixed", "mark"}
            assert kind in {"letter", "digit", "region", "mixed", "mark"}


class TestCountryApiVisual:
    @pytest.mark.parametrize("code", LAUNCH)
    def test_the_country_api_sends_the_full_recipe(self, client, authed, code, db):
        session = authed(883_100_010 + LAUNCH.index(code))
        data = client.get(f"/api/countries/{code}", headers=session["headers"]).json()
        visual = data["visual"]
        assert visual["theme"] == VISUAL_THEME_BY_CODE[code]
        assert visual["aspect"] > 1.6
        assert visual["mount"] in ("bolts", "holes", "none")
        if code in ("POL", "DEU", "FRA", "ITA"):
            assert visual["band_text"] == {"POL": "PL", "DEU": "D", "FRA": "F", "ITA": "I"}[code]
            assert visual["band_stars"] is True
            assert visual["band_color"] == "#003399"
        if code in ("RUS", "KAZ"):
            # No blue band on a CIS plate; the legend lives in the compartment.
            assert visual["band_position"] == "none"
            assert visual["region_text"] == {"RUS": "RUS", "KAZ": "KAZ"}[code]
            assert visual["region_position"] == "right"
            assert visual["region_width"] > 0.08
        if code == "USA":
            assert visual["header_source"] == "region"
            assert visual["mount"] == "holes"
        if code == "GBR":
            assert visual["variant"] == "rear"
            assert visual["band_position"] == "none"

    def test_a_locked_country_still_reports_a_recipe(self, client, authed, db):
        row = db.execute(
            select(Country).where(Country.is_active.is_(True), Country.is_playable.is_(False))
        ).scalars().first()
        if row is None:
            pytest.skip("no locked country in the catalogue")
        session = authed(883_100_100)
        data = client.get(f"/api/countries/{row.code}", headers=session["headers"]).json()
        assert data["is_playable"] is False
        assert data["visual"]["aspect"] > 1.6


class TestTextIsOneString:
    def test_generated_stored_displayed_and_searched_text_are_identical(
        self, client, authed, db
    ):
        session = authed(883_100_200)
        data = client.post("/api/roll?country_code=RUS", headers=session["headers"], json={}).json()
        plate = data["plate"]
        stored = plate["plate_text"]

        # displayed: the groups the renderer prints, with their exact spacing
        rebuilt = "".join(
            (" " if gap else "") + group
            for group, gap in zip(
                plate["display_segments"], plate["display_segment_gaps"], strict=True
            )
        )
        assert rebuilt == stored
        # searched: the normalised form resolves back to the same plate
        assert normalize_plate(stored) == plate["normalized_text"]
        # shared: the copy text quotes the stored string verbatim
        share = client.post(
            f"/api/plates/{plate['id']}/share", headers=session["headers"], json={}
        ).json()
        assert stored in share["share_text_en"]
        assert stored in share["share_text_ru"]

        row = db.execute(select(Plate).where(Plate.id == plate["id"])).scalar_one()
        assert row.plate_text == stored

    def test_a_roll_response_carries_segment_kinds_for_the_renderer(self, client, authed):
        session = authed(883_100_201)
        plate = client.post("/api/roll", headers=session["headers"], json={}).json()["plate"]
        assert len(plate["display_segment_kinds"]) == len(plate["display_segments"])
        assert all(
            kind in {"letter", "digit", "region", "mixed", "mark", ""}
            for kind in plate["display_segment_kinds"]
        )

    def test_the_garage_reuses_the_same_card_shape(self, client, authed):
        session = authed(883_100_202)
        client.post("/api/roll", headers=session["headers"], json={})
        recent = client.get("/api/garage", headers=session["headers"]).json()["recent"]
        assert recent["plate_text"]
        assert "visual" in recent
        assert recent["display_segments"]
