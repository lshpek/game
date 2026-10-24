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
    """Kind-specific payload, or ``None`` for a vehicle plate."""
    if kind_for_plate_type(plate.plate_type) is not CollectibleKind.SIM_CARD:
        return None
    details = plate.details or {}
    brand = str(details.get("operator") or "")
    if not brand:
        brand = legacy_operator_label(str(details.get("operator_code") or ""))
    return {
        "operator_code": str(details.get("operator_code") or ""),
        "operator": brand,
        "operator_local": str(details.get("operator_local") or brand),
        "operator_is_real": bool(details.get("operator_is_real", False)),
        "operator_visual": str(details.get("operator_visual") or "neutral"),
        "operator_accent": str(details.get("operator_accent") or "#c9a227"),
        "rarity_modifier": float(details.get("rarity_modifier") or 1.0),
        "value_modifier": float(details.get("value_modifier") or 1.0),
        "series": str(details.get("series") or ""),
        "edition": str(details.get("edition") or ""),
        "synthetic_number": str(details.get("synthetic_number") or plate.plate_text),
        "calling_code": str(details.get("calling_code") or ""),
        "synthetic": True,
    }


def first_discoverer(plate: "Plate", db=None) -> dict[str, object] | None:
    """Safe public identity of the first discoverer."""
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
    """Canonical collectible payload."""
    country = plate.country
    region = plate.region
    traits = list(plate.traits or [])
    kind = kind_for_plate_type(plate.plate_type)

    return {
        "id": plate.id,
        "plate_text": plate.plate_text,
        "normalized_text": plate.normalized_text,
        "display_segments": list(plate.display_segments or []),
        "display_segment_gaps": derive_segment_gaps(
            plate.plate_text, list(plate.display_segments or [])
        ),
        "display_segment_kinds": segment_kinds(
            list(plate.display_segments or []), plate.region_code
        ),
        "letters": list(plate.letter_parts or []),
        "numbers": list(plate.numeric_parts or []),
        "plate_type": plate.plate_type,
        "kind": kind.value,
        "rarity": plate.rarity,
        "rarity_score": int(plate.rarity_score),
        "rarity_color": RARITY_COLOR.get(plate.rarity, RARITY_COLOR["COMMON"]),
        "reasons": traits[:4],
        "reason_labels": trait_labels(traits[:4]),
        "traits": traits,
        "tags": list(plate.tags or []),
        "story": plate.story or "",
        "story_ru": plate.story_ru or plate.story or "",
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
        "collector_value": int(plate.collector_value),
        "currency_code": plate.currency_code,
        "currency_symbol": plate.currency_symbol,
        "dealer_value": int(plate.dealer_value),
        "country": {
            "code": country.code if country else "",
            "iso_alpha2": (country.iso_alpha2 or "") if country else "",
            "name_en": country.name_en if country else "",
            "name_ru": country.name_ru if country else "",
            "flag": country.flag if country else "",
        },
        "reel_alphabets": {
            "letters": str((country.config or {}).get("alphabet") or "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            if country
            else "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
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
        "visual": serialize_visual(
            (country.config or {}).get("visual", "eu_long") if country else "eu_long",
            alpha2=(country.iso_alpha2 or "") if country else "",
            alpha3=country.code if country else "",
            country_code=country.code if country else "",
        ),
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
