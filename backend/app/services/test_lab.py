"""Internal test lab.

The most powerful internal surface of the game, and the one with the strictest
isolation rules:

* **Simulation** - pure. Builds the exact roll payload the client would receive
  without spending a roll, touching a wallet, adding to a collection, moving a
  leaderboard or writing a discovery record.
* **Live admin test** - mutates one chosen player on purpose, through the very
  same services the real game uses, and is always audited.

Two hard rules:

1. the production RNG configuration is never touched. No rarity weights, no
   country weights, no global override is written, restored or raced over. A
   forced rarity is produced by handing the desired rarity to the engine as the
   ``luck`` tier of a *local* generation pass.
2. every mutation is a normal service call, so ledger entries, ownership rows,
   progression counters and first-discovery bookkeeping stay consistent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import NotFoundError, ValidationError
from app.core.locks import user_lock
from app.core.timeutils import as_aware
from app.game.collectibles import KINDS, CollectibleKind, normalize_kind, plate_types_for
from app.game.plate_generator import (
    GeneratedPlate,
    GenerationContext,
    PlateGenerator,
    TemplateOption,
    build_generated_plate,
    styles_for_text,
)
from app.game.plate_patterns import split_plate
from app.game.plate_rarity import RARITY_ORDER, Rarity
from app.game.plate_templates import normalize_plate, parse_template
from app.game.rng import default_rng
from app.models.plates import Country, Plate, PlateTemplate
from app.models.user import User
from app.services.catalog import build_snapshot
from app.services.economy import EconomyService
from app.services.plates import PlateService
from app.services.progression import ProgressionService

#: Menu labels for the collectible kinds, in both panel languages.
CATEGORY_LABELS: dict[CollectibleKind, str] = {
    CollectibleKind.VEHICLE_PLATE: "\U0001F699 Vehicle plate",
    CollectibleKind.SIM_CARD: "\U0001F4F7 SIM card",
}

CATEGORY_EMOJI: dict[CollectibleKind, str] = {
    CollectibleKind.VEHICLE_PLATE: "\U0001F699",
    CollectibleKind.SIM_CARD: "\U0001F4F7",
}

# Reusable presets. They only carry *intent* (a country, a rarity, a trait
# goal); every generation still goes through the real template/analysis stack, so
# a preset can never invent an invalid plate format.
TEST_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "code": "MYTHIC_USA",
        "label": "MYTHIC USA",
        "emoji": "💎",
        "country_code": "USA",
        "rarity": Rarity.MYTHIC.value,
    },
    {
        "code": "LEGENDARY_RUSSIA",
        "label": "LEGENDARY Russia",
        "emoji": "🏅",
        "country_code": "RUS",
        "rarity": Rarity.LEGENDARY.value,
    },
    {
        "code": "SECRET_JAPAN",
        "label": "SECRET Japan",
        "emoji": "🕶",
        "country_code": "JPN",
        "rarity": Rarity.SECRET.value,
    },
    {
        "code": "REPEATED_777",
        "label": "777 repeating",
        "emoji": "7️⃣",
        "country_code": None,
        "rarity": None,
        "require_trait": "contains_777",
    },
    {
        "code": "PALINDROME",
        "label": "Palindrome",
        "emoji": "🪞",
        "country_code": None,
        "rarity": None,
        "require_trait": "palindrome",
    },
{
        "code": "FIRST_DISCOVERY",
        "label": "First discovery",
        "emoji": "\U0001F947",
        "country_code": None,
        "rarity": None,
    },
    {
        "code": "SIM_CROWN_RUSSIA",
        "label": "CROWN SIM (Russia)",
        "emoji": "\U0001F4F7",
        "country_code": "RUS",
        "kind": CollectibleKind.SIM_CARD.value,
        "rarity": Rarity.LEGENDARY.value,
    },
    {
        "code": "SIM_ORIGIN_JAPAN",
        "label": "ORIGIN SIM (Japan)",
        "emoji": "\U0001F4F7",
        "country_code": "JPN",
        "kind": CollectibleKind.SIM_CARD.value,
        "rarity": Rarity.COMMON.value,
    },
)

# Default country for trait goals that do not name one ("777", "palindrome").
DEFAULT_TRAIT_COUNTRY = "RUS"


def preset_by_code(code: str) -> dict[str, Any]:
    wanted = str(code).upper()
    for preset in TEST_PRESETS:
        if preset["code"] == wanted:
            return dict(preset)
    raise NotFoundError("Preset not found.", code="PRESET_NOT_FOUND")


@dataclass(slots=True)
class TestLabResult:
    """One generated plate plus the context the admin needs to judge it."""

    generated: GeneratedPlate
    plate_id: int | None
    created: bool
    mode: str
    granted: bool = False
    is_duplicate: bool = False
    is_first_discovery: bool = False
    flags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        plate = self.generated
        return {
            "mode": self.mode,
            "plate_id": self.plate_id,
            "created": self.created,
            "granted": self.granted,
            "is_duplicate": self.is_duplicate,
            "is_first_discovery": self.is_first_discovery,
            "plate": {
                "id": self.plate_id,
                "kind": plate.kind.value,
                "plate_text": plate.plate_text,
                "normalized_text": plate.normalized_text,
                "display_segments": list(plate.display_segments),
                "country_code": plate.country.code,
                "country_flag": self.flags.get(plate.country.code, ""),
                "region_code": plate.region_code,
                "template_code": plate.template_code,
                "template_pattern": plate.template_pattern,
                "plate_type": plate.plate_type,
                "rarity": plate.rarity.value,
                "natural_rarity": plate.natural_rarity.value,
                "luck_rarity": plate.luck_rarity.value,
                "rarity_score": int(plate.rarity_score),
                "collector_value": int(plate.collector_value),
                "dealer_value": int(plate.dealer_value),
                "currency_code": plate.currency_code,
                "currency_symbol": plate.currency_symbol,
                "traits": list(plate.analysis.traits),
                "tags": list(plate.analysis.tags),
                "digits": list(plate.analysis.digits),
                "letters": list(plate.analysis.letters),
                "numeric_core": plate.analysis.numeric_core,
                "is_secret": bool(plate.is_secret),
                # Kind-specific payload: the SIM card's operator, series, edition and
                # the synthetic number printed on it. Empty for a vehicle plate.
                "details": dict(plate.details or {}),
            },
        }


class TestLabService:
    """Generates plates for internal testing - simulation or live."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.plates = PlateService(db)
        self.economy = EconomyService(db)
        self.progression = ProgressionService(db)

    # --- catalogue helpers ----------------------------------------------
    def context(self) -> GenerationContext:
        """A private, per-call snapshot: no shared mutable generation state."""
        return build_snapshot(self.db, self.settings.rarity_weights).context

    def flags(self) -> dict[str, str]:
        return {str(code): str(flag) for code, flag in self.db.execute(select(Country.code, Country.flag)).all()}

    def countries(self) -> list[dict[str, object]]:
        rows = self.db.execute(
            select(Country).where(Country.is_active.is_(True)).order_by(Country.sort_order, Country.id)
        ).scalars()
        template_counts = {
            int(country_id): int(count)
            for country_id, count in self.db.execute(
                select(PlateTemplate.country_id, func.count(func.distinct(PlateTemplate.code)))
                .where(PlateTemplate.is_active.is_(True))
                .group_by(PlateTemplate.country_id)
            ).all()
        }
        return [
            {
                "code": country.code,
                "iso_alpha2": country.iso_alpha2 or "",
                "flag": country.flag,
                "name_en": country.name_en,
                "name_ru": country.name_ru,
                "region_group": country.region_group,
                "calling_code": (country.sim_config or {}).get("calling_code", ""),
                "is_playable": bool(country.is_playable),
                "templates": template_counts.get(int(country.id), 0),
            }
            for country in rows
        ]

    def country(self, code: str) -> Country:
        country = self.db.execute(select(Country).where(Country.code == str(code).upper())).scalar_one_or_none()
        if country is None:
            raise NotFoundError("Country not found.", code="COUNTRY_NOT_FOUND")
        return country

    def presets(self) -> list[dict[str, Any]]:
        return [dict(preset) for preset in TEST_PRESETS]

    def rarities(self) -> list[str]:
        return [rarity.value for rarity in RARITY_ORDER]

    def categories(self) -> list[dict[str, object]]:
        """The collectible kinds, straight from the domain module.

        The panel builds its menu from this list, so a new kind appears in the test
        lab without a bot release.
        """
        return [
            {
                "code": kind.value,
                "label": CATEGORY_LABELS.get(kind, kind.value),
                "emoji": CATEGORY_EMOJI.get(kind, "\U0001F4E6"),
            }
            for kind in KINDS
        ]

    # --- generation ------------------------------------------------------
    def generate(
        self,
        *,
        country_code: str | None = None,
        region_code: str | None = None,
        template_code: str | None = None,
        kind: str | None = None,
        rarity: str | None = None,
        preset: str | None = None,
        require_trait: str | None = None,
    ) -> TestLabResult:
        """Build a collectible without touching a single row."""
        if preset:
            definition = preset_by_code(preset)
            country_code = country_code or definition.get("country_code")
            rarity = rarity or definition.get("rarity")
            kind = kind or definition.get("kind")
            require_trait = require_trait or definition.get("require_trait")

        if require_trait and not country_code:
            country_code = DEFAULT_TRAIT_COUNTRY

        target = Rarity(str(rarity).upper()) if rarity else None
        wanted = normalize_kind(kind)
        if kind and wanted is None:
            raise ValidationError(f"Unknown collectible kind: {kind!r}.", code="BAD_CATEGORY")

        ctx = self.context()
        # Local event multipliers only; nothing global is written.
        ctx.event_multipliers = {}
        if wanted is not None:
            narrowed = self._narrow(ctx, wanted, country_code, template_code)
            if narrowed is None:
                raise ValidationError(
                    f"{country_code or 'This country'} has no {wanted.value} layout yet.",
                    code="BAD_CATEGORY",
                )
            ctx = narrowed

        generator = PlateGenerator(ctx, default_rng())
        generated = generator.generate_targeted(
            country_code=country_code,
            region_code=region_code,
            template_code=template_code,
            luck=target or Rarity.COMMON,
            target_rarity=target,
            require_trait=require_trait,
        )
        return TestLabResult(
            generated=generated,
            plate_id=None,
            created=False,
            mode="SIMULATION",
            flags=self.flags(),
        )

    def _narrow(
        self,
        ctx: GenerationContext,
        kind: CollectibleKind,
        country_code: str | None,
        template_code: str | None,
    ) -> GenerationContext | None:
        """Restrict a private snapshot to one collectible kind.

        The same narrowing the roll does, applied to a throw-away context: the
        production RNG and the production pool are never modified.
        """
        wanted_types = plate_types_for(kind)
        countries = tuple(
            country
            for country in ctx.countries
            if country_code is None or country.code == str(country_code).upper()
        )
        if not countries:
            return None
        templates: dict[str, tuple[TemplateOption, ...]] = {}
        for country in countries:
            options = tuple(
                option
                for option in ctx.templates_by_country.get(country.code, ())
                if (option.plate_type or "").upper() in wanted_types
            )
            if template_code:
                options = tuple(option for option in options if option.code == template_code)
            if options:
                templates[country.code] = options
        usable = tuple(country for country in countries if templates.get(country.code))
        if not usable:
            return None
        return replace(ctx, countries=usable, templates_by_country=templates)

    # --- simulation ------------------------------------------------------
    def simulate(
        self,
        *,
        country_code: str | None = None,
        region_code: str | None = None,
        template_code: str | None = None,
        kind: str | None = None,
        rarity: str | None = None,
        preset: str | None = None,
        require_trait: str | None = None,
    ) -> dict[str, object]:
        """Read-only roll preview. Never writes, never spends a roll."""
        result = self.generate(
            country_code=country_code,
            region_code=region_code,
            template_code=template_code,
            kind=kind,
            rarity=rarity,
            preset=preset,
            require_trait=require_trait,
        )
        payload = result.to_dict()
        payload["mutated"] = False
        payload["spent_roll"] = False
        return payload

    # --- live ------------------------------------------------------------
    def live_roll(
        self,
        user: User,
        *,
        country_code: str | None = None,
        region_code: str | None = None,
        template_code: str | None = None,
        kind: str | None = None,
        rarity: str | None = None,
        preset: str | None = None,
        require_trait: str | None = None,
        mark_first_discovery: bool = False,
    ) -> dict[str, object]:
        """Perform a real roll *for* one player, admin source, fully audited.

        The daily allowance is intentionally left alone: the admin does not spend
        the player's rolls, the plate is simply created and granted.
        """
        with user_lock(user.id, "testlab"):
            generated = self.generate(
                country_code=country_code,
                region_code=region_code,
                template_code=template_code,
                kind=kind,
                rarity=rarity,
                preset=preset,
                require_trait=require_trait,
            ).generated

            plate, created = self.plates.materialize(generated)
            grant = self.plates.grant(plate, user)
            is_first = self.plates.record_discovery(plate, user, source="ADMIN")

            if mark_first_discovery and not is_first:
                override = self.plates.set_first_discoverer(plate, user, source="ADMIN", override=True)
                is_first = bool(override.get("changed"))

            self._update_user_best(user, plate)
            self.progression.recompute_counters(user)
            self.db.commit()

            payload = TestLabResult(
                generated=generated,
                plate_id=plate.id,
                created=created,
                mode="LIVE",
                granted=True,
                is_duplicate=grant.is_duplicate,
                is_first_discovery=is_first,
                flags=self.flags(),
            ).to_dict()
            payload["mutated"] = True
            payload["spent_roll"] = False
            payload["balance"] = self.economy.balance(user.id)
            payload["plates_count"] = int(user.plates_count)
            payload["first_discoveries_count"] = int(user.first_discoveries_count)
            return payload

    def _update_user_best(self, user: User, plate: Plate) -> None:
        """Keep the cached best-find counters coherent with the new plate."""
        if int(plate.collector_value) > int(user.best_collector_value):
            user.best_collector_value = int(plate.collector_value)
            user.best_plate_id = plate.id
        if int(plate.dealer_value) >= int(user.best_value):
            user.best_value = int(plate.dealer_value)
            user.best_rarity = plate.rarity
        self.db.flush()

    # --- forced plate text ----------------------------------------------
    def force_plate(
        self,
        raw_text: str,
        *,
        country_code: str | None = None,
        rarity: str | None = None,
        grant_to: User | None = None,
        mark_first_discovery: bool = False,
    ) -> dict[str, object]:
        """Materialise a plate the admin typed, e.g. ``A777AA 77``.

        The text is normalised with the engine's Unicode-safe normaliser, matched
        against a real template of the target country (so an impossible format is
        rejected instead of silently inserted), then scored and priced by the same
        code path a real roll uses. Unicode alphabets (Cyrillic, Georgian,
        Armenian, Japanese) survive untouched.
        """
        text = (raw_text or "").strip()
        if not text:
            raise ValidationError("Plate text is empty.", code="PLATE_TEXT_EMPTY")
        if len(text) > 32:
            raise ValidationError("Plate text is too long.", code="PLATE_TEXT_TOO_LONG")

        normalized = normalize_plate(text)
        if not normalized:
            raise ValidationError("Plate text has no usable characters.", code="PLATE_TEXT_INVALID")

        digits, letters = split_plate(text)
        country, template = self._resolve_shape(
            normalized=normalized,
            digit_count=len("".join(digits)),
            letter_count=len("".join(letters)),
            country_code=country_code,
        )

        target = Rarity(str(rarity).upper()) if rarity else None
        ctx = self.context()
        ctx.event_multipliers = {}
        country_def = next((item for item in ctx.countries if item.code == country.code), None)
        if country_def is None:
            raise ValidationError("Country is not available for generation.", code="COUNTRY_INACTIVE")

        template_option = next(
            (item for item in ctx.templates_by_country.get(country.code, ()) if item.code == template.code),
            None,
        )
        if template_option is None:
            raise ValidationError("Template is not active.", code="BAD_PLATE_TEMPLATE")

        display_text = self._render_like_template(text, template_option.pattern)
        styles = styles_for_text(display_text)

        generated = build_generated_plate(
            plate_text=display_text,
            country=country_def,
            region=None,
            template=template_option,
            luck=target or Rarity.COMMON,
            styles=styles,
            force_secret=target is Rarity.SECRET,
        )

        if grant_to is None:
            payload = TestLabResult(
                generated=generated,
                plate_id=None,
                created=False,
                mode="SIMULATION",
                flags=self.flags(),
            ).to_dict()
            payload["mutated"] = False
            payload["spent_roll"] = False
            return payload

        with user_lock(grant_to.id, "testlab"):
            plate, created = self.plates.materialize(generated)
            grant = self.plates.grant(plate, grant_to)
            is_first = self.plates.record_discovery(plate, grant_to, source="ADMIN")
            if mark_first_discovery and not is_first:
                self.plates.set_first_discoverer(plate, grant_to, source="ADMIN", override=True)
                is_first = True
            self._update_user_best(grant_to, plate)
            self.progression.recompute_counters(grant_to)
            self.db.commit()

        payload = TestLabResult(
            generated=generated,
            plate_id=plate.id,
            created=created,
            mode="LIVE",
            granted=True,
            is_duplicate=grant.is_duplicate,
            is_first_discovery=is_first,
            flags=self.flags(),
        ).to_dict()
        payload["mutated"] = True
        payload["spent_roll"] = False
        payload["balance"] = self.economy.balance(grant_to.id)
        payload["plates_count"] = int(grant_to.plates_count)
        return payload

    def _resolve_shape(
        self,
        *,
        normalized: str,
        digit_count: int,
        letter_count: int,
        country_code: str | None,
    ) -> tuple[Country, PlateTemplate]:
        """Find the country/template whose slot layout matches the typed text."""
        countries = (
            [self.country(country_code)]
            if country_code
            else list(
                self.db.execute(
                    select(Country)
                    .where(Country.is_active.is_(True), Country.is_playable.is_(True))
                    .order_by(Country.sort_order, Country.id)
                ).scalars()
            )
        )

        for country in countries:
            for template in self._usable_templates(country):
                parsed = parse_template(template.pattern)
                if parsed.has_region_slot:
                    continue
                if parsed.digit_slots != digit_count or parsed.letter_slots != letter_count:
                    continue
                return country, template

        if country_code:
            # The admin named a country explicitly: keep the text as long as one
            # active template can host it.
            country = self.country(country_code)
            fallback = next(iter(self._usable_templates(country)), None)
            if fallback is None:
                raise ValidationError("This country has no active template.", code="BAD_PLATE_TEMPLATE")
            return country, fallback

        raise ValidationError(
            "That plate text does not match any country template.",
            code="PLATE_SHAPE_MISMATCH",
            details={"normalized": normalized},
        )

    def _usable_templates(self, country: Country) -> list[PlateTemplate]:
        rows = self.db.execute(
            select(PlateTemplate)
            .where(
                PlateTemplate.country_id == country.id,
                PlateTemplate.is_active.is_(True),
            )
            .order_by(PlateTemplate.sort_order, PlateTemplate.id)
        ).scalars()
        usable: list[PlateTemplate] = []
        for template in rows:
            try:
                parse_template(template.pattern)
            except ValidationError:
                continue
            usable.append(template)
        return usable

    def _render_like_template(self, text: str, pattern: str) -> str:
        """Re-apply the separators a template implies, keeping typed characters."""
        separators = [part.text.strip() for part in parse_template(pattern).parts if part.is_literal()]
        body = " ".join(normalize_plate(text).split())
        separators = [item for item in separators if item]
        if not separators or not body:
            return body
        chunks = body.split(" ")
        rebuilt = chunks[0]
        for index, separator in enumerate(separators):
            if index < len(chunks) - 1:
                rebuilt += f"{separator}{chunks[index + 1]}"
        return rebuilt.strip()

    # --- inspection -------------------------------------------------------
    def plate_detail(self, plate: Plate) -> dict[str, object]:
        discoverer = None
        if plate.first_discovered_by_id:
            user = self.db.get(User, plate.first_discovered_by_id)
            if user is not None:
                discoverer = {
                    "user_id": user.id,
                    "telegram_id": int(user.telegram_id),
                    "username": user.username,
                    "display_name": user.display_name,
                }
        country = self.country(plate.country_code) if plate.country_code else None
        return {
            "id": plate.id,
            "plate_text": plate.plate_text,
            "normalized_text": plate.normalized_text,
            "country_code": plate.country_code,
            "country_flag": country.flag if country else "",
            "region_code": plate.region_code,
            "template_code": plate.template.code if plate.template else "",
            "template_pattern": plate.template.pattern if plate.template else "",
            "rarity": plate.rarity,
            "rarity_score": int(plate.rarity_score),
            "collector_value": int(plate.collector_value),
            "currency_code": plate.currency_code,
            "currency_symbol": plate.currency_symbol,
            "dealer_value": int(plate.dealer_value),
            "discovery_count": int(plate.discovery_count),
            "first_discoverer": discoverer,
            "first_discovered_at": (
                as_aware(plate.first_discovered_at).isoformat() if plate.first_discovered_at else None
            ),
            "season_code": plate.season_code,
            "is_secret": bool(plate.is_secret),
            "plate_type": plate.plate_type,
            "traits": list(plate.traits or []),
            "tags": list(plate.tags or []),
            "owners": self.plates.plate_owners(plate.id, limit=10),
            "history": self.plates.discovery_history(plate.id, limit=10),
        }


__all__ = [
    "DEFAULT_TRAIT_COUNTRY",
    "TEST_PRESETS",
    "TestLabResult",
    "TestLabService",
    "preset_by_code",
]
