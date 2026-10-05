"""Plate endpoints: roll, garage, collection, DEALER, WORLD and sharing."""

from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, idempotency_key, rate_limit
from app.api.plate_serializers import plate_card
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.core.timeutils import utcnow
from app.db.session import get_db
from app.game.collectibles import normalize_kind, parse_hunt_filter, plate_types_for
from app.game.plate_rarity import RARITY_RANK
from app.game.roll_reel import build_reel
from app.models.enums import AnalyticsEventName, RollSource, TransactionType
from app.models.plates import Country, Plate, UserPlate
from app.models.social import ShareEvent
from app.models.user import User
from app.schemas.plates import (
    CollectionResponse,
    CountryDetail,
    DealerSaleRequest,
    FavoriteResponse,
    PlateCard,
    PlateRollHistoryItem,
    PlateRollResponse,
    PlateShareView,
    ReelFrame,
    SaleResponse,
    SellAllResponse,
    ShareResponse,
    WorldResponse,
)
from app.services import countries as country_service
from app.services.albums import AlbumService
from app.services.analytics import AnalyticsService
from app.services.catalog import snapshot
from app.services.cosmetics import CosmeticService
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.events import EventService
from app.services.goals import GoalService, country_completion
from app.services.idempotency import IdempotencyService
from app.services.plate_rolls import PlateRollService
from app.services.plates import PlateService
from app.services.premium import PremiumService
from app.services.progression import ProgressionService
from app.services.world import WorldService

router = APIRouter(tags=["plates"])

# Sort keys accepted by the collection endpoint.
SORT_KEYS = ("recent", "value", "rarest", "name", "discovery")

#: Idempotency scope for the per-plate sale. A double tap replays the first result.
SELL_SCOPE = "sell"
#: Idempotency scope for the batch sale.
SELL_ALL_SCOPE = "sell_all"


def _sale_ledger_key(user_id: int, plate_id: int, key: str | None) -> str:
    """Ledger idempotency key for one sale.

    Two independent protections: the client's request key (so a retry is free) and the
    plate itself, so even two *different* keys can never pay out the same physical copy.
    """
    return f"sell:{user_id}:{plate_id}:{key or 'once'}"


def _roll_response(outcome, db: Session, *, reel: list[dict[str, object]] | None = None) -> PlateRollResponse:
    card = plate_card(outcome.plate, user_plate=outcome.user_plate, owned=True, db=db)
    return PlateRollResponse(
        roll_id=outcome.roll.id,
        plate=PlateCard(**card),
        rarity=outcome.plate.rarity,
        natural_rarity=outcome.roll.natural_rarity,
        luck_rarity=outcome.roll.luck_rarity,
        rarity_score=int(outcome.plate.rarity_score),
        is_duplicate=outcome.is_duplicate,
        is_first_discovery=outcome.is_first_discovery,
        is_new_country=outcome.is_new_country,
        is_new_region=outcome.is_new_region,
        numora_awarded=outcome.numora_awarded,
        balance=outcome.balance,
        rolls_remaining=outcome.rolls_remaining,
        sale_value=outcome.sale_value,
        collector_level=outcome.collector_level,
        missions_completed=outcome.missions_completed,
        albums_completed=outcome.albums_completed,
        unlocked_achievements=outcome.unlocked_achievements,
        event=outcome.event,
        replayed=outcome.replayed,
        share_start_param=outcome.share_start_param,
        rolls=outcome.rolls,
        next_target=outcome.next_target,
        reel=[ReelFrame(**frame) for frame in (reel or [])],
        # --- compatibility aliases for the previous number-roll client
        value=outcome.sale_value,
        coins_awarded=outcome.numora_awarded,
        conversion_value=outcome.sale_value,
        number=PlateCard(**card),
    )


@router.post(
    "/roll",
    response_model=PlateRollResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Roll a collectible number - the server decides everything",
)
def perform_roll(
    category: str | None = Query(
        default=None,
        max_length=24,
        description="Optional hunt filter: VEHICLE_PLATE or SIM_CARD.",
    ),
    country_code: str | None = Query(
        default=None,
        max_length=32,
        description=(
            "Optional hunt filter: restrict the roll to one ISO country. "
            "Validated server-side; defaults to the player's active country."
        ),
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    key: str | None = Depends(idempotency_key),
) -> PlateRollResponse:
    """Draw one collectible.

    The client may only narrow the *eligible pool* with ``category`` and
    ``country_code``. Everything that decides the outcome - the serial, the SIM number
    printed on the card, its rarity, its value, whether it is a first discovery,
    whether it is a duplicate and the reward - is computed here. When no country is
    given, the player's active country decides; with none at all, the whole world is
    the pool.
    """
    hunt = parse_hunt_filter(category=category, country_code=country_code)
    hunt["country_code"] = country_service.roll_country(db, user, hunt.get("country_code"))
    service = PlateRollService(db, settings)
    outcome = service.perform_roll(
        user,
        source=RollSource.DAILY,
        idempotency_key=key,
        **hunt,
    )

    # First real roll activates any pending referral (reward paid here only).
    from app.services.referrals import ReferralService

    ReferralService(db, settings).activate(user)
    db.commit()

    # The reel is built *after* the result is committed, from the same catalogue with a
    # separate RNG. Nothing here can influence what the player just won, and nothing here
    # is persisted - see `app.game.roll_reel`.
    reel = build_reel(
        snapshot(db, settings.rarity_weights).context,
        country_code=hunt.get("country_code"),
        kind=hunt.get("category"),
    )
    return _roll_response(outcome, db, reel=reel)


@router.get("/roll/history", response_model=list[PlateRollHistoryItem], summary="Recent rolls")
def roll_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlateRollHistoryItem]:
    rows = PlateRollService(db, settings).history(user.id, limit=limit, offset=offset)
    return [
        PlateRollHistoryItem(
            roll_id=row.id,
            plate_text=row.plate.plate_text if row.plate else "",
            plate_id=row.plate_id,
            country_code=row.plate.country_code if row.plate else "",
            rarity=row.rarity,
            rarity_score=int(row.rarity_score),
            collector_value=int(row.collector_value),
            currency_symbol=row.plate.currency_symbol if row.plate else "",
            dealer_value=int(row.dealer_value),
            is_duplicate=bool(row.is_duplicate),
            is_first_discovery=bool(row.is_first_discovery),
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


def _collection_conditions(
    user: User,
    *,
    country: str | None,
    region: str | None,
    rarity: str | None,
    kind: str | None,
    tag: str | None,
    search: str | None,
    favorite: bool,
    duplicates: bool,
    new_only: bool,
    secret: bool,
    provider: str | None = None,
) -> list:
    """Every collection filter, expressed once so the query stays readable."""
    from app.game.plate_templates import normalize_plate

    conditions = [UserPlate.user_id == user.id]
    if rarity and rarity.upper() != "ALL":
        conditions.append(Plate.rarity == rarity.upper())
    if provider and provider.lower() != "all":
        # The operator a SIM card prints. Matched on the stored provider code inside
        # `plates.details`, which is indexed by country rather than by brand, so this
        # filter narrows an already-country-scoped page instead of the whole world.
        needle = f'%"operator_code":"{provider.lower()}%"'
        conditions.append(cast(Plate.details, String).like(needle))
    if country and country.upper() not in {"ALL", "WORLD"}:
        # Both ISO forms must land on the same rows, so a shared link works even when
        # it carries the two-letter code.
        conditions.append(
            or_(
                Plate.country_code == country.upper(),
                Plate.country_id
                == select(Country.id)
                .where(
                    or_(Country.code == country.upper(), Country.iso_alpha2 == country.upper())
                )
                .scalar_subquery(),
            )
        )
    if region and region.upper() != "ALL":
        conditions.append(Plate.region_code == region.upper())
    if favorite:
        conditions.append(UserPlate.is_favorite.is_(True))
    if duplicates:
        conditions.append(UserPlate.duplicate_count > 0)
    if new_only:
        conditions.append(UserPlate.is_new.is_(True))
    if secret:
        conditions.append(Plate.is_secret.is_(True))
    if kind:
        wanted = normalize_kind(kind)
        if wanted is None:
            raise ValidationError(
                f"Unknown collectible kind: {kind!r}.", code="BAD_CATEGORY"
            )
        conditions.append(
            or_(*[Plate.plate_type == name for name in plate_types_for(wanted)])
        )
    if tag and tag.lower() != "all":
        conditions.append(cast(Plate.tags, sa.String).like(f'%"{tag.lower()}"%'))
    if search:
        normalized = normalize_plate(search)
        compact = normalized.replace(" ", "")
        clauses = [
            Plate.country_code.ilike(f"%{search}%"),
            Plate.region_code.ilike(f"%{search}%"),
            Plate.story.ilike(f"%{search}%"),
        ]
        if normalized:
            # ``normalized_text`` keeps single spaces (``B EI 8938``), while the
            # client may send a spaceless fragment (``BE`` from ``B EI 8938``).
            # Match both the spaced and the compact form so any substring of
            # the visible plate text is found.
            clauses.append(Plate.normalized_text.like(f"%{normalized}%"))
            clauses.append(Plate.plate_text.ilike(f"%{search}%"))
        if compact:
            clauses.append(
                func.replace(Plate.normalized_text, " ", "").like(f"%{compact}%")
            )
        conditions.append(or_(*clauses))
    return conditions


@router.get("/collection", response_model=CollectionResponse, summary="Paginated garage")
def collection(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    country: str | None = Query(default=None, max_length=8),
    region: str | None = Query(default=None, max_length=16),
    rarity: str | None = Query(default=None, max_length=16),
    kind: str | None = Query(
        default=None,
        max_length=24,
        description="Optional filter: VEHICLE_PLATE or SIM_CARD.",
    ),
    tag: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, max_length=48),
    sort: str = Query(default="recent"),
    favorite: bool = Query(default=False),
    duplicates: bool = Query(default=False),
    new_only: bool = Query(default=False),
    secret: bool = Query(default=False),
    provider: str | None = Query(
        default=None,
        max_length=48,
        description="Filter SIM cards by the operator brand printed on them.",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionResponse:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 100))
    # Without an explicit country the collection follows the player's active country,
    # so the screen matches what the roll is actually producing.
    effective_country = country
    if not effective_country and user.active_country_code:
        active = country_service.active_country(db, user)
        effective_country = active.code if active else None
    conditions = _collection_conditions(
        user,
        country=effective_country,
        region=region,
        rarity=rarity,
        kind=kind,
        tag=tag,
        search=search,
        favorite=favorite,
        duplicates=duplicates,
        new_only=new_only,
        secret=secret,
        provider=provider,
    )

    base = select(UserPlate, Plate).join(Plate, Plate.id == UserPlate.plate_id).where(*conditions)
    total = int(
        db.execute(select(func.count()).select_from(base.subquery())).scalar_one() or 0
    )

    order_by = {
        "recent": UserPlate.last_acquired_at.desc(),
        "value": Plate.collector_value.desc(),
        "rarest": Plate.rarity_score.desc(),
        "name": Plate.plate_text.asc(),
        "discovery": Plate.discovery_count.desc(),
    }.get(sort, UserPlate.last_acquired_at.desc())

    rows = db.execute(
        base.order_by(order_by).limit(page_size).offset((page - 1) * page_size)
    ).all()

    breakdown_rows = db.execute(
        select(Plate.rarity, func.count(func.distinct(UserPlate.plate_id)))
        .join(UserPlate, UserPlate.plate_id == Plate.id)
        .where(UserPlate.user_id == user.id)
        .group_by(Plate.rarity)
    ).all()
    breakdown = dict.fromkeys(RARITY_RANK, 0)
    for code, count in breakdown_rows:
        breakdown[code] = int(count)

    stats = db.execute(
        select(
            func.count(UserPlate.duplicate_count).filter(UserPlate.duplicate_count > 0),
            func.coalesce(func.sum(UserPlate.duplicate_count), 0),
        ).where(UserPlate.user_id == user.id)
    ).one()
    duplicates_count = int(stats[0] or 0)
    duplicate_copies = int(stats[1] or 0)

    total_dealer = int(
        db.execute(
            select(func.coalesce(func.sum(Plate.dealer_value), 0))
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user.id)
        ).scalar_one()
        or 0
    )

    world = WorldService(db, settings.rarity_weights)
    overview = world.overview(user)

    return CollectionResponse(
        items=[
            PlateCard(**plate_card(plate, user_plate=owned, db=db)) for owned, plate in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
        rarity_breakdown=breakdown,
        progress=float(overview["progress"]),
        target=int(overview["total_plates"]),
        duplicates_count=duplicates_count,
        total_dealer_value=total_dealer + duplicate_copies,
        # Echoed so the UI can label the screen without a second request.
        country_code=effective_country,
    )


@router.get("/plates/{plate_id}", response_model=PlateShareView, summary="Plate detail")
def plate_detail(
    plate_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlateShareView:
    service = PlateService(db)
    plate = service.require_plate(plate_id)
    owned = service.get_user_plate(user.id, plate.id)
    if owned is not None:
        # Opening a plate clears its NEW badge.
        service.mark_seen(owned)
        db.commit()
    AnalyticsService(db).track(
        AnalyticsEventName.COUNTRY_OPENED.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"plate_id": plate.id, "country": plate.country_code},
    )
    db.commit()
    return PlateShareView(
        plate=PlateCard(**plate_card(plate, user_plate=owned, db=db)),
        discoverer=plate_card(plate, db=db).get("first_discoverer"),  # type: ignore[arg-type]
        is_owned=owned is not None,
        start_param=f"plate_{plate.id}",
    )


@router.get("/garage", summary="Garage hero: best plate, recent find and progress")
def garage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Everything the home screen shows, in one request."""
    best_owned = (
        db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user.id)
            .order_by(Plate.rarity_score.desc(), Plate.collector_value.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    recent = (
        db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user.id)
            .order_by(UserPlate.last_acquired_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    world = WorldService(db, settings.rarity_weights)
    # Aggregates only: the home screen needs the totals, not the atlas, and building
    # 60 country cards on every app open is the one thing that made this endpoint
    # expensive once the catalogue grew to the full ISO list.
    economy = world.economy_context(user)
    level = ProgressionService(db).current_level(user)
    event = EventService(db).serialize()
    goals = GoalService(db)
    hunt_country = country_service.active_country(db, user)

    return {
        "best": PlateCard(**plate_card(best_owned, db=db)) if best_owned is not None else None,
        "recent": PlateCard(**plate_card(recent, db=db)) if recent is not None else None,
        "plates_count": int(user.plates_count),
        "countries_count": int(user.countries_count),
        "regions_count": int(user.regions_count),
        "first_discoveries": int(user.first_discoveries_count),
        "best_collector_value": int(user.best_collector_value),
        "world_progress": economy["progress"],
        # The world target, sent rather than reconstructed by the client from the
        # progress fraction.
        "collection_target": int(economy["total_plates"]),
        "playable_countries": int(economy["playable_total"]),
        "locked_countries": int(economy["locked_total"]),
        "total_dealer_value": int(economy["total_dealer_value"]),
        "level": level.to_dict(),
        "event": event,
        # The hunt the player is currently in, so the home screen can say
        # "I'm going to hunt Japan" without a second request.
        "hunt_country": hunt_country.code if hunt_country else None,
        "hunt_country_name_en": hunt_country.name_en if hunt_country else "",
        "hunt_country_name_ru": hunt_country.name_ru if hunt_country else "",
        "hunt_country_flag": hunt_country.flag if hunt_country else "",
        "country_progress": (
            country_completion(db, user, hunt_country) if hunt_country is not None else None
        ),
        # Exactly one objective, so the player is never left without a next step.
        "next_target": goals.next_target(user),
        # The authoritative roll economy, including the regeneration countdown.
        "rolls": DailyService(db, settings).sync(user).to_dict(),
        "albums_completed": [
            item for item in AlbumService(db).progress_for_user(user) if item["completed"]
        ],
        "equipped_cosmetics": CosmeticService(db).equipped_codes(user.id),
    }


@router.get("/world", response_model=WorldResponse, summary="World atlas overview")
def world_overview(
    limit: int = Query(default=60, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldResponse:
    """The atlas, one page at a time.

    The full ISO 3166-1 list is ~250 entries, so the screen pages through them
    instead of shipping the whole world in every response. ``total_plates`` and
    ``progress`` stay global, so the header never depends on the current page.
    """
    overview = WorldService(db, settings.rarity_weights).overview(
        user, limit=limit, offset=offset
    )
    event = EventService(db).serialize()
    AnalyticsService(db).track(
        AnalyticsEventName.APP_OPEN.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"screen": "world"},
    )
    db.commit()
    return WorldResponse(**overview, event=event)


@router.get("/world/{country_code}", response_model=CountryDetail, summary="Country detail")
def country_detail(
    country_code: str = Path(min_length=2, max_length=4),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CountryDetail:
    payload = WorldService(db, settings.rarity_weights).country_detail(user, country_code)
    AnalyticsService(db).track(
        AnalyticsEventName.COUNTRY_OPENED.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"screen": "country", "country": country_code.upper()},
    )
    db.commit()
    return CountryDetail(**payload)


@router.post(
    "/plates/{plate_id}/sell",
    response_model=SaleResponse,
    dependencies=[Depends(rate_limit("sell", "rate_limit_sell"))],
    summary="Sell duplicate copies to the DEALER",
)
def sell_duplicate(
    payload: DealerSaleRequest,
    plate_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    key: str | None = Depends(idempotency_key),
) -> SaleResponse:
    """Sell copies of a plate the player already owns.

    Three guarantees, all server-side:

    * **Duplicates only.** The final copy is protected unless the client explicitly opts
      in, so a stray tap can never destroy a collection entry.
    * **No silent clamping.** Asking for more copies than exist is *rejected*, not
      quietly reduced - a client that miscounts must see the error rather than sell a
      different amount than the player asked for.
    * **Idempotent.** A double tap, a retry or a flaky connection replays the first
      result instead of paying twice.
    """
    from app.core.locks import user_lock

    service = PlateService(db)
    replay = IdempotencyService(db)
    with user_lock(user.id):
        stored = replay.get(user.id, SELL_SCOPE, key)
        if stored:
            try:
                return SaleResponse(**stored)
            except TypeError:  # pragma: no cover - a stale record must not block a sale
                pass

        owned = service.get_user_plate(user.id, plate_id)
        if owned is None:
            raise NotFoundError("You do not own this plate.", code="PLATE_NOT_OWNED")

        premium = PremiumService(db, settings)
        sellable = service.sellable_copies(owned, allow_last=payload.allow_last)
        if sellable <= 0:
            # No duplicates: the UI must not offer an active SELL button for this case,
            # and a request that does anyway is a clear, explainable refusal.
            raise ValidationError(
                "You only own the original copy - there is nothing to sell.",
                code="NO_DUPLICATES",
                details={"duplicate_count": int(owned.duplicate_count)},
            )
        if int(payload.copies) > sellable:
            raise ValidationError(
                f"Only {sellable} duplicate cop{'y' if sellable == 1 else 'ies'} available.",
                code="NOT_ENOUGH_DUPLICATES",
                details={"sellable": sellable, "requested": int(payload.copies)},
            )
        copies = int(payload.copies)

        amount = service.apply_sale(
            owned,
            copies=copies,
            premium_multiplier=premium.duplicate_coin_multiplier(user.id),
            allow_last=payload.allow_last,
        )
        tx = EconomyService(db).credit(
            user.id,
            amount,
            TransactionType.DUPLICATE_CONVERSION,
            reference_type="plate",
            reference_id=str(plate_id),
            idempotency_key=_sale_ledger_key(user.id, plate_id, key),
            meta={"copies": copies, "plate": owned.plate.plate_text},
        )
        user.duplicates_sold_count = int(user.duplicates_sold_count) + copies
        response = SaleResponse(
            plate_id=plate_id,
            plate_text=owned.plate.plate_text,
            copies_sold=copies,
            numora_gained=amount,
            duplicates_left=int(owned.duplicate_count),
            balance=int(tx.balance_after),
        )
        AnalyticsService(db).track(
            AnalyticsEventName.SELL_COMPLETED,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={"plate_id": plate_id, "copies": copies, "numora": amount},
        )
        replay.remember(user.id, SELL_SCOPE, key, response.model_dump())
        db.commit()
        return response


@router.post(
    "/collection/sell-duplicates",
    response_model=SellAllResponse,
    dependencies=[Depends(rate_limit("sell", "rate_limit_sell"))],
    summary="Sell every spare duplicate copy at once",
)
def sell_all_duplicates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    key: str | None = Depends(idempotency_key),
) -> SellAllResponse:
    """Batch sale. Only spare copies are touched - the last one is protected."""
    from app.core.locks import user_lock

    service = PlateService(db)
    with user_lock(user.id):
        replay = IdempotencyService(db)
        stored = replay.get(user.id, SELL_ALL_SCOPE, key)
        if stored:
            try:
                return SellAllResponse(**stored)
            except TypeError:  # pragma: no cover
                pass

        premium = PremiumService(db, settings)
        economy = EconomyService(db)
        multiplier = premium.duplicate_coin_multiplier(user.id)

        rows = (
            db.execute(
                select(UserPlate)
                .where(UserPlate.user_id == user.id, UserPlate.duplicate_count > 0)
                .order_by(UserPlate.id)
            )
            .scalars()
            .all()
        )
        if not rows:
            raise ValidationError("You have no duplicates to sell.", code="NO_DUPLICATES")

        total = 0
        copies_total = 0
        plates_sold = 0
        for owned in rows:
            copies = int(owned.duplicate_count)
            amount = service.apply_sale(owned, copies=copies, premium_multiplier=multiplier)
            economy.credit(
                user.id,
                amount,
                TransactionType.DUPLICATE_CONVERSION,
                reference_type="plate",
                reference_id=str(owned.plate_id),
                # Keyed by the plate so a retried batch can never pay the same plate twice.
                idempotency_key=f"sell_all:{user.id}:{owned.plate_id}:{key or 'batch'}",
                meta={"copies": copies, "batch": True, "plate": owned.plate.plate_text},
            )
            total += amount
            copies_total += copies
            plates_sold += 1

        user.duplicates_sold_count = int(user.duplicates_sold_count) + copies_total
        response = SellAllResponse(
            plates_sold=plates_sold,
            copies_sold=copies_total,
            numora_gained=total,
            balance=economy.balance(user.id),
        )
        AnalyticsService(db).track(
            AnalyticsEventName.SELL_COMPLETED,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={
                "plates": plates_sold,
                "copies": copies_total,
                "numora": total,
                "batch": True,
            },
        )
        if key:
            replay.remember(user.id, SELL_ALL_SCOPE, key, response.model_dump())
        db.commit()
        return response


@router.post(
    "/plates/{plate_id}/favorite",
    response_model=FavoriteResponse,
    dependencies=[Depends(rate_limit("roll", "rate_limit_roll"))],
    summary="Toggle the favourite flag",
)
def toggle_favorite(
    plate_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteResponse:
    service = PlateService(db)
    owned = service.get_user_plate(user.id, plate_id)
    if owned is None:
        raise NotFoundError("You do not own this plate.", code="PLATE_NOT_OWNED")
    is_favorite = service.toggle_favorite(owned)
    AnalyticsService(db).track(
        AnalyticsEventName.PLATE_FAVORITED.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"plate_id": plate_id, "favorite": is_favorite},
    )
    db.commit()
    return FavoriteResponse(plate_id=plate_id, is_favorite=is_favorite)


@router.post(
    "/plates/{plate_id}/share",
    response_model=ShareResponse,
    dependencies=[Depends(rate_limit("share", "rate_limit_default"))],
    summary="Record a share and return the deep link",
)
def share_plate(
    plate_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareResponse:
    """Build a share link for a plate the player owns.

    The deep link carries an *encoded plate id*, never raw plate text, so a
    recipient cannot be sent arbitrary content.
    """
    service = PlateService(db)
    owned = service.get_user_plate(user.id, plate_id)
    if owned is None:
        raise NotFoundError("You do not own this plate.", code="PLATE_NOT_OWNED")

    plate = owned.plate
    start_param = f"plate_{plate.id}"
    db.add(
        ShareEvent(
            user_id=user.id,
            number_id=None,
            channel="telegram",
            start_param=start_param,
            created_at=utcnow(),
        )
    )
    user.shares_count = int(user.shares_count) + 1
    AnalyticsService(db).track(
        AnalyticsEventName.SHARE_CLICKED.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={
            "plate_id": plate.id,
            "country": plate.country_code,
            "rarity": plate.rarity,
            "score": int(plate.rarity_score),
        },
    )
    db.commit()

    country_name = plate.country.name_en if plate.country else ""
    region_name = plate.region.name_en if plate.region else ""
    # Share copy is built server-side so both languages stay in sync and the
    # client never assembles product text.
    nl = "\n"
    share_en = (
        f"NUMORA{nl}{plate.country.flag if plate.country else ''} {country_name.upper()}{nl}"
        f"{region_name}{nl}{nl}{plate.plate_text}{nl}{plate.rarity}{nl}"
        f"Collector Value: {plate.currency_symbol}{plate.collector_value:,}{nl}"
        f"Dealer: +{plate.dealer_value:,} NUMORA{nl}{nl}Can you beat this?"
    )
    share_ru = (
        f"NUMORA{nl}{plate.country.flag if plate.country else ''} {country_name.upper()}{nl}"
        f"{region_name}{nl}{nl}{plate.plate_text}{nl}{plate.rarity}{nl}"
        f"Коллекционная ценность: {plate.currency_symbol}{plate.collector_value:,}{nl}"
        f"Дилер: +{plate.dealer_value:,} NUMORA{nl}{nl}Сможешь лучше?"
    )

    return ShareResponse(
        plate_id=plate.id,
        plate_text=plate.plate_text,
        rarity=plate.rarity,
        rarity_score=int(plate.rarity_score),
        collector_value=int(plate.collector_value),
        currency_symbol=plate.currency_symbol,
        dealer_value=int(plate.dealer_value),
        start_param=start_param,
        mini_app_link=settings.telegram_mini_app_link(start_param),
        share_text_en=share_en,
        share_text_ru=share_ru,
    )


@router.get("/albums", summary="Album (collection set) progress")
def albums(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return AlbumService(db).progress_for_user(user)


@router.get("/event", summary="The currently active global event")
def event(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return EventService(db).serialize()
