"""Albums (collection sets) and their completion rewards.

Album membership is tag-driven, so a new plate automatically lands in the right
sets without a backfill job. Completion rewards are paid exactly once per user
per album, guarded by ``reward_paid`` on the progress row.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.game.countries import THEME_TAG_MAP
from app.models.enums import TransactionType
from app.models.numora import AlbumProgress
from app.models.plates import Album, Plate, PlateTemplate, Region, UserPlate
from app.models.user import User
from app.services.cosmetics import CosmeticService
from app.services.economy import EconomyService


def tag_filter(tags: tuple[str, ...]):
    """Portable "the tags JSON contains any of these" filter.

    ``LIKE`` over the JSON text behaves identically on SQLite and PostgreSQL, so
    development and production run exactly the same query.
    """
    clauses = [cast(Plate.tags, sa.String).like(f'%"{tag}"%') for tag in tags]
    return or_(*clauses) if clauses else None


class AlbumService:
    """Album progress and completion rewards."""

    def __init__(self, db: Session, economy: EconomyService | None = None) -> None:
        self.db = db
        self.economy = economy or EconomyService(db)
        self.cosmetics = CosmeticService(db)

    def albums(self) -> list[Album]:
        return list(
            self.db.execute(
                select(Album)
                .where(Album.is_active.is_(True))
                .order_by(Album.sort_order, Album.id)
            )
            .scalars()
            .all()
        )

    def _tags_for(self, album: Album) -> tuple[str, ...]:
        return () if album.kind == "COUNTRY" else THEME_TAG_MAP.get(album.code, ())

    def _collected_for(self, user_id: int, album: Album) -> int:
        query = (
            select(func.count(func.distinct(UserPlate.plate_id)))
            .join(Plate, Plate.id == UserPlate.plate_id)
            .where(UserPlate.user_id == user_id)
        )
        if album.kind == "COUNTRY" and album.country_id is not None:
            query = query.where(Plate.country_id == album.country_id)
        else:
            tags = self._tags_for(album)
            if not tags:
                return 0
            query = query.where(tag_filter(tags))
        return int(self.db.execute(query).scalar_one() or 0)

    def _total_for(self, album: Album) -> int:
        """How many plates the album can ever contain.

        Derived from the live catalogue so it stays meaningful as countries and
        templates grow, instead of being a frozen hand-counted number.
        """
        if album.kind == "COUNTRY" and album.country_id is not None:
            templates = int(
                self.db.execute(
                    select(func.count(PlateTemplate.id)).where(
                        PlateTemplate.country_id == album.country_id,
                        PlateTemplate.is_active.is_(True),
                    )
                ).scalar_one()
                or 0
            )
            regions = int(
                self.db.execute(
                    select(func.count(Region.id)).where(Region.country_id == album.country_id)
                ).scalar_one()
                or 0
            )
            # Each active template family contributes one collectible per
            # region, which keeps the goal demanding but genuinely reachable.
            return max(1, templates * max(1, regions))

        tags = self._tags_for(album)
        if not tags:
            return 0
        # A theme completes once you hold a qualifying plate from every country
        # that can produce one.
        query = select(func.count(func.distinct(Plate.country_id))).where(tag_filter(tags))
        return int(self.db.execute(query).scalar_one() or 0)

    def _row(self, user_id: int, album: Album) -> AlbumProgress:
        row = self.db.execute(
            select(AlbumProgress).where(
                AlbumProgress.user_id == user_id, AlbumProgress.album_id == album.id
            )
        ).scalar_one_or_none()
        if row is None:
            row = AlbumProgress(
                user_id=user_id,
                album_id=album.id,
                collected=0,
                total=0,
                reward_paid=False,
                updated_at=utcnow(),
            )
            self.db.add(row)
            self.db.flush()
        return row

    def _card(self, album: Album, row: AlbumProgress, collected: int, total: int) -> dict[str, object]:
        config = album.config or {}
        return {
            "code": album.code,
            "name_en": album.name_en,
            "name_ru": album.name_ru,
            "description_en": album.description_en,
            "description_ru": album.description_ru,
            "icon": album.icon,
            "kind": album.kind,
            "collected": collected,
            "total": total,
            "progress": 0.0 if total <= 0 else round(min(1.0, collected / total), 4),
            "percent": round((collected / total) * 100, 1) if total else 0.0,
            "completed": row.completed_at is not None,
            "reward_coins": int(config.get("reward_coins", 0)),
            "reward_title": config.get("reward_title"),
        }

    # --- public API -----------------------------------------------------
    def progress_for_user(self, user: User) -> list[dict[str, object]]:
        """Album board for the collection screen."""
        items: list[dict[str, object]] = []
        for album in self.albums():
            row = self._row(user.id, album)
            collected = self._collected_for(user.id, album)
            total = self._total_for(album)
            row.collected = collected
            row.total = total
            row.updated_at = utcnow()
            items.append(self._card(album, row, collected, total))
        self.db.flush()
        return items

    def evaluate(self, user: User) -> list[dict[str, object]]:
        """Recompute progress and pay any newly-completed rewards."""
        completed: list[dict[str, object]] = []
        for album in self.albums():
            row = self._row(user.id, album)
            collected = self._collected_for(user.id, album)
            total = self._total_for(album)
            row.collected = collected
            row.total = total
            row.updated_at = utcnow()

            if total > 0 and collected >= total and row.completed_at is None:
                row.completed_at = utcnow()
                card = self._card(album, row, collected, total)
                self._reward(user, album, row)
                completed.append(card)

        self.db.flush()
        return completed

    def _reward(self, user: User, album: Album, row: AlbumProgress) -> None:
        """Pay a completion reward exactly once."""
        if row.reward_paid:
            return
        row.reward_paid = True

        config = album.config or {}
        coins = int(config.get("reward_coins", 0))
        title = config.get("reward_title")
        cosmetics = list(config.get("reward_cosmetics", []))

        if coins:
            self.economy.credit(
                user.id,
                coins,
                TransactionType.ALBUM_REWARD,
                reference_type="album",
                reference_id=album.code,
                idempotency_key=f"album:{user.id}:{album.code}",
            )
        if title:
            self.cosmetics.grant_title(user, str(title), source=album.code)
        for code in cosmetics:
            self.cosmetics.grant(user, str(code), source=f"album:{album.code}")

        from app.services.progression import XP_PER_ALBUM, ProgressionService

        ProgressionService(self.db).add_xp(user, XP_PER_ALBUM)
        self.db.flush()


__all__ = ["AlbumService", "tag_filter"]
