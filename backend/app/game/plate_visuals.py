"""Country plate presentation recipes.

Every plate in NUMORA is rendered from a *recipe* the server sends with the
collectible. This module owns those recipes: proportions, surface, typography,
country identifier, region placement, mounting hardware and finish. The client
renders the recipe and never decides how a country's plate looks.

Design contract
---------------
* One recipe per physical plate family, with a **country-specific recipe** whenever a
  launch country has its own real layout.
* No giant flag emoji standing in for a plate identifier. The country identifier is a
  small printed code inside a proper side band - the EU blue band with the country's
  alpha-2 code for EU-style plates, the national band elsewhere.
* Country-specific layout is expressed in data: aspect ratio, letter/digit hierarchy,
  where the region block sits, how many mounting bolts, what the surface looks like.
* Every recipe degrades to a documented generic family, which is honestly labelled as
  a game layout rather than a reproduction of any real scheme.

Honesty
-------
Recipes reproduce the *familiar proportions and layout logic* of real plates so a
collectible is instantly recognisable. They are a stylised game presentation: they make
no regulatory claim, and a country shipped on a generic family is not pretending to be
an exact reproduction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Shared presentation constants
# ---------------------------------------------------------------------------

#: Real CSS stacks behind a stable font key, so the client never hardcodes a family.
FONT_STACKS: dict[str, str] = {
    "euro": "'Arial Narrow', 'Roboto Condensed', 'Helvetica Neue', Arial, sans-serif",
    "condensed": "'Arial Narrow', 'Roboto Condensed', 'Helvetica Neue', Arial, sans-serif",
    "cyrillic": "'PT Sans Narrow', 'Roboto Condensed', 'Helvetica Neue', Arial, sans-serif",
    "wide": "'Trebuchet MS', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
    "japanese": "'Hiragino Kaku Gothic ProN', 'Noto Sans JP', 'Yu Gothic', sans-serif",
    "sans": "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
    "mono": "'Roboto Mono', 'SFMono-Regular', 'Consolas', monospace",
}

#: The EU band colour (EU identity blue) and its print colour.
EU_BAND = "#003399"
EU_BAND_TEXT = "#ffd300"


@dataclass(frozen=True, slots=True)
class PlateVisual:
    """Presentation contract for one country's plate family.

    Everything here is configuration for the renderer, grouped as physical shape,
    surface, typography, country identifier, region placement, mounting and finish.
    """

    theme: str
    #: Physical family key. Drives the renderer's structural template.
    plate_family: str = "eu_long"
    #: Which front/rear variant this recipe represents.
    variant: str = "standard"

    # --- physical shape --------------------------------------------------
    aspect: float = 4.6
    radius: str = "6px"
    border_width: str = "2px"

    # --- surface ----------------------------------------------------------
    background: str = "#f4f6fb"
    #: Second stop of the face gradient, giving the enamel a slight falloff.
    background_alt: str = "#e8ecf4"
    border: str = "#1f2937"
    text: str = "#111827"
    muted: str = "#6b7280"
    accent: str = "#7c5cff"
    texture: str = "metal"

    # --- typography -------------------------------------------------------
    font_stack: str = "euro"
    letter_spacing: str = "0.06em"
    #: Space between printed groups.
    group_gap: str = "0.9em"
    #: Digits are printed larger than letters on most real plates.
    digit_scale: float = 1.0
    letter_scale: float = 0.92
    digit_weight: int = 700

    # --- country identifier -----------------------------------------------
    #: ``"left"``/``"right"`` print a side band; ``"none"`` disables it.
    band_position: str = "left"
    band_color: str | None = None
    #: Band width as a fraction of the plate *height*.
    band_width: float = 0.0
    #: Printed inside the band: the EU country code or a national mark.
    band_text: str = ""
    #: ``"static"`` prints ``band_text``; ``"country_alpha2"``/``"country_alpha3"``
    #: print the country's own ISO code, which is what an EU-style band does.
    band_text_source: str = "static"
    band_text_color: str = "#ffffff"
    #: The EU star ring, drawn as vector arcs rather than emoji.
    band_stars: bool = False
    #: A small national emblem inside the band - never a giant flag overlay.
    band_flag: bool = False

    # --- header ------------------------------------------------------------
    header: str = ""
    header_align: str = "center"
    #: ``"static"`` uses ``header``; ``"region"`` prints the region's name (a US
    #: state's own name, so no two states read the same); ``"none"`` hides it.
    header_source: str = "static"
    header_color: str | None = None

    # --- region placement ---------------------------------------------------
    #: ``"right"`` = separate right-hand block (Russia/Kazakhstan style),
    #: ``"inline"`` = part of the printed serial, ``"badge"`` = small corner badge,
    #: ``"none"`` = the country has no regions.
    region_position: str = "inline"
    region_style: str = "block"
    region_badge: bool = True
    show_flag: bool = True
    show_region_flag: bool = True

    # --- mounting -----------------------------------------------------------
    #: Physical mounting bolts. Four on cars and trucks, two on US-style plates,
    #: none on a moped plate.
    bolts: int = 4
    mount_color: str = "#8a9099"

    # --- finish --------------------------------------------------------------
    gloss: bool = True
    #: Strength of the diagonal reflection pass, 0..1.
    sheen: float = 0.5
    #: Small printed corner mark (sponsor block, crest, class mark).
    emblem: str = ""

    extra: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Country-specific recipes for the launch set
# ---------------------------------------------------------------------------
PLATE_VISUALS: dict[str, PlateVisual] = {
    # --- Russia: 520x112 style. White field, black frame, and the region code in
    # its own right-hand compartment, separated from the registration.
    "ru": PlateVisual(
        theme="ru",
        plate_family="cis_right_region",
        aspect=2.46,
        radius="5px",
        border_width="2px",
        background="#ffffff",
        background_alt="#f2f4f7",
        border="#111827",
        text="#0b1220",
        muted="#4b5563",
        accent="#2f6bd8",
        texture="metal",
        font_stack="cyrillic",
        letter_spacing="0.04em",
        letter_scale=0.9,
        group_gap="0.7em",
        band_position="right",
        band_color="#0b1220",
        band_width=0.36,
        band_text="",
        band_text_source="country_alpha3",
        band_text_color="#ffffff",
        band_flag=True,
        header="",
        header_source="none",
        region_position="right",
        region_style="block",
        bolts=4,
        sheen=0.55,
        emblem="flag",
    ),
    # --- Kazakhstan: same two-compartment logic, national band.
    "kz": PlateVisual(
        theme="kz",
        plate_family="cis_right_region",
        aspect=2.46,
        radius="5px",
        border_width="2px",
        background="#ffffff",
        background_alt="#eef4fb",
        border="#0f3f8f",
        text="#0a1c3d",
        muted="#3f5a86",
        accent="#0096c7",
        texture="metal",
        font_stack="cyrillic",
        letter_spacing="0.04em",
        letter_scale=0.9,
        group_gap="0.7em",
        band_position="right",
        band_color="#0096c7",
        band_width=0.34,
        band_text="",
        band_text_source="country_alpha3",
        band_text_color="#ffffff",
        band_flag=True,
        header="",
        header_source="none",
        region_position="right",
        region_style="block",
        bolts=4,
        sheen=0.5,
        emblem="flag",
    ),
    # --- Germany: EU band with the D and the star ring, district seal on the right.
    "de": PlateVisual(
        theme="de",
        plate_family="eu_long",
        aspect=4.9,
        radius="5px",
        border_width="3px",
        background="#fdfdfb",
        background_alt="#eceee9",
        border="#111111",
        text="#111111",
        muted="#3f3f46",
        accent="#111111",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.17,
        band_text="D",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        region_style="seal",
        bolts=4,
        sheen=0.62,
    ),
    # --- Poland: EU band with PL and the star ring.
    "pol": PlateVisual(
        theme="pol",
        plate_family="eu_long",
        aspect=4.9,
        radius="5px",
        border_width="3px",
        background="#fbfbf8",
        background_alt="#e9ecef",
        border="#1a1a1a",
        text="#111827",
        muted="#4b5563",
        accent="#dc2626",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.17,
        band_text="PL",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        region_style="badge",
        bolts=4,
        sheen=0.55,
    ),
    # --- France: EU band with F, department seal.
    "fr": PlateVisual(
        theme="fr",
        plate_family="eu_long",
        aspect=4.3,
        radius="5px",
        border_width="3px",
        background="#ffffff",
        background_alt="#f1f3f7",
        border="#1f2937",
        text="#0b1220",
        muted="#5b6474",
        accent="#0055a4",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.18,
        band_text="F",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        region_style="seal",
        bolts=4,
        sheen=0.5,
    ),
    # --- Italy: EU band with I, province code on the right.
    "it": PlateVisual(
        theme="it",
        plate_family="eu_long",
        aspect=4.3,
        radius="5px",
        border_width="3px",
        background="#ffffff",
        background_alt="#f1f5f2",
        border="#1f2937",
        text="#0b1220",
        muted="#5b6474",
        accent="#009246",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.18,
        band_text="I",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        region_style="block",
        bolts=4,
        sheen=0.5,
    ),
    # --- United Kingdom: yellow rear plate, black print, no EU band.
    "gb": PlateVisual(
        theme="gb",
        plate_family="uk",
        variant="rear",
        aspect=4.6,
        radius="4px",
        border_width="2px",
        background="#f7d117",
        background_alt="#e0b800",
        border="#111111",
        text="#111111",
        muted="#3f3f46",
        accent="#c8102e",
        texture="reflective",
        font_stack="condensed",
        letter_spacing="0.08em",
        group_gap="0.65em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_source="none",
        region_position="badge",
        region_style="badge",
        bolts=4,
        sheen=0.42,
    ),
    # --- Japan: green-on-white, small class digit, region class up top.
    "jp": PlateVisual(
        theme="jp",
        plate_family="jp",
        aspect=3.0,
        radius="5px",
        border_width="2px",
        background="#fbfdfb",
        background_alt="#eef4ef",
        border="#1f2d3d",
        text="#164d2b",
        muted="#3d6b50",
        accent="#1f6feb",
        texture="metal",
        font_stack="japanese",
        letter_spacing="0.06em",
        digit_scale=0.82,
        letter_scale=1.0,
        group_gap="0.6em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_align="center",
        header_source="region",
        header_color="#164d2b",
        region_position="inline",
        region_style="block",
        bolts=4,
        sheen=0.6,
        emblem="green_mark",
    ),
    # --- USA: state-branded. The header carries the state's own name, so no two
    # states read the same.
    "us": PlateVisual(
        theme="us",
        plate_family="us_state",
        aspect=2.0,
        radius="10px",
        border_width="2px",
        background="#fdfdfd",
        background_alt="#eef1f5",
        border="#1f2937",
        text="#0f172a",
        muted="#64748b",
        accent="#2563eb",
        texture="enamel",
        font_stack="sans",
        letter_spacing="0.14em",
        group_gap="0.55em",
        digit_weight=600,
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_align="center",
        header_source="region",
        header_color="#1f2937",
        region_position="badge",
        region_style="badge",
        bolts=2,
        sheen=0.65,
        emblem="state_tag",
    ),
    # --- Canada: wordmark top-left, short serial, province badge.
    "ca": PlateVisual(
        theme="ca",
        plate_family="americas_long",
        aspect=2.4,
        radius="8px",
        border_width="2px",
        background="#fdfdfd",
        background_alt="#eef2f6",
        border="#1f2937",
        text="#0f172a",
        muted="#64748b",
        accent="#d80621",
        texture="enamel",
        font_stack="sans",
        letter_spacing="0.1em",
        group_gap="0.55em",
        digit_weight=600,
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="CANADA",
        header_align="left",
        header_source="static",
        header_color="#d80621",
        region_position="badge",
        region_style="badge",
        bolts=2,
        sheen=0.6,
        emblem="state_tag",
    ),
    # --- United Arab Emirates
    "ae": PlateVisual(
        theme="ae",
        plate_family="mideast",
        aspect=2.6,
        radius="6px",
        border_width="2px",
        background="#f7f9fc",
        background_alt="#e8edf4",
        border="#0f172a",
        text="#0b1220",
        muted="#64748b",
        accent="#c8a24a",
        texture="chrome",
        font_stack="wide",
        letter_spacing="0.08em",
        group_gap="0.7em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="UAE",
        header="",
        header_source="region",
        header_color="#334155",
        region_position="badge",
        region_style="badge",
        bolts=2,
        sheen=0.7,
        emblem="crest",
    ),
    "am": PlateVisual(
        theme="am",
        plate_family="eu_long",
        aspect=4.2,
        radius="5px",
        border_width="3px",
        background="#ffffff",
        background_alt="#f2f5fa",
        border="#1f2937",
        text="#0b1220",
        muted="#5b6474",
        accent="#d12d2d",
        texture="metal",
        font_stack="wide",
        letter_spacing="0.06em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.17,
        band_text="AM",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        bolts=4,
        sheen=0.5,
    ),
    "ge": PlateVisual(
        theme="ge",
        plate_family="eu_long",
        aspect=4.3,
        radius="5px",
        border_width="3px",
        background="#ffffff",
        background_alt="#f2f6fa",
        border="#1f2937",
        text="#0b1220",
        muted="#5b6474",
        accent="#e11d48",
        texture="metal",
        font_stack="condensed",
        letter_spacing="0.06em",
        group_gap="0.7em",
        band_position="left",
        band_color="#0f766e",
        band_width=0.17,
        band_text="GE",
        band_text_color="#ffffff",
        header="",
        header_source="none",
        region_position="badge",
        bolts=4,
        sheen=0.5,
    ),
    # --- Documented generic families ---------------------------------------
    "european": PlateVisual(
        theme="european",
        plate_family="eu_long",
        aspect=4.6,
        radius="5px",
        border_width="3px",
        background="#fbfbfa",
        background_alt="#eceef2",
        border="#1a1a1a",
        text="#111827",
        muted="#4b5563",
        accent="#7c5cff",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.17,
        band_text="",
        band_text_source="country_alpha2",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        bolts=4,
        sheen=0.5,
    ),
    "eu_long": PlateVisual(
        theme="eu_long",
        plate_family="eu_long",
        aspect=4.9,
        radius="5px",
        border_width="3px",
        background="#fbfbfa",
        background_alt="#eceef2",
        border="#1a1a1a",
        text="#111827",
        muted="#4b5563",
        accent="#7c5cff",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.7em",
        band_position="left",
        band_color=EU_BAND,
        band_width=0.17,
        band_text="",
        band_text_source="country_alpha2",
        band_text_color=EU_BAND_TEXT,
        band_stars=True,
        header="",
        header_source="none",
        region_position="badge",
        bolts=4,
        sheen=0.5,
    ),
    "britain": PlateVisual(
        theme="britain",
        plate_family="uk",
        variant="front",
        aspect=4.6,
        radius="4px",
        border_width="2px",
        background="#f7f7f5",
        background_alt="#e6e6e2",
        border="#111111",
        text="#111111",
        muted="#3f3f46",
        accent="#c8102e",
        texture="reflective",
        font_stack="condensed",
        letter_spacing="0.08em",
        group_gap="0.65em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_source="none",
        region_position="badge",
        region_style="badge",
        bolts=4,
        sheen=0.42,
    ),
    "mideast": PlateVisual(
        theme="mideast",
        plate_family="mideast",
        aspect=2.6,
        radius="6px",
        border_width="2px",
        background="#f7f9fc",
        background_alt="#e8edf4",
        border="#0f172a",
        text="#0b1220",
        muted="#64748b",
        accent="#c8a24a",
        texture="chrome",
        font_stack="wide",
        letter_spacing="0.08em",
        group_gap="0.7em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_source="region",
        header_color="#334155",
        region_position="badge",
        region_style="badge",
        bolts=2,
        sheen=0.7,
        emblem="crest",
    ),
    "nordic": PlateVisual(
        theme="nordic",
        plate_family="eu_long",
        aspect=4.9,
        radius="5px",
        border_width="3px",
        background="#f8faf8",
        background_alt="#e9efe9",
        border="#0f172a",
        text="#0f172a",
        muted="#475569",
        accent="#0f766e",
        texture="metal",
        font_stack="euro",
        letter_spacing="0.05em",
        group_gap="0.75em",
        band_position="left",
        band_color="#0f172a",
        band_width=0.15,
        band_text="",
        band_text_source="country_alpha2",
        band_text_color="#ffffff",
        header="",
        header_source="none",
        region_position="badge",
        bolts=4,
        sheen=0.45,
    ),
    "latam": PlateVisual(
        theme="latam",
        plate_family="americas_long",
        aspect=2.1,
        radius="8px",
        border_width="2px",
        background="#fdfdfd",
        background_alt="#eef1f5",
        border="#1f2937",
        text="#0f172a",
        muted="#64748b",
        accent="#16a34a",
        texture="enamel",
        font_stack="sans",
        letter_spacing="0.1em",
        group_gap="0.55em",
        digit_weight=600,
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_align="center",
        header_source="region",
        header_color="#1f2937",
        region_position="badge",
        bolts=2,
        sheen=0.6,
        emblem="state_tag",
    ),
    "seasia": PlateVisual(
        theme="seasia",
        plate_family="asia_wide",
        aspect=2.2,
        radius="6px",
        border_width="2px",
        background="#fbfbf8",
        background_alt="#eef0ee",
        border="#1f2937",
        text="#0f172a",
        muted="#64748b",
        accent="#0ea5e9",
        texture="metal",
        font_stack="wide",
        letter_spacing="0.08em",
        group_gap="0.6em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_source="region",
        header_color="#334155",
        region_position="badge",
        bolts=2,
        sheen=0.55,
        emblem="state_tag",
    ),
    "oceania": PlateVisual(
        theme="oceania",
        plate_family="asia_wide",
        aspect=2.2,
        radius="8px",
        border_width="2px",
        background="#fbfbf8",
        background_alt="#eef0ee",
        border="#1f2937",
        text="#0f172a",
        muted="#64748b",
        accent="#0891b2",
        texture="metal",
        font_stack="wide",
        letter_spacing="0.1em",
        group_gap="0.6em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_source="region",
        header_color="#334155",
        region_position="badge",
        bolts=2,
        sheen=0.55,
        emblem="state_tag",
    ),
    "africa": PlateVisual(
        theme="africa",
        plate_family="asia_wide",
        aspect=2.3,
        radius="8px",
        border_width="2px",
        background="#fbfbf8",
        background_alt="#eef0ee",
        border="#1f2937",
        text="#0f172a",
        muted="#64748b",
        accent="#ca8a04",
        texture="metal",
        font_stack="wide",
        letter_spacing="0.1em",
        group_gap="0.6em",
        band_position="none",
        band_color=None,
        band_width=0.0,
        band_text="",
        header="",
        header_source="region",
        header_color="#334155",
        region_position="badge",
        bolts=2,
        sheen=0.55,
        emblem="state_tag",
    ),
}

DEFAULT_VISUAL = PlateVisual(theme="european")


def visual_for(theme: str) -> PlateVisual:
    """Recipe for a theme key, falling back to the documented generic EU family."""
    return PLATE_VISUALS.get(theme, DEFAULT_VISUAL)


def band_text_for(visual: PlateVisual, *, alpha2: str = "", alpha3: str = "") -> str:
    """Resolve the code printed inside a country's side band.

    An EU-style band carries the country's own ISO alpha-2 code - Poland prints ``PL``,
    not a generic ``EU`` placeholder - so the country identifier is never a stand-in.
    """
    source = visual.band_text_source
    if source == "country_alpha2":
        return str(alpha2 or "").strip().upper()[:2]
    if source == "country_alpha3":
        return str(alpha3 or "").strip().upper()[:3]
    return visual.band_text


def serialize_visual(theme: str, *, alpha2: str = "", alpha3: str = "") -> dict[str, object]:
    """JSON-serialisable visual contract for the API.

    The payload is complete: the client can render a country's plate correctly with
    no knowledge of that country, and a new country needs no frontend change.
    """
    visual = visual_for(theme)
    data: dict[str, object] = {
        "theme": visual.theme,
        "plate_family": visual.plate_family,
        "variant": visual.variant,
        "aspect": visual.aspect,
        "radius": visual.radius,
        "border_width": visual.border_width,
        "background": visual.background,
        "background_alt": visual.background_alt,
        "border": visual.border,
        "text": visual.text,
        "muted": visual.muted,
        "accent": visual.accent,
        "texture": visual.texture,
        "font_stack": FONT_STACKS.get(visual.font_stack, visual.font_stack),
        "font_stack_key": visual.font_stack,
        "letter_spacing": visual.letter_spacing,
        "group_gap": visual.group_gap,
        "digit_scale": visual.digit_scale,
        "letter_scale": visual.letter_scale,
        "digit_weight": visual.digit_weight,
        "band_position": visual.band_position,
        "band_color": visual.band_color,
        "band_width": visual.band_width,
        "band_text": band_text_for(visual, alpha2=alpha2, alpha3=alpha3),
        "band_text_source": visual.band_text_source,
        "band_text_color": visual.band_text_color,
        "band_stars": visual.band_stars,
        "band_flag": visual.band_flag,
        "header": visual.header,
        "header_align": visual.header_align,
        "header_source": visual.header_source,
        "header_color": visual.header_color or visual.muted,
        "region_position": visual.region_position,
        "region_style": visual.region_style,
        "region_badge": visual.region_badge,
        "show_flag": visual.show_flag,
        "show_region_flag": visual.show_region_flag,
        "bolts": visual.bolts,
        "mount_color": visual.mount_color,
        "gloss": visual.gloss,
        "sheen": visual.sheen,
        "emblem": visual.emblem,
    }
    data.update(visual.extra)
    return data


__all__ = [
    "DEFAULT_VISUAL",
    "EU_BAND",
    "FONT_STACKS",
    "PLATE_VISUALS",
    "PlateVisual",
    "band_text_for",
    "serialize_visual",
    "visual_for",
]
