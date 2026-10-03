"""Season catalogue."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeasonDefinition:
    """A timed content season with its own special numbers and rewards."""

    code: str
    name: str
    description: str
    special_numbers: tuple[str, ...]
    rewards: dict[str, object]
    duration_days: int = 90
    sort_order: int = 0


SEASON_DEFINITIONS: tuple[SeasonDefinition, ...] = (
    SeasonDefinition(
        code="season-1-internet",
        name="Season 1 - Internet",
        description="A tribute to the numbers that built the web.",
        special_numbers=("1337", "0404", "0500", "0200", "0301", "8008", "0420"),
        rewards={"badge": "season1", "bonus_coins": 5000},
        duration_days=90,
        sort_order=1,
    ),
    SeasonDefinition(
        code="season-2-time",
        name="Season 2 - Time",
        description="Years, clocks and everything that counts down.",
        special_numbers=("2024", "1999", "2000", "1970", "0060", "1024"),
        rewards={"badge": "season2", "bonus_coins": 5000},
        duration_days=90,
        sort_order=2,
    ),
)


def season_by_code(code: str) -> SeasonDefinition | None:
    return next((item for item in SEASON_DEFINITIONS if item.code == code), None)
