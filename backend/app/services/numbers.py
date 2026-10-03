"""Number catalogue and ownership operations."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.game.analyzer import NumberAnalysis, analyze, normalize_number
from app.game.story import build_story
from app.game.valuation import compute_value
from app.models.number import Discovery, Number, UserNumber
from app.models.user import User


@dataclass(slots=True)
class GrantResult:
    """Outcome of granting a number to a player."""

    user_number: UserNumber
    number: Number
    is_duplicate: bool
    is_first_discovery: bool
    value: int


class NumberService:
    """Creates catalogue entries lazily and tracks ownership."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- catalogue ------------------------------------------------------
    def get_by_value(self, raw: str | int) -> Number | None:
        value = normalize_number(raw)
        return self.db.execute(select(Number).where(Number.value_str == value)).scalar_one_or_none()

    def get_or_create(self, raw: str | int) -> tuple[Number, bool]:
        """Return the catalogue row, creating it on first discovery.

        Returns ``(number, created)``. Uses a savepoint so a concurrent insert
        of the same number simply re-reads the winner's row.
        """
        value = normalize_number(raw)
        existing = self.get_by_value(value)
        if existing is not None:
            return existing, False

        analysis = analyze(value)
        number = Number(
            value_str=value,
            value_int=analysis.value,
            rarity=analysis.rarity.value,
            base_value=compute_value(analysis.rarity, analysis.traits, value, discovery_count=0),
            traits=list(analysis.traits),
            tags=list(analysis.tags),
            story=build_story(analysis),
            is_special=analysis.is_special,
            discovery_count=0,
            first_discovered_by_id=None,
            first_discovered_at=None,
        )
        try:
            with self.db.begin_nested():
                self.db.add(number)
                self.db.flush()
        except IntegrityError:
            return self.get_by_value(value), False  # type: ignore[return-value]
        return number, True

    def current_value(self, number: Number) -> int:
        """Live value - recomputed because discovery count changes over time."""
        return compute_value(number.rarity, list(number.traits or []), number.value_str, number.discovery_count)

    def analysis_for(self, number: Number) -> NumberAnalysis:
        return analyze(number.value_str)

    # --- ownership ------------------------------------------------------
    def record_discovery(self, number: Number, user_id: int, *, source: str) -> bool:
        """Register a find and return ``True`` when it is the world-first one."""
        is_first = number.first_discovered_by_id is None
        number.discovery_count = int(number.discovery_count) + 1
        if is_first:
            number.first_discovered_by_id = user_id
            number.first_discovered_at = utcnow()

        self.db.add(
            Discovery(
                number_id=number.id,
                user_id=user_id,
                is_first_discovery=is_first,
                source=source,
                created_at=utcnow(),
            )
        )
        self.db.flush()
        return is_first

    def get_user_number(self, user_id: int, number_id: int) -> UserNumber | None:
        return self.db.execute(
            select(UserNumber).where(UserNumber.user_id == user_id, UserNumber.number_id == number_id)
        ).scalar_one_or_none()

    def grant(self, user: User, number: Number, *, value: int | None = None) -> GrantResult:
        """Give a number to the player, handling duplicates."""
        now = utcnow()
        awarded_value = value if value is not None else self.current_value(number)
        user_number = self.get_user_number(user.id, number.id)

        if user_number is not None:
            user_number.duplicate_count = int(user_number.duplicate_count) + 1
            user_number.last_acquired_at = now
            self.db.flush()
            return GrantResult(user_number, number, True, False, awarded_value)

        user_number = UserNumber(
            user_id=user.id,
            number_id=number.id,
            duplicate_count=0,
            coins_earned=0,
            first_acquired_at=now,
            last_acquired_at=now,
        )
        self.db.add(user_number)
        user.unique_numbers_count = int(user.unique_numbers_count) + 1
        self.db.flush()
        return GrantResult(user_number, number, False, False, awarded_value)

    def add_coins_earned(self, user_number: UserNumber, amount: int) -> None:
        user_number.coins_earned = int(user_number.coins_earned) + int(amount)
        self.db.flush()
