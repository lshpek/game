"""Plate challenges: a friend beats the challenger's plate.

Resolution is entirely server-side. The client supplies only a challenge code;
the opponent's plate comes from their latest roll and the comparison uses the
stored ``rarity_score`` - never a client-supplied value.

Replay and abuse protection:

* a challenge can only be accepted once;
* the challenger cannot accept their own challenge;
* the reward is paid exactly once, guarded by the completed status;
* stale challenges expire instead of lingering forever.
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
from app.models.enums import AnalyticsEventName, ChallengeStatus, TransactionType
from app.models.plates import Plate, PlateChallenge, UserPlate
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.services.economy import EconomyService
from app.services.plates import PlateService

CHALLENGE_CODE_BYTES = 6
CHALLENGE_TTL_DAYS = 7
CHALLENGE_REWARD_COINS = 300


class PlateChallengeService:
    """Creates, resolves and expires plate challenges."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.plates = PlateService(db)
        self.economy = EconomyService(db)
        self.analytics = AnalyticsService(db)

    # --- helpers --------------------------------------------------------
    @staticmethod
    def generate_code() -> str:
        raw = secrets.token_urlsafe(CHALLENGE_CODE_BYTES)
        return raw.replace("-", "").replace("_", "")[:12]

    def get_by_code(self, code: str) -> PlateChallenge:
        challenge = self.db.execute(
            select(PlateChallenge).where(PlateChallenge.code == code)
        ).scalar_one_or_none()
        if challenge is None:
            raise NotFoundError("Challenge not found.", code="CHALLENGE_NOT_FOUND")
        return challenge

    def _expire_if_needed(self, challenge: PlateChallenge) -> PlateChallenge:
        if challenge.status != ChallengeStatus.PENDING.value:
            return challenge
        expires = as_aware(challenge.expires_at)
        if expires is not None and expires < utcnow():
            challenge.status = ChallengeStatus.EXPIRED.value
            self.db.flush()
        return challenge

    def _best_owned_plate(self, user_id: int) -> Plate | None:
        return self.db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id)
            .order_by(Plate.rarity_score.desc(), Plate.collector_value.desc())
            .limit(1)
        ).scalars().first()

    def _latest_owned_plate(self, user_id: int) -> Plate | None:
        return self.db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id)
            .order_by(UserPlate.last_acquired_at.desc())
            .limit(1)
        ).scalars().first()

    # --- commands -------------------------------------------------------
    def create(self, user: User, *, plate_id: int | None = None) -> PlateChallenge:
        """Create a challenge from one of the player's plates."""
        if plate_id is not None:
            plate = self.plates.get_plate(plate_id)
            if plate is None:
                raise NotFoundError("Plate not found.", code="PLATE_NOT_FOUND")
            if self.plates.get_user_plate(user.id, plate.id) is None:
                raise ValidationError("You do not own that plate.", code="PLATE_NOT_OWNED")
        else:
            plate = self._best_owned_plate(user.id)
            if plate is None:
                raise ConflictError(
                    "Roll a plate before challenging a friend.", code="NO_PLATES"
                )

        challenge = PlateChallenge(
            code=self.generate_code(),
            challenger_id=user.id,
            challenger_plate_id=plate.id,
            challenger_score=int(plate.rarity_score),
            status=ChallengeStatus.PENDING.value,
            reward_coins=CHALLENGE_REWARD_COINS,
            expires_at=utcnow() + timedelta(days=CHALLENGE_TTL_DAYS),
        )
        self.db.add(challenge)
        self.analytics.track(
            AnalyticsEventName.CHALLENGE_CREATED.value,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={
                "plate_id": plate.id,
                "rarity": plate.rarity,
                "score": int(plate.rarity_score),
            },
        )
        self.db.commit()
        self.db.refresh(challenge)
        return challenge

    def accept(self, user: User, code: str) -> PlateChallenge:
        """Accept a challenge with the player's most recent plate."""
        with user_lock(user.id):
            challenge = self._expire_if_needed(self.get_by_code(code))

            if challenge.challenger_id == user.id:
                raise ValidationError(
                    "You cannot accept your own challenge.", code="SELF_ACCEPTANCE"
                )
            if challenge.status != ChallengeStatus.PENDING.value:
                raise ConflictError(
                    "This challenge is no longer open.", code="CHALLENGE_CLOSED"
                )
            if challenge.opponent_id == user.id:
                raise ConflictError(
                    "You already accepted this challenge.", code="ALREADY_ACCEPTED"
                )

            plate = self._latest_owned_plate(user.id)
            if plate is None:
                raise ConflictError("Roll a plate before accepting.", code="NO_PLATES")

            opponent_score = int(plate.rarity_score)
            challenge.opponent_id = user.id
            challenge.opponent_plate_id = plate.id
            challenge.opponent_score = opponent_score

            challenger_score = int(challenge.challenger_score)
            if challenger_score > opponent_score:
                challenge.winner_id = challenge.challenger_id
            elif opponent_score > challenger_score:
                challenge.winner_id = user.id
            else:
                challenge.winner_id = None  # draw

            challenge.status = ChallengeStatus.COMPLETED.value
            challenge.completed_at = utcnow()

            # Paid exactly once: the status flip above is the guard.
            if challenge.winner_id is not None:
                winner = self.db.get(User, challenge.winner_id)
                if winner is not None:
                    self.economy.credit(
                        winner.id,
                        int(challenge.reward_coins),
                        TransactionType.CHALLENGE_REWARD,
                        reference_type="plate_challenge",
                        reference_id=challenge.code,
                        idempotency_key=f"plate_challenge:{challenge.id}",
                    )
                    winner.challenges_completed = int(winner.challenges_completed) + 1

            user.challenges_completed = int(user.challenges_completed) + 1
            self.analytics.track(
                AnalyticsEventName.CHALLENGE_COMPLETED.value,
                user_id=user.id,
                telegram_id=user.telegram_id,
                props={"code": challenge.code, "winner": challenge.winner_id, "score": opponent_score},
            )
            self.db.commit()
            self.db.refresh(challenge)
            return challenge

    def list_for_user(self, user_id: int, limit: int = 30) -> list[PlateChallenge]:
        rows = (
            self.db.execute(
                select(PlateChallenge)
                .where(
                    (PlateChallenge.challenger_id == user_id)
                    | (PlateChallenge.opponent_id == user_id)
                )
                .order_by(PlateChallenge.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [self._expire_if_needed(row) for row in rows]

    # --- serialisation --------------------------------------------------
    @staticmethod
    def _person(user: User | None) -> dict[str, object] | None:
        if user is None:
            return None
        return {
            "display_name": user.display_name,
            "username": user.username,
            "photo_url": user.photo_url,
        }

    def serialize(self, challenge: PlateChallenge) -> dict[str, object]:
        challenger = self.db.get(User, challenge.challenger_id)
        opponent = self.db.get(User, challenge.opponent_id) if challenge.opponent_id else None
        challenger_plate = self.db.get(Plate, challenge.challenger_plate_id)
        opponent_plate = (
            self.db.get(Plate, challenge.opponent_plate_id) if challenge.opponent_plate_id else None
        )
        return {
            "code": challenge.code,
            "status": challenge.status,
            "challenger": self._person(challenger),
            "opponent": self._person(opponent),
            "challenger_plate_id": challenge.challenger_plate_id,
            "challenger_plate_text": challenger_plate.plate_text if challenger_plate else None,
            "challenger_rarity": challenger_plate.rarity if challenger_plate else None,
            "challenger_score": int(challenge.challenger_score),
            "opponent_plate_id": challenge.opponent_plate_id,
            "opponent_plate_text": opponent_plate.plate_text if opponent_plate else None,
            "opponent_rarity": opponent_plate.rarity if opponent_plate else None,
            "opponent_score": challenge.opponent_score,
            "winner_id": challenge.winner_id,
            "reward_coins": int(challenge.reward_coins),
            "expires_at": (
                as_aware(challenge.expires_at).isoformat() if challenge.expires_at else None
            ),
            "completed_at": (
                as_aware(challenge.completed_at).isoformat() if challenge.completed_at else None
            ),
        }

    def serialize_public(self, challenge: PlateChallenge) -> dict[str, object]:
        """View for someone who has not accepted yet: hide the opponent."""
        data = self.serialize(challenge)
        for key in ("opponent_plate_id", "opponent_plate_text", "opponent_rarity", "opponent_score"):
            data.pop(key, None)
        return data


__all__ = ["CHALLENGE_REWARD_COINS", "PlateChallengeService"]