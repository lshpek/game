"""Server-authoritative plate generation.

The frontend never decides a country, a region, a serial, a rarity or a value -
it only animates the result this engine returns.

Pipeline::

    country selection (weights + event modifiers)
      -> region selection (weighted)
      -> template selection (weighted, region compatible)
      -> serial generation from the template language
      -> pattern analysis
      -> rarity scoring
      -> rarity resolution (natural + luck + score)
      -> collector / dealer valuation

Production uses ``secrets.SystemRandom``; tests inject a seeded
``random.Random`` through the ``rng`` parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.game.countries import CountryDef
from app.game.plate_patterns import PlateAnalysis, analyze_plate
from app.game.plate_rarity import (
    Rarity,
    compute_rarity_score,
    natural_rarity,
    resolve_final_rarity,
)
from app.game.plate_templates import ParsedTemplate, Token, normalize_plate, parse_template
from app.game.plate_valuation import value_for_analysis
from app.game.rng import weighted_choice

# A roll never repeats the same serial twice in a row: the generator retries
# (a handful of times) before falling back to the last candidate.
MAX_GENERATION_ATTEMPTS = 8


@dataclass(frozen=True, slots=True)
class RegionOption:
    code: str
    name_en: str
    name_ru: str
    weight: float


@dataclass(frozen=True, slots=True)
class TemplateOption:
    code: str
    pattern: str
    weight: float
    plate_type: str
    rarity_floor: str
    requires_region: bool
    multiplier: float = 1.0


@dataclass(slots=True)
class GenerationContext:
    """Everything the engine needs that does not come from the RNG."""

    countries: tuple[CountryDef, ...]
    regions_by_country: dict[str, tuple[RegionOption, ...]]
    templates_by_country: dict[str, tuple[TemplateOption, ...]]
    rarity_weights: dict[str, float]
    event_multipliers: dict[str, float] = field(default_factory=dict)
    season_code: str | None = None


@dataclass(slots=True)
class GeneratedPlate:
    """The fully-resolved outcome of one generation pass."""

    plate_text: str
    normalized_text: str
    display_segments: list[str]
    country: CountryDef
    region_code: str | None
    region_name_en: str
    region_name_ru: str
    template_code: str
    template_pattern: str
    plate_type: str
    analysis: PlateAnalysis
    rarity: Rarity
    natural_rarity: Rarity
    luck_rarity: Rarity
    rarity_score: int
    collector_value: int
    dealer_value: int
    currency_code: str
    currency_symbol: str
    reasons: list[str]
    display_letters: list[str]
    display_numbers: list[str]
    segment_styles: list[dict[str, str]] = field(default_factory=list)
    is_secret: bool = False

    @property
    def unique_key(self) -> tuple[str, str]:
        """Identity of a collectible: the same serial may exist per country."""
        return (self.country.code, self.normalized_text)


# --- selection helpers -----------------------------------------------------
def pick_country(ctx: GenerationContext, rng) -> CountryDef:
    """Weighted country choice, boosted by any active event modifiers."""
    weights = {
        country.code: float(country.weight) * float(ctx.event_multipliers.get(country.code, 1.0))
        for country in ctx.countries
    }
    chosen = weighted_choice(weights, rng)
    return next(c for c in ctx.countries if c.code == chosen)


def pick_region(ctx: GenerationContext, country: CountryDef, rng) -> RegionOption | None:
    regions = ctx.regions_by_country.get(country.code, ())
    if not regions:
        return None
    weights = {region.code: float(region.weight) for region in regions}
    chosen = weighted_choice(weights, rng)
    return next(region for region in regions if region.code == chosen)


def pick_template(
    ctx: GenerationContext,
    country: CountryDef,
    region: RegionOption | None,
    rng,
) -> TemplateOption:
    options = [
        option
        for option in ctx.templates_by_country.get(country.code, ())
        if region is not None or not option.requires_region
    ]
    if not options:  # pragma: no cover - guarded by the seed invariant
        raise ValueError(f"No usable templates for country {country.code}")
    weights = {option.code: float(option.weight) for option in options}
    chosen = weighted_choice(weights, rng)
    return next(option for option in options if option.code == chosen)


def _letter(alphabet: str, rng) -> str:
    if not alphabet:
        return "A"
    return alphabet[rng.randint(0, len(alphabet) - 1)]


def render_template(
    parsed: ParsedTemplate,
    *,
    alphabet: str,
    region_code: str | None,
    rng,
) -> tuple[str, list[dict[str, str]]]:
    """Materialise a template into plate text plus per-segment style hints.

    Each non-separator segment carries its kind so the client can colour letters,
    digits and the region distinctly without hardcoding any country logic.
    """
    parts: list[str] = []
    styles: list[dict[str, str]] = []

    for part in parsed.parts:
        if part.is_literal():
            parts.append(part.text)  # type: ignore[attr-defined]
            continue

        token: Token = part  # type: ignore[assignment]
        kind = token.kind
        if kind == "D":
            text = str(rng.randint(0, 9))
        elif kind in ("L", "A"):
            text = "".join(_letter(alphabet, rng) for _ in (token.choices or ("",)))
        elif kind == "F":
            text = token.choices[0] if token.choices else "0"
        elif kind == "X":
            choices = token.choices or "0123456789"
            text = choices[rng.randint(0, len(choices) - 1)]
        elif kind == "R":
            # An empty region slot must not leave a dangling separator.
            parts.append(region_code or "")
            if region_code:
                styles.append({"kind": "region", "text": region_code})
            continue
        else:  # pragma: no cover - parse_template rejects unknown kinds
            text = ""
        parts.append(text)
        styles.append({"kind": "letter" if kind in ("L", "A") else "digit", "text": text})

    rendered = "".join(parts)
    while "  " in rendered:
        rendered = rendered.replace("  ", " ")
    return rendered.strip(), [style for style in styles if style["text"]]


def display_segments(styles: list[dict[str, str]]) -> list[str]:
    return [style["text"] for style in styles]


class PlateGenerator:
    """Turns RNG draws into a fully-resolved :class:`GeneratedPlate`."""

    def __init__(self, ctx: GenerationContext, rng) -> None:
        self.ctx = ctx
        self.rng = rng

    def _attempt(
        self,
        country: CountryDef,
        region: RegionOption | None,
        template: TemplateOption,
        luck: Rarity,
        *,
        discovery_count: int = 0,
    ) -> GeneratedPlate:
        parsed = parse_template(template.pattern)
        plate_text, styles = render_template(
            parsed,
            alphabet=country.alphabet,
            region_code=region.code if region else None,
            rng=self.rng,
        )
        region_code = region.code if region else None

        analysis = analyze_plate(
            plate_text,
            region_code=region_code,
            rarity_floor=template.rarity_floor,
            plate_type=template.plate_type,
            country_tag=country.tag,
            is_secret=False,
            season_code=self.ctx.season_code,
        )

        # Events nudge the score slightly, but can never dominate the patterns.
        raw_event = float(self.ctx.event_multipliers.get(country.code, 1.0))
        event_modifier = 1.0 + min(0.35, max(0.0, raw_event - 1.0) * 0.2)

        score = compute_rarity_score(
            analysis,
            country_modifier=country.rarity_modifier,
            template_multiplier=template.multiplier,
            event_modifier=event_modifier,
            novelty_bonus=6.0 if discovery_count == 0 else 0.0,
        )

        nat = natural_rarity(analysis)
        rarity = resolve_final_rarity(
            natural=nat,
            luck=luck,
            score=score,
            traits=analysis.traits,
            template_floor=template.rarity_floor,
        )

        dealer_value, collector_value = value_for_analysis(
            rarity,
            analysis,
            discovery_count=discovery_count,
            country_multiplier=country.rarity_modifier,
            region_multiplier=1.12 if "region_match" in analysis.traits else 1.0,
            template_multiplier=template.multiplier,
            country_value_scale=country.value_scale,
        )

        reasons = list(analysis.reasons)
        return GeneratedPlate(
            plate_text=plate_text,
            normalized_text=normalize_plate(plate_text),
            display_segments=display_segments(styles),
            country=country,
            region_code=region_code,
            region_name_en=region.name_en if region else "",
            region_name_ru=region.name_ru if region else "",
            template_code=template.code,
            template_pattern=template.pattern,
            plate_type=template.plate_type,
            analysis=analysis,
            rarity=rarity,
            natural_rarity=nat,
            luck_rarity=luck,
            rarity_score=score,
            collector_value=collector_value,
            dealer_value=dealer_value,
            currency_code=country.currency_code,
            currency_symbol=country.currency_symbol,
            reasons=reasons[:4],
            display_letters=list(analysis.letters),
            display_numbers=list(analysis.digits),
            segment_styles=styles,
            is_secret=rarity is Rarity.SECRET,
        )

    def generate(
        self,
        *,
        luck: Rarity,
        rejected: set[tuple[str, str]] | None = None,
    ) -> GeneratedPlate:
        """Generate one plate, retrying when the serial was already rejected.

        ``rejected`` lets the service pass the keys the player already owns so a
        roll reliably produces something new when a fresh plate is possible.
        """
        seen: set[tuple[str, str]] = set(rejected or set())
        last: GeneratedPlate | None = None

        for _ in range(MAX_GENERATION_ATTEMPTS):
            country = pick_country(self.ctx, self.rng)
            region = pick_region(self.ctx, country, self.rng)
            template = pick_template(self.ctx, country, region, self.rng)
            plate = self._attempt(country, region, template, luck)
            last = plate
            if plate.unique_key not in seen:
                return plate
            seen.add(plate.unique_key)

        # Extremely unlikely after MAX_GENERATION_ATTEMPTS; returning the last
        # candidate is better than failing the roll.
        return last  # type: ignore[return-value]


__all__ = [
    "GeneratedPlate",
    "GenerationContext",
    "PlateGenerator",
    "RegionOption",
    "TemplateOption",
    "display_segments",
    "pick_country",
    "pick_region",
    "pick_template",
    "render_template",
]