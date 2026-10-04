"""Country visual identity.

Each country gets a plate *theme*: dimensions, background, border, typography,
country band, header text, region placement and badge styling. The client reads
these values and renders; it never hardcodes country presentation logic.

Deliberately restrained: subtle cues (a country band, a small emblem mark, a
state name strip) rather than giant flag emoji plastered over every card.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PlateVisual:
    """Presentation contract for one country's plates."""

    theme: str
    aspect: float = 4.6
    background: str = "#f4f6fb"
    border: str = "#1f2937"
    text: str = "#111827"
    muted: str = "#6b7280"
    accent: str = "#7c5cff"
    band_color: str | None = None
    band_width: float = 0.0
    header: str = ""
    header_align: str = "center"
    show_flag: bool = True
    show_region_flag: bool = True
    region_badge: bool = True
    font_stack: str = "display"
    letter_spacing: str = "0.06em"
    gloss: bool = True
    texture: str = "metal"
    extra: dict[str, str] = field(default_factory=dict)


PLATE_VISUALS: dict[str, PlateVisual] = {
    "ru": PlateVisual(
        theme="ru", aspect=4.9, background="#ffffff", border="#111827",
        text="#0b1220", muted="#5b6474", accent="#2f6bd8", header="RUS",
        header_align="left", show_flag=False, texture="metal",
        extra={"outline": "1px solid #111827"},
    ),
    "us": PlateVisual(
        theme="us", aspect=3.0, background="#fdfdfd", border="#1f2937",
        text="#0f172a", muted="#64748b", accent="#2563eb", header="STATE",
        header_align="center", show_flag=False, show_region_flag=True,
        region_badge=True, font_stack="mono", texture="enamel",
    ),
    "kz": PlateVisual(
        theme="kz", aspect=4.4, background="#f7fbff", border="#0f3f8f",
        text="#0a1c3d", muted="#3f5a86", accent="#0096c7", band_color="#0096c7",
        band_width=0.06, header="KAZ", texture="metal",
    ),
    "de": PlateVisual(
        theme="de", aspect=4.9, background="#fdfdfb", border="#111827",
        text="#111827", muted="#4b5563", accent="#111827", band_color="#1a1a1a",
        band_width=0.055, header="D", header_align="left", show_flag=False,
        texture="metal",
    ),
    "gb": PlateVisual(
        theme="gb", aspect=4.6, background="#f6f6f4", border="#111111",
        text="#111111", muted="#555555", accent="#c8102e", header="GB",
        header_align="right", show_flag=False, region_badge=True, texture="reflective",
    ),
    "fr": PlateVisual(
        theme="fr", aspect=4.3, background="#ffffff", border="#1f2937",
        text="#0b1220", muted="#5b6474", accent="#0055a4", header="F",
        header_align="right", show_flag=False, texture="metal",
    ),
    "it": PlateVisual(
        theme="it", aspect=4.3, background="#ffffff", border="#1f2937",
        text="#0b1220", muted="#5b6474", accent="#009246", header="I",
        header_align="left", show_flag=False, texture="metal",
    ),
    "ca": PlateVisual(
        theme="ca", aspect=3.6, background="#ffffff", border="#1f2937",
        text="#0f172a", muted="#64748b", accent="#d80621", header="CANADA",
        header_align="left", show_flag=False, region_badge=True,
        font_stack="mono", texture="enamel",
    ),
    "jp": PlateVisual(
        theme="jp", aspect=2.9, background="#f7fafc", border="#1f2d3d",
        text="#0d1b2a", muted="#52606d", accent="#1f6feb", header="JP",
        header_align="center", region_badge=True, font_stack="mono",
        letter_spacing="0.02em", texture="metal",
    ),
    "ae": PlateVisual(
        theme="ae", aspect=2.6, background="#f6f8fb", border="#0f172a",
        text="#0b1220", muted="#64748b", accent="#c8a24a", header="UAE",
        header_align="center", region_badge=True, gloss=True, texture="chrome",
        extra={"glow": "0 18px 46px rgba(200,162,74,0.28)"},
    ),
    "am": PlateVisual(
        theme="am", aspect=4.2, background="#ffffff", border="#1f2937",
        text="#0b1220", muted="#5b6474", accent="#d12d2d", header="AM",
        header_align="center", show_flag=False, region_badge=True, texture="metal",
    ),
    "ge": PlateVisual(
        theme="ge", aspect=4.3, background="#ffffff", border="#1f2937",
        text="#0b1220", muted="#5b6474", accent="#e11d48", header="GE",
        header_align="center", show_flag=False, region_badge=True, texture="metal",
    ),
}

DEFAULT_VISUAL = PlateVisual(theme="european")


def visual_for(theme: str) -> PlateVisual:
    return PLATE_VISUALS.get(theme, DEFAULT_VISUAL)


def serialize_visual(theme: str) -> dict[str, object]:
    """JSON-serialisable visual contract for the API."""
    visual = visual_for(theme)
    data: dict[str, object] = {
        "theme": visual.theme,
        "aspect": visual.aspect,
        "background": visual.background,
        "border": visual.border,
        "text": visual.text,
        "muted": visual.muted,
        "accent": visual.accent,
        "band_color": visual.band_color,
        "band_width": visual.band_width,
        "header": visual.header,
        "header_align": visual.header_align,
        "show_flag": visual.show_flag,
        "show_region_flag": visual.show_region_flag,
        "region_badge": visual.region_badge,
        "font_stack": visual.font_stack,
        "letter_spacing": visual.letter_spacing,
        "gloss": visual.gloss,
        "texture": visual.texture,
    }
    data.update(visual.extra)
    return data


__all__ = ["DEFAULT_VISUAL", "PLATE_VISUALS", "PlateVisual", "serialize_visual", "visual_for"]
