"""License plate collectibles: countries, regions, templates and ownership.

The relational core of NUMORA. Configuration-heavy parts (template patterns,
visual themes, rarity modifiers) live in JSONB because they are read as a whole
and never queried by inner key; everything the game filters or aggregates on -
country code, region code, rarity, value - is a real indexed column.

Legacy 4-digit ``Number`` rows are untouched so existing players keep their
collection.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class Country(Base, TimestampMixin):
    """One country or territory of the world catalogue.

    ``code`` is the ISO 3166-1 **alpha-3** identifier and the engine's stable key;
    ``iso_alpha2`` carries the two-letter form used by deep links and share payloads.

    ``is_active`` and ``is_playable`` are different on purpose: every ISO country is
    active (listed by the WORLD screen), but only countries with a complete
    generation and presentation setup are playable. A locked country can be released
    by flipping one flag - no schema change is involved.
    """

    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, index=True, nullable=False)
    #: ISO 3166-1 alpha-2 code. Nullable only so the migration can backfill it.
    iso_alpha2: Mapped[str | None] = mapped_column(String(2), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(96), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(96), nullable=False)
    flag: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    # Generation configuration: alphabet, letter policy, rarity/coin modifiers,
    # visual theme id, layout family and special rules.
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # SIM/number presentation configuration: calling code, printed groupings,
    # fictional operators and editions. Separate from ``config`` because it is owned
    # and validated by ``app.game.sim_cards``.
    sim_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    #: Assigned calling code, printed on the country's SIM cards and searchable so
    #: "7" finds Russia.
    calling_code: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    #: Lower-cased ``code alpha2 name_en name_ru calling_code`` blob used by the
    #: country search. Kept as a column because ``lower()`` is ASCII-only on SQLite,
    #: which would otherwise make "россия" unfindable in local development.
    search_text: Mapped[str] = mapped_column(String(256), default="", nullable=False, index=True)
    # Continent / album grouping, e.g. "EUROPE".
    region_group: Mapped[str] = mapped_column(String(24), index=True, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    is_playable: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    regions: Mapped[list["Region"]] = relationship(
        back_populates="country", cascade="all, delete-orphan", lazy="selectin"
    )
    templates: Mapped[list["PlateTemplate"]] = relationship(
        back_populates="country", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Country {self.code}>"

class Region(Base, TimestampMixin):
    """A region/state/canton whose code is part of the plate."""

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(
        ForeignKey("countries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(64), nullable=False)
    # Extra generation config: allowed suffixes, region rarity bonus.
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    country: Mapped[Country] = relationship(back_populates="regions")

    __table_args__ = (UniqueConstraint("country_id", "code", name="uq_regions_country_code"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Region {self.code} {self.name_en}>"


class PlateTemplate(Base, TimestampMixin):
    """One plate layout for a country (or one of its regions).

    ``pattern`` uses the template language implemented in
    :mod:`app.game.plate_templates`; ``config`` holds generation weights and
    optional constraints.
    """

    __tablename__ = "plate_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(
        ForeignKey("countries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    pattern: Mapped[str] = mapped_column(String(96), nullable=False)
    plate_type: Mapped[str] = mapped_column(String(24), index=True, default="STANDARD", nullable=False)
    weight: Mapped[float] = mapped_column(default=1.0, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rarity_floor: Mapped[str] = mapped_column(String(16), default="COMMON", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    country: Mapped[Country] = relationship(back_populates="templates")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlateTemplate {self.code} {self.pattern!r}>"


class Plate(Base, TimestampMixin):
    """A concrete collectible plate, created lazily on first roll."""

    __tablename__ = "plates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(
        ForeignKey("countries.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("plate_templates.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    plate_text: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    display_segments: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    numeric_parts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    letter_parts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    plate_type: Mapped[str] = mapped_column(String(24), index=True, default="STANDARD", nullable=False)
    #: Kind-specific payload, shaped by :mod:`app.game.collectibles`.
    #: SIM cards carry ``operator``, ``series``, ``edition`` and the printed
    #: ``synthetic_number``; vehicle plates carry their layout description. Read as a
    #: whole, never queried by inner key, which is why it is JSON.
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    rarity_score: Mapped[int] = mapped_column(Integer, index=True, default=0, nullable=False)

    # Fictional, country-local presentation value. NEVER a market price.
    collector_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # Authoritative game-economy value in NUMORA.
    dealer_value: Mapped[int] = mapped_column(BigInteger, index=True, default=0, nullable=False)
    # Kept for backwards compatibility with the legacy ``coin_value`` column.
    coin_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    story: Mapped[str] = mapped_column(Text, default="", nullable=False)
    story_ru: Mapped[str] = mapped_column(Text, default="", nullable=False)
    traits: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    visual_style: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)

    country_code: Mapped[str] = mapped_column(String(3), default="", nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(16), default=None)
    currency_code: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    currency_symbol: Mapped[str] = mapped_column(String(8), default="$", nullable=False)

    season_code: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    discovery_count: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)
    first_discovered_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    first_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    country: Mapped[Country] = relationship(lazy="joined")
    region: Mapped["Region | None"] = relationship(lazy="joined")
    template: Mapped[PlateTemplate] = relationship(lazy="joined")

    __table_args__ = (
        # A textual plate may legitimately exist in more than one country, so the
        # identity of a collectible is (country, normalized serial) - never the
        # serial alone.
        UniqueConstraint("country_id", "normalized_text", name="uq_plates_country_normalized"),
        # Composite indexes the game actually filters on; the single-column
        # ones come from ``index=True`` on the mapped columns.
        Index("ix_plates_country_rarity", "country_id", "rarity"),
        Index("ix_plates_country_region", "country_id", "region_id"),
        Index("ix_plates_rarity_value", "rarity", "collector_value"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Plate {self.plate_text} {self.rarity}>"


class UserPlate(Base, TimestampMixin):
    """Ownership row; duplicates increment ``duplicate_count``."""

    __tablename__ = "user_plates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plate_id: Mapped[int] = mapped_column(ForeignKey("plates.id", ondelete="CASCADE"), index=True, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Number of copies sold to the DEALER; the final copy is protected by default.
    copies_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plate: Mapped[Plate] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "plate_id", name="uq_user_plates_user_plate"),
        Index("ix_user_plates_user_acquired", "user_id", "first_acquired_at"),
    )


class PlateDiscovery(Base):
    """Every roll that found a plate - powers discovery counters."""

    __tablename__ = "plate_discoveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate_id: Mapped[int] = mapped_column(ForeignKey("plates.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    is_first_discovery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="ROLL", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_plate_discoveries_plate_created", "plate_id", "created_at"),)


class Album(Base, TimestampMixin):
    """A collectible album (per country, continent, or theme)."""

    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(64), nullable=False)
    description_en: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    description_ru: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="THEME", nullable=False)
    country_id: Mapped[int | None] = mapped_column(
        ForeignKey("countries.id", ondelete="CASCADE"), nullable=True
    )
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PlateAlbum(Base):
    """Join table: which plates belong to which album."""

    __tablename__ = "plate_albums"

    plate_id: Mapped[int] = mapped_column(
        ForeignKey("plates.id", ondelete="CASCADE"), primary_key=True
    )
    album_id: Mapped[int] = mapped_column(
        ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class PlateChallenge(Base, TimestampMixin):
    """Duel: the opponent's roll is compared on ``rarity_score`` server-side."""

    __tablename__ = "plate_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    challenger_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    opponent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    challenger_plate_id: Mapped[int] = mapped_column(ForeignKey("plates.id", ondelete="CASCADE"), nullable=False)
    opponent_plate_id: Mapped[int | None] = mapped_column(ForeignKey("plates.id", ondelete="SET NULL"), nullable=True)
    challenger_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opponent_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True, nullable=False)
    reward_coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    challenger_plate: Mapped[Plate] = relationship(foreign_keys=[challenger_plate_id], lazy="joined")
    opponent_plate: Mapped[Plate | None] = relationship(foreign_keys=[opponent_plate_id], lazy="joined")


__all__ = [
    "Album",
    "Country",
    "Plate",
    "PlateAlbum",
    "PlateChallenge",
    "PlateDiscovery",
    "PlateTemplate",
    "Region",
    "UserPlate",
]
