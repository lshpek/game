"""User provisioning, profile aggregation and collection queries."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.errors import NotFoundError, ValidationError
from app.core.locks import user_lock
from app.core.security import TelegramUser
from app.core.timeutils import as_aware, utcnow
from app.game.analyzer import normalize_number
from app.game.rarity import RARITY_RANK
from app.game.valuation import duplicate_conversion_reward
from app.models.enums import AnalyticsEventName, TransactionType, UserRole
from app.models.number import Number, UserNumber
from app.models.plates import Plate, PlateDiscovery
from app.models.social import ShareEvent
from app.models.user import User, Wallet
from app.services.analytics import AnalyticsService
from app.services.daily import DailyService
from app.services.economy import EconomyService
from app.services.numbers import NumberService
from app.services.premium import PremiumService

TOTAL_NUMBERS = 10_000


@dataclass(slots=True)
class CollectionPage:
    items: list[dict[str, object]]
    total: int
    page: int
    page_size: int
    has_more: bool


class UserService:
    """Reads and writes user records and their collection views."""

    def __init__(self, db: Session, config: Settings | None = None) -> None:
        self.db = db
        self.settings = config or settings
        self.economy = EconomyService(db)
        self.numbers = NumberService(db)
        self.premium = PremiumService(db, self.settings)
        self.daily = DailyService(db, self.settings)
        self.analytics = AnalyticsService(db)

    # --- provisioning ---------------------------------------------------
    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def require_by_id(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        return user

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.db.execute(select(User).where(User.telegram_id == telegram_id)).scalar_one_or_none()

    def apply_admin_role(self, user: User) -> None:
        """Promote/demote based on the configured admin id list (server side)."""
        user.role = (
            UserRole.ADMIN.value if user.telegram_id in set(self.settings.admin_telegram_ids) else UserRole.USER.value
        )

    def upsert_from_telegram(self, profile: TelegramUser) -> tuple[User, bool]:
        """Create or refresh the local user from verified Telegram data."""
        user = self.get_by_telegram_id(profile.id)
        created = False
        if user is None:
            user = User(
                telegram_id=profile.id,
                role=UserRole.USER.value,
                first_name=profile.first_name,
                last_name=profile.last_name,
                username=profile.username,
                language_code=profile.language_code,
                photo_url=profile.photo_url,
                is_telegram_premium=profile.is_premium,
            )
            self.db.add(user)
            self.db.flush()
            self.db.add(Wallet(user_id=user.id, coins=0, total_earned=0, total_spent=0))
            created = True
        else:
            user.first_name = profile.first_name or user.first_name
            user.last_name = profile.last_name or user.last_name
            user.username = profile.username or user.username
            user.language_code = profile.language_code or user.language_code
            user.photo_url = profile.photo_url or user.photo_url
            user.is_telegram_premium = profile.is_premium

        self.apply_admin_role(user)
        self.db.flush()
        return user, created

    # --- profile --------------------------------------------------------
    def profile(self, user: User) -> dict[str, object]:
        """The full profile the app boots with."""
        from app.models.numora import SupporterEntitlement
        from app.services.cosmetics import CosmeticService
        from app.services.progression import ProgressionService
        from app.services.world import WorldService

        wallet = self.economy.get_wallet(user.id)
        allowance = self.daily.status(user)
        expires_at = self.premium.expires_at(user.id)
        level = ProgressionService(self.db).current_level(user)

        # Recount so the profile is always accurate, even after a direct write.
        ProgressionService(self.db).recompute_counters(user)
        first_discoveries = int(
            self.db.execute(
                select(func.count(func.distinct(PlateDiscovery.plate_id))).where(
                    PlateDiscovery.user_id == user.id,
                    PlateDiscovery.is_first_discovery.is_(True),
                )
            ).scalar_one()
            or 0
        )
        user.first_discoveries_count = first_discoveries

        best_plate = self.db.get(Plate, user.best_plate_id) if user.best_plate_id else None
        overview = WorldService(self.db, self.settings.rarity_weights).overview(user)
        supporter = (
            self.db.execute(
                select(func.count(SupporterEntitlement.id)).where(
                    SupporterEntitlement.user_id == user.id,
                    SupporterEntitlement.is_active.is_(True),
                )
            ).scalar_one()
            or 0
        ) > 0
        self.db.flush()

        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
            "language_code": user.language_code,
            "role": user.role,
            "is_admin": user.is_admin,
            "is_banned": bool(user.is_banned),
            # --- economy: the user-facing name is NUMORA
            "coins": int(wallet.coins),
            "total_earned": int(wallet.total_earned),
            "total_spent": int(wallet.total_spent),
            # --- activity
            "total_rolls": int(user.total_rolls),
            "containers_opened": int(user.containers_opened),
            # --- collection
            "plates_count": int(user.plates_count),
            "countries_count": int(user.countries_count),
            "regions_count": int(user.regions_count),
            "first_discoveries_count": first_discoveries,
            "duplicates_sold_count": int(user.duplicates_sold_count),
            "collection_progress": float(overview["progress"]),
            "collection_target": int(overview["total_plates"]),
            "collector_level": level.to_dict(),
            # --- best find
            "best_value": int(user.best_value),
            "best_rarity": user.best_rarity or None,
            "best_collector_value": int(user.best_collector_value),
            "best_plate_id": user.best_plate_id,
            "best_plate_text": best_plate.plate_text if best_plate is not None else "",
            # --- social
            "referrals_count": int(user.referrals_count),
            "shares_count": int(user.shares_count),
            "challenges_completed": int(user.challenges_completed),
            # --- daily
            "current_streak": int(user.current_streak),
            "longest_streak": int(user.longest_streak),
            "rolls_remaining": allowance.rolls_remaining,
            "daily_allowance": allowance.daily_allowance,
            "daily_resets_at": allowance.resets_at,
            "can_claim_daily": allowance.can_claim,
            # --- entitlements and cosmetics
            "premium": {
                "active": self.premium.is_premium(user.id),
                "tier": self.premium.active_tier(user.id),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "perks": self.premium.perks(user.id),
            },
            "supporter": supporter,
            "season_pass_active": bool(user.season_pass_active),
            "equipped_title": user.equipped_title,
            "equipped_cosmetics": CosmeticService(self.db).equipped_codes(user.id),
            "created_at": as_aware(user.created_at).isoformat() if user.created_at else None,
            "last_seen_at": as_aware(user.updated_at).isoformat() if user.updated_at else None,
            # --- legacy aliases for older clients
            "unique_numbers": int(user.plates_count),
        }

    def top_items(self, user: User, limit: int = 3) -> dict[str, object]:
        """Rarest and highest-value owned numbers (bounded queries)."""
        rarity_order = RARITY_RANK
        rarest = (
            self.db.execute(
                select(UserNumber, Number)
                .join(Number, Number.id == UserNumber.number_id)
                .where(UserNumber.user_id == user.id)
                .order_by(Number.base_value.desc())
                .limit(limit)
            )
            .all()
        )
        highest = (
            self.db.execute(
                select(UserNumber, Number)
                .join(Number, Number.id == UserNumber.number_id)
                .where(UserNumber.user_id == user.id)
                .order_by(Number.value_int.desc())
                .limit(limit)
            )
            .all()
        )
        return {
            "rarest": [self._serialize_owned(un, number) for un, number in rarest],
            "highest_value": [self._serialize_owned(un, number) for un, number in highest],
            "rarity_rank": dict(rarity_order),
        }

    def _serialize_owned(self, user_number: UserNumber, number: Number) -> dict[str, object]:
        return {
            "number": number.value_str,
            "rarity": number.rarity,
            "value": self.numbers.current_value(number),
            "duplicate_count": int(user_number.duplicate_count),
            "traits": list(number.traits or []),
            "tags": list(number.tags or []),
            "story": number.story,
            "is_special": bool(number.is_special),
            "discovery_count": int(number.discovery_count),
            "acquired_at": as_aware(user_number.first_acquired_at).isoformat()
            if user_number.first_acquired_at
            else None,
        }

    # --- collection -----------------------------------------------------
    def collection(
        self,
        user: User,
        *,
        page: int = 1,
        page_size: int = 30,
        rarity: str | None = None,
        search: str | None = None,
        sort: str = "recent",
        only_duplicates: bool = False,
    ) -> CollectionPage:
        """Paginated, filterable view of the player's numbers."""
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))
        conditions = [UserNumber.user_id == user.id]

        if rarity and rarity.upper() != "ALL":
            conditions.append(Number.rarity == rarity.upper())
        if search:
            cleaned = search.strip()
            if cleaned.isdigit():
                conditions.append(Number.value_str.like(f"%{cleaned.zfill(4)[:4]}%"))
            else:
                conditions.append(
                    or_(
                        Number.story.ilike(f"%{cleaned}%"),
                    )
                )
        if only_duplicates:
            conditions.append(UserNumber.duplicate_count > 0)

        base = (
            select(UserNumber, Number)
            .join(Number, Number.id == UserNumber.number_id)
            .where(*conditions)
        )

        order_by = {
            "recent": UserNumber.first_acquired_at.desc(),
            "value": Number.base_value.desc(),
            "number": Number.value_int.asc(),
            "duplicates": UserNumber.duplicate_count.desc(),
        }.get(sort, UserNumber.first_acquired_at.desc())

        total = int(
            self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one() or 0
        )
        rows = self.db.execute(
            base.order_by(order_by).limit(page_size).offset((page - 1) * page_size)
        ).all()

        return CollectionPage(
            items=[self._serialize_owned(un, number) for un, number in rows],
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

    def rarity_breakdown(self, user: User) -> dict[str, int]:
        rows = self.db.execute(
            select(Number.rarity, func.count())
            .join(UserNumber, UserNumber.number_id == Number.id)
            .where(UserNumber.user_id == user.id)
            .group_by(Number.rarity)
        ).all()
        breakdown = dict.fromkeys(RARITY_RANK, 0)
        for rarity, count in rows:
            breakdown[str(rarity)] = int(count)
        return breakdown

    def number_detail(self, user: User, raw: str) -> dict[str, object]:
        value = normalize_number(raw)
        number = self.numbers.get_by_value(value)
        if number is None:
            # Not discovered by anyone yet - describe it from the rules engine.
            from app.game.analyzer import analyze
            from app.game.story import build_story
            from app.game.valuation import compute_value

            analysis = analyze(value)
            return {
                "number": value,
                "rarity": analysis.rarity.value,
                "value": compute_value(analysis.rarity, analysis.traits, value, 0),
                "traits": list(analysis.traits),
                "tags": list(analysis.tags),
                "story": build_story(analysis),
                "is_special": analysis.is_special,
                "discovery_count": 0,
                "owned": False,
                "duplicate_count": 0,
                "undiscovered": True,
            }

        owned = self.numbers.get_user_number(user.id, number.id)
        payload = self._serialize_owned(owned, number) if owned else {
            "number": number.value_str,
            "rarity": number.rarity,
            "value": self.numbers.current_value(number),
            "duplicate_count": 0,
            "traits": list(number.traits or []),
            "tags": list(number.tags or []),
            "story": number.story,
            "is_special": bool(number.is_special),
            "discovery_count": int(number.discovery_count),
            "acquired_at": None,
        }
        payload["owned"] = owned is not None
        payload["first_discovered_at"] = (
            as_aware(number.first_discovered_at).isoformat() if number.first_discovered_at else None
        )
        return payload

    # --- duplicates -----------------------------------------------------
    def convert_duplicate(self, user: User, raw: str) -> dict[str, object]:
        """Trade one duplicate copy for COINS (audited in the ledger)."""
        value = normalize_number(raw)
        number = self.numbers.get_by_value(value)
        if number is None:
            raise NotFoundError("Number not found.", code="NUMBER_NOT_FOUND")

        with user_lock(user.id, "duplicate"):
            user_number = self.numbers.get_user_number(user.id, number.id)
            if user_number is None:
                raise ValidationError("You do not own that number.", code="NUMBER_NOT_OWNED")
            if int(user_number.duplicate_count) <= 0:
                raise ValidationError("No duplicates to convert.", code="NO_DUPLICATES")

            base_reward = duplicate_conversion_reward(self.numbers.current_value(number))
            multiplier = self.premium.duplicate_coin_multiplier(user.id)
            reward = round(base_reward * multiplier)

            user_number.duplicate_count = int(user_number.duplicate_count) - 1
            self.numbers.add_coins_earned(user_number, reward)

            tx = self.economy.credit(
                user.id,
                reward,
                TransactionType.DUPLICATE_CONVERSION,
                reference_type="number",
                reference_id=number.value_str,
                meta={"duplicate_count_left": int(user_number.duplicate_count), "multiplier": multiplier},
            )
            self.db.commit()
            return {
                "number": number.value_str,
                "coins_gained": reward,
                "duplicates_left": int(user_number.duplicate_count),
                "balance": int(tx.balance_after),
            }

    def convert_all_duplicates(self, user: User) -> dict[str, object]:
        """Convert every duplicate copy in one audited pass."""
        rows = (
            self.db.execute(
                select(UserNumber, Number)
                .join(Number, Number.id == UserNumber.number_id)
                .where(UserNumber.user_id == user.id, UserNumber.duplicate_count > 0)
            )
            .all()
        )
        if not rows:
            raise ValidationError("No duplicates to convert.", code="NO_DUPLICATES")

        multiplier = self.premium.duplicate_coin_multiplier(user.id)
        total = 0
        converted = 0
        for user_number, number in rows:
            unit = round(duplicate_conversion_reward(self.numbers.current_value(number)) * multiplier)
            amount = unit * int(user_number.duplicate_count)
            converted += int(user_number.duplicate_count)
            user_number.duplicate_count = 0
            self.numbers.add_coins_earned(user_number, amount)
            self.economy.credit(
                user.id,
                amount,
                TransactionType.DUPLICATE_CONVERSION,
                reference_type="number",
                reference_id=number.value_str,
                meta={"converted": converted, "multiplier": multiplier},
            )
            total += amount

        self.db.commit()
        return {
            "coins_gained": total,
            "converted": converted,
            "balance": self.economy.balance(user.id),
        }

    # --- sharing --------------------------------------------------------
    def record_share(self, user: User, raw: str, *, channel: str = "telegram") -> dict[str, object]:
        value = normalize_number(raw)
        number = self.numbers.get_by_value(value)
        if number is None:
            raise NotFoundError("Number not found.", code="NUMBER_NOT_FOUND")

        start_param = f"number_{number.value_str}"
        self.db.add(
            ShareEvent(
                user_id=user.id,
                number_id=number.id,
                channel=channel,
                start_param=start_param,
                created_at=utcnow(),
            )
        )
        user.shares_count = int(user.shares_count) + 1
        self.analytics.track(
            AnalyticsEventName.SHARE.value,
            user_id=user.id,
            telegram_id=user.telegram_id,
            props={"number": number.value_str, "channel": channel},
        )
        self.db.commit()
        return {
            "start_param": start_param,
            "mini_app_link": self.settings.telegram_mini_app_link(start_param),
            "number": number.value_str,
            "rarity": number.rarity,
            "value": self.numbers.current_value(number),
        }
