"""Mobile operator provider catalogue - the SIM line's real-world brands.

A collectible SIM card in NUMORA is a physical plastic card with a printed operator
brand, a printed synthetic number and an edition. This module owns *which brands a
country can print*: real, current mobile operators that actually operate in the
country the card belongs to.

Why real brands
---------------
A fictional brand set made every card in the game read like the same beige rectangle.
Using the operators a player actually sees in their own country gives the SIM line a
recognisable identity, makes "collect two different operators" a real goal, and lets a
provider carry a genuine collector weight inside the game.

Game-economy contract (important)
----------------------------------
A provider here influences **game** rarity weighting, game value, visual desirability
and set completion - nothing else. It never claims that a provider's real tariffs,
subscriber base or market position determine anything in NUMORA, and it never grants a
real-world benefit. ``rarity_modifier`` / ``value_modifier`` are game balance numbers
and are documented as such.

Branding currency
-----------------
Brands are recorded as currently used. Russia's Tele2 was rebranded to **T2** in 2022,
so the catalogue carries ``t2`` (not ``tele2``); Poland's T-Mobile is ``t-mobile`` for
the same reason.

Fallback honesty
----------------
Curated countries below use real operators. A country without a curated line falls
back to documented **game operator names** derived from its ISO code. Those are
explicitly *not* claims about any real carrier, and they are marked ``game=True`` so
the UI can say so.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Tunable ceiling for any single provider modifier. A provider can lift a collectible,
#: it can never manufacture a tier on its own - the number pattern always dominates.
MAX_PROVIDER_MODIFIER = 1.20
MIN_PROVIDER_MODIFIER = 0.85

#: A country's SIM line always offers at least this many brands, so "collect two
#: different operators" is a reachable goal everywhere.
MIN_PROVIDERS_PER_COUNTRY = 2


@dataclass(frozen=True, slots=True)
class ProviderDef:
    """One mobile operator brand a country can print on a collectible SIM card.

    ``rarity_modifier`` and ``value_modifier`` are **game balance numbers only**.
    They express how desirable the brand is inside NUMORA's collector game; they make
    no claim whatsoever about the operator's real tariffs, customers or finances.
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
    #: ``False`` for documented game-only brands so nothing implies a real carrier.
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
    )


# ---------------------------------------------------------------------------
# Curated real-operator lines
# ---------------------------------------------------------------------------
# Every entry below is a real mobile network operator operating in that country,
# recorded under its current branding. ``rarity`` / ``value`` describe collector
# desirability *inside the game* and are deliberately modest: a famous brand with a
# boring number must not jump the rarity ladder.
PROVIDERS: tuple[ProviderDef, ...] = (
    # --- Russia ------------------------------------------------------------
    _p("mts", "RUS", "MTS", "МТС", 1.30, 1.06, 1.10, "waveform", "#ff0032"),
    _p("megafon", "RUS", "MegaFon", "МегаФон", 1.20, 1.05, 1.08, "waveform", "#00a651"),
    _p("beeline", "RUS", "Beeline", "Билайн", 1.15, 1.04, 1.06, "waveform", "#fcee13"),
    # Tele2 Russia was rebranded to T2 in 2022; new content uses the current brand.
    _p("t2", "RUS", "T2", "Т2", 1.00, 1.02, 1.04, "waveform", "#ff8200"),
    # --- Poland ------------------------------------------------------------
    _p("orange_pl", "POL", "Orange", "Orange", 1.25, 1.05, 1.08, "waveform", "#ff7900"),
    _p("play_pl", "POL", "Play", "Play", 1.20, 1.03, 1.05, "burst", "#7b2d8e"),
    _p("tmobile_pl", "POL", "T-Mobile", "T-Mobile", 1.15, 1.05, 1.07, "burst", "#e20074"),
    _p("plus_pl", "POL", "Plus", "Plus", 1.00, 1.01, 1.02, "burst", "#7ec141"),
    # --- Kazakhstan --------------------------------------------------------
    _p("kcell_kz", "KAZ", "Kcell", "Кселл", 1.30, 1.05, 1.08, "waveform", "#8dc63f"),
    _p("beeline_kz", "KAZ", "Beeline", "Билайн", 1.15, 1.03, 1.05, "waveform", "#fcee13"),
    _p("tele2_kz", "KAZ", "Tele2", "Tele2", 1.00, 1.01, 1.03, "waveform", "#0033a0"),
    # --- Germany -----------------------------------------------------------
    _p("telekom_de", "DEU", "Telekom", "Telekom", 1.25, 1.05, 1.08, "blocks", "#e20074"),
    _p("vodafone_de", "DEU", "Vodafone", "Vodafone", 1.20, 1.04, 1.06, "circle", "#e60000"),
    _p("o2_de", "DEU", "O2", "O2", 1.10, 1.03, 1.04, "circle", "#003a8d"),
    _p("oneandone_de", "DEU", "1&1", "1&1", 0.95, 1.02, 1.03, "blocks", "#2aa198"),
    # --- United Kingdom ----------------------------------------------------
    _p("ee_gb", "GBR", "EE", "EE", 1.30, 1.07, 1.11, "circle", "#4c2c92"),
    _p("o2_gb", "GBR", "O2", "O2", 1.25, 1.06, 1.09, "circle", "#0050ff"),
    _p("three_gb", "GBR", "Three", "Three", 1.15, 1.05, 1.07, "circle", "#000000"),
    _p("vodafone_gb", "GBR", "Vodafone", "Vodafone", 1.20, 1.05, 1.07, "circle", "#e60000"),
    _p("giffgaff_gb", "GBR", "giffgaff", "giffgaff", 1.00, 1.03, 1.04, "burst", "#c6007e"),
    # --- France ------------------------------------------------------------
    _p("orange_fr", "FRA", "Orange", "Orange", 1.30, 1.07, 1.10, "blocks", "#ff7900"),
    _p("sfr_fr", "FRA", "SFR", "SFR", 1.20, 1.05, 1.07, "burst", "#e5007d"),
    _p("bouygues_fr", "FRA", "Bouygues", "Bouygues", 1.05, 1.03, 1.04, "blocks", "#8dc63f"),
    _p("free_fr", "FRA", "Free", "Free", 1.00, 1.04, 1.06, "waveform", "#ff5f00"),
    # --- Italy -------------------------------------------------------------
    _p("tim_it", "ITA", "TIM", "TIM", 1.30, 1.06, 1.09, "blocks", "#009246"),
    _p("vodafone_it", "ITA", "Vodafone", "Vodafone", 1.20, 1.05, 1.07, "circle", "#e60000"),
    _p("windtre_it", "ITA", "WindTre", "WindTre", 1.10, 1.04, 1.05, "burst", "#ff9800"),
    _p("three_it", "ITA", "3 Italia", "3 Italia", 1.05, 1.03, 1.04, "circle", "#000000"),
    # --- USA ---------------------------------------------------------------
    _p("verizon_us", "USA", "Verizon", "Verizon", 1.25, 1.05, 1.07, "check", "#ee0000"),
    _p("att_us", "USA", "AT&T", "AT&T", 1.25, 1.05, 1.07, "globe", "#0077c8"),
    _p("tmobile_us", "USA", "T-Mobile", "T-Mobile", 1.30, 1.07, 1.10, "dots", "#e20074"),
    _p("boost_us", "USA", "Boost", "Boost", 0.95, 1.01, 1.02, "burst", "#f9d616"),
    _p("cricket_us", "USA", "Cricket", "Cricket", 0.95, 1.01, 1.03, "blocks", "#4cbb17"),
    # --- Japan -------------------------------------------------------------
    _p("docomo_jp", "JPN", "docomo", "ドコモ", 1.30, 1.08, 1.11, "blocks", "#e60012"),
    _p("au_jp", "JPN", "au", "au", 1.20, 1.06, 1.08, "burst", "#ff6600"),
    _p("softbank_jp", "JPN", "SoftBank", "ソフトバンク", 1.20, 1.06, 1.08, "waveform", "#0088ff"),
    _p("rakuten_jp", "JPN", "Rakuten", "楽天モバイル", 1.05, 1.03, 1.05, "blocks", "#bf0000"),
    # --- UAE ---------------------------------------------------------------
    _p("du_ae", "ARE", "du", "دو", 1.30, 1.07, 1.10, "burst", "#ffcc00"),
    _p("etisalat_ae", "ARE", "Etisalat", "اتصالات", 1.15, 1.05, 1.07, "circle", "#a4ce4e"),
    # --- Canada ------------------------------------------------------------
    _p("rogers_ca", "CAN", "Rogers", "Rogers", 1.25, 1.06, 1.08, "blocks", "#c8102e"),
    _p("bell_ca", "CAN", "Bell", "Bell", 1.20, 1.05, 1.07, "globe", "#0057a7"),
    _p("telus_ca", "CAN", "TELUS", "TELUS", 1.15, 1.05, 1.07, "check", "#00a8e1"),
    _p("fido_ca", "CAN", "Fido", "Fido", 1.05, 1.03, 1.04, "burst", "#c8102e"),
    # --- Armenia -----------------------------------------------------------
    _p("beeline_am", "ARM", "Beeline", "Билайн", 1.30, 1.05, 1.08, "waveform", "#fcee13"),
    _p("cellplus_am", "ARM", "CellPlus", "CellPlus", 1.05, 1.02, 1.03, "blocks", "#0033a0"),
    _p("vivacell_am", "ARM", "VivaCell", "VivaCell", 1.05, 1.02, 1.04, "burst", "#ff8200"),
    _p("mobifone_am", "ARM", "Mobifone", "Mobifone", 1.00, 1.01, 1.03, "circle", "#0057a7"),
    # --- Georgia -----------------------------------------------------------
    _p("magti_ge", "GEO", "Magti", "მაგთი", 1.25, 1.05, 1.07, "waveform", "#0057a7"),
    _p("bakcell_ge", "GEO", "Bakcell", "ბაქქელი", 1.15, 1.04, 1.06, "circle", "#fcee13"),
    _p("silabest_ge", "GEO", "Silabest", "Silabest", 1.05, 1.02, 1.03, "waveform", "#e60012"),
    _p("telecom_ge", "GEO", "Georgian Telecom", "ქართული ტელეკომი", 1.00, 1.01, 1.03, "blocks", "#009966"),
    # --- Spain / Portugal / Netherlands / Belgium / Switzerland / Austria ----
    _p("movistar_es", "ESP", "Movistar", "Movistar", 1.25, 1.06, 1.08, "waveform", "#00a1e4"),
    _p("orange_es", "ESP", "Orange", "Orange", 1.15, 1.04, 1.06, "blocks", "#ff7900"),
    _p("vodafone_es", "ESP", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("digimobil_es", "ESP", "DigiMobil", "DigiMobil", 1.00, 1.02, 1.03, "burst", "#00b7c9"),
    _p("nos_pt", "PRT", "NOS", "NOS", 1.25, 1.05, 1.07, "waveform", "#ff0000"),
    _p("vodafone_pt", "PRT", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("orange_pt", "PRT", "Orange", "Orange", 1.15, 1.04, 1.06, "blocks", "#ff7900"),
    _p("kpn_nl", "NLD", "KPN", "KPN", 1.25, 1.05, 1.07, "blocks", "#007bc7"),
    _p("vodafone_nl", "NLD", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("odido_nl", "NLD", "Odido", "Odido", 1.05, 1.03, 1.04, "burst", "#c6007e"),
    _p("proximus_be", "BEL", "Proximus", "Proximus", 1.25, 1.06, 1.08, "burst", "#8dc63f"),
    _p("orange_be", "BEL", "Orange", "Orange", 1.15, 1.04, 1.06, "blocks", "#ff7900"),
    _p("telenet_be", "BEL", "Telenet", "Telenet", 1.10, 1.03, 1.05, "waveform", "#c900a1"),
    _p("swisscom_ch", "CHE", "Swisscom", "Swisscom", 1.25, 1.06, 1.08, "blocks", "#002b7f"),
    _p("sunrise_ch", "CHE", "Sunrise", "Sunrise", 1.10, 1.04, 1.05, "burst", "#ffdc00"),
    _p("salt_ch", "CHE", "Salt", "Salt", 1.00, 1.01, 1.03, "circle", "#ffcc00"),
    _p("a1_at", "AUT", "A1", "A1", 1.25, 1.05, 1.07, "circle", "#e20074"),
    _p("magenta_at", "AUT", "Magenta", "Magenta", 1.15, 1.04, 1.06, "burst", "#7b2d8e"),
    _p("three_at", "AUT", "3", "3", 1.05, 1.02, 1.04, "circle", "#000000"),
    # --- Nordics / Baltics / CEE -------------------------------------------
    _p("telia_se", "SWE", "Telia", "Telia", 1.25, 1.05, 1.07, "waveform", "#f8b400"),
    _p("telenor_se", "SWE", "Telenor", "Telenor", 1.15, 1.04, 1.05, "circle", "#0072ce"),
    _p("tre_se", "SWE", "3", "3", 1.05, 1.02, 1.03, "burst", "#000000"),
    _p("telia_no", "NOR", "Telia", "Telia", 1.25, 1.05, 1.07, "waveform", "#f8b400"),
    _p("telenor_no", "NOR", "Telenor", "Telenor", 1.15, 1.04, 1.05, "circle", "#0072ce"),
    _p("telia_dk", "DNK", "Telia", "Telia", 1.20, 1.05, 1.06, "waveform", "#00a9e0"),
    _p("telenor_dk", "DNK", "Telenor", "Telenor", 1.15, 1.04, 1.05, "circle", "#00a9e0"),
    _p("elisa_fi", "FIN", "Elisa", "Elisa", 1.25, 1.05, 1.07, "globe", "#ff6600"),
    _p("dna_fi", "FIN", "DNA", "DNA", 1.15, 1.04, 1.05, "circle", "#00b4e2"),
    _p("siman_is", "ISL", "Síminn", "Síminn", 1.15, 1.04, 1.05, "circle", "#00b7c9"),
    _p("vodafone_ie", "IRL", "Vodafone", "Vodafone", 1.25, 1.05, 1.07, "circle", "#e60000"),
    _p("eir_ie", "IRL", "eir", "eir", 1.10, 1.03, 1.04, "blocks", "#00a9e0"),
    _p("elisa_ee", "EST", "Elisa", "Elisa", 1.20, 1.05, 1.06, "globe", "#ff6600"),
    _p("tele2_ee", "EST", "Tele2", "Tele2", 1.10, 1.03, 1.04, "circle", "#0033a0"),
    _p("lmt_lv", "LVA", "LMT", "LMT", 1.20, 1.05, 1.06, "waveform", "#e2001a"),
    _p("tele2_lv", "LVA", "Tele2", "Tele2", 1.10, 1.03, 1.04, "circle", "#0033a0"),
    _p("tele2_lt", "LTU", "Tele2", "Tele2", 1.20, 1.05, 1.06, "circle", "#0033a0"),
    _p("bite_lt", "LTU", "Bite", "Bite", 1.10, 1.03, 1.04, "burst", "#ff8200"),
    _p("o2_cz", "CZE", "O2", "O2", 1.20, 1.05, 1.06, "circle", "#0050ff"),
    _p("tmobile_cz", "CZE", "T-Mobile", "T-Mobile", 1.15, 1.04, 1.06, "burst", "#e20074"),
    _p("orange_sk", "SVK", "Orange", "Orange", 1.20, 1.05, 1.06, "blocks", "#ff7900"),
    _p("telekom_sk", "SVK", "Telekom", "Telekom", 1.15, 1.04, 1.06, "blocks", "#e20074"),
    _p("yettel_hu", "HUN", "Yettel", "Yettel", 1.20, 1.05, 1.06, "blocks", "#ffdd00"),
    _p("telekom_hu", "HUN", "Telekom", "Telekom", 1.15, 1.04, 1.06, "waveform", "#0050ff"),
    _p("digi_ro", "ROU", "Digi", "Digi", 1.15, 1.04, 1.05, "blocks", "#ff7900"),
    _p("orange_ro", "ROU", "Orange", "Orange", 1.15, 1.04, 1.06, "circle", "#ff7900"),
    _p("vivacom_bg", "BGR", "Vivacom", "Vivacom", 1.15, 1.04, 1.05, "waveform", "#e2001a"),
    _p("telekom_bg", "BGR", "Telekom", "Telekom", 1.15, 1.04, 1.06, "circle", "#0050ff"),
    _p("cosmote_gr", "GRC", "Cosmote", "Cosmote", 1.25, 1.06, 1.08, "blocks", "#0050ff"),
    _p("vodafone_gr", "GRC", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("nova_gr", "GRC", "nova", "nova", 1.10, 1.03, 1.04, "burst", "#9d0a4a"),
    # --- Americas / rest ---------------------------------------------------
    _p("telcel_mx", "MEX", "Telcel", "Telcel", 1.30, 1.06, 1.08, "circle", "#0a2c8c"),
    _p("movistar_mx", "MEX", "Movistar", "Movistar", 1.15, 1.04, 1.06, "waveform", "#00a1e4"),
    _p("att_mx", "MEX", "AT&T", "AT&T", 1.10, 1.03, 1.04, "globe", "#0077c8"),
    _p("vivo_br", "BRA", "Vivo", "Vivo", 1.30, 1.06, 1.09, "blocks", "#8dc63f"),
    _p("claro_br", "BRA", "Claro", "Claro", 1.20, 1.05, 1.07, "burst", "#ff7900"),
    _p("tim_br", "BRA", "TIM", "TIM", 1.15, 1.04, 1.06, "waveform", "#0b3d91"),
    _p("personal_ar", "ARG", "Personal", "Personal", 1.20, 1.05, 1.06, "burst", "#00539f"),
    _p("claro_ar", "ARG", "Claro", "Claro", 1.15, 1.04, 1.06, "circle", "#d22630"),
    _p("movistar_cl", "CHL", "Movistar", "Movistar", 1.25, 1.06, 1.08, "waveform", "#00539f"),
    _p("entel_cl", "CHL", "Entel", "Entel", 1.05, 1.02, 1.03, "circle", "#8dc63f"),
    _p("claro_co", "COL", "Claro", "Claro", 1.25, 1.05, 1.07, "burst", "#d22630"),
    _p("movistar_co", "COL", "Movistar", "Movistar", 1.20, 1.04, 1.06, "waveform", "#e20074"),
    # --- Asia-Pacific ------------------------------------------------------
    _p("skt_kr", "KOR", "SKT", "SKT", 1.30, 1.07, 1.09, "circle", "#e20074"),
    _p("kt_kr", "KOR", "KT", "KT", 1.25, 1.06, 1.08, "blocks", "#00a651"),
    _p("lgu_kr", "KOR", "LG U+", "LG U+", 1.20, 1.05, 1.07, "burst", "#d71920"),
    _p("chinamobile_cn", "CHN", "China Mobile", "中国移动", 1.30, 1.06, 1.08, "globe", "#0060a5"),
    _p("chinaunicom_cn", "CHN", "China Unicom", "中国联通", 1.20, 1.05, 1.06, "blocks", "#d51f2e"),
    _p("chinatelecom_cn", "CHN", "China Telecom", "中国电信", 1.15, 1.04, 1.06, "circle", "#005bac"),
    _p("airtel_in", "IND", "Airtel", "Airtel", 1.25, 1.06, 1.08, "circle", "#e40000"),
    _p("jio_in", "IND", "Jio", "Jio", 1.30, 1.07, 1.09, "globe", "#0f3cc9"),
    _p("vi_in", "IND", "Vi", "Vi", 1.15, 1.04, 1.06, "burst", "#ff6600"),
    _p("turkcell_tr", "TUR", "Turkcell", "Turkcell", 1.30, 1.06, 1.08, "burst", "#f9d616"),
    _p("turktelekom_tr", "TUR", "Turk Telekom", "Türk Telekom", 1.25, 1.05, 1.07, "circle", "#00c1de"),
    _p("vodafone_tr", "TUR", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("pelago_th", "THA", "AIS", "AIS", 1.25, 1.05, 1.07, "globe", "#7dc31a"),
    _p("dtac_th", "THA", "dtac", "dtac", 1.15, 1.04, 1.06, "burst", "#00a8e1"),
    _p("true_th", "THA", "True", "True", 1.15, 1.04, 1.06, "waveform", "#e40000"),
    _p("singtel_sg", "SGP", "Singtel", "Singtel", 1.30, 1.07, 1.09, "globe", "#ec1c24"),
    _p("starhub_sg", "SGP", "StarHub", "StarHub", 1.15, 1.04, 1.06, "blocks", "#00a1e4"),
    _p("optus_au", "AUS", "Optus", "Optus", 1.25, 1.06, 1.08, "burst", "#00b140"),
    _p("telstra_au", "AUS", "Telstra", "Telstra", 1.30, 1.06, 1.08, "blocks", "#004b8d"),
    _p("vodafone_au", "AUS", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("one_nz", "NZL", "One", "One", 1.20, 1.05, 1.06, "burst", "#7ec141"),
    _p("spark_nz", "NZL", "Spark", "Spark", 1.15, 1.04, 1.05, "circle", "#00a1e4"),
    _p("vodacom_za", "ZAF", "Vodacom", "Vodacom", 1.30, 1.06, 1.08, "circle", "#e60000"),
    _p("mtn_za", "ZAF", "MTN", "MTN", 1.30, 1.06, 1.08, "blocks", "#ffcc00"),
    _p("telkom_za", "ZAF", "Telkom", "Telkom", 1.15, 1.04, 1.05, "waveform", "#007749"),
    # --- Eastern Europe ----------------------------------------------------
    _p("kyivstar_ua", "UKR", "Kyivstar", "Київстар", 1.25, 1.05, 1.07, "circle", "#0072ce"),
    _p("vodafone_ua", "UKR", "Vodafone", "Vodafone", 1.15, 1.04, 1.06, "circle", "#e60000"),
    _p("kyivstar_by", "BLR", "Kyivstar", "Kyivstar", 1.15, 1.04, 1.05, "circle", "#0072ce"),
    _p("life_by", "BLR", "life:)", "life:)", 1.05, 1.02, 1.03, "burst", "#fcee13"),
    # --- Middle East -------------------------------------------------------
    _p("zain_sa", "SAU", "Zain", "زين", 1.25, 1.06, 1.08, "burst", "#0070c0"),
    _p("stc_sa", "SAU", "stc", "STC", 1.25, 1.06, 1.08, "blocks", "#8dc63f"),
    _p("mobily_sa", "SAU", "Mobily", "موبايلي", 1.15, 1.04, 1.06, "globe", "#7c2f87"),
    _p("orange_il", "ISR", "Orange", "Orange", 1.20, 1.05, 1.06, "blocks", "#ff7900"),
    _p("partner_il", "ISR", "Partner", "Partner", 1.15, 1.04, 1.05, "circle", "#ff8200"),
    _p("cellcom_il", "ISR", "Cellcom", "Cellcom", 1.10, 1.03, 1.04, "waveform", "#7b2d8e"),
)

_BY_CODE: dict[str, ProviderDef] = {provider.code: provider for provider in PROVIDERS}

#: Legacy fictional operators from the first SIM line. They stay renderable (an
#: existing card still shows its brand) but are never generated any more.
LEGACY_OPERATOR_CODES: frozenset[str] = frozenset(
    {
        "numa",
        "nova",
        "orbit",
        "volt",
        "pulse",
        "axis",
        "ion",
        "lumen",
        "kite",
    }
)


def _game_provider(country_code: str, index: int) -> ProviderDef:
    """A documented **game** operator for a country with no curated line.

    It is deliberately not styled after any real carrier: the brand is the ISO code
    plus an index, so nothing can be mistaken for a real network and nothing here
    makes a claim about one.
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
    """Keep a provider modifier inside its documented, bounded range."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(MIN_PROVIDER_MODIFIER, min(MAX_PROVIDER_MODIFIER, number))


def provider_by_code(code: str | None) -> ProviderDef | None:
    """Resolve a provider code. Legacy fictional codes resolve to ``None``."""
    if not code:
        return None
    return _BY_CODE.get(str(code).strip().lower())


def providers_for(country_code: str) -> tuple[ProviderDef, ...]:
    """Every active provider a country may print on a collectible SIM card.

    A country whose real line is a single operator (Iceland, for instance) is topped up
    with documented **game** brands, so "collect two different operators" is always a
    reachable goal without inventing a second real carrier.
    """
    code = str(country_code or "").strip().upper()
    line = tuple(
        provider for provider in PROVIDERS if provider.country == code and provider.is_active
    )
    if len(line) >= MIN_PROVIDERS_PER_COUNTRY:
        return line
    if line:
        filler = _game_line(code)
        return line + filler[: MIN_PROVIDERS_PER_COUNTRY - len(line)]
    return _game_line(code)


def curated_countries() -> tuple[str, ...]:
    """Countries that carry a curated real-operator line."""
    return tuple(sorted({provider.country for provider in PROVIDERS}))


__all__ = [
    "LEGACY_OPERATOR_CODES",
    "MAX_PROVIDER_MODIFIER",
    "MIN_PROVIDERS_PER_COUNTRY",
    "MIN_PROVIDER_MODIFIER",
    "PROVIDERS",
    "ProviderDef",
    "clamp_modifier",
    "curated_countries",
    "provider_by_code",
    "providers_for",
]
