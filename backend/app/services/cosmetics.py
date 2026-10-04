"""Cosmetics: catalogue, ownership and equipping.

Cosmetics are presentation only. Nothing in this module can change rarity,
valuation or the ledger - that separation is what makes them safe to sell.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.timeutils import utcnow
from app.models.numora import Cosmetic, CosmeticTitle, UserCosmetic
from app.models.user import User

COSMETIC_KINDS = (
    "PLATE_FINISH",
    "PLATE_GLOW",
    "CARD_EFFECT",
    "PROFILE_FRAME",
    "GARAGE_BACKGROUND",
    "TITLE",
)


class CosmeticService:
    """Lists the catalogue and manages what a player owns and wears."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def catalogue(self, kind: str | None = None) -> list[Cosmetic]:
        stmt = select(Cosmetic).where(Cosmetic.is_active.is_(True))
        if kind:
            stmt = stmt.where(Cosmetic.kind == kind.upper())
        return list(self.db.execute(stmt.order_by(Cosmetic.sort_order, Cosmetic.id)).scalars().all())

    def owned_codes(self, user_id: int) -> set[str]:
        rows = self.db.execute(
            select(Cosmetic.code)
            .join(UserCosmetic, UserCosmetic.cosmetic_id == Cosmetic.id)
            .where(UserCosmetic.user_id == user_id)
        ).scalars()
        return set(rows)

    def equipped_codes(self, user_id: int) -> dict[str, str]:
        """``{kind: code}`` for everything the player currently wears."""
        rows = self.db.execute(
            select(Cosmetic.kind, Cosmetic.code)
            .join(UserCosmetic, UserCosmetic.cosmetic_id == Cosmetic.id)
            .where(UserCosmetic.user_id == user_id, UserCosmetic.equipped.is_(True))
        ).all()
        return {str(kind): str(code) for kind, code in rows}

    def serialize(self, user_id: int) -> list[dict[str, object]]:
        """Full catalogue annotated with ownership and equipped state."""
        owned = self.owned_codes(user_id)
        equipped = self.equipped_codes(user_id)
        items: list[dict[str, object]] = []
        for cosmetic in self.catalogue():
            is_owned = cosmetic.code in owned
            items.append(
                {
                    "code": cosmetic.code,
                    "kind": cosmetic.kind,
                    "name_en": cosmetic.name_en,
                    "name_ru": cosmetic.name_ru,
                    "description_en": cosmetic.description_en,
                    "description_ru": cosmetic.description_ru,
                    "config": dict(cosmetic.config or {}),
                    "price_stars": int(cosmetic.price_stars),
                    "price_numora": int(cosmetic.price_numora),
                    "rarity": cosmetic.rarity_code,
                    "owned": is_owned,
                    "equipped": equipped.get(cosmetic.kind) == cosmetic.code,
                    "locked": not is_owned,
                }
            )
        return items

    # --- writes ---------------------------------------------------------
    def grant(self, user: User, code: str, *, source: str = "PURCHASE") -> UserCosmetic:
        """Give a cosmetic. Idempotent - a second grant is a no-op."""
        cosmetic = self.db.execute(
            select(Cosmetic).where(Cosmetic.code == code)
        ).scalar_one_or_none()
        if cosmetic is None:
            raise NotFoundError("Cosmetic not found.", code="COSMETIC_NOT_OWNED_NOT_FOUND")

        existing = self.db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == user.id, UserCosmetic.cosmetic_id == cosmetic.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        row = UserCosmetic(user_id=user.id, cosmetic_id=cosmetic.id, equipped=False, acquired_at=utcnow())
        self.db.add(row)
        self.db.flush()
        return row

    def equip(self, user: User, code: str) -> str:
        """Equip one cosmetic, unequipping whatever held that slot before."""
        cosmetic = self.db.execute(
            select(Cosmetic).where(Cosmetic.code == code)
        ).scalar_one_or_none()
        if cosmetic is None:
            raise NotFoundError("Cosmetic not found.", code="COSMETIC_NOT_FOUND")

        owned = self.db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == user.id, UserCosmetic.cosmetic_id == cosmetic.id
            )
        ).scalar_one_or_none()
        if owned is None:
            raise ValidationError("You do not own this cosmetic.", code="COSMETIC_NOT_OWNED")

        for row in self.db.execute(
            select(UserCosmetic).where(UserCosmetic.user_id == user.id, UserCosmetic.equipped.is_(True))
        ).scalars():
            if row.cosmetic.kind == cosmetic.kind:
                row.equipped = False

        owned.equipped = True
        user.equipped_cosmetic_code = cosmetic.code
        self.db.flush()
        return cosmetic.code

    def unequip(self, user: User, code: str) -> None:
        row = self.db.execute(
            select(UserCosmetic)
            .join(Cosmetic, Cosmetic.id == UserCosmetic.cosmetic_id)
            .where(UserCosmetic.user_id == user.id, Cosmetic.code == code)
        ).scalar_one_or_none()
        if row is None:
            return
        row.equipped = False
        if user.equipped_cosmetic_code == code:
            user.equipped_cosmetic_code = None
        self.db.flush()

    # --- titles ---------------------------------------------------------
    def titles(self, user_id: int) -> list[dict[str, object]]:
        rows = (
            self.db.execute(
                select(CosmeticTitle).where(CosmeticTitle.user_id == user_id).order_by(CosmeticTitle.id)
            )
            .scalars()
            .all()
        )
        return [
            {"title": row.title, "source": row.source, "equipped": bool(row.equipped)} for row in rows
        ]

    def grant_title(self, user: User, title: str, *, source: str = "") -> None:
        existing = self.db.execute(
            select(CosmeticTitle).where(
                CosmeticTitle.user_id == user.id, CosmeticTitle.title == title
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        self.db.add(
            CosmeticTitle(
                user_id=user.id, title=title, source=source, equipped=False, acquired_at=utcnow()
            )
        )
        self.db.flush()

    def equip_title(self, user: User, title: str) -> None:
        row = self.db.execute(
            select(CosmeticTitle).where(CosmeticTitle.user_id == user.id, CosmeticTitle.title == title)
        ).scalar_one_or_none()
        if row is None:
            raise ValidationError("You do not own this title.", code="TITLE_NOT_OWNED")
        for other in self.db.execute(
            select(CosmeticTitle).where(CosmeticTitle.user_id == user.id)
        ).scalars():
            other.equipped = other.id == row.id
        user.equipped_title = title
        self.db.flush()


__all__ = ["COSMETIC_KINDS", "CosmeticService"]
