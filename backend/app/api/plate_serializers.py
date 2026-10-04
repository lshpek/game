"""Plate serialisation shared by every endpoint.

One canonical shape, used by the roll result, the collection grid, the garage
hero, the share card and the challenge view. Presenting a plate identically
everywhere is what keeps the frontend free of business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.timeutils import as_aware
from app.game.plate_rarity import RARITY_COLOR
from app.game.plate_traits import trait_labels
from app.game.plate_visuals import serialize_visual

if TYPE_CHECKING:  # pragma: no cover
    from app.models.plates import Plate, UserPlate


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
    """Canonical plate payload.

    ``collector_value`` is an explicitly *estimated in-game* value in the
    country's display currency; ``dealer_value`` is the NUMORA amount the DEALER
    pays. Neither is real money.
    """
    country = plate.country
    region = plate.region
    traits = list(plate.traits or [])

    return {
        "id": plate.id,
        "plate_text": plate.plate_text,
        "normalized_text": plate.normalized_text,
        "display_segments": list(plate.display_segments or []),
        "letters": list(plate.letter_parts or []),
        "numbers": list(plate.numeric_parts or []),
        "plate_type": plate.plate_type,
        "rarity": plate.rarity,
        "rarity_score": int(plate.rarity_score),
        "rarity_color": RARITY_COLOR.get(plate.rarity, RARITY_COLOR["COMMON"]),
        "reasons": traits[:4],
        "reason_labels": trait_labels(traits[:4]),
        "traits": traits,
        "tags": list(plate.tags or []),
        "story": plate.story or "",
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
            "name_en": country.name_en if country else "",
            "name_ru": country.name_ru if country else "",
            "flag": country.flag if country else "",
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
            (country.config or {}).get("visual", "european") if country else "european"
        ),
        "owned": bool(user_plate is not None) if owned is None else owned,
        "duplicate_count": int(user_plate.duplicate_count) if user_plate is not None else 0,
        "is_favorite": bool(user_plate.is_favorite) if user_plate is not None else False,
        "is_new": bool(user_plate.is_new) if user_plate is not None else False,
        "acquired_at": (
            as_aware(user_plate.first_acquired_at).isoformat()
            if user_plate is not None and user_plate.first_acquired_at
            else None
        ),
        # Compatibility alias for the legacy ``number`` field.
        "number": plate.plate_text,
    }


__all__ = ["first_discoverer", "plate_card"]