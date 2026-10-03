"""Friend challenges.

A challenge is always compared on server-stored values: the client can only
supply a challenge code, never a number, rarity or value.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.locks import user_lock
from app.core.timeutils import as_aware, utcnow
from app.game.rarity import rarity_rank
from app.models.enums import AnalyticsEventName, ChallengeStatus
from app.models.number import Number, UserNumber
from app.models.social import Challenge
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.services.numbers import NumberService

CHALLENGE_CODE_BYTES = 6
CHALLENGE_TTL_DAYS = 7


class ChallengeService:
    """Creates, resolves and expires challenges."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.numbers = NumberService(db)
        self.analytics = AnalyticsService(db)

    # --- helpers --------------------------------------------------------
    @staticmethod
    def generate_code() -> str:
        return secrets.token_urlsafe(CHALLENGE_CODE_BYTES).replace("-", "").replace("_", "")[:12]

    def get_by_code(self, code: str) -> Challenge:
        challenge = self.db.execute(select(Challenge).where(Challenge.code == code)).scalar_one_or_none()
        if challenge is None:
            raise NotFoundError("Challenge not found.", code="CHALLENGE_NOT_FOUND")
        return challenge

    def _expire_if_needed(self, challenge: Challenge) -> Challenge:
        if challenge.status != ChallengeStatus.PENDING.value:
            return challenge
        expires = as_aware(challenge.expires_at)
        if expires is not None and expires < utcnow():
            challenge.status = ChallengeStatus.EXPIRED.value
            self.db.flush()
        return challenge

    def _best_owned_number(self, user_id: int) -> Number | None:
        return self.db.execute(
            select(Number)
            .join(UserNumber, UserNumber.number_id == Number.id)
            .where(UserNumber.user_id == user_id)
            .order_by(Number.base_value.desc())
            .limit(1)
        ).scalar_one_or_none()

    # --- commands -------------------------------------------------------
    def create(self, user: User, *, number_value: str | None = None) -> Challenge:
        """Create a challenge from one of the user's numbers (or their best)."""
        if number_value:
            number = self.numbers.get_by_value(number_value)
            if number is None:
                raise NotFoundError("Number not found.", code="NUMBER_NOT_FOUND")
            if self.numbers.get_user_number(user.id, number.id) is None:
                raise ValidationError("You do not own that number.", code="NUMBER_NOT_OWNED")
        else:
            number = self._best_owned_number(user.id)
            if number is None:
                raise ConflictError("Roll a number before challenging a friend.", code="NO_NUMBERS")

        challenge = Challenge(
            code=self.generate_code(),
            challenger_id=user.id,
            challenger_number_id=number.id,
            challenger_rarity=number.rarity,
            challenger_value=int(number.base_value),
            status=ChallengeStatus.PENDING.value,
            expires_at=utcnow() + timedelta(days=CHALLENGE_TTL_DAYS),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.db.add(challenge)
        self.db.flush()
        self.analytics.track(
            AnalyticsEventName.CHALLENGE_CREATED.value,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={"code": challenge.code, "number": number.value_str},
        )
        self.db.commit()
        self.db.refresh(challenge)
        return challenge

    def accept(self, user: User, code: str) -> Challenge:
        """Respond to a challenge with the user's latest roll."""
        with user_lock(user.id, "challenge"):
            challenge = self._expire_if_needed(self.get_by_code(code))
            if challenge.status != ChallengeStatus.PENDING.value:
                raise ConflictError("This challenge is no longer open.", code="CHALLENGE_CLOSED")
            if challenge.challenger_id == user.id:
                raise ConflictError("You cannot accept your own challenge.", code="CHALLENGE_SELF")

            latest = self._latest_owned_number(user.id)
            if latest is None:
                raise ConflictError("Roll a number first, then accept the challenge.", code="NO_NUMBERS")

            challenge.opponent_id = user.id
            challenge.opponent_number_id = latest.id
            challenge.opponent_rarity = latest.rarity
            challenge.opponent_value = int(latest.base_value)

            challenger_score = (rarity_rank(challenge.challenger_rarity), int(challenge.challenger_value))
            opponent_score = (rarity_rank(latest.rarity), int(latest.base_value))
            if opponent_score > challenger_score:
                challenge.winner_id = user.id
            elif opponent_score < challenger_score:
                challenge.winner_id = challenge.challenger_id
            else:
                challenge.winner_id = None  # draw

            challenge.status = ChallengeStatus.COMPLETED.value
            challenge.completed_at = utcnow()
            self.db.flush()

            if challenge.winner_id:
                winner = self.db.get(User, challenge.winner_id)
                if winner is not None:
                    winner.challenges_completed = int(winner.challenges_completed) + 1

            self.analytics.track(
                AnalyticsEventName.CHALLENGE_COMPLETED.value,
                user_id=user.id,
                telegram_id=user.telegram_id,
                props={"code": code, "winner_id": challenge.winner_id},
            )
            self.db.commit()
            self.db.refresh(challenge)
            return challenge

    def list_for_user(self, user_id: int, limit: int = 30) -> list[Challenge]:
        rows = (
            self.db.execute(
                select(Challenge)
                .where((Challenge.challenger_id == user_id) | (Challenge.opponent_id == user_id))
                .order_by(Challenge.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [self._expire_if_needed(row) for row in rows]

    def _latest_owned_number(self, user_id: int) -> Number | None:
        return self.db.execute(
            select(Number)
            .join(UserNumber, UserNumber.number_id == Number.id)
            .where(UserNumber.user_id == user_id)
            .order_by(UserNumber.last_acquired_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    # --- serialisation ---------------------------------------------------
    @staticmethod
    def _person(user: User | None) -> dict[str, object] | None:
        if user is None:
            return None
        return {"display_name": user.display_name, "username": user.username, "photo_url": user.photo_url}

    def serialize(self, challenge: Challenge) -> dict[str, object]:
        challenger = self.db.get(User, challenge.challenger_id)
        opponent = self.db.get(User, challenge.opponent_id) if challenge.opponent_id else None
        challenger_number = self.db.get(Number, challenge.challenger_number_id)
        opponent_number = self.db.get(Number, challenge.opponent_number_id) if challenge.opponent_number_id else None
        return {
            "code": challenge.code,
            "status": challenge.status,
            "challenger": self._person(challenger),
            "opponent": self._person(opponent),
            "challenger_number": challenger_number.value_str if challenger_number else None,
            "challenger_rarity": challenge.challenger_rarity,
            "challenger_value": int(challenge.challenger_value),
            "opponent_number": opponent_number.value_str if opponent_number else None,
            "opponent_rarity": challenge.opponent_rarity,
            "opponent_value": challenge.opponent_value,
            "winner_id": challenge.winner_id,
            "expires_at": as_aware(challenge.expires_at).isoformat() if challenge.expires_at else None,
            "completed_at": as_aware(challenge.completed_at).isoformat() if challenge.completed_at else None,
        }

    def serialize_public(self, challenge: Challenge) -> dict[str, object]:
        """View of a challenge for someone who has not accepted it yet."""
        data = self.serialize(challenge)
        data.pop("opponent_number", None)
        return data
