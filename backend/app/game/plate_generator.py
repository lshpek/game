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

from dataclasses import dataclass, field, replace

from app.game.collectibles import (
    CollectibleKind,
    kind_for_plate_type,
    plate_types_for,
)
from app.game.countries import CountryDef
from app.game.plate_patterns import PlateAnalysis, analyze_plate
from app.game.plate_status import status_series_for
from app.game.plate_rarity import (
    Rarity,
    compute_rarity_score,
    natural_rarity,
    rarity_rank,
    resolve_final_rarity,
)
from app.game.plate_templates import (
    ParsedTemplate,
    Token,
    normalize_plate,
    parse_template,
)
from app.game.plate_valuation import value_for_analysis
from app.game.providers import clamp_modifier
from app.game.rng import weighted_choice
from app.game.sim_cards import card_details, details_to_dict

# A roll never repeats the same serial twice in a row: the generator retries
# (a handful of times) before falling back to the last candidate.
MAX_GENERATION_ATTEMPTS = 8

# Rarer targets get a larger bounded candidate pool. The tier itself is sampled once
# from the exact global weights; candidates are accepted only when their own patterns
# earn that tier. If no exact match is found, the best candidate at or below the target
# is returned rather than allowing luck to promote it.
RARITY_CANDIDATE_BUDGET: dict[Rarity, int] = {
    Rarity.COMMON: 16,
    Rarity.UNCOMMON: 32,
    Rarity.RARE: 96,
    Rarity.EPIC: 256,
    Rarity.LEGENDARY: 512,
    Rarity.MYTHIC: 1024,
    Rarity.SECRET: 2048,
}

# Upper bound for a targeted admin-test generation. Bounded on purpose: the test
# lab must never spin, even when the requested outcome is statistically absurd.
TARGETED_MAX_ATTEMPTS = 40


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
    #: Template configuration (kind, operator, edition, generation knobs).
    config: dict[str, object] = field(default_factory=dict)


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
    #: Kind-specific payload written to ``plates.details``. Empty for vehicle
    #: plates; populated by :mod:`app.game.sim_cards` for SIM cards.
    details: dict[str, object] = field(default_factory=dict)

    @property
    def kind(self) -> CollectibleKind:
        """Which collectible kind this is."""
        return kind_for_plate_type(self.plate_type)

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
    country_code: str = "",
) -> tuple[str, list[dict[str, str]]]:
    """Materialise a template into plate text plus grouped style hints.

    Styles are emitted as *printed groups* - ``A683``, ``ВС``, ``54`` - never one entry
    per character, because that is how a real plate is typeset: a run of letters or
    digits, separated from the next by a gap. Each group carries its kind so the client
    can set digits and letters at their different sizes, and a ``sep`` flag so the
    renderer reproduces the exact spacing without knowing any country logic.

    Joining the groups with their ``sep`` prefixes reproduces ``plate_text`` byte for
    byte, which is what keeps the printed, stored, searched and shared strings identical.
    """
    parts: list[str] = []
    chars: list[tuple[str, str]] = []  # (kind, character) in print order

    for part in parsed.parts:
        if part.is_literal():
            literal = str(part.text)
            parts.append(literal)
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
            chars.extend(("region", ch) for ch in (region_code or ""))
            continue
        else:  # pragma: no cover - parse_template rejects unknown kinds
            text = ""
        parts.append(text)
        style_kind = "letter" if kind in ("L", "A") else "digit"
        chars.extend((style_kind, ch) for ch in text)

    rendered = "".join(parts)
    while "  " in rendered:
        rendered = rendered.replace("  ", " ")
    rendered = rendered.strip()
    return rendered, group_styles(rendered, chars)


def group_styles(text: str, chars: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Fold per-character kinds into printed groups aligned with ``text``.

    Alignment is done by walking the rendered string, so a group only merges with the
    next one when the characters are truly adjacent and of the same kind. Whitespace in
    the text becomes the ``sep`` of the group that follows it.
    """
    styles: list[dict[str, str]] = []
    index = 0
    pending_sep = False
    for char in text:
        if char.isspace():
            pending_sep = True
            continue
        kind = chars[index][0] if index < len(chars) else _kind_of(char)
        index += 1
        if (
            styles
            and not pending_sep
            and styles[-1]["kind"] == kind
            and kind in ("letter", "digit", "region")
        ):
            styles[-1]["text"] += char
            continue
        styles.append({"kind": kind, "text": char, "sep": " " if pending_sep else ""})
        pending_sep = False
    return styles


def _kind_of(char: str) -> str:
    if char.isdigit():
        return "digit"
    if char.isalpha():
        return "letter"
    return "mark"


def styles_for_text(plate_text: str, region_code: str | None = None) -> list[dict[str, str]]:
    """Grouped style hints for an *authored* plate (used by the admin lab).

    Mirrors what :func:`render_template` produces while generating, so a plate an admin
    types by hand renders in the client exactly like a rolled one.
    """
    chars: list[tuple[str, str]] = []
    text = plate_text
    if region_code and region_code in text:
        start = text.find(region_code)
        for position, char in enumerate(text):
            if start <= position < start + len(region_code):
                chars.append(("region", char))
            else:
                chars.append((_kind_of(char), char))
    else:
        chars = [(_kind_of(char), char) for char in text]
    return group_styles(text, chars)


def display_segments(styles: list[dict[str, str]]) -> list[str]:
    """The printed groups, in order."""
    return [style["text"] for style in styles]


def segment_gaps(styles: list[dict[str, str]]) -> list[bool]:
    """Whether a space precedes each printed group.

    The plate text is reconstructed as ``"".join((" " if gap else "") + group)``, so the
    renderer reproduces the exact spacing without knowing any country logic.
    """
    return [str(style.get("sep") or "") == " " for style in styles]


def derive_segment_gaps(plate_text: str, segments: list[str]) -> list[bool]:
    """Whether a space precedes each stored group, recovered from the plate text.

    :func:`segment_gaps` needs the style list, which only exists at render time. A stored
    collectible keeps just the groups, so the spacing is recovered by locating each group
    in the authoritative text. Works for rows written before gaps were stored, too.
    """
    gaps: list[bool] = []
    cursor = 0
    for segment in segments:
        index = plate_text.find(segment, cursor) if segment else -1
        if index < 0:
            gaps.append(False)
            continue
        gaps.append(index > 0 and plate_text[index - 1].isspace())
        cursor = index + len(segment)
    return gaps


def segment_kinds(segments: list[str], region_code: str | None = None) -> list[str]:
    """Classify each printed group as ``letter`` / ``digit`` / ``region``.

    The renderer needs this to print a plate the way the country prints it - digits and
    letters are set at different sizes, and a region's own block is separated from the
    registration. Deriving it from the stored segments (never from the template) keeps
    the printed object, the stored value and the searched value the same string.
    """
    out: list[str] = []
    for segment in segments:
        text = str(segment or "")
        if not text:
            out.append("")
            continue
        has_letters = any(ch.isalpha() for ch in text)
        has_digits = any(ch.isdigit() for ch in text)
        if region_code and text == region_code and has_digits:
            out.append("region")
        elif has_letters and has_digits:
            out.append("mixed")
        elif has_letters:
            out.append("letter")
        elif has_digits:
            out.append("digit")
        else:
            out.append("mark")
    return out


def build_generated_plate(
    *,
    plate_text: str,
    country: CountryDef,
    region: RegionOption | None,
    template: TemplateOption,
    luck: Rarity,
    styles: list[dict[str, str]],
    event_multipliers: dict[str, float] | None = None,
    discovery_count: int = 0,
    force_secret: bool = False,
    season_code: str | None = None,
    force_rarity: Rarity | None = None,
) -> GeneratedPlate:
    """Score, price and package one already-rendered plate.

    Single source of truth for "plate text in, collectible out": the roll engine
    and the admin test lab both go through here, so a forced plate is scored by
    exactly the same rules as a real one.

    ``force_rarity`` is the admin-only escape hatch: the normal resolver only ever
    moves a plate *up* the rarity ladder, so a requested rarity could not be
    honoured for COMMON. When set, it wins outright - and the value is still
    derived from the real analysis, so a forced plate never gets a made-up price.
    """
    parsed_region = region.code if region else None
    analysis = analyze_plate(
        plate_text,
        region_code=parsed_region,
        # A template label is not a pattern and cannot elevate generated rarity.
        rarity_floor="COMMON",
        plate_type=template.plate_type,
        country_tag=country.tag,
        is_secret=False,
        season_code=season_code,
    )

    provider_value = clamp_modifier(_config_value(template.config, "provider_value_modifier"))

    score = compute_rarity_score(
        analysis,
    )

    nat = natural_rarity(analysis)
    rarity = force_rarity or resolve_final_rarity(
        natural=nat,
        luck=luck,
        score=score,
        traits=analysis.traits,
        template_floor=template.rarity_floor,
        force_secret=force_secret,
    )

    status_series = status_series_for(country.code, analysis.letters)
    dealer_value, collector_value = value_for_analysis(
        rarity,
        analysis,
        discovery_count=discovery_count,
        country_multiplier=country.rarity_modifier,
        region_multiplier=1.12 if "region_match" in analysis.traits else 1.0,
        template_multiplier=template.multiplier,
        country_value_scale=country.value_scale,
        provider_multiplier=provider_value,
        collector_multiplier=status_series.collector_multiplier if status_series else 1.0,
    )

    details = _details_for(template, country, plate_text)
    if status_series is not None:
        details["status_series"] = status_series.to_dict()

    return GeneratedPlate(
        plate_text=plate_text,
        normalized_text=normalize_plate(plate_text),
        display_segments=display_segments(styles),
        country=country,
        region_code=parsed_region,
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
        reasons=list(analysis.reasons)[:4],
        display_letters=list(analysis.letters),
        display_numbers=list(analysis.digits),
        segment_styles=styles,
        is_secret=rarity is Rarity.SECRET,
        details=details,
    )


def _config_value(config: dict[str, object], key: str, default: float = 1.0) -> float:
    """Read a numeric template-config value, tolerating absent or malformed entries."""
    try:
        return float(config.get(key, default))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _details_for(
    template: TemplateOption,
    country: CountryDef,
    plate_text: str,
) -> dict[str, object]:
    """Type-specific payload for the generated collectible.

    Only SIM cards carry one. The number printed on the card is the value the engine
    just rendered - the frontend never synthesises it, and the provider, series and
    edition come from the template that produced it.
    """
    if kind_for_plate_type(template.plate_type) is not CollectibleKind.SIM_CARD:
        return {}
    config = template.config or {}
    details = card_details(
        country_code=country.code,
        operator_code=str(config.get("operator_code") or config.get("provider_code") or ""),
        edition=str(config.get("edition") or "ORIGIN"),
        number=plate_text,
        rarity_modifier=clamp_modifier(_config_value(config, "provider_rarity_modifier")),
        value_modifier=clamp_modifier(_config_value(config, "provider_value_modifier")),
    )
    return details_to_dict(details)


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
        force_secret: bool = False,
        force_rarity: Rarity | None = None,
    ) -> GeneratedPlate:
        parsed = parse_template(template.pattern)
        plate_text, styles = render_template(
            parsed,
            alphabet=country.alphabet,
            region_code=region.code if region else None,
            rng=self.rng,
            country_code=country.code,
        )
        return build_generated_plate(
            plate_text=plate_text,
            country=country,
            region=region,
            template=template,
            luck=luck,
            styles=styles,
            event_multipliers=self.ctx.event_multipliers,
            discovery_count=discovery_count,
            force_secret=force_secret,
            force_rarity=force_rarity,
            season_code=self.ctx.season_code,
        )

    def generate(
        self,
        *,
        luck: Rarity,
        rejected: set[tuple[str, str]] | None = None,
        category: CollectibleKind | None = None,
        country_code: str | None = None,
    ) -> GeneratedPlate:
        """Generate a collectible by accepting candidates that earn the sampled tier.

        ``rejected`` lets the service pass the keys the player already owns so a
        roll reliably produces something new when a fresh plate is possible. ``luck`` is
        a desired tier sampled from the global rarity weights, not a rarity promotion:
        every accepted result is scored from its own valid pattern.

        ``category`` and ``country_code`` only **narrow the eligible pool**. They
        decide which templates may be picked, never what the collectible is worth:
        the rarity resolver, the valuation and the reward all still run on the
        generated structure. That is what makes "hunt SIM cards" a gameplay filter
        rather than a way to forge a result.
        """
        pool = self._narrow(country_code=country_code, category=category)
        if pool is None:
            # An empty catalogue for the requested hunt must not fail the roll:
            # fall back to the world so a player always gets a collectible.
            pool = self.ctx

        seen: set[tuple[str, str]] = set(rejected or set())
        last: GeneratedPlate | None = None

        target_rank = rarity_rank(luck)
        best: GeneratedPlate | None = None
        best_rank = -1
        best_score = -1

        for _ in range(RARITY_CANDIDATE_BUDGET.get(luck, MAX_GENERATION_ATTEMPTS)):
            country = pick_country(pool, self.rng)
            region = pick_region(pool, country, self.rng)
            template = pick_template(pool, country, region, self.rng)
            plate = self._attempt(country, region, template, luck)
            last = plate

            candidate_rank = rarity_rank(plate.rarity)
            if candidate_rank == target_rank and plate.unique_key not in seen:
                return plate

            if candidate_rank <= target_rank and (
                candidate_rank > best_rank
                or (candidate_rank == best_rank and plate.rarity_score > best_score)
            ):
                best = plate
                best_rank = candidate_rank
                best_score = plate.rarity_score
            seen.add(plate.unique_key)

        # A bounded search may not find an exact tier in a narrow country/kind pool.
        # Return its strongest valid candidate, never an RNG-promoted label.
        if best is not None:
            return best
        return last  # type: ignore[return-value]

    def _narrow(
        self,
        *,
        country_code: str | None,
        category: CollectibleKind | None,
    ) -> GenerationContext | None:
        """Restrict the generation context to one country and/or kind.

        Returns ``None`` when the request matches nothing, so the caller can fall
        back to the world instead of raising in front of the player.
        """
        wanted_country = str(country_code or "").strip().upper() or None
        # A kind owns a *set* of stored plate types: vehicle plates keep the
        # historical values (STANDARD, COMMERCIAL, MOTORCYCLE, ...), so matching on a
        # single string would silently return an empty pool for every country.
        wanted_types = plate_types_for(category) if category is not None else None

        countries = tuple(
            country
            for country in self.ctx.countries
            if wanted_country is None or country.code == wanted_country
        )
        if not countries:
            return None

        templates_by_country: dict[str, tuple[TemplateOption, ...]] = {}
        for country in countries:
            options = self.ctx.templates_by_country.get(country.code, ())
            if wanted_types is not None:
                options = tuple(
                    option
                    for option in options
                    if (option.plate_type or "").upper() in wanted_types
                )
            templates_by_country[country.code] = options

        # A country can legitimately have no template for the requested kind yet.
        # Keep only the countries that do, and drop templates whose region slot the
        # country cannot fill.
        usable: list[CountryDef] = []
        narrowed: dict[str, tuple[TemplateOption, ...]] = {}
        for country in countries:
            options = templates_by_country[country.code]
            if not options:
                continue
            usable.append(country)
            narrowed[country.code] = options
        if not usable:
            return None

        return replace(
            self.ctx,
            countries=tuple(usable),
            templates_by_country=narrowed,
        )

    # --- admin test lab --------------------------------------------------
    def generate_targeted(
        self,
        *,
        country_code: str | None = None,
        region_code: str | None = None,
        template_code: str | None = None,
        luck: Rarity = Rarity.COMMON,
        target_rarity: Rarity | None = None,
        require_trait: str | None = None,
        max_attempts: int = TARGETED_MAX_ATTEMPTS,
    ) -> GeneratedPlate:
        """Deterministic generation for the internal test lab.

        This is an *isolated* path: it never touches the rarity weights, the
        country weights or any global state. It picks the country/template by
        *code* out of the very same catalogue snapshot the roll engine uses, and
        simply keeps drawing until the requested outcome is reached (bounded, so
        it can never spin forever).

        ``target_rarity`` is honoured by feeding it in as ``luck`` - the engine's
        own resolver takes the most prestigious of natural/luck/score - so the
        production RNG configuration is never modified to satisfy a test.
        """
        countries = self.ctx.countries
        if country_code:
            wanted = country_code.upper()
            countries = tuple(c for c in countries if c.code == wanted)
            if not countries:
                raise ValueError(f"Unknown country code: {wanted}")
        country = countries[0]

        region = self._pick_region(country, region_code)
        template = self._pick_template(country, region, template_code)
        wanted_rarity = target_rarity or luck
        force_secret = wanted_rarity is Rarity.SECRET

        last: GeneratedPlate | None = None
        for _ in range(max(1, max_attempts)):
            plate = self._attempt(
                country,
                region,
                template,
                wanted_rarity,
                force_secret=force_secret,
                # An explicit target is authoritative, so no retry loop is needed
                # to reach it: the resolver only ever moves plates up the ladder.
                force_rarity=target_rarity,
            )
            last = plate
            if plate.rarity is wanted_rarity and (
                require_trait is None or require_trait in plate.analysis.traits
            ):
                return plate
            if require_trait is None and target_rarity is None:
                return plate

        if last is None:  # pragma: no cover - max_attempts >= 1 guarantees this
            raise ValueError("Targeted generation produced nothing.")
        return last

    def _pick_region(self, country: CountryDef, region_code: str | None) -> RegionOption | None:
        options = self.ctx.regions_by_country.get(country.code, ())
        if not options:
            return None
        if region_code:
            wanted = region_code.upper()
            for option in options:
                if option.code.upper() == wanted:
                    return option
            raise ValueError(f"Unknown region code {wanted} for {country.code}")
        return pick_region(self.ctx, country, self.rng)

    def _pick_template(
        self,
        country: CountryDef,
        region: RegionOption | None,
        template_code: str | None,
    ) -> TemplateOption:
        usable = [
            option
            for option in self.ctx.templates_by_country.get(country.code, ())
            if region is not None or not option.requires_region
        ]
        if not usable:
            raise ValueError(f"No usable templates for country {country.code}")
        if template_code:
            wanted = template_code.upper()
            for option in usable:
                if option.code.upper() == wanted:
                    return option
            raise ValueError(f"Unknown template {wanted} for {country.code}")
        return pick_template(self.ctx, country, region, self.rng)


__all__ = [
    "MAX_GENERATION_ATTEMPTS",
    "RARITY_CANDIDATE_BUDGET",
    "TARGETED_MAX_ATTEMPTS",
    "GeneratedPlate",
    "GenerationContext",
    "PlateGenerator",
    "RegionOption",
    "TemplateOption",
    "build_generated_plate",
    "derive_segment_gaps",
    "display_segments",
    "group_styles",
    "pick_country",
    "pick_region",
    "pick_template",
    "render_template",
    "segment_gaps",
    "segment_kinds",
    "styles_for_text",
]
