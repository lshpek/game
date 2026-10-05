"""The two collectible kinds NUMORA ships.

``VEHICLE_PLATE``
    A physical vehicle registration plate - the flagship object.

``SIM_CARD``
    A physical SIM card carrying a **synthetic** number printed on it. The number is
    information on the card, never an independent collectible: there is no
    ``PHONE_NUMBER`` kind, and nothing here resolves, validates or reverse-looks-up a
    number. See :mod:`app.game.sim_cards` for the safety contract.

Why the kinds are a *data* axis
-------------------------------
:class:`~app.game.countries.TemplateDef` already carries ``plate_type`` and
:class:`~app.models.plates.Plate` already stores it, with a *country-scoped* unique
constraint on the normalised value. The kind is therefore configuration, not schema:
adding a kind means adding templates, and the whole roll pipeline, ownership,
duplicates, first discovery, albums, missions, leaderboards and the ledger keep
working untouched.

Server authority: the kind of a roll is decided here, on the server, from the
eligible template pool. The client sends a *filter* (kind / country) and never a
result.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import ValidationError
from app.game import sim_cards
from app.game.countries import TemplateDef, is_playable


class CollectibleKind(StrEnum):
    """The kinds of object a player can hunt. Exactly two, by design."""

    VEHICLE_PLATE = "VEHICLE_PLATE"
    SIM_CARD = "SIM_CARD"


#: Alias kept so existing imports and admin screens keep reading naturally.
CollectibleCategory = CollectibleKind

#: ``Plate.plate_type`` values stored per kind. Vehicle plates keep the historical
#: values (``STANDARD``, ``COMMERCIAL``, ``MOTORCYCLE`` ...), so the kind is resolved
#: from a *set* rather than a single string.
SIM_PLATE_TYPE = "SIM"

#: Plate types that identify a SIM card.
SIM_PLATE_TYPES: frozenset[str] = frozenset({SIM_PLATE_TYPE})

#: Every plate type that is a physical vehicle plate. Anything unknown falls back here
#: so a historic row can never break a roll or a collection page.
VEHICLE_PLATE_TYPES: frozenset[str] = frozenset(
    {
        "",
        "STANDARD",
        "VEHICLE",
        "COMMERCIAL",
        "MOTORCYCLE",
        "SPECIAL",
        "HISTORICAL",
        "GOVERNMENT_STYLE",
        "DIPLOMATIC_STYLE",
    }
)

#: Stored ``plate_type`` for new vehicle templates.
DEFAULT_VEHICLE_PLATE_TYPE = "STANDARD"

#: Total weight the SIM card pool contributes *per country*.
#:
#: A country generates many SIM templates (operators x printed groupings x editions),
#: so a per-template factor would make the pool size - not this constant - decide how
#: often a card appears, and SIMs would quietly become the common case. Normalising the
#: *total* keeps SIM cards a rarity: against a ~7.5-weight vehicle pool that is roughly
#: one roll in seven.
SIM_POOL_WEIGHT = 1.2

#: Accepted client aliases, lower-cased.
_ALIASES: dict[str, CollectibleKind] = {
    "PLATE": CollectibleKind.VEHICLE_PLATE,
    "PLATES": CollectibleKind.VEHICLE_PLATE,
    "VEHICLE": CollectibleKind.VEHICLE_PLATE,
    "VEHICLE_PLATE": CollectibleKind.VEHICLE_PLATE,
    "SIM": CollectibleKind.SIM_CARD,
    "SIMS": CollectibleKind.SIM_CARD,
    "SIM_CARD": CollectibleKind.SIM_CARD,
    "SIM_CARDS": CollectibleKind.SIM_CARD,
}

#: Values that mean "do not filter".
_NO_FILTER = frozenset({"", "ALL", "WORLD", "ANY"})

KINDS: tuple[CollectibleKind, ...] = (
    CollectibleKind.VEHICLE_PLATE,
    CollectibleKind.SIM_CARD,
)


def kind_for_plate_type(plate_type: str | None) -> CollectibleKind:
    """Map a stored ``plate_type`` onto a kind, defaulting to a vehicle plate.

    Rows written before the SIM line existed carry ``PHONE``; migration 0005 folds
    them into SIM cards. Until that runs, such a row is still a physical card with a
    synthetic number on it, so it resolves to ``SIM_CARD`` here rather than being
    shown as a third kind.
    """
    if not plate_type:
        return CollectibleKind.VEHICLE_PLATE
    value = str(plate_type).upper()
    if value in SIM_PLATE_TYPES or value == "PHONE":
        return CollectibleKind.SIM_CARD
    return CollectibleKind.VEHICLE_PLATE


#: Historical alias.
category_for_plate_type = kind_for_plate_type


def matches_kind(plate_type: str | None, kind: CollectibleKind) -> bool:
    """Whether a stored ``plate_type`` belongs to ``kind``."""
    return kind_for_plate_type(plate_type) is kind


def plate_types_for(kind: CollectibleKind) -> frozenset[str]:
    """The stored ``plate_type`` values a kind owns."""
    return SIM_PLATE_TYPES if kind is CollectibleKind.SIM_CARD else VEHICLE_PLATE_TYPES


def normalize_kind(value: str | None) -> CollectibleKind | None:
    """Accept a kind from a client filter. ``None`` means "reject"."""
    if value is None:
        return None
    return _ALIASES.get(str(value).strip().upper())


# ---------------------------------------------------------------------------
# SIM_CARDS
# ---------------------------------------------------------------------------
def sim_templates(country_code: str) -> tuple[TemplateDef, ...]:
    """Collectible SIM templates for one *playable* country.

    One template per provider, printed grouping and edition. The pattern carries the
    country's synthetic number grouping, so the *printed number is generated by the
    engine* and the frontend never invents it; the provider, its two game modifiers, the
    series and the edition travel in the template config and land in ``plates.details``.

    A locked country yields nothing: that is what makes "coming soon" mean the roll
    cannot produce it, rather than the UI merely hiding it.
    """
    if not is_playable(country_code):
        return ()

    providers = sim_cards.operators_for(country_code)
    patterns = sim_cards.sim_patterns(country_code)
    # Weight is normalised across the whole pool, so a country with more providers or
    # editions is not silently more likely to produce a card. The provider's own weight
    # is what makes a big brand more common, exactly like the real market looks.
    unit = SIM_POOL_WEIGHT / (len(providers) * len(patterns) * _edition_weight_total())

    templates: list[TemplateDef] = []
    for provider in providers:
        for index, pattern in enumerate(patterns):
            for edition, weight, floor in sim_cards.EDITIONS:
                templates.append(
                    TemplateDef(
                        code=(
                            f"{str(country_code).lower()}_sim_{provider.code}_"
                            f"{edition.lower()}_{index + 1}"
                        ),
                        pattern=pattern,
                        weight=weight * provider.weight * unit,
                        plate_type=SIM_PLATE_TYPE,
                        rarity_floor=floor,
                        config={
                            "kind": CollectibleKind.SIM_CARD.value,
                            sim_cards.SYNTHETIC_FLAG: True,
                            "operator_code": provider.code,
                            "provider_code": provider.code,
                            "provider_brand": provider.brand,
                            "provider_is_real": provider.real_brand,
                            "provider_visual": provider.visual,
                            "provider_accent": provider.accent,
                            # Game balance only - never a real-world claim.
                            "provider_rarity_modifier": provider.rarity_modifier,
                            "provider_value_modifier": provider.value_modifier,
                            "edition": edition,
                        },
                    )
                )
    return tuple(templates)


def _edition_weight_total() -> float:
    """Sum of the edition weights, so a normalised pool is template-count agnostic."""
    return sum(weight for _edition, weight, _floor in sim_cards.EDITIONS) or 1.0


def templates_for_kind(country_code: str, kind: CollectibleKind) -> tuple[TemplateDef, ...]:
    """Templates a country contributes to one kind."""
    if kind is CollectibleKind.SIM_CARD:
        return sim_templates(country_code)
    return ()


def parse_hunt_filter(
    *,
    category: str | None = None,
    country_code: str | None = None,
) -> dict[str, object]:
    """Validate a client's hunt filter.

    Only a *filter* is accepted. A malformed value is rejected loudly rather than
    quietly ignored, because a silent fallback would leave the player hunting for
    plates while the UI shows something else - the kind of mismatch that reads as a
    bug and destroys trust in the fairness of a roll.
    """
    parsed = normalize_kind(category)
    if category is not None and parsed is None and str(category).strip().upper() not in _NO_FILTER:
        raise ValidationError(
            f"Unknown collectible kind: {category!r}. "
            f"Use one of {', '.join(item.value for item in KINDS)}.",
            code="BAD_CATEGORY",
        )

    country = str(country_code or "").strip().upper()
    if country and len(country) > 8:
        raise ValidationError(
            "Country must be an ISO 3166-1 alpha-3 or alpha-2 code such as RUS.",
            code="BAD_COUNTRY",
        )

    return {
        "category": parsed,
        "country_code": country or None,
    }


__all__ = [
    "DEFAULT_VEHICLE_PLATE_TYPE",
    "KINDS",
    "SIM_PLATE_TYPE",
    "SIM_PLATE_TYPES",
    "VEHICLE_PLATE_TYPES",
    "CollectibleCategory",
    "CollectibleKind",
    "category_for_plate_type",
    "kind_for_plate_type",
    "matches_kind",
    "normalize_kind",
    "parse_hunt_filter",
    "plate_types_for",
    "sim_templates",
    "templates_for_kind",
]
