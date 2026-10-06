"""The NUMORA carrier catalogue - the SIM line's fictional brands.

A collectible SIM card in NUMORA is a physical plastic card with a printed
carrier brand, a printed synthetic number and an edition. This module owns
*which brands a country can print*: NUMORA's own universe of fictional
carriers.

Why fictional brands
--------------------
A collectible SIM must never read like a real person's subscriber line. A
realistic synthetic number printed under a real operator's brand creates
exactly that impression, so the active catalogue is the game's own universe:
every brand here is invented for NUMORA. Nothing here is a real network,
nothing here claims real tariffs, customers or coverage, and a card never
implies a real-world benefit.

Game-economy contract
---------------------
A carrier influences **game** rarity weighting, game value, visual
desirability and set completion - nothing else. ``rarity_modifier`` /
``value_modifier`` are game balance numbers, clamped to a narrow band so the
*number* always dominates the tier.

Home markets
------------
A carrier's ``country`` is its fictional home market - metadata only, never a
filter. Every country draws its line from the whole universe, so the field
exists for the catalogue's own bookkeeping (and the ``sim_providers`` column
that stores it), not to scope what a country may print.

Compatibility
-------------
Cards already in a player's collection keep the brand they were printed with.
The retired real-operator catalogue stays renderable as
:data:`LEGACY_PROVIDERS` - an existing card still shows its brand, its local
name and its colours - but nothing new is ever generated with it.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Tunable ceiling for any single carrier modifier. A carrier can lift a
#: collectible, it can never manufacture a tier on its own - the number
#: pattern always dominates.
MAX_PROVIDER_MODIFIER = 1.20
MIN_PROVIDER_MODIFIER = 0.85

#: A country's SIM line always offers at least this many carriers, so
#: "collect two different carriers" is a reachable goal everywhere.
MIN_PROVIDERS_PER_COUNTRY = 2

#: How many carriers one country's line carries. Every line is the same
#: size, so a country with more playable neighbours is not silently more
#: likely to print any given brand.
LINE_SIZE = 3


@dataclass(frozen=True, slots=True)
class ProviderDef:
    """One carrier brand a country can print on a collectible SIM card.

    ``rarity_modifier`` and ``value_modifier`` are **game balance numbers
    only**. They express how desirable the brand is inside NUMORA's
    collector game; they make no claim whatsoever about any real network.
    """

    code: str
    country: str
    brand: str
    local_name: str = ""
    #: Relative chance of this brand being printed. Higher = more common.
    weight: float = 1.0
    #: Game rarity weighting, clamped to ``[MIN_PROVIDER_MODIFIER, MAX_PROVIDER_MODIFIER]``.
    rarity_modifier: float = 1.0
    #: Game value weighting, clamped to the same bounds.
    value_modifier: float = 1.0
    #: Card identity style key the renderer uses for the brand block.
    visual: str = "neutral"
    accent: str = "#c9a227"
    #: ``False`` for every brand in the active catalogue: nothing in NUMORA
    #: is a real carrier, so nothing implies one.
    real_brand: bool = True
    is_active: bool = True


def _p(
    code: str,
    country: str,
    brand: str,
    local_name: str = "",
    weight: float = 1.0,
    rarity: float = 1.0,
    value: float = 1.0,
    visual: str = "neutral",
    accent: str = "#c9a227",
    real: bool = False,
) -> ProviderDef:
    return ProviderDef(
        code=code,
        country=country,
        brand=brand,
        local_name=local_name or brand,
        weight=weight,
        rarity_modifier=rarity,
        value_modifier=value,
        visual=visual,
        accent=accent,
        real_brand=real,
    )


# ---------------------------------------------------------------------------
# The NUMORA universe - the active catalogue
# ---------------------------------------------------------------------------
# Every entry below is invented for the game. A carrier's home market is
# fiction too: it is where the brand is "based" inside the game world, and
# it never limits which countries may print the brand.
NUMORA_CARRIERS: tuple[ProviderDef, ...] = (
    _p("nova", "RUS", "Nova", "Nova", 1.30, 1.06, 1.08, "burst", "#7b2d8e"),
    _p("vega", "GBR", "Vega", "Vega", 1.25, 1.05, 1.08, "dots", "#06b6d4"),
    _p("orbit", "USA", "Orbit", "Orbit", 1.20, 1.05, 1.07, "circle", "#5b8cff"),
    _p("aurora", "NOR", "Aurora", "Aurora", 1.15, 1.04, 1.06, "blocks", "#34d399"),
    _p("volt", "DEU", "Volt", "Volt", 1.15, 1.04, 1.06, "waveform", "#fbbf24"),
    _p("pulse", "JPN", "Pulse", "Pulse", 1.10, 1.03, 1.05, "waveform", "#22d3ee"),
    _p("axis", "FRA", "Axis", "Axis", 1.05, 1.02, 1.04, "blocks", "#e20074"),
    _p("ion", "ITA", "Ion", "Ion", 1.00, 1.01, 1.03, "circle", "#a855f7"),
    _p("zephyr", "USA", "Zephyr", "Zephyr", 1.00, 1.01, 1.03, "waveform", "#8b5cf6"),
    _p("lumen", "KAZ", "Lumen", "Lumen", 0.95, 1.00, 1.02, "globe", "#f97316"),
    _p("nomad", "TUR", "Nomad", "Nomad", 0.95, 1.00, 1.02, "check", "#f43f5e"),
    _p("kite", "POL", "Kite", "Kite", 0.90, 0.99, 1.01, "burst", "#84cc16"),
    _p("quanta", "CHE", "Quanta", "Quanta", 0.90, 0.99, 1.01, "circle", "#eab308"),
    _p("drift", "NLD", "Drift", "Drift", 0.85, 0.98, 1.00, "dots", "#14b8a6"),
    _p("helix", "SWE", "Helix", "Helix", 0.85, 0.98, 1.00, "waveform", "#ec4899"),
    _p("echo", "ESP", "Echo", "Echo", 0.80, 0.97, 0.99, "globe", "#f97316"),
    _p("flux", "BEL", "Flux", "Flux", 0.80, 0.97, 0.99, "burst", "#6366f1"),
    _p("prism", "AUT", "Prism", "Prism", 0.75, 0.96, 0.98, "blocks", "#d946ef"),
    _p("terra", "BRA", "Terra", "Terra", 0.75, 0.96, 0.98, "check", "#22c55e"),
    _p("solaris", "IND", "Solaris", "Solaris", 0.70, 0.95, 0.97, "circle", "#fb923c"),
    _p("nebula", "KOR", "Nebula", "Nebula", 0.70, 0.95, 0.97, "waveform", "#a78bfa"),
    _p("cirrus", "AUS", "Cirrus", "Cirrus", 0.65, 0.94, 0.96, "dots", "#38bdf8"),
    _p("atlas", "ARE", "Atlas", "Atlas", 0.65, 0.94, 0.96, "globe", "#f43f5e"),
    _p("onyx", "ZAF", "Onyx", "Onyx", 0.60, 0.93, 0.95, "blocks", "#94a3b8"),
)

# ---------------------------------------------------------------------------
# Retired real-operator catalogue
# ---------------------------------------------------------------------------
# The brands below are real mobile network operators. They were the active
# catalogue before NUMORA moved to its own fictional universe, and they stay
# here for one reason only: a card already in a player's collection keeps
# the brand it was printed with. Nothing new is ever generated with them,
# and the seeder never writes them.
LEGACY_PROVIDERS: tuple[ProviderDef, ...] = (
    # --- Russia ------------------------------------------------------------
    _p("mts", "RUS", "MTS", "МТС", 1.30, 1.06, 1.10, "waveform", "#ff0032", real=True),
    _p("megafon", "RUS", "MegaFon", "МегаФон", 1.20, 1.05, 1.08, "waveform", "#00a651", real=True),
    _p("beeline", "RUS", "Beeline", "Билайн", 1.15, 1.04, 1.06, "waveform", "#fcee13", real=True),
    # Tele2 Russia was rebranded to T2 in 2022; the retired line carries the
    # current brand it was last printed with.
    _p("t2", "RUS", "T2", "Т2", 1.00, 1.02, 1.04, "waveform", "#ff8200", real=True),
    # --- Poland ------------------------------------------------------------
    _p("orange_pl", "POL", "Orange", "Orange", 1.25, 1.05, 1.08, "waveform", "#ff7900", real=True),
    _p("play_pl", "POL", "Play", "Play", 1.20, 1.03, 1.05, "burst", "#7b2d8e", real=True),
    _p("tmobile_pl", "POL", "T-Mobile", "T-Mobile", 1.15, 1.05, 1.07, "burst", "#e20074", real=True),
    _p("plus_pl", "POL", "Plus", "Plus", 1.00, 1.01, 1.02, "burst", "#7ec141", real=True),
    # --- Kazakhstan --------------------------------------------------------
    _p("kcell_kz", "KAZ", "Kcell", "Кселл", 1.30, 1.05, 1.08, "waveform", "#8dc63f", real=True),
    _p("beeline_kz", "KAZ", "Beeline", "Билайн", 1.15, 1.03, 1.05, "waveform", "#fcee13", real=True),
    _p("tele2_kz", "KAZ", "Tele2", "Tele2", 1.00, 1.01, 1.03, "waveform", "#0033a0", real=True),
    # --- Germany -----------------------------------------------------------
    _p("telekom_de", "DEU", "Telekom", "Telekom", 1.25, 1.05, 1.08, "blocks", "#e20074", real=True),
    _p("vodafone_de", "DEU", "Vodafone", "Vodafone", 1.20, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("o2_de", "DEU", "O2", "O2", 1.10, 1.03, 1.04, "circle", "#003a8d", real=True),
    _p("oneandone_de", "DEU", "1&1", "1&1", 0.95, 1.02, 1.03, "blocks", "#2aa198", real=True),
    # --- United Kingdom ----------------------------------------------------
    _p("ee_gb", "GBR", "EE", "EE", 1.30, 1.07, 1.11, "circle", "#4c2c92", real=True),
    _p("o2_gb", "GBR", "O2", "O2", 1.25, 1.06, 1.09, "circle", "#0050ff", real=True),
    _p("three_gb", "GBR", "Three", "Three", 1.15, 1.05, 1.07, "circle", "#000000", real=True),
    _p("vodafone_gb", "GBR", "Vodafone", "Vodafone", 1.20, 1.05, 1.07, "circle", "#e60000", real=True),
    _p("giffgaff_gb", "GBR", "giffgaff", "giffgaff", 1.00, 1.03, 1.04, "burst", "#c6007e", real=True),
    # --- France ------------------------------------------------------------
    _p("orange_fr", "FRA", "Orange", "Orange", 1.30, 1.07, 1.10, "blocks", "#ff7900", real=True),
    _p("sfr_fr", "FRA", "SFR", "SFR", 1.20, 1.05, 1.07, "burst", "#e5007d", real=True),
    _p("bouygues_fr", "FRA", "Bouygues", "Bouygues", 1.05, 1.03, 1.04, "blocks", "#8dc63f", real=True),
    _p("free_fr", "FRA", "Free", "Free", 1.00, 1.04, 1.06, "waveform", "#ff5f00", real=True),
    # --- Italy -------------------------------------------------------------
    _p("tim_it", "ITA", "TIM", "TIM", 1.30, 1.06, 1.09, "blocks", "#009246", real=True),
    _p("vodafone_it", "ITA", "Vodafone", "Vodafone", 1.20, 1.05, 1.07, "circle", "#e60000", real=True),
    _p("windtre_it", "ITA", "WindTre", "WindTre", 1.10, 1.04, 1.05, "burst", "#ff9800", real=True),
    _p("three_it", "ITA", "3 Italia", "3 Italia", 1.05, 1.03, 1.04, "circle", "#000000", real=True),
    # --- USA ---------------------------------------------------------------
    _p("verizon_us", "USA", "Verizon", "Verizon", 1.25, 1.05, 1.07, "check", "#ee0000", real=True),
    _p("att_us", "USA", "AT&T", "AT&T", 1.25, 1.05, 1.07, "globe", "#0077c8", real=True),
    _p("tmobile_us", "USA", "T-Mobile", "T-Mobile", 1.30, 1.07, 1.10, "dots", "#e20074", real=True),
    _p("boost_us", "USA", "Boost", "Boost", 0.95, 1.01, 1.02, "burst", "#f9d616", real=True),
    _p("cricket_us", "USA", "Cricket", "Cricket", 0.95, 1.01, 1.03, "blocks", "#4cbb17", real=True),
    # --- Japan -------------------------------------------------------------
    _p("docomo_jp", "JPN", "docomo", "ドコモ", 1.30, 1.08, 1.11, "blocks", "#e60012", real=True),
    _p("au_jp", "JPN", "au", "au", 1.20, 1.06, 1.08, "burst", "#ff6600", real=True),
    _p("softbank_jp", "JPN", "SoftBank", "ソフトバンク", 1.20, 1.06, 1.08, "waveform", "#0088ff", real=True),
    _p("rakuten_jp", "JPN", "Rakuten", "楽天モバイル", 1.05, 1.03, 1.05, "blocks", "#bf0000", real=True),
    # --- UAE ---------------------------------------------------------------
    _p("du_ae", "ARE", "du", "دو", 1.30, 1.07, 1.10, "burst", "#ffcc00", real=True),
    _p("etisalat_ae", "ARE", "Etisalat", "اتصالات", 1.15, 1.05, 1.07, "circle", "#a4ce4e", real=True),
    # --- Canada ------------------------------------------------------------
    _p("rogers_ca", "CAN", "Rogers", "Rogers", 1.25, 1.06, 1.08, "blocks", "#c8102e", real=True),
    _p("bell_ca", "CAN", "Bell", "Bell", 1.20, 1.05, 1.07, "globe", "#0057a7", real=True),
    _p("telus_ca", "CAN", "TELUS", "TELUS", 1.15, 1.05, 1.07, "check", "#00a8e1", real=True),
    _p("fido_ca", "CAN", "Fido", "Fido", 1.05, 1.03, 1.04, "burst", "#c8102e", real=True),
    # --- Armenia -----------------------------------------------------------
    _p("beeline_am", "ARM", "Beeline", "Билайн", 1.30, 1.05, 1.08, "waveform", "#fcee13", real=True),
    _p("cellplus_am", "ARM", "CellPlus", "CellPlus", 1.05, 1.02, 1.03, "blocks", "#0033a0", real=True),
    _p("vivacell_am", "ARM", "VivaCell", "VivaCell", 1.05, 1.02, 1.04, "burst", "#ff8200", real=True),
    _p("mobifone_am", "ARM", "Mobifone", "Mobifone", 1.00, 1.01, 1.03, "circle", "#0057a7", real=True),
    # --- Georgia -----------------------------------------------------------
    _p("magti_ge", "GEO", "Magti", "მაგთი", 1.25, 1.05, 1.07, "waveform", "#0057a7", real=True),
    _p("bakcell_ge", "GEO", "Bakcell", "ბაქქელი", 1.15, 1.04, 1.06, "circle", "#fcee13", real=True),
    _p("silabest_ge", "GEO", "Silabest", "Silabest", 1.05, 1.02, 1.03, "waveform", "#e60012", real=True),
    _p("telecom_ge", "GEO", "Georgian Telecom", "ქართული ტელეკომი", 1.00, 1.01, 1.03, "blocks", "#009966", real=True),
    # --- Spain / Portugal / Netherlands / Belgium / Switzerland / Austria --
    _p("movistar_es", "ESP", "Movistar", "Movistar", 1.25, 1.06, 1.08, "waveform", "#00a1e4", real=True),
    _p("orange_es", "ESP", "Orange", "Orange", 1.15, 1.04, 1.06, "blocks", "#ff7900", real=True),
    _p("vodafone_es", "ESP", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("digimobil_es", "ESP", "DigiMobil", "DigiMobil", 1.00, 1.02, 1.03, "burst", "#00b7c9", real=True),
    _p("nos_pt", "PRT", "NOS", "NOS", 1.25, 1.05, 1.07, "waveform", "#ff0000", real=True),
    _p("vodafone_pt", "PRT", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("orange_pt", "PRT", "Orange", "Orange", 1.15, 1.04, 1.06, "blocks", "#ff7900", real=True),
    _p("kpn_nl", "NLD", "KPN", "KPN", 1.25, 1.05, 1.07, "blocks", "#007bc7", real=True),
    _p("vodafone_nl", "NLD", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("odido_nl", "NLD", "Odido", "Odido", 1.05, 1.03, 1.04, "burst", "#c6007e", real=True),
    _p("proximus_be", "BEL", "Proximus", "Proximus", 1.25, 1.06, 1.08, "burst", "#8dc63f", real=True),
    _p("orange_be", "BEL", "Orange", "Orange", 1.15, 1.04, 1.06, "blocks", "#ff7900", real=True),
    _p("telenet_be", "BEL", "Telenet", "Telenet", 1.10, 1.03, 1.05, "waveform", "#c900a1", real=True),
    _p("swisscom_ch", "CHE", "Swisscom", "Swisscom", 1.25, 1.06, 1.08, "blocks", "#002b7f", real=True),
    _p("sunrise_ch", "CHE", "Sunrise", "Sunrise", 1.10, 1.04, 1.05, "burst", "#ffdc00", real=True),
    _p("salt_ch", "CHE", "Salt", "Salt", 1.00, 1.01, 1.03, "circle", "#ffcc00", real=True),
    _p("a1_at", "AUT", "A1", "A1", 1.25, 1.05, 1.07, "circle", "#e20074", real=True),
    _p("magenta_at", "AUT", "Magenta", "Magenta", 1.15, 1.04, 1.06, "burst", "#7b2d8e", real=True),
    _p("three_at", "AUT", "3", "3", 1.05, 1.02, 1.04, "circle", "#000000", real=True),
    # --- Nordics / Baltics / CEE -------------------------------------------
    _p("telia_se", "SWE", "Telia", "Telia", 1.25, 1.05, 1.07, "waveform", "#f8b400", real=True),
    _p("telenor_se", "SWE", "Telenor", "Telenor", 1.15, 1.04, 1.05, "circle", "#0072ce", real=True),
    _p("tre_se", "SWE", "3", "3", 1.05, 1.02, 1.03, "burst", "#000000", real=True),
    _p("telia_no", "NOR", "Telia", "Telia", 1.25, 1.05, 1.07, "waveform", "#f8b400", real=True),
    _p("telenor_no", "NOR", "Telenor", "Telenor", 1.15, 1.04, 1.05, "circle", "#0072ce", real=True),
    _p("telia_dk", "DNK", "Telia", "Telia", 1.20, 1.05, 1.06, "waveform", "#00a9e0", real=True),
    _p("telenor_dk", "DNK", "Telenor", "Telenor", 1.15, 1.04, 1.05, "circle", "#00a9e0", real=True),
    _p("elisa_fi", "FIN", "Elisa", "Elisa", 1.25, 1.05, 1.07, "globe", "#ff6600", real=True),
    _p("dna_fi", "FIN", "DNA", "DNA", 1.15, 1.04, 1.05, "circle", "#00b4e2", real=True),
    _p("siman_is", "ISL", "Síminn", "Síminn", 1.15, 1.04, 1.05, "circle", "#00b7c9", real=True),
    _p("vodafone_ie", "IRL", "Vodafone", "Vodafone", 1.25, 1.05, 1.07, "circle", "#e60000", real=True),
    _p("eir_ie", "IRL", "eir", "eir", 1.10, 1.03, 1.04, "blocks", "#00a9e0", real=True),
    _p("elisa_ee", "EST", "Elisa", "Elisa", 1.20, 1.05, 1.06, "globe", "#ff6600", real=True),
    _p("tele2_ee", "EST", "Tele2", "Tele2", 1.10, 1.03, 1.04, "circle", "#0033a0", real=True),
    _p("lmt_lv", "LVA", "LMT", "LMT", 1.20, 1.05, 1.06, "waveform", "#e2001a", real=True),
    _p("tele2_lv", "LVA", "Tele2", "Tele2", 1.10, 1.03, 1.04, "circle", "#0033a0", real=True),
    _p("tele2_lt", "LTU", "Tele2", "Tele2", 1.20, 1.05, 1.06, "circle", "#0033a0", real=True),
    _p("bite_lt", "LTU", "Bite", "Bite", 1.10, 1.03, 1.04, "burst", "#ff8200", real=True),
    _p("o2_cz", "CZE", "O2", "O2", 1.20, 1.05, 1.06, "circle", "#0050ff", real=True),
    _p("tmobile_cz", "CZE", "T-Mobile", "T-Mobile", 1.15, 1.04, 1.06, "burst", "#e20074", real=True),
    _p("orange_sk", "SVK", "Orange", "Orange", 1.20, 1.05, 1.06, "blocks", "#ff7900", real=True),
    _p("telekom_sk", "SVK", "Telekom", "Telekom", 1.15, 1.04, 1.06, "blocks", "#e20074", real=True),
    _p("yettel_hu", "HUN", "Yettel", "Yettel", 1.20, 1.05, 1.06, "blocks", "#ffdd00", real=True),
    _p("telekom_hu", "HUN", "Telekom", "Telekom", 1.15, 1.04, 1.06, "waveform", "#0050ff", real=True),
    _p("digi_ro", "ROU", "Digi", "Digi", 1.15, 1.04, 1.05, "blocks", "#ff7900", real=True),
    _p("orange_ro", "ROU", "Orange", "Orange", 1.15, 1.04, 1.06, "circle", "#ff7900", real=True),
    _p("vivacom_bg", "BGR", "Vivacom", "Vivacom", 1.15, 1.04, 1.05, "waveform", "#e2001a", real=True),
    _p("telekom_bg", "BGR", "Telekom", "Telekom", 1.15, 1.04, 1.06, "circle", "#0050ff", real=True),
    _p("cosmote_gr", "GRC", "Cosmote", "Cosmote", 1.25, 1.06, 1.08, "blocks", "#0050ff", real=True),
    _p("vodafone_gr", "GRC", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("nova_gr", "GRC", "nova", "nova", 1.10, 1.03, 1.04, "burst", "#9d0a4a", real=True),
    # --- Americas / rest ---------------------------------------------------
    _p("telcel_mx", "MEX", "Telcel", "Telcel", 1.30, 1.06, 1.08, "circle", "#0a2c8c", real=True),
    _p("movistar_mx", "MEX", "Movistar", "Movistar", 1.15, 1.04, 1.06, "waveform", "#00a1e4", real=True),
    _p("att_mx", "MEX", "AT&T", "AT&T", 1.10, 1.03, 1.04, "globe", "#0077c8", real=True),
    _p("vivo_br", "BRA", "Vivo", "Vivo", 1.30, 1.06, 1.09, "blocks", "#8dc63f", real=True),
    _p("claro_br", "BRA", "Claro", "Claro", 1.20, 1.05, 1.07, "burst", "#ff7900", real=True),
    _p("tim_br", "BRA", "TIM", "TIM", 1.15, 1.04, 1.06, "waveform", "#0b3d91", real=True),
    _p("personal_ar", "ARG", "Personal", "Personal", 1.20, 1.05, 1.06, "burst", "#00539f", real=True),
    _p("claro_ar", "ARG", "Claro", "Claro", 1.15, 1.04, 1.06, "circle", "#d22630", real=True),
    _p("movistar_cl", "CHL", "Movistar", "Movistar", 1.25, 1.06, 1.08, "waveform", "#00539f", real=True),
    _p("entel_cl", "CHL", "Entel", "Entel", 1.05, 1.02, 1.03, "circle", "#8dc63f", real=True),
    _p("claro_co", "COL", "Claro", "Claro", 1.25, 1.05, 1.07, "burst", "#d22630", real=True),
    _p("movistar_co", "COL", "Movistar", "Movistar", 1.20, 1.04, 1.06, "waveform", "#e20074", real=True),
    # --- Asia-Pacific ------------------------------------------------------
    _p("skt_kr", "KOR", "SKT", "SKT", 1.30, 1.07, 1.09, "circle", "#e20074", real=True),
    _p("kt_kr", "KOR", "KT", "KT", 1.25, 1.06, 1.08, "blocks", "#00a651", real=True),
    _p("lgu_kr", "KOR", "LG U+", "LG U+", 1.20, 1.05, 1.07, "burst", "#d71920", real=True),
    _p("chinamobile_cn", "CHN", "China Mobile", "中国移动", 1.30, 1.06, 1.08, "globe", "#0060a5", real=True),
    _p("chinaunicom_cn", "CHN", "China Unicom", "中国联通", 1.20, 1.05, 1.06, "blocks", "#d51f2e", real=True),
    _p("chinatelecom_cn", "CHN", "China Telecom", "中国电信", 1.15, 1.04, 1.06, "circle", "#005bac", real=True),
    _p("airtel_in", "IND", "Airtel", "Airtel", 1.25, 1.06, 1.08, "circle", "#e40000", real=True),
    _p("jio_in", "IND", "Jio", "Jio", 1.30, 1.07, 1.09, "globe", "#0f3cc9", real=True),
    _p("vi_in", "IND", "Vi", "Vi", 1.15, 1.04, 1.06, "burst", "#ff6600", real=True),
    _p("turkcell_tr", "TUR", "Turkcell", "Turkcell", 1.30, 1.06, 1.08, "burst", "#f9d616", real=True),
    _p("turktelekom_tr", "TUR", "Turk Telekom", "Türk Telekom", 1.25, 1.05, 1.07, "circle", "#00c1de", real=True),
    _p("vodafone_tr", "TUR", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("pelago_th", "THA", "AIS", "AIS", 1.25, 1.05, 1.07, "globe", "#7dc31a", real=True),
    _p("dtac_th", "THA", "dtac", "dtac", 1.15, 1.04, 1.06, "burst", "#00a8e1", real=True),
    _p("true_th", "THA", "True", "True", 1.15, 1.04, 1.06, "waveform", "#e40000", real=True),
    _p("singtel_sg", "SGP", "Singtel", "Singtel", 1.30, 1.07, 1.09, "globe", "#ec1c24", real=True),
    _p("starhub_sg", "SGP", "StarHub", "StarHub", 1.15, 1.04, 1.06, "blocks", "#00a1e4", real=True),
    _p("optus_au", "AUS", "Optus", "Optus", 1.25, 1.06, 1.08, "burst", "#00b140", real=True),
    _p("telstra_au", "AUS", "Telstra", "Telstra", 1.30, 1.06, 1.08, "blocks", "#004b8d", real=True),
    _p("vodafone_au", "AUS", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("one_nz", "NZL", "One", "One", 1.20, 1.05, 1.06, "burst", "#7ec141", real=True),
    _p("spark_nz", "NZL", "Spark", "Spark", 1.15, 1.04, 1.05, "circle", "#00a1e4", real=True),
    _p("vodacom_za", "ZAF", "Vodacom", "Vodacom", 1.30, 1.06, 1.08, "circle", "#e60000", real=True),
    _p("mtn_za", "ZAF", "MTN", "MTN", 1.30, 1.06, 1.08, "blocks", "#ffcc00", real=True),
    _p("telkom_za", "ZAF", "Telkom", "Telkom", 1.15, 1.04, 1.05, "waveform", "#007749", real=True),
    # --- Eastern Europe ----------------------------------------------------
    _p("kyivstar_ua", "UKR", "Kyivstar", "Київстар", 1.25, 1.05, 1.07, "circle", "#0072ce", real=True),
    _p("vodafone_ua", "UKR", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000", real=True),
    _p("kyivstar_by", "BLR", "Kyivstar", "Kyivstar", 1.15, 1.04, 1.05, "circle", "#0072ce", real=True),
    _p("life_by", "BLR", "life:)", "life:)", 1.05, 1.02, 1.03, "burst", "#fcee13", real=True),
    # --- Middle East -------------------------------------------------------
    _p("zain_sa", "SAU", "Zain", "زين", 1.25, 1.06, 1.08, "burst", "#0070c0", real=True),
    _p("stc_sa", "SAU", "stc", "STC", 1.25, 1.06, 1.08, "blocks", "#8dc63f", real=True),
    _p("mobily_sa", "SAU", "Mobily", "موبايلي", 1.15, 1.04, 1.06, "globe", "#7c2f87", real=True),
    _p("orange_il", "ISR", "Orange", "Orange", 1.20, 1.05, 1.06, "blocks", "#ff7900", real=True),
    _p("partner_il", "ISR", "Partner", "Partner", 1.15, 1.04, 1.05, "circle", "#ff8200", real=True),
    _p("cellcom_il", "ISR", "Cellcom", "Cellcom", 1.10, 1.03, 1.04, "waveform", "#7b2d8e", real=True),
)

#: The one brand from the first SIM line that never joined the NUMORA
#: universe. It stays renderable - an existing card still shows its brand -
#: but it is never generated any more.
RETIRED_OPERATOR_CODES: frozenset[str] = frozenset({"numa"})

_BY_CODE: dict[str, ProviderDef] = {carrier.code: carrier for carrier in NUMORA_CARRIERS}

_LEGACY_BY_CODE: dict[str, ProviderDef] = {
    provider.code: provider for provider in LEGACY_PROVIDERS
}


def _game_provider(country_code: str, index: int) -> ProviderDef:
    """A documented **game** carrier for a country with no line at all.

    Defensive only: :func:`providers_for` always returns a line, so this
    exists for the day the universe itself is empty. It is deliberately not
    styled after any real carrier.
    """
    code = country_code.strip().upper() or "XXX"
    slug = code.lower()
    names = ("NOVA", "ORBIT", "PULSE", "AXIS")
    accents = ("#5b8cff", "#a855f7", "#22d3ee", "#fbbf24")
    brand = f"{code} {names[index % len(names)]}"
    return ProviderDef(
        code=f"{slug}_game_{index + 1}",
        country=code,
        brand=brand,
        local_name=brand,
        weight=1.0,
        rarity_modifier=1.0 + (index % 3) * 0.02,
        value_modifier=1.0 + (index % 2) * 0.03,
        visual=("waveform", "burst", "circle", "blocks")[index % 4],
        accent=accents[index % len(accents)],
        real_brand=False,
    )


def _game_line(country_code: str) -> tuple[ProviderDef, ...]:
    start = sum(ord(ch) for ch in country_code.upper()) % 4
    return tuple(_game_provider(country_code, start + offset) for offset in range(3))


def clamp_modifier(value: float | None, default: float = 1.0) -> float:
    """Keep a carrier modifier inside its documented, bounded range."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(MIN_PROVIDER_MODIFIER, min(MAX_PROVIDER_MODIFIER, number))


def provider_by_code(code: str | None) -> ProviderDef | None:
    """Resolve a carrier by code: the NUMORA universe first, then the
    retired catalogue, so a card printed with an old brand keeps the
    identity it was printed with."""
    if not code:
        return None
    key = str(code).strip().lower()
    return _BY_CODE.get(key) or _LEGACY_BY_CODE.get(key)


def providers_for(country_code: str) -> tuple[ProviderDef, ...]:
    """The carriers a country may print on a collectible SIM card.

    Every country draws a stable line of :data:`LINE_SIZE` carriers from the
    NUMORA universe, so "collect two different carriers" is a reachable goal
    everywhere and no country ever prints a real network's brand. The line
    is derived from the country code alone: identical on every boot, and a
    card's brand never depends on when it was rolled.
    """
    code = str(country_code or "").strip().upper() or "NUMORA"
    seed = sum(ord(character) for character in code)
    # A step coprime with the universe size, so a line walks the whole
    # universe and never repeats a carrier within itself.
    step = 7
    line: list[ProviderDef] = []
    index = seed % len(NUMORA_CARRIERS)
    while len(line) < LINE_SIZE:
        carrier = NUMORA_CARRIERS[index % len(NUMORA_CARRIERS)]
        if carrier not in line:
            line.append(carrier)
        index += step
    return tuple(line)


def legacy_operator_label(operator_code: str | None) -> str:
    """The brand label for a retired carrier code.

    A card written before the NUMORA catalogue - or with a real operator
    from the retired catalogue - keeps the brand it was printed with. An
    unknown code is upper-cased, which is honest: it reads as a code, not
    as a claim about any carrier.
    """
    provider = provider_by_code(operator_code)
    if provider is not None:
        return provider.brand
    return str(operator_code or "").strip().upper() or "NUMORA"


__all__ = [
    "LEGACY_PROVIDERS",
    "LINE_SIZE",
    "MAX_PROVIDER_MODIFIER",
    "MIN_PROVIDERS_PER_COUNTRY",
    "MIN_PROVIDER_MODIFIER",
    "NUMORA_CARRIERS",
    "RETIRED_OPERATOR_CODES",
    "ProviderDef",
    "clamp_modifier",
    "legacy_operator_label",
    "provider_by_code",
    "providers_for",
]
