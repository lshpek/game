"""ORM -> response model helpers shared by routers."""

from __future__ import annotations

from app.core.timeutils import as_aware
from app.game.valuation import compute_value
from app.models.number import Number, UserNumber


def number_card(
    number: Number,
    *,
    value: int | None = None,
    user_number: UserNumber | None = None,
    discovery_count: int | None = None,
    owned: bool | None = None,
) -> dict[str, object]:
    """Build the canonical number payload used by every screen."""
    discoveries = int(number.discovery_count) if discovery_count is None else int(discovery_count)
    computed = (
        compute_value(number.rarity, list(number.traits or []), number.value_str, discoveries)
        if value is None
        else int(value)
    )
    acquired_at = None
    if user_number is not None and user_number.first_acquired_at is not None:
        acquired_at = as_aware(user_number.first_acquired_at).isoformat()

    return {
        "number": number.value_str,
        "rarity": number.rarity,
        "value": computed,
        "traits": list(number.traits or []),
        "tags": list(number.tags or []),
        "story": number.story or "",
        "is_special": bool(number.is_special),
        "discovery_count": discoveries,
        "duplicate_count": int(user_number.duplicate_count) if user_number is not None else 0,
        "owned": bool(user_number is not None) if owned is None else owned,
        "acquired_at": acquired_at,
        "first_discovered_at": (
            as_aware(number.first_discovered_at).isoformat() if number.first_discovered_at else None
        ),
        "undiscovered": False,
    }


def maybe_card(number: Number | None, **kwargs: object) -> dict[str, object] | None:
    return number_card(number, **kwargs) if number is not None else None  # type: ignore[arg-type]
