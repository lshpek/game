"""Plate catalogue, discovery, ownership and the DEALER.

Everything that mutates a plate goes through this service so the invariants
live in one place:

* a collectible's identity is ``(country, normalized serial)``;
* the DEALER only ever sells *extra* copies - the last copy is protected unless
  an explicit ``allow_last`` is passed by a confirmed user action;
* every sale and every grant writes a ledger row keyed for idempotency.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.timeutils import as_aware, utcnow

# Album membership by tag: the theme sets defined in the catalogue.
from app.game.countries import THEME_TAG_MAP
from app.game.plate_generator import GeneratedPlate
from app.game.plate_stories import build_plate_story
from app.models.plates import Album, Country, Plate, PlateDiscovery, PlateTemplate, Region, UserPlate
from app.models.user import User


@dataclass(slots=True)
class PlateGrant:
    """Outcome of granting one plate to a player."""

    plate: Plate
    user_plate: UserPlate
    is_duplicate: bool
    is_first_discovery: bool
    is_new_country: bool = False
    is_new_region: bool = False


class PlateService:
    """Catalogue persistence plus ownership and discovery bookkeeping."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- lookups ---------------------------------------------------------
    def country_by_code(self, code: str) -> Country | None:
        return self.db.execute(
            select(Country).where(Country.code == code.upper())
        ).scalar_one_or_none()

    def require_country(self, code: str) -> Country:
        country = self.country_by_code(code)
        if country is None:
            raise NotFoundError("Country not found.", code="COUNTRY_NOT_FOUND")
        return country

    def region_for(self, country_code: str, region_code: str | None) -> Region | None:
        if not region_code:
            return None
        country = self.country_by_code(country_code)
        if country is None:
            return None
        return self.db.execute(
            select(Region).where(Region.country_id == country.id, Region.code == region_code)
        ).scalar_one_or_none()

    def template_for(self, code: str) -> PlateTemplate | None:
        return self.db.execute(
            select(PlateTemplate).where(PlateTemplate.code == code)
        ).scalar_one_or_none()

    def get_plate(self, plate_id: int) -> Plate | None:
        return self.db.get(Plate, plate_id)

    def require_plate(self, plate_id: int) -> Plate:
        plate = self.get_plate(plate_id)
        if plate is None:
            raise NotFoundError("Plate not found.", code="PLATE_NOT_FOUND")
        return plate

    def find_plate(self, country_code: str, normalized_text: str) -> Plate | None:
        country = self.country_by_code(country_code)
        if country is None:
            return None
        return self.db.execute(
            select(Plate).where(
                Plate.country_id == country.id,
                Plate.normalized_text == normalized_text,
            )
        ).scalar_one_or_none()

    def get_user_plate(self, user_id: int, plate_id: int) -> UserPlate | None:
        return self.db.execute(
            select(UserPlate).where(UserPlate.user_id == user_id, UserPlate.plate_id == plate_id)
        ).scalar_one_or_none()

    # --- persistence -----------------------------------------------------
    def materialize(self, generated: GeneratedPlate, *, season_code: str | None = None) -> tuple[Plate, bool]:
        """Persist a generated plate as a catalogue row.

        Returns ``(plate, created)``. A concurrent insert of the same
        ``(country, serial)`` simply re-reads the winner's row, so two players
        rolling the same plate never produce duplicates.
        """
        country = self.require_country(generated.country.code)
        region = self.region_for(generated.country.code, generated.region_code)
        template = self.template_for(generated.template_code)
        if template is None:
            raise ValidationError(
                f"Unknown plate template: {generated.template_code}", code="BAD_PLATE_TEMPLATE"
            )

        existing = self.find_plate(generated.country.code, generated.normalized_text)
        if existing is not None:
            return existing, False

        visual = (country.config or {}).get("visual", "european")
        story = build_plate_story(
            traits=list(generated.analysis.traits),
            country_code=generated.country.code,
            rarity=generated.rarity,
            is_secret=generated.is_secret,
        )
        story_ru = build_plate_story(
            traits=list(generated.analysis.traits),
            country_code=generated.country.code,
            rarity=generated.rarity,
            is_secret=generated.is_secret,
            lang="ru",
        )

        plate = Plate(
            country_id=country.id,
            region_id=region.id if region else None,
            template_id=template.id,
            plate_text=generated.plate_text,
            normalized_text=generated.normalized_text,
            display_segments=list(generated.display_segments),
            numeric_parts=list(generated.analysis.digits),
            letter_parts=list(generated.analysis.letters),
            plate_type=generated.plate_type,
            rarity=generated.rarity.value,
            rarity_score=int(generated.rarity_score),
            collector_value=int(generated.collector_value),
            dealer_value=int(generated.dealer_value),
            # Legacy alias column so old readers keep working.
            coin_value=int(generated.dealer_value),
            story=story,
            story_ru=story_ru,
            traits=list(generated.analysis.traits),
            tags=list(generated.analysis.tags),
            visual_style=visual,
            country_code=country.code,
            region_code=region.code if region else None,
            currency_code=generated.currency_code,
            currency_symbol=generated.currency_symbol,
            season_code=season_code,
            is_secret=bool(generated.is_secret),
            discovery_count=0,
        )
        try:
            with self.db.begin_nested():
                self.db.add(plate)
                self.db.flush()
        except IntegrityError:
            # Someone else created the exact same collectible first.
            found = self.find_plate(generated.country.code, generated.normalized_text)
            if found is None:  # pragma: no cover - defensive
                raise
            return found, False

        self._attach_albums(plate)
        return plate, True

    def _attach_albums(self, plate: Plate) -> None:
        """Link a new plate to every album its tags belong to."""
        tags = set(plate.tags or [])
        if not tags:
            return
        wanted = [code for code, required in THEME_TAG_MAP.items() if tags & set(required)]
        if not wanted:
            return
        albums = (
            self.db.execute(select(Album).where(Album.code.in_(wanted), Album.is_active.is_(True)))
            .scalars()
            .all()
        )
        from app.models.plates import PlateAlbum

        for album in albums:
            self.db.add(PlateAlbum(plate_id=plate.id, album_id=album.id))
        self.db.flush()

    # --- discovery + ownership -------------------------------------------
    def record_discovery(
        self,
        plate: Plate,
        user: User,
        *,
        source: str,
        lang: str = "en",
    ) -> bool:
        """Register a find; return ``True`` when it is the world-first one."""
        now = utcnow()
        is_first = plate.first_discovered_by_id is None
        plate.discovery_count = int(plate.discovery_count) + 1
        if is_first:
            plate.first_discovered_by_id = user.id
            plate.first_discovered_at = now

        self.db.add(
            PlateDiscovery(
                plate_id=plate.id,
                user_id=user.id,
                is_first_discovery=is_first,
                source=source,
                created_at=now,
            )
        )
        if is_first:
            # The first-discovery sentence is baked in so the story stays
            # deterministic for every later viewer.
            plate.story = build_plate_story(
                traits=list(plate.traits or []),
                country_code=plate.country_code,
                rarity=plate.rarity,
                is_secret=bool(plate.is_secret),
                is_first_discovery=True,
            )
            plate.story_ru = build_plate_story(
                traits=list(plate.traits or []),
                country_code=plate.country_code,
                rarity=plate.rarity,
                is_secret=bool(plate.is_secret),
                is_first_discovery=True,
                lang="ru",
            )
        self.db.flush()
        return is_first

    def grant(self, plate: Plate, user: User) -> PlateGrant:
        """Give a plate to the player, handling duplicates and new-region flags.

        The caller that generated the number is the only place a dealer value is
        known; the roll pipeline books it on the ``UserPlate`` row itself, so this
        method does not need it.
        """
        now = utcnow()
        owned = self.get_user_plate(user.id, plate.id)

        if owned is not None:
            owned.duplicate_count = int(owned.duplicate_count) + 1
            owned.last_acquired_at = now
            self.db.flush()
            return PlateGrant(plate, owned, True, False)

        new_country = not self._has_country(user.id, plate.country_id)
        new_region = bool(
            plate.region_id is not None and not self._has_region(user.id, plate.region_id)
        )

        owned = UserPlate(
            user_id=user.id,
            plate_id=plate.id,
            duplicate_count=0,
            coins_earned=0,
            copies_sold=0,
            is_favorite=False,
            is_new=True,
            first_acquired_at=now,
            last_acquired_at=now,
        )
        self.db.add(owned)
        self.db.flush()
        return PlateGrant(plate, owned, False, False, new_country, new_region)

    def _has_country(self, user_id: int, country_id: int) -> bool:
        query = (
            select(func.count())
            .select_from(UserPlate)
            .join(Plate, Plate.id == UserPlate.plate_id)
            .where(UserPlate.user_id == user_id, Plate.country_id == country_id)
        )
        return int(self.db.execute(query).scalar_one() or 0) > 0

    def _has_region(self, user_id: int, region_id: int) -> bool:
        query = (
            select(func.count())
            .select_from(UserPlate)
            .join(Plate, Plate.id == UserPlate.plate_id)
            .where(UserPlate.user_id == user_id, Plate.region_id == region_id)
        )
        return int(self.db.execute(query).scalar_one() or 0) > 0

    def mark_seen(self, user_plate: UserPlate) -> None:
        """Clear the NEW badge once the player has looked at the plate."""
        user_plate.is_new = False
        self.db.flush()

    def toggle_favorite(self, user_plate: UserPlate) -> bool:
        user_plate.is_favorite = not bool(user_plate.is_favorite)
        self.db.flush()
        return bool(user_plate.is_favorite)

    # --- the DEALER ------------------------------------------------------
    def sellable_copies(self, user_plate: UserPlate, *, allow_last: bool = False) -> int:
        """How many copies may be sold right now.

        By default only *extra* copies are sellable so a player can never
        accidentally destroy the last plate a collection needs.
        """
        extra = int(user_plate.duplicate_count)
        if allow_last and int(user_plate.copies_sold) == 0:
            # Advanced path: the caller must have confirmed explicitly.
            return extra + 1
        return extra

    def sale_value(self, plate: Plate, *, premium_multiplier: float = 1.0) -> int:
        from app.game.plate_valuation import duplicate_sale_value

        return duplicate_sale_value(
            int(plate.dealer_value), premium_multiplier=premium_multiplier
        )

    def apply_sale(
        self,
        user_plate: UserPlate,
        *,
        copies: int,
        premium_multiplier: float = 1.0,
    ) -> int:
        """Remove ``copies`` duplicates and return the NUMORA to credit.

        Mutates only the copy counters; the caller writes the ledger row so the
        money movement stays in :mod:`app.services.economy`.
        """
        if copies <= 0:
            raise ValidationError("Nothing to sell.", code="NO_DUPLICATES")
        available = int(user_plate.duplicate_count)
        if copies > available:
            raise ConflictError(
                "You do not have that many duplicates.",
                code="NOT_ENOUGH_DUPLICATES",
                details={"available": available, "requested": copies},
            )
        user_plate.duplicate_count = available - copies
        user_plate.copies_sold = int(user_plate.copies_sold) + copies
        user_plate.last_acquired_at = utcnow()
        self.db.flush()
        return self.sale_value(user_plate.plate, premium_multiplier=premium_multiplier) * copies

    # --- statistics -----------------------------------------------------
    def country_progress(self, user_id: int) -> dict[int, int]:
        """``{country_id: distinct plates collected}`` for one player."""
        rows = self.db.execute(
            select(Plate.country_id, func.count(func.distinct(UserPlate.plate_id)))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id)
            .group_by(Plate.country_id)
        ).all()
        return {int(country_id): int(count) for country_id, count in rows}

    def region_progress(self, user_id: int) -> dict[int, int]:
        rows = self.db.execute(
            select(Plate.region_id, func.count(func.distinct(UserPlate.plate_id)))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user_id, Plate.region_id.isnot(None))
            .group_by(Plate.region_id)
        ).all()
        return {int(region_id): int(count) for region_id, count in rows}

    def collection_size(self, user_id: int) -> int:
        query = (
            select(func.count(func.distinct(UserPlate.plate_id)))
            .where(UserPlate.user_id == user_id)
            .select_from(UserPlate)
        )
        return int(self.db.execute(query).scalar_one() or 0)

    # --- first discovery -------------------------------------------------
    def set_first_discoverer(
        self,
        plate: Plate,
        user: User,
        *,
        source: str = "ADMIN",
        override: bool = False,
    ) -> dict[str, object]:
        """Move (or create) the world-first discovery record of a plate.

        Consistency rules enforced here, not by the caller:

        * a plate has at most one first discoverer - reassigning demotes the old
          ``PlateDiscovery`` row instead of creating a contradictory second one;
        * the cached ``first_discoveries_count`` of both the previous and the new
          discoverer is recomputed from ``plate_discoveries``;
        * the discovery counter never shrinks.
        """
        previous_id = plate.first_discovered_by_id
        if previous_id is not None and previous_id == user.id:
            return {
                "plate_id": plate.id,
                "first_discoverer_id": previous_id,
                "previous_discoverer_id": previous_id,
                "changed": False,
                "demoted_user_id": None,
            }
        if previous_id is not None and not override:
            raise ConflictError(
                "This plate already has a first discoverer.",
                code="FIRST_DISCOVERY_TAKEN",
                details={"plate_id": plate.id},
            )

        demoted: int | None = None
        if previous_id is not None:
            demoted = int(previous_id)
            for row in self.db.execute(
                select(PlateDiscovery).where(
                    PlateDiscovery.plate_id == plate.id,
                    PlateDiscovery.is_first_discovery.is_(True),
                )
            ).scalars():
                row.is_first_discovery = False

        now = utcnow()
        existing = self.db.execute(
            select(PlateDiscovery).where(PlateDiscovery.plate_id == plate.id, PlateDiscovery.user_id == user.id)
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(
                PlateDiscovery(
                    plate_id=plate.id,
                    user_id=user.id,
                    is_first_discovery=True,
                    source=source[:16],
                    created_at=now,
                )
            )
            plate.discovery_count = int(plate.discovery_count) + 1
        else:
            existing.is_first_discovery = True
            existing.source = source[:16]

        plate.first_discovered_by_id = user.id
        plate.first_discovered_at = now
        plate.story = build_plate_story(
            traits=list(plate.traits or []),
            country_code=plate.country_code,
            rarity=plate.rarity,
            is_secret=bool(plate.is_secret),
            is_first_discovery=True,
        )
        plate.story_ru = build_plate_story(
            traits=list(plate.traits or []),
            country_code=plate.country_code,
            rarity=plate.rarity,
            is_secret=bool(plate.is_secret),
            is_first_discovery=True,
            lang="ru",
        )
        self.db.flush()

        # Keep the cached counters honest for both sides of the move.
        touched = {int(user.id)}
        if demoted is not None:
            touched.add(demoted)
        for user_id in touched:
            self.sync_first_discoveries(user_id)

        return {
            "plate_id": plate.id,
            "first_discoverer_id": int(user.id),
            "previous_discoverer_id": demoted,
            "changed": True,
            "demoted_user_id": demoted,
        }

    def sync_first_discoveries(self, user_id: int) -> int:
        """Recount ``first_discoveries_count`` for one player from the truth."""
        total = int(
            self.db.execute(
                select(func.count(func.distinct(PlateDiscovery.plate_id))).where(
                    PlateDiscovery.user_id == user_id,
                    PlateDiscovery.is_first_discovery.is_(True),
                )
            ).scalar_one()
            or 0
        )
        user = self.db.get(User, user_id)
        if user is not None:
            user.first_discoveries_count = total
            self.db.flush()
        return total

    def plate_owners(self, plate_id: int, limit: int = 10) -> list[dict[str, object]]:
        """Who owns a plate - read-only ownership inspection."""
        rows = self.db.execute(
            select(UserPlate, User)
            .join(User, User.id == UserPlate.user_id)
            .where(UserPlate.plate_id == plate_id)
            .order_by(UserPlate.first_acquired_at)
            .limit(max(1, min(limit, 50)))
        ).all()
        return [
            {
                "user_id": user.id,
                "telegram_id": int(user.telegram_id),
                "username": user.username,
                "display_name": user.display_name,
                "duplicate_count": int(owned.duplicate_count),
                "copies_sold": int(owned.copies_sold),
                "acquired_at": as_aware(owned.first_acquired_at).isoformat()
                if owned.first_acquired_at
                else None,
            }
            for owned, user in rows
        ]

    def discovery_history(self, plate_id: int, limit: int = 10) -> list[dict[str, object]]:
        """Who found a plate and when - read-only discovery inspection."""
        rows = self.db.execute(
            select(PlateDiscovery, User)
            .join(User, User.id == PlateDiscovery.user_id)
            .where(PlateDiscovery.plate_id == plate_id)
            .order_by(PlateDiscovery.id.desc())
            .limit(max(1, min(limit, 50)))
        ).all()
        return [
            {
                "user_id": user.id,
                "telegram_id": int(user.telegram_id),
                "username": user.username,
                "is_first_discovery": bool(row.is_first_discovery),
                "source": row.source,
                "created_at": as_aware(row.created_at).isoformat() if row.created_at else None,
            }
            for row, user in rows
        ]


__all__ = ["PlateGrant", "PlateService"]
