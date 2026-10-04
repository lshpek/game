"""Daily missions.

Progress is server-authoritative: the client can only *read* missions. Each
roll (and each social action) reports what happened, and this service decides
whether a mission advanced and pays its reward exactly once per UTC day.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.enums import TransactionType
from app.models.numora import Mission, UserMission
from app.models.user import User
from app.services.economy import EconomyService

# Mission metric -> the event counters that advance it. A mission may listen to
# several events at once (e.g. ``ROLL`` also advances ``rolls``).
EVENT_METRICS: dict[str, tuple[str, ...]] = {
    "ROLL": ("rolls",),
    "FIND_RARE": ("rare_found",),
    "NEW_COUNTRY": ("new_country",),
    "REPEATED_PATTERN": ("repeated_pattern",),
    "FIND_777": ("find_777",),
    "FIND_PALINDROME": ("find_palindrome",),
    "COUNTRY_PLATE": ("country_plate",),
    "DUPLICATE": ("duplicate",),
    "SHARE": ("share",),
    "CHALLENGE": ("challenge",),
}


@dataclass(slots=True)
class MissionOutcome:
    code: str
    name_en: str
    name_ru: str
    progress: int
    target: int
    completed: bool
    reward_coins: int
    reward_rolls: int
    reward_xp: int
    just_completed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name_en": self.name_en,
            "name_ru": self.name_ru,
            "progress": self.progress,
            "target": self.target,
            "completed": self.completed,
            "reward_coins": self.reward_coins,
            "reward_rolls": self.reward_rolls,
            "reward_xp": self.reward_xp,
        }


class MissionService:
    """Evaluates and pays daily missions."""

    def __init__(self, db: Session, economy: EconomyService | None = None) -> None:
        self.db = db
        self.economy = economy or EconomyService(db)

    def definitions(self) -> list[Mission]:
        return list(
            self.db.execute(
                select(Mission)
                .where(Mission.is_active.is_(True))
                .order_by(Mission.sort_order, Mission.id)
            )
            .scalars()
            .all()
        )

    def _row(self, user_id: int, mission: Mission, day) -> UserMission:
        row = self.db.execute(
            select(UserMission).where(
                UserMission.user_id == user_id,
                UserMission.mission_id == mission.id,
                UserMission.mission_date == day,
            )
        ).scalar_one_or_none()
        if row is None:
            row = UserMission(
                user_id=user_id,
                mission_id=mission.id,
                mission_date=day,
                progress=0,
                reward_paid=False,
                created_at=utcnow(),
            )
            self.db.add(row)
            self.db.flush()
        return row

    def progress(self, user_id: int, day=None) -> list[MissionOutcome]:
        """Read today's mission board (creating empty rows on first view)."""
        day = day or utcnow().date()
        results: list[MissionOutcome] = []
        for mission in self.definitions():
            row = self._row(user_id, mission, day)
            results.append(
                MissionOutcome(
                    code=mission.code,
                    name_en=mission.name_en,
                    name_ru=mission.name_ru,
                    progress=int(row.progress),
                    target=int(mission.target),
                    completed=row.completed_at is not None,
                    reward_coins=int(mission.reward_coins),
                    reward_rolls=int(mission.reward_rolls),
                    reward_xp=int(mission.reward_xp),
                )
            )
        self.db.flush()
        return results

    def record(self, user: User, events: dict[str, int], *, day=None) -> list[MissionOutcome]:
        """Advance every mission matching ``events`` and pay completed rewards."""
        day = day or utcnow().date()
        completed: list[MissionOutcome] = []

        for mission in self.definitions():
            delta = 0
            for metric in EVENT_METRICS.get(mission.metric, ()):
                delta += int(events.get(metric, 0))
            if delta <= 0:
                continue

            row = self._row(user.id, mission, day)
            if row.completed_at is not None:
                continue

            row.progress = min(int(mission.target), int(row.progress) + delta)
            if row.progress >= int(mission.target):
                row.completed_at = utcnow()
                outcome = self._pay(user, mission, row)
                completed.append(outcome)

        self.db.flush()
        return completed

    def _pay(self, user: User, mission: Mission, row: UserMission) -> MissionOutcome:
        """Pay a mission reward exactly once (guarded by ``reward_paid``)."""
        if not row.reward_paid:
            row.reward_paid = True

            if mission.reward_coins:
                self.economy.credit(
                    user.id,
                    int(mission.reward_coins),
                    TransactionType.MISSION_REWARD,
                    reference_type="mission",
                    reference_id=mission.code,
                    idempotency_key=(
                        f"mission:{user.id}:{row.mission_date.isoformat()}:{mission.code}"
                    ),
                )
            if mission.reward_rolls:
                user.bonus_rolls = int(user.bonus_rolls) + int(mission.reward_rolls)
            if mission.reward_xp:
                from app.services.progression import ProgressionService

                ProgressionService(self.db).add_xp(user, int(mission.reward_xp))
            self.db.flush()

        return MissionOutcome(
            code=mission.code,
            name_en=mission.name_en,
            name_ru=mission.name_ru,
            progress=int(row.progress),
            target=int(mission.target),
            completed=True,
            reward_coins=int(mission.reward_coins),
            reward_rolls=int(mission.reward_rolls),
            reward_xp=int(mission.reward_xp),
            just_completed=True,
        )

    def serialize(self, outcomes: list[MissionOutcome]) -> list[dict[str, object]]:
        return [item.to_dict() for item in outcomes]

    # --- admin overrides -------------------------------------------------
    # Used by the internal tooling only. They reuse ``_pay`` so a mission reward
    # can never be paid twice, no matter how often a mission is completed.

    def _outcome(self, mission: Mission, row: UserMission) -> MissionOutcome:
        return MissionOutcome(
            code=mission.code,
            name_en=mission.name_en,
            name_ru=mission.name_ru,
            progress=int(row.progress),
            target=int(mission.target),
            completed=row.completed_at is not None,
            reward_coins=int(mission.reward_coins),
            reward_rolls=int(mission.reward_rolls),
            reward_xp=int(mission.reward_xp),
        )

    def find(self, code: str) -> Mission:
        """Resolve a mission by code, case-insensitively (codes ship lower-case)."""
        wanted = str(code).strip()
        mission = self.db.execute(
            select(Mission).where(func.upper(Mission.code) == wanted.upper())
        ).scalar_one_or_none()
        if mission is None:
            from app.core.errors import NotFoundError

            raise NotFoundError("Mission not found.", code="MISSION_NOT_FOUND")
        return mission

    def add_progress(self, user: User, code: str, delta: int, *, day=None) -> MissionOutcome:
        """Advance one mission without paying until the target is reached."""
        mission = self.find(code)
        row = self._row(user.id, mission, day or utcnow().date())
        row.progress = min(int(mission.target), int(row.progress) + max(0, int(delta)))
        paid_now = False
        if row.progress >= int(mission.target) and row.completed_at is None:
            row.completed_at = utcnow()
            paid_now = not bool(row.reward_paid)
            self._pay(user, mission, row)
        self.db.flush()
        outcome = self._outcome(mission, row)
        outcome.just_completed = paid_now
        return outcome

    def complete(self, user: User, code: str, *, day=None) -> MissionOutcome:
        """Force a mission to its target and pay its reward exactly once."""
        mission = self.find(code)
        row = self._row(user.id, mission, day or utcnow().date())
        row.progress = int(mission.target)
        paid_now = False
        if row.completed_at is None:
            row.completed_at = utcnow()
            paid_now = not bool(row.reward_paid)
            self._pay(user, mission, row)
        self.db.flush()
        outcome = self._outcome(mission, row)
        outcome.just_completed = paid_now
        return outcome

    def reset(self, user: User, code: str, *, day=None) -> MissionOutcome:
        """Clear today's progress for one mission."""
        mission = self.find(code)
        row = self._row(user.id, mission, day or utcnow().date())
        row.progress = 0
        row.completed_at = None
        row.reward_paid = False
        self.db.flush()
        return self._outcome(mission, row)

    def board(self, user: User, *, day=None) -> list[MissionOutcome]:
        """Today's board with the raw ``reward_paid`` flag preserved."""
        day = day or utcnow().date()
        results: list[MissionOutcome] = []
        for mission in self.definitions():
            row = self._row(user.id, mission, day)
            outcome = self._outcome(mission, row)
            results.append(outcome)
        self.db.flush()
        return results

    def reward_paid_flags(self, user_id: int, *, day=None) -> dict[str, bool]:
        """``{mission_code: reward_paid}`` for today's board."""
        day = day or utcnow().date()
        rows = self.db.execute(
            select(Mission.code, UserMission.reward_paid)
            .join(UserMission, UserMission.mission_id == Mission.id)
            .where(UserMission.user_id == user_id, UserMission.mission_date == day)
        ).all()
        return {str(code): bool(paid) for code, paid in rows}


__all__ = ["EVENT_METRICS", "MissionOutcome", "MissionService"]