"""Plate API schemas.

Every response is typed so the frontend never has to guess a field's shape.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlateVisualSchema(BaseModel):
    """The complete country presentation recipe.

    The client renders exactly what is here: the plate's real physical size, the surface,
    the typography, the country identifier band, region placement, mounting hardware and
    finish. Nothing about a country's plate shape lives in the frontend.

    ``aspect`` is the ratio derived from ``width_mm``/``height_mm``; it is sent alongside
    them so a client can use either, but the millimetre dimensions are the source of
    truth and a payload where they disagree is a bug on the server.
    """

    theme: str = "eu_long"
    #: The country this recipe belongs to. Two countries on one physical standard differ
    #: only here - in the code printed in their band and in their accent colour - so the
    #: client needs it to tell them apart.
    country_code: str = ""
    plate_family: str = "eu_long"
    variant: str = "standard"

    # Physical geometry.
    width_mm: int = 520
    height_mm: int = 112
    aspect: float = 4.643
    radius: str = "6px"
    border_width: str = "2px"

    # Surface.
    background: str = "#f4f6fb"
    background_alt: str = "#e8ecf4"
    border: str = "#1f2937"
    text: str = "#111827"
    muted: str = "#6b7280"
    accent: str = "#7c5cff"
    texture: str = "metal"

    # Typography.
    font_stack: str = "display"
    font_stack_key: str = "euro"
    letter_spacing: str = "0.06em"
    group_gap: str = "0.9em"
    digit_scale: float = 1.0
    letter_scale: float = 0.92
    digit_weight: int = 700

    # Country identifier.
    band_position: str = "left"
    band_color: str | None = None
    band_width: float = 0.0
    band_text: str = ""
    band_text_source: str = "static"
    band_text_color: str = "#ffffff"
    band_stars: bool = False
    #: ``None`` = no flag; a key such as ``"ru"`` or ``"ge"`` = that country's flag,
    #: drawn as vectors inside the identifier band.
    band_flag: str | None = None
    band_emblem: str = ""

    # Printed header.
    header: str = ""
    header_align: str = "center"
    header_source: str = "static"
    header_color: str = "#6b7280"
    header_offset: float = 0.08

    # Region placement.
    region_position: str = "inline"
    region_style: str = "block"
    region_badge: bool = True
    region_width: float = 0.0
    #: Whether the right-hand compartment prints the country's flag above the code.
    region_flag: bool = False
    #: The code printed in that compartment (e.g. ``RUS``), resolved server-side.
    region_text: str = ""
    show_flag: bool = True
    show_region_flag: bool = True

    # Mounting hardware: ``bolts`` | ``holes`` | ``none``.
    mount: str = "bolts"
    mount_color: str = "#8a9099"
    mount_size: float = 0.11

    # Finish.
    gloss: bool = True
    sheen: float = 0.5
    #: Raised-lettering relief, 0..1.
    relief: float = 0.35
    #: Surface grain, 0..1.
    grain: float = 0.16
    emblem: str = ""


class CountryRef(BaseModel):
    code: str = ""
    #: ISO 3166-1 alpha-2 code, for share links and deep links.
    iso_alpha2: str = ""
    name_en: str = ""
    name_ru: str = ""
    flag: str = ""


class RegionRef(BaseModel):
    code: str
    name_en: str
    name_ru: str


class TemplateRef(BaseModel):
    code: str = ""
    pattern: str = ""


class DiscovererRef(BaseModel):
    display_name: str
    username: str | None = None
    photo_url: str | None = None


class SimOperator(BaseModel):
    """Deprecated alias kept so an older client keeps reading a valid payload."""

    code: str
    name: str
    name_local: str = ""


class SimCardDetails(BaseModel):
    """Type-specific payload stored on a SIM card collectible."""

    operator_code: str = ""
    operator: str = ""
    operator_local: str = ""
    #: ``False`` marks a documented game brand, so the UI never implies a real carrier.
    operator_is_real: bool = True
    operator_visual: str = "neutral"
    operator_accent: str = "#c9a227"
    #: Game balance numbers carried with the card so its value stays explainable. They
    #: are not claims about the operator's real tariffs, customers or finances.
    rarity_modifier: float = 1.0
    value_modifier: float = 1.0
    series: str = ""
    edition: str = ""
    synthetic_number: str = ""
    calling_code: str = ""
    synthetic: bool = True


class SimProviderItem(BaseModel):
    """One operator brand a country may print, as advertised to the client."""

    code: str
    brand: str
    local_name: str = ""
    rarity_modifier: float = 1.0
    value_modifier: float = 1.0
    visual: str = "neutral"
    accent: str = "#c9a227"
    is_real_brand: bool = True


class SimCardConfig(BaseModel):
    """How one country prints its collectible SIM cards.

    Purely presentational: the number on a card is generated by the backend and is never
    composed by the client. ``synthetic`` is always ``true`` - no card in the game
    carries a real subscriber number.
    """

    calling_code: str = ""
    groups: list[int] = Field(default_factory=list)
    providers: list[SimProviderItem] = Field(default_factory=list)
    editions: list[str] = Field(default_factory=list)
    synthetic: bool = True
    #: Compatibility alias for clients built against the previous key. Derived from the
    #: same catalogue, so the two lists can never disagree about who a country can
    #: print.
    operators: list[SimOperator] = Field(default_factory=list)


class RollBalance(BaseModel):
    """The authoritative roll economy, as the client renders it.

    The client shows ``normal_rolls`` and ``bonus_rolls`` and counts down to
    ``next_roll_at``. It never computes the economy itself.
    """

    rolls_remaining: int = 0
    normal_rolls: int = 0
    bonus_rolls: int = 0
    daily_allowance: int = 20
    bank_cap: int = 20
    resets_at: str = ""
    next_roll_at: str | None = None
    seconds_to_next_roll: int = 0
    regen_minutes: int = 45


class NextTarget(BaseModel):
    """One objective, machine-readable. The client renders the sentence via i18n."""

    code: str
    country_code: str = ""
    country_name_en: str = ""
    country_name_ru: str = ""
    country_flag: str = ""
    current: int = 0
    target: int = 0
    remaining: int = 0
    progress: float = 0.0
    section_code: str | None = None
    mission_code: str | None = None
    album_code: str | None = None
    rarity: str | None = None
    achievement_code: str | None = None
    reward_coins: int = 0
    providers_total: int = 0


class CountrySection(BaseModel):
    """One completion set inside a country."""

    code: str
    name_en: str = ""
    name_ru: str = ""
    collected: int = 0
    total: int = 0
    remaining: int = 0
    progress: float = 0.0
    completed: bool = False


class CountryCompletion(BaseModel):
    """Country completion: the four sets plus the overall total."""

    country_code: str
    sections: list[CountrySection] = Field(default_factory=list)
    collected: int = 0
    total: int = 0
    remaining: int = 0
    progress: float = 0.0
    completed: bool = False


class VehiclePlateDetails(BaseModel):
    """Type-specific payload for a vehicle plate."""

    layout: str = ""
    family: str = ""


class PlateCard(BaseModel):
    """Canonical collectible representation used everywhere in the app."""

    id: int
    plate_text: str
    normalized_text: str
    display_segments: list[str] = Field(default_factory=list)
    #: Whether a space precedes each group. Together with the groups this reconstructs
    #: ``plate_text`` byte for byte, so the printed, stored, searched and shared values
    #: can never drift apart.
    display_segment_gaps: list[bool] = Field(default_factory=list)
    #: Per-group classification (``letter`` / ``digit`` / ``region`` / ``mixed``) so the
    #: renderer sets the typography the way the country actually prints it.
    display_segment_kinds: list[str] = Field(default_factory=list)
    letters: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    plate_type: str = "STANDARD"
    #: The collectible kind: ``VEHICLE_PLATE`` or ``SIM_CARD``. Clients select on
    #: this and never branch on ``plate_type``; a new kind is a catalogue change, not
    #: a client release.
    kind: str = "VEHICLE_PLATE"
    rarity: str
    rarity_score: int = 0
    rarity_color: str = "#8b93a7"
    reasons: list[str] = Field(default_factory=list)
    reason_labels: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    story: str = ""
    is_secret: bool = False
    season_code: str | None = None
    discovery_count: int = 0
    first_discovered_at: str | None = None
    first_discoverer: DiscovererRef | None = None

    # Fictional, country-local presentation value.
    collector_value: int = 0
    currency_code: str = "USD"
    currency_symbol: str = "$"
    # Authoritative NUMORA economy value.
    dealer_value: int = 0

    country: CountryRef = Field(default_factory=CountryRef)
    region: RegionRef | None = None
    template: TemplateRef = Field(default_factory=TemplateRef)
    visual: PlateVisualSchema = Field(default_factory=PlateVisualSchema)
    #: Kind-specific payload: present for SIM cards, empty for vehicle plates.
    details: SimCardDetails | None = None

    owned: bool = False
    duplicate_count: int = 0
    is_favorite: bool = False
    is_new: bool = False
    acquired_at: str | None = None


class ReelFrame(BaseModel):
    """One synthetic collectible shown while the roll reel is spinning.

    A frame is a *picture*, never a result. It is generated from the real catalogue with a
    separate RNG stream, is not persisted, and is not scored, valued or granted - the
    real collectible is sent separately as :attr:`PlateRollResponse.plate`. That is what
    makes the reel honest: a client that believed a frame would own nothing.
    """

    plate_text: str
    display_segments: list[str] = Field(default_factory=list)
    display_segment_gaps: list[bool] = Field(default_factory=list)
    display_segment_kinds: list[str] = Field(default_factory=list)
    #: The same recipe contract the real card carries, so a frame renders through the
    #: identical component as the result.
    visual: PlateVisualSchema = Field(default_factory=PlateVisualSchema)
    #: ``VEHICLE_PLATE`` or ``SIM_CARD`` - the two collectible kinds, nothing else.
    kind: str = "VEHICLE_PLATE"
    country_code: str = ""
    country_name_en: str = ""
    country_flag: str = ""


class DisplayCurrencySchema(BaseModel):
    """One selectable display currency.

    Presentation only. ``rate`` is a fixed display rate - units of this currency per 1
    NUMORA - and switching it changes nothing the backend stores or the economy pays out.
    """

    code: str
    name: str
    #: A representative country flag, so a picker row is recognisable at a glance.
    flag: str = ""
    rate: float = 1.0
    #: Minor digits to print; 0 for a whole-unit currency such as JPY.
    fraction_digits: int = 2


class CurrencyCatalogResponse(BaseModel):
    """The currencies a playable country in the catalogue actually uses, plus the game's.

    Derived from the country catalogue rather than written out, so the list cannot drift
    from the world and a country added later brings its currency with it.
    """

    #: The currency the economy is denominated in. Also the default display currency.
    game_currency: str = "NUMORA"
    #: The three-letter code shown in the picker.
    game_currency_code: str = "NMR"
    currencies: list[DisplayCurrencySchema] = Field(default_factory=list)


class PlateRollResponse(BaseModel):
    success: bool = True
    roll_id: int
    plate: PlateCard
    rarity: str
    natural_rarity: str
    luck_rarity: str
    rarity_score: int
    is_duplicate: bool
    is_first_discovery: bool
    is_new_country: bool = False
    is_new_region: bool = False
    numora_awarded: int = 0
    balance: int
    rolls_remaining: int
    sale_value: int
    collector_level: int
    #: Authoritative roll economy after this roll, including the regeneration countdown.
    rolls: RollBalance = Field(default_factory=RollBalance)
    #: The single next objective, machine-readable.
    next_target: NextTarget | None = None
    #: Synthetic frames for the reel animation, generated server-side and never
    #: persisted. The winning collectible is ``plate``; these are only what it scrolls
    #: through on the way there.
    reel: list[ReelFrame] = Field(default_factory=list)
    missions_completed: list[dict[str, Any]] = Field(default_factory=list)
    albums_completed: list[dict[str, Any]] = Field(default_factory=list)
    unlocked_achievements: list[dict[str, Any]] = Field(default_factory=list)
    event: dict[str, Any] | None = None
    replayed: bool = False
    share_start_param: str
    # Compatibility aliases for clients built against the number roll. Kept
    # deliberately: an old client must keep reading a valid collectible while it
    # updates, and none of these fields leaks game rules the backend does not own.
    value: int = 0
    coins_awarded: int = 0
    conversion_value: int = 0
    number: PlateCard | None = None


class PlateRollHistoryItem(BaseModel):
    roll_id: int
    plate_text: str
    plate_id: int
    country_code: str
    rarity: str
    rarity_score: int
    collector_value: int
    currency_symbol: str
    dealer_value: int
    is_duplicate: bool
    is_first_discovery: bool
    created_at: str


class CollectionResponse(BaseModel):
    items: list[PlateCard]
    page: int
    page_size: int
    total: int
    has_more: bool
    rarity_breakdown: dict[str, int] = Field(default_factory=dict)
    progress: float = 0.0
    target: int = 0
    duplicates_count: int = 0
    total_dealer_value: int = 0
    #: The country the list was filtered by (``None`` = the whole world).
    country_code: str | None = None


class SaleResponse(BaseModel):
    plate_id: int
    plate_text: str
    copies_sold: int
    numora_gained: int
    duplicates_left: int
    balance: int


class SellAllResponse(BaseModel):
    plates_sold: int
    copies_sold: int
    numora_gained: int
    balance: int


class FavoriteResponse(BaseModel):
    plate_id: int
    is_favorite: bool


class ShareResponse(BaseModel):
    plate_id: int
    plate_text: str
    rarity: str
    rarity_score: int
    collector_value: int
    currency_symbol: str
    dealer_value: int
    start_param: str
    mini_app_link: str
    share_text_en: str = ""
    share_text_ru: str = ""


class CountrySummary(BaseModel):
    code: str
    iso_alpha2: str = ""
    name_en: str
    name_ru: str
    flag: str
    region_group: str
    currency_code: str
    currency_symbol: str
    calling_code: str = ""
    visual: PlateVisualSchema = Field(default_factory=PlateVisualSchema)
    collected: int = 0
    total: int = 0
    progress: float = 0.0
    percent: float = 0.0
    best_rarity: str | None = None
    regions_collected: int = 0
    regions_total: int = 0
    completed: bool = False
    sort_order: int = 0
    is_active: bool = True
    #: Whether a roll may currently produce this country.
    is_playable: bool = True


class WorldResponse(BaseModel):
    countries: list[CountrySummary]
    total_collected: int
    total_plates: int
    progress: float
    event: dict[str, Any] | None = None
    offset: int = 0
    limit: int = 60
    countries_total: int = 0
    playable_total: int = 0
    locked_total: int = 0


class CountryDetail(BaseModel):
    code: str
    iso_alpha2: str = ""
    name_en: str
    name_ru: str
    flag: str
    region_group: str
    currency_code: str
    currency_symbol: str
    calling_code: str = ""
    visual: PlateVisualSchema = Field(default_factory=PlateVisualSchema)
    is_playable: bool = True
    collected: int
    total: int
    progress: float
    percent: float
    best_rarity: str | None = None
    completed: bool
    #: How many of the country's regions the player has something from.
    regions_collected: int = 0
    regions_total: int = 0
    regions: list[dict[str, Any]] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    #: The four completion sets plus the country's overall total.
    completion: CountryCompletion | None = None
    #: The single objective for this country.
    next_target: NextTarget | None = None


class AlbumProgressItem(BaseModel):
    code: str
    name_en: str
    name_ru: str
    description_en: str = ""
    description_ru: str = ""
    icon: str = ""
    kind: str = "THEME"
    collected: int
    total: int
    progress: float
    percent: float
    completed: bool
    reward_coins: int = 0
    reward_title: str | None = None


class MissionItem(BaseModel):
    code: str
    name_en: str
    name_ru: str
    description_en: str = ""
    description_ru: str = ""
    icon: str = "target"
    progress: int
    target: int
    completed: bool
    reward_coins: int
    reward_rolls: int
    reward_xp: int


class CosmeticItem(BaseModel):
    code: str
    kind: str
    name_en: str
    name_ru: str
    description_en: str = ""
    description_ru: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    price_stars: int = 0
    price_numora: int = 0
    rarity: str = "COMMON"
    owned: bool = False
    equipped: bool = False
    locked: bool = True


class EquipCosmeticResponse(BaseModel):
    code: str
    equipped: bool
    equipped_map: dict[str, str] = Field(default_factory=dict)


class EventResponse(BaseModel):
    code: str
    name_en: str
    name_ru: str
    flag: str
    country_multipliers: dict[str, float] = Field(default_factory=dict)
    ends_at: str | None = None
    reward_coins: int = 0
    reward_title: str | None = None
    is_event: bool = False


class PlateShareView(BaseModel):
    """Public view of a shared plate (used by deep links)."""

    plate: PlateCard
    discoverer: DiscovererRef | None = None
    is_owned: bool = False
    start_param: str = ""


class DealerSaleRequest(BaseModel):
    copies: int = Field(default=1, ge=1, le=999)
    allow_last: bool = Field(
        default=False,
        description="Explicit opt-in required before the final copy may be sold.",
    )
