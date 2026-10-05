"""Plate serialisation shared by every endpoint.

One canonical shape, used by the roll result, the collection grid, the garage
hero, the share card and the challenge view. Presenting a plate identically
everywhere is what keeps the frontend free of business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.timeutils import as_aware
from app.game.collectibles import CollectibleKind, kind_for_plate_type
from app.game.plate_formats import serialize_visual
from app.game.plate_generator import derive_segment_gaps, segment_kinds
from app.game.plate_rarity import RARITY_COLOR
from app.game.plate_status import collector_bio
from app.game.plate_traits import trait_labels
from app.game.sim_cards import legacy_operator_label

if TYPE_CHECKING:  # pragma: no cover
    from app.models.plates import Plate, UserPlate


def sim_details(plate: "Plate") -> dict[str, object] | None:
    """Kind-specific payload, or ``None`` for a vehicle plate.

    Only the fields the SIM card actually prints are exposed; nothing else from
    ``plates.details`` leaks into the API.

    The provider block carries the brand a country's real operators print, plus its two
    **game** modifiers so the client can explain why a card is worth more without ever
    implying a real-world tariff, market or financial claim. ``synthetic`` is always
    ``True``: no card in the game carries a real subscriber number.
    """
    if kind_for_plate_type(plate.plate_type) is not CollectibleKind.SIM_CARD:
        return None
    details = plate.details or {}
    brand = str(details.get("operator") or "")
    if not brand:
        # A card written before the provider catalogue existed (or one whose brand was
        # retired) must still render: fall back to the stored code, never to nothing.
        brand = legacy_operator_label(str(details.get("operator_code") or ""))
    return {
        "operator_code": str(details.get("operator_code") or ""),
        "operator": brand,
        "operator_local": str(details.get("operator_local") or brand),
        # ``False`` marks a documented game brand, so the UI can be honest about it.
        "operator_is_real": bool(details.get("operator_is_real", False)),
        "operator_visual": str(details.get("operator_visual") or "neutral"),
        "operator_accent": str(details.get("operator_accent") or "#c9a227"),
        "rarity_modifier": float(details.get("rarity_modifier") or 1.0),
        "value_modifier": float(details.get("value_modifier") or 1.0),
        "series": str(details.get("series") or ""),
        "edition": str(details.get("edition") or ""),
        # The number the backend generated and printed on the card. The client
        # renders it; it never composes one.
        "synthetic_number": str(details.get("synthetic_number") or plate.plate_text),
        "calling_code": str(details.get("calling_code") or ""),
        "synthetic": True,
    }


def first_discoverer(plate: "Plate", db=None) -> dict[str, object] | None:
    """Safe public identity of the first discoverer.

    Only the username or display name is exposed - never the Telegram id.
    """
    user_id = plate.first_discovered_by_id
    if not user_id or db is None:
        return None
    from app.models.user import User as UserModel

    user = db.get(UserModel, user_id)
    if user is None:
        return None
    return {
        "display_name": user.display_name,
        "username": user.username,
        "photo_url": user.photo_url,
    }


def plate_card(
    plate: "Plate",
    *,
    user_plate: "UserPlate | None" = None,
    owned: bool | None = None,
    db=None,
) -> dict[str, object]:
    """Canonical collectible payload.

    ``collector_value`` is an explicitly *estimated in-game* value in the
    country's display currency; ``dealer_value`` is the NUMORA amount the DEALER
    pays. Neither is real money.
    """
    country = plate.country
    region = plate.region
    traits = list(plate.traits or [])
    kind = kind_for_plate_type(plate.plate_type)

    return {
        "id": plate.id,
        "plate_text": plate.plate_text,
        "normalized_text": plate.normalized_text,
        "display_segments": list(plate.display_segments or []),
        # Whether a space precedes each group. Reconstructing the printed text from
        # segments + gaps is byte-identical to ``plate_text``, which is what keeps the
        # displayed, stored, searched and shared strings the same value.
        "display_segment_gaps": derive_segment_gaps(
            plate.plate_text, list(plate.display_segments or [])
        ),
        # Per-group classification so the renderer can set digits, letters and a
        # separate region block the way the country actually prints them.
        "display_segment_kinds": segment_kinds(
            list(plate.display_segments or []), plate.region_code
        ),
        "letters": list(plate.letter_parts or []),
        "numbers": list(plate.numeric_parts or []),
        "plate_type": plate.plate_type,
        # The collectible kind. The frontend selects on ``kind`` for every object and
        # never branches on ``plate_type``; ``plate_type`` stays for existing
        # consumers and for the admin panel.
        "kind": kind.value,
        "rarity": plate.rarity,
        "rarity_score": int(plate.rarity_score),
        "rarity_color": RARITY_COLOR.get(plate.rarity, RARITY_COLOR["COMMON"]),
        "reasons": traits[:4],
        "reason_labels": trait_labels(traits[:4]),
        "traits": traits,
        "tags": list(plate.tags or []),
        "story": plate.story or "",
        "collector_bio": collector_bio(
            rarity=plate.rarity,
            kind=kind.value,
            country_code=plate.country_code,
            letter_groups=list(plate.letter_parts or []),
            traits=traits,
            region_code=plate.region.code if plate.region else None,
            region_name_en=plate.region.name_en if plate.region else "",
            region_name_ru=plate.region.name_ru if plate.region else "",
        ),
        "is_secret": bool(plate.is_secret),
        "season_code": plate.season_code,
        "discovery_count": int(plate.discovery_count),
        "first_discovered_at": (
            as_aware(plate.first_discovered_at).isoformat() if plate.first_discovered_at else None
        ),
        "first_discoverer": first_discoverer(plate, db),
        # Fictional, country-local presentation value.
        "collector_value": int(plate.collector_value),
        "currency_code": plate.currency_code,
        "currency_symbol": plate.currency_symbol,
        # Authoritative game-economy value in NUMORA.
        "dealer_value": int(plate.dealer_value),
        "country": {
            "code": country.code if country else "",
            "iso_alpha2": (country.iso_alpha2 or "") if country else "",
            "name_en": country.name_en if country else "",
            "name_ru": country.name_ru if country else "",
            "flag": country.flag if country else "",
        },
        "reel_alphabets": {
            "letters": str((country.config or {}).get("alphabet") or "ABCDEFGHIJKLMNOPQRSTUVWXYZ") if country else "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "digits": "0123456789",
        },
        "region": (
            {"code": region.code, "name_en": region.name_en, "name_ru": region.name_ru}
            if region
            else None
        ),
        "template": {
            "code": plate.template.code if plate.template else "",
            "pattern": plate.template.pattern if plate.template else "",
        },
        # The physical format, plus the country's own identity: its two-letter code goes
        # into the band and its accent colour travels with the recipe, so two countries on
        # one standard never render as the same picture.
        "visual": serialize_visual(
            (country.config or {}).get("visual", "eu_long") if country else "eu_long",
            alpha2=(country.iso_alpha2 or "") if country else "",
            alpha3=country.code if country else "",
            country_code=country.code if country else "",
        ),
        # Present for SIM cards (operator, series, edition, printed number); ``None``
        # for a vehicle plate, so the client can branch on the payload it receives
        # rather than on guesswork.
        "details": sim_details(plate),
        "owned": bool(user_plate is not None) if owned is None else owned,
        "duplicate_count": int(user_plate.duplicate_count) if user_plate is not None else 0,
        "is_favorite": bool(user_plate.is_favorite) if user_plate is not None else False,
        "is_new": bool(user_plate.is_new) if user_plate is not None else False,
        "acquired_at": (
            as_aware(user_plate.first_acquired_at).isoformat()
            if user_plate is not None and user_plate.first_acquired_at
            else None
        ),
    }


__all__ = ["first_discoverer", "plate_card", "sim_details"]
