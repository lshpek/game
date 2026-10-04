"""Read models for the admin control surfaces.

Dashboard, user lookup, ledger, catalogue, leaderboards, analytics, system
health and the audit viewer. Every query here is bounded and aggregate-only -
nothing in this module ever writes.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select

from app import __version__
from app.core.errors import ValidationError
from app.core.logging import error_buffer
from app.core.timeutils import as_aware, start_of_utc_day, utcnow
from app.game.plate_rarity import RARITY_RANK, Rarity, rarity_case
from app.models.admin import AdminAuditLog
from app.models.enums import PaymentStatus
from app.models.numora import GameEvent, PlateRoll
from app.models.payment import Payment, PremiumEntitlement
from app.models.plates import Country, Plate, PlateDiscovery, PlateTemplate, Region, UserPlate
from app.models.user import User, Wallet, WalletTransaction
from app.services.admin_base import (
    ANALYTICS_PERIODS,
    AdminServiceBase,
    _fingerprint,
    _flow_sum,
    _name_conditions,
    _short,
)
from app.services.leaderboards import periods

__all__ = ["AdminReadsMixin"]


def _plate_text_like(term: str):
    """Case-insensitive ``contains`` over both the display and the normalised form.

    Both sides are pushed through the same normaliser the catalogue uses, because
    a pasted plate routinely differs from the stored one by a non-breaking space or
    a different separator - and SQLite's ``upper()`` is ASCII-only, so Cyrillic and
    Georgian plates would otherwise never match. Normalising both sides makes the
    comparison script-agnostic instead of a coin toss.
    """
    from app.game.plate_templates import normalize_plate

    variants = {term.strip(), normalize_plate(term)}
    variants = {value for value in variants if value}
    if not variants:  # pragma: no cover - guarded by the caller
        variants = {term}
    clauses = []
    for value in variants:
        pattern = f"%{value}%"
        clauses.append(Plate.normalized_text.ilike(pattern))
        clauses.append(Plate.plate_text.ilike(pattern))
    return or_(*clauses)


class AdminReadsMixin(AdminServiceBase):
    """Read-only views used by every control-surface screen."""

    # reads
    # ==================================================================
    def dashboard(self) -> dict[str, Any]:
        """Live control-centre snapshot."""
        today = start_of_utc_day()
        db = self.db

        users_total = int(db.execute(select(func.count()).select_from(User)).scalar_one() or 0)
        users_new_today = int(
            db.execute(select(func.count()).select_from(User).where(User.created_at >= today)).scalar_one() or 0
        )
        users_active_today = int(
            db.execute(
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .where(or_(User.last_roll_at >= today, User.updated_at >= today))
            ).scalar_one()
            or 0
        )

        rolls_total = int(db.execute(select(func.count()).select_from(PlateRoll)).scalar_one() or 0)
        rolls_today = int(
            db.execute(select(func.count()).select_from(PlateRoll).where(PlateRoll.created_at >= today)).scalar_one()
            or 0
        )

        plates_total = int(db.execute(select(func.count()).select_from(Plate)).scalar_one() or 0)
        countries_in_play = int(db.execute(select(func.count(func.distinct(Plate.country_id)))).scalar_one() or 0)
        first_discoveries = int(
            db.execute(
                select(func.count()).select_from(PlateDiscovery).where(PlateDiscovery.is_first_discovery.is_(True))
            ).scalar_one()
            or 0
        )

        circulation = int(db.execute(select(func.coalesce(func.sum(Wallet.coins), 0))).scalar_one() or 0)
        issued_today = int(
            db.execute(
                select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                    WalletTransaction.created_at >= today, WalletTransaction.amount > 0
                )
            ).scalar_one()
            or 0
        )
        spent_today = int(
            db.execute(
                select(func.coalesce(func.sum(-WalletTransaction.amount), 0)).where(
                    WalletTransaction.created_at >= today, WalletTransaction.amount < 0
                )
            ).scalar_one()
            or 0
        )

        payments_paid = int(
            db.execute(
                select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.PAID.value)
            ).scalar_one()
            or 0
        )
        stars_revenue = int(
            db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == PaymentStatus.PAID.value)
            ).scalar_one()
            or 0
        )
        now = utcnow()
        pro_active = int(
            db.execute(
                select(func.count(func.distinct(PremiumEntitlement.user_id))).where(
                    PremiumEntitlement.is_active.is_(True),
                    PremiumEntitlement.expires_at.isnot(None),
                    PremiumEntitlement.expires_at > now,
                )
            ).scalar_one()
            or 0
        )

        season = self.season_service.active()
        event = self.event_service.active()
        errors = error_buffer.snapshot(50)

        return {
            "generated_at": utcnow().isoformat(),
            "users": {
                "total": users_total,
                "new_today": users_new_today,
                "active_today": users_active_today,
            },
            "rolls": {"total": rolls_total, "today": rolls_today},
            "collection": {
                "plates": plates_total,
                "countries": countries_in_play,
                "first_discoveries": first_discoveries,
            },
            "economy": {
                "circulation": circulation,
                "issued_today": issued_today,
                "spent_today": spent_today,
            },
            "monetization": {
                "paid_purchases": payments_paid,
                "stars_revenue": stars_revenue,
                "pro_active": pro_active,
            },
            "season": {
                "code": season.code if season else None,
                "name": season.name if season else None,
                "is_active": bool(season),
                "event_code": event.code,
                "event_name": event.name_ru,
                "event_ends_at": event.to_dict().get("ends_at"),
            },
            "system": {
                "api": "ok",
                "database": self._database_health(),
                "version": __version__,
                "environment": self.settings.app_env,
                "rate_limit_enabled": bool(self.settings.rate_limit_enabled),
                "errors_recent": len(errors),
                "errors_failed_operations": self.audit.failed_count(),
            },
            "recent_actions": [self.audit.serialize(row) for row in self.audit.recent(limit=5)],
        }

    def _database_health(self) -> str:
        try:
            self.db.execute(select(func.count()).select_from(User)).scalar_one()
        except Exception:  # pragma: no cover - only on a broken connection
            return "unavailable"
        return "ok"

    # --- users ---------------------------------------------------------
    def search_users(self, query: str | None, *, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """Search by Telegram id, internal id, @username or display name."""
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 20))
        stmt = select(User, Wallet).outerjoin(Wallet, Wallet.user_id == User.id)

        conditions = _name_conditions(query)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = select(func.count()).select_from(User).where(*conditions)
        else:
            count_stmt = select(func.count()).select_from(User)

        total = int(self.db.execute(count_stmt).scalar_one() or 0)
        rows = self.db.execute(stmt.order_by(User.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_more": page * page_size < total,
            "items": [
                {
                    "id": user.id,
                    "telegram_id": int(user.telegram_id),
                    "username": user.username,
                    "display_name": user.display_name,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.is_admin,
                    "is_banned": bool(user.is_banned),
                    "coins": int(wallet.coins) if wallet else 0,
                    "collector_level": int(user.collector_level),
                    "plates_count": int(user.plates_count),
                    "total_rolls": int(user.total_rolls),
                    "created_at": as_aware(user.created_at).isoformat() if user.created_at else None,
                }
                for user, wallet in rows
            ],
        }

    def user_detail(self, user_id: int) -> dict[str, Any]:
        """Full player snapshot used by the Telegram user panel."""
        user = self.require_user(user_id)
        wallet = self.economy.get_wallet(user.id)
        level = self.progression.current_level(user)
        entitlement = self.premium.active_entitlement(user.id)
        expires = as_aware(entitlement.expires_at) if entitlement else None
        allowance = self.daily.status(user)

        best_plate = self.db.get(Plate, user.best_plate_id) if user.best_plate_id else None
        first_discoveries = int(
            self.db.execute(
                select(func.count(func.distinct(PlateDiscovery.plate_id))).where(
                    PlateDiscovery.user_id == user.id,
                    PlateDiscovery.is_first_discovery.is_(True),
                )
            ).scalar_one()
            or 0
        )
        last_activity = max(
            [value for value in (as_aware(user.last_roll_at), as_aware(user.updated_at)) if value],
            default=None,
        )
        rarest = self.db.execute(
            select(Plate)
            .join(UserPlate, UserPlate.plate_id == Plate.id)
            .where(UserPlate.user_id == user.id)
            .order_by(rarity_case(Plate.rarity).desc(), Plate.rarity_score.desc())
            .limit(1)
        ).scalar_one_or_none()

        return {
            "id": user.id,
            "telegram_id": int(user.telegram_id),
            "username": user.username,
            "display_name": user.display_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_admin": user.is_admin,
            "is_protected_admin": self._is_protected_admin(user),
            "is_banned": bool(user.is_banned),
            "coins": int(wallet.coins),
            "total_earned": int(wallet.total_earned),
            "total_spent": int(wallet.total_spent),
            "total_rolls": int(user.total_rolls),
            "bonus_rolls": int(user.bonus_rolls),
            "daily_rolls_used": int(user.daily_rolls_used),
            "rolls_remaining": allowance.rolls_remaining,
            "daily_allowance": allowance.daily_allowance,
            "collector_level": level.to_dict(),
            "collection_xp": int(user.collection_xp),
            "plates_count": int(user.plates_count),
            "countries_count": int(user.countries_count),
            "regions_count": int(user.regions_count),
            "first_discoveries_count": first_discoveries,
            "current_streak": int(user.current_streak),
            "longest_streak": int(user.longest_streak),
            "best_value": int(user.best_value),
            "best_rarity": user.best_rarity or None,
            "best_plate": (
                {
                    "id": best_plate.id,
                    "plate_text": best_plate.plate_text,
                    "country_code": best_plate.country_code,
                    "rarity": best_plate.rarity,
                    "collector_value": int(best_plate.collector_value),
                }
                if best_plate is not None
                else None
            ),
            "rarest_plate": (
                {
                    "id": rarest.id,
                    "plate_text": rarest.plate_text,
                    "country_code": rarest.country_code,
                    "rarity": rarest.rarity,
                }
                if rarest is not None
                else None
            ),
            "premium": {
                "active": entitlement is not None,
                "tier": entitlement.tier if entitlement else None,
                "starts_at": as_aware(entitlement.starts_at).isoformat()
                if entitlement and entitlement.starts_at
                else None,
                "expires_at": expires.isoformat() if expires else None,
                "perks": self.premium.perks(user.id),
            },
            "season_pass_active": bool(user.season_pass_active),
            "equipped_title": user.equipped_title,
            "equipped_cosmetics": self.cosmetics.equipped_codes(user.id),
            "referrals_count": int(user.referrals_count),
            "shares_count": int(user.shares_count),
            "challenges_completed": int(user.challenges_completed),
            "containers_opened": int(user.containers_opened),
            "created_at": as_aware(user.created_at).isoformat() if user.created_at else None,
            "last_activity_at": last_activity.isoformat() if last_activity else None,
        }

    def user_economy(self, user_id: int, *, limit: int = 12) -> dict[str, Any]:
        """Balance, lifetime totals and the tail of the ledger."""
        user = self.require_user(user_id)
        wallet = self.economy.get_wallet(user.id)
        transactions = self.economy.last_transactions(user.id, limit=max(1, min(limit, 30)))
        return {
            "user_id": user.id,
            "telegram_id": int(user.telegram_id),
            "username": user.username,
            "coins": int(wallet.coins),
            "total_earned": int(wallet.total_earned),
            "total_spent": int(wallet.total_spent),
            "transactions": [self._transaction_item(row) for row in transactions],
        }

    def _transaction_item(self, row: WalletTransaction) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "type": row.type,
            "amount": int(row.amount),
            "balance_after": int(row.balance_after),
            "reference_type": row.reference_type or "",
            "reference_id": row.reference_id or "",
            "idempotency_key": row.idempotency_key or "",
            "meta": row.meta or {},
            "created_at": as_aware(row.created_at).isoformat() if row.created_at else None,
        }

    def transactions(
        self,
        *,
        user_id: int | None = None,
        tx_type: str | None = None,
        sign: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Append-only ledger viewer."""
        limit = max(1, min(int(limit), 50))
        stmt = select(WalletTransaction)
        if user_id:
            stmt = stmt.where(WalletTransaction.user_id == int(user_id))
        if tx_type:
            stmt = stmt.where(WalletTransaction.type == str(tx_type).upper())
        if sign == "in":
            stmt = stmt.where(WalletTransaction.amount > 0)
        elif sign == "out":
            stmt = stmt.where(WalletTransaction.amount < 0)

        total = int(self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0)
        # ``.scalars()`` is lazy: consuming it once for the owner lookup left nothing
        # for the item loop, so the ledger rendered with a count and no rows. It is
        # materialised here, exactly once.
        rows = list(
            self.db.execute(
                stmt.order_by(WalletTransaction.id.desc()).limit(limit).offset(max(0, offset))
            ).scalars()
        )
        owner_ids = {row.user_id for row in rows}
        usernames = {}
        if owner_ids:
            usernames = {
                user.id: user
                for user in self.db.execute(select(User).where(User.id.in_(owner_ids))).scalars()
            }
        items = []
        for row in rows:
            item = self._transaction_item(row)
            owner = usernames.get(row.user_id)
            item["username"] = owner.username if owner else None
            item["telegram_id"] = int(owner.telegram_id) if owner else None
            items.append(item)
        return {
            "total": total,
            "limit": limit,
            "offset": max(0, offset),
            "has_more": max(0, offset) + len(items) < total,
            "items": items,
        }

    # --- plates ---------------------------------------------------------
    def list_payments(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        product_code: str | None = None,
        charge_id: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Payment state an operator can reconcile against a support ticket.

        The grant flag and the recorded failure reason are the two fields that
        matter: ``PENDING`` + ``granted=false`` means the player paid and nothing
        happened yet, and ``FAILED`` carries the reason it did not.
        """
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        stmt = select(Payment)
        if user_id:
            stmt = stmt.where(Payment.user_id == int(user_id))
        if status:
            stmt = stmt.where(Payment.status == str(status).upper())
        if product_code:
            stmt = stmt.where(Payment.product_code == str(product_code))
        if charge_id:
            stmt = stmt.where(Payment.external_id == str(charge_id))

        total = int(self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0)
        rows = list(
            self.db.execute(stmt.order_by(Payment.id.desc()).limit(limit).offset(offset)).scalars()
        )
        owner_ids = {row.user_id for row in rows}
        owners: dict[int, User] = {}
        if owner_ids:
            owners = {
                user.id: user
                for user in self.db.execute(select(User).where(User.id.in_(owner_ids))).scalars()
            }
        items = []
        for row in rows:
            payload = dict(row.payload or {})
            owner = owners.get(row.user_id)
            items.append(
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "telegram_id": int(owner.telegram_id) if owner else None,
                    "username": owner.username if owner else None,
                    "provider": row.provider,
                    "product_code": row.product_code,
                    "amount": int(row.amount),
                    "currency": row.currency,
                    "status": row.status,
                    "granted": bool(row.granted),
                    "invoice_payload": row.invoice_payload,
                    "external_id": row.external_id,
                    "failure_reason": payload.get("failure_reason"),
                    "failure_type": payload.get("failure_type"),
                    "grant_summary": payload.get("granted"),
                    "paid_at": as_aware(row.paid_at).isoformat() if row.paid_at else None,
                    "created_at": as_aware(row.created_at).isoformat() if row.created_at else None,
                }
            )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
            "items": items,
        }

    def payment_detail(self, payment_id: int) -> dict[str, Any]:
        detail = self.db.get(Payment, int(payment_id))
        if detail is None:
            raise ValidationError("Payment not found.", code="PAYMENT_NOT_FOUND")
        return self._payment_item(detail, self.db.get(User, detail.user_id))

    def _payment_item(self, row: Payment, owner: User | None) -> dict[str, Any]:
        payload = dict(row.payload or {})
        return {
            "id": row.id,
            "user_id": row.user_id,
            "telegram_id": int(owner.telegram_id) if owner else None,
            "username": owner.username if owner else None,
            "provider": row.provider,
            "product_code": row.product_code,
            "amount": int(row.amount),
            "currency": row.currency,
            "status": row.status,
            "granted": bool(row.granted),
            "invoice_payload": row.invoice_payload,
            "external_id": row.external_id,
            "failure_reason": payload.get("failure_reason"),
            "failure_type": payload.get("failure_type"),
            "grant_summary": payload.get("granted"),
            "paid_at": as_aware(row.paid_at).isoformat() if row.paid_at else None,
            "refunded_at": as_aware(row.refunded_at).isoformat() if row.refunded_at else None,
            "refunded_amount": int(row.refunded_amount or 0),
            "created_at": as_aware(row.created_at).isoformat() if row.created_at else None,
        }

    def search_plates(
        self,
        *,
        query: str | None = None,
        sort: str = "recent",
        country_code: str | None = None,
        category: str | None = None,
        rarity: str | None = None,
        page: int = 1,
        page_size: int = 8,
    ) -> dict[str, Any]:
        """Browse the collectible catalogue: text search, filters and curated sorts.

        A numeric query is **not** treated as a catalogue id on its own. ``#1234``
        (or an explicit ``id=``) means "open entry 1234"; anything else - ``777``,
        ``RUS``, ``+1 777`` - is a text search across the display and normalised
        forms, because serials and country codes are just as likely to be typed as
        a row number.
        """
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 15))
        stmt = select(Plate)
        conditions = []
        cleaned = (query or "").strip().lstrip("@")

        explicit_id: int | None = None
        if cleaned.startswith("#") and cleaned[1:].isdigit():
            explicit_id = int(cleaned[1:])
        elif cleaned.isdigit():
            # Match the serial *or* the id, so an operator typing either one gets
            # the number they meant instead of an empty page.
            conditions.append(
                or_(
                    Plate.id == int(cleaned),
                    _plate_text_like(cleaned),
                )
            )
        elif cleaned:
            conditions.append(_plate_text_like(cleaned))
        if explicit_id is not None:
            conditions.append(Plate.id == explicit_id)
        if country_code:
            conditions.append(Plate.country_code == str(country_code).upper())
        if category:
            conditions.append(func.upper(func.coalesce(Plate.plate_type, "")) == str(category).upper())
        if rarity:
            conditions.append(Plate.rarity == str(rarity).upper())
        if conditions:
            stmt = stmt.where(*conditions)

        count_stmt = select(func.count()).select_from(Plate)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        order = {
            "rarest": (rarity_case(Plate.rarity).desc(), Plate.rarity_score.desc()),
            "value": (Plate.collector_value.desc(),),
            "discoveries": (Plate.discovery_count.desc(),),
            "secret": (Plate.is_secret.desc(), Plate.collector_value.desc()),
            "text": (Plate.plate_text.asc(),),
        }.get(sort, (Plate.id.desc(),))

        total = int(self.db.execute(count_stmt).scalar_one() or 0)
        rows = self.db.execute(stmt.order_by(*order).limit(page_size).offset((page - 1) * page_size)).scalars()
        flags = self.test_lab.flags()
        return {
            "page": page,
            "total": total,
            "has_more": page * page_size < total,
            "sort": sort,
            "items": [
                {
                    "id": plate.id,
                    "plate_text": plate.plate_text,
                    "country_code": plate.country_code,
                    "country_flag": flags.get(plate.country_code, ""),
                    "rarity": plate.rarity,
                    "collector_value": int(plate.collector_value),
                    "dealer_value": int(plate.dealer_value),
                    "discovery_count": int(plate.discovery_count),
                    "is_secret": bool(plate.is_secret),
                    "owner_count": self._owner_count(plate.id),
                }
                for plate in rows
            ],
        }

    def _owner_count(self, plate_id: int) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(UserPlate).where(UserPlate.plate_id == plate_id)
            ).scalar_one()
            or 0
        )

    def plate_detail(self, plate_id: int) -> dict[str, Any]:
        return self.test_lab.plate_detail(self.plates.require_plate(plate_id))

    # --- ranks ----------------------------------------------------------
    def ranks(self, *, category: str = "COLLECTION", period: str = "daily", limit: int = 10) -> dict[str, Any]:
        """Collection leaderboards - never wallet balance."""
        board = self.leaderboards.leaderboard(category=category, period=period, limit=limit)
        entries = list(board["entries"])  # type: ignore[arg-type]
        users = {
            user.id: user
            for user in self.db.execute(
                select(User).where(User.id.in_({int(entry["user_id"]) for entry in entries} or {0}))
            ).scalars()
        }
        for entry in entries:
            owner = users.get(int(entry["user_id"]))
            entry["db_id"] = int(entry["user_id"])
            entry["telegram_id"] = int(owner.telegram_id) if owner is not None else None
        return {
            "category": board["category"],
            "period": board["period"],
            "label": board["label"],
            "entries": entries,
            "categories": ["COLLECTION", "COUNTRIES", "FIRST_DISCOVERIES", "RARITY", "ROLLS"],
            "periods": list(periods().keys()),
        }

    # --- world ----------------------------------------------------------
    def countries(self) -> dict[str, Any]:
        rows = self.db.execute(select(Country).order_by(Country.sort_order, Country.id)).scalars()
        plate_counts = {
            str(code): int(count)
            for code, count in self.db.execute(
                select(Plate.country_code, func.count()).group_by(Plate.country_code)
            ).all()
        }
        discovery_counts = {
            str(code): int(count)
            for code, count in self.db.execute(
                select(Plate.country_code, func.count(func.distinct(PlateDiscovery.plate_id)))
                .join(PlateDiscovery, PlateDiscovery.plate_id == Plate.id)
                .group_by(Plate.country_code)
            ).all()
        }
        template_counts = {
            int(country_id): int(count)
            for country_id, count in self.db.execute(
                select(PlateTemplate.country_id, func.count()).group_by(PlateTemplate.country_id)
            ).all()
        }
        region_counts = {
            int(country_id): int(count)
            for country_id, count in self.db.execute(
                select(Region.country_id, func.count()).group_by(Region.country_id)
            ).all()
        }
        # ``Plate.country_code`` holds the code itself, so the discovery tally is
        # keyed by code while plate/template/region tallies use the country id.
        return {
            "items": [
                {
                    "id": country.id,
                    "code": country.code,
                    "flag": country.flag,
                    "name_en": country.name_en,
                    "name_ru": country.name_ru,
                    "region_group": country.region_group,
                    "is_active": bool(country.is_active),
                    "plates": plate_counts.get(country.code, 0),
                    "discoveries": discovery_counts.get(country.code, 0),
                    "templates": template_counts.get(int(country.id), 0),
                    "regions": region_counts.get(int(country.id), 0),
                }
                for country in rows
            ]
        }

    def events(self) -> dict[str, Any]:
        active = self.event_service.active()
        rows = self.db.execute(select(GameEvent).order_by(GameEvent.sort_order, GameEvent.id)).scalars()
        return {
            "active": active.to_dict(),
            "items": [
                {
                    "id": row.id,
                    "code": row.code,
                    "name_en": row.name_en,
                    "name_ru": row.name_ru,
                    "flag": row.flag,
                    "starts_at": as_aware(row.starts_at).isoformat() if row.starts_at else None,
                    "ends_at": as_aware(row.ends_at).isoformat() if row.ends_at else None,
                    "is_active": bool(row.is_active),
                    "country_multipliers": dict(row.country_multipliers or {}),
                    "reward_coins": int(row.reward_coins),
                    "reward_title": row.reward_title or "",
                }
                for row in rows
            ],
        }

    def seasons(self) -> dict[str, Any]:
        return {"items": [self.season_service.serialize(row) for row in self.season_service.list_all()]}

    # --- analytics ------------------------------------------------------
    def analytics(self, period: str = "today") -> dict[str, Any]:
        """Bounded SQL aggregation over the requested window.

        Every number is a single ``COUNT``/``SUM`` over an indexed column - no
        unbounded scan, no row materialisation, so the screen stays fast on a
        production-sized table.
        """
        key = str(period).lower()
        if key not in ANALYTICS_PERIODS:
            raise ValidationError("Unknown analytics period.", code="BAD_PERIOD")
        days = ANALYTICS_PERIODS[key]
        since = None if days is None else (start_of_utc_day() if days == 0 else utcnow() - timedelta(days=days))

        def _since(column):
            return [column >= since] if since is not None else []

        def _count(stmt) -> int:
            return int(self.db.execute(stmt).scalar_one() or 0)

        users_total = _count(select(func.count()).select_from(User))
        users_new = _count(select(func.count()).select_from(User).where(*_since(User.created_at)))
        users_active = _count(
            select(func.count(func.distinct(User.id))).select_from(User).where(*_since(User.last_roll_at))
        )

        rolls = _count(select(func.count()).select_from(PlateRoll).where(*_since(PlateRoll.created_at)))
        plates_discovered = _count(select(func.count()).select_from(Plate).where(*_since(Plate.created_at)))
        first_discoveries = _count(
            select(func.count())
            .select_from(PlateDiscovery)
            .where(
                PlateDiscovery.is_first_discovery.is_(True),
                *_since(PlateDiscovery.created_at),
            )
        )

        rank = rarity_case(PlateRoll.rarity)
        rare_plus = _count(
            select(func.count())
            .select_from(PlateRoll)
            .where(rank >= RARITY_RANK[Rarity.RARE.value], *_since(PlateRoll.created_at))
        )
        legendary_plus = _count(
            select(func.count())
            .select_from(PlateRoll)
            .where(rank >= RARITY_RANK[Rarity.LEGENDARY.value], *_since(PlateRoll.created_at))
        )
        mythic = _count(
            select(func.count())
            .select_from(PlateRoll)
            .where(PlateRoll.rarity == Rarity.MYTHIC.value, *_since(PlateRoll.created_at))
        )
        secret = _count(
            select(func.count()).select_from(Plate).where(Plate.is_secret.is_(True), *_since(Plate.created_at))
        )

        issued = _flow_sum(self.db, WalletTransaction.amount, WalletTransaction.created_at, since, incoming=True)
        spent = _flow_sum(self.db, WalletTransaction.amount, WalletTransaction.created_at, since, incoming=False)
        circulation = int(self.db.execute(select(func.coalesce(func.sum(Wallet.coins), 0))).scalar_one() or 0)

        purchases = _count(
            select(func.count())
            .select_from(Payment)
            .where(Payment.status == PaymentStatus.PAID.value, *_since(Payment.paid_at))
        )
        stars = int(
            self.db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == PaymentStatus.PAID.value, *_since(Payment.paid_at)
                )
            ).scalar_one()
            or 0
        )

        return {
            "period": key,
            "since": since.isoformat() if since else None,
            "users": {"total": users_total, "new": users_new, "active": users_active},
            "rolls": {
                "total": rolls,
                "unique_plates": plates_discovered,
                "first_discoveries": first_discoveries,
                "rare_plus": rare_plus,
                "legendary_plus": legendary_plus,
                "mythic": mythic,
                "secret": secret,
            },
            "economy": {"issued": issued, "spent": spent, "circulation": circulation},
            "monetization": {"purchases": purchases, "stars_revenue": stars},
            "social": self._social_metrics(since),
            "rarity_distribution": self._rarity_distribution(since),
            "country_distribution": self._country_distribution(since),
            "top_collectors": self._top_users(User.plates_count, "plates"),
            "top_first_discoverers": self._top_users(User.first_discoveries_count, "first_discoveries"),
            "top_rollers": self._top_users(User.total_rolls, "rolls"),
        }

    def _social_metrics(self, since) -> dict[str, int]:
        from app.models.social import Referral, ShareEvent

        def _count(stmt) -> int:
            return int(self.db.execute(stmt).scalar_one() or 0)

        return {
            "referrals": _count(
                select(func.count())
                .select_from(Referral)
                .where(*([Referral.created_at >= since] if since is not None else []))
            ),
            "shares": _count(
                select(func.count())
                .select_from(ShareEvent)
                .where(*([ShareEvent.created_at >= since] if since is not None else []))
            ),
            "challenges": int(
                self.db.execute(select(func.coalesce(func.sum(User.challenges_completed), 0))).scalar_one() or 0
            ),
        }

    def _rarity_distribution(self, since) -> dict[str, int]:
        stmt = select(PlateRoll.rarity, func.count()).group_by(PlateRoll.rarity)
        if since is not None:
            stmt = stmt.where(PlateRoll.created_at >= since)
        distribution = dict.fromkeys((rarity.value for rarity in Rarity), 0)
        for rarity, count in self.db.execute(stmt).all():
            distribution[str(rarity)] = int(count)
        return distribution

    def _country_distribution(self, since) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Plate.country_code, func.count(PlateRoll.id))
            .join(PlateRoll, PlateRoll.plate_id == Plate.id)
            .where(*([PlateRoll.created_at >= since] if since is not None else []))
            .group_by(Plate.country_code)
            .order_by(func.count(PlateRoll.id).desc())
            .limit(12)
        ).all()
        flags = self.test_lab.flags()
        return [{"code": str(code), "flag": flags.get(str(code), ""), "rolls": int(count)} for code, count in rows]

    def _top_users(self, column, metric: str) -> list[dict[str, Any]]:
        rows = self.db.execute(select(User, column.label("score")).order_by(column.desc(), User.id).limit(5)).all()
        return [
            {
                "user_id": user.id,
                "telegram_id": int(user.telegram_id),
                "username": user.username,
                "display_name": user.display_name,
                "metric": metric,
                "score": int(score or 0),
            }
            for user, score in rows
        ]

    # --- system ---------------------------------------------------------
    def system(self) -> dict[str, Any]:
        errors = error_buffer.snapshot(50)
        season = self.season_service.active()
        return {
            "api_health": "ok",
            "database_health": self._database_health(),
            "version": __version__,
            "environment": self.settings.app_env,
            "rate_limit_enabled": bool(self.settings.rate_limit_enabled),
            "rate_limit_window": int(self.settings.rate_limit_window_seconds),
            "active_season": season.code if season else None,
            "error_buffer_count": len(errors),
            "recent_errors": [
                {
                    "ts": item.get("ts", ""),
                    "logger": item.get("logger", ""),
                    "message": _short(item.get("message", "")),
                    "request_id": item.get("request_id", "-"),
                }
                for item in errors[:5]
            ],
            "failed_operations": self.audit.failed_count(),
            "telegram_bot_username": self.settings.telegram_bot_username,
            "mini_app_short_name": self.settings.mini_app_short_name,
            "admin_ids_configured": len(self.settings.admin_telegram_ids),
            "service_token_set": bool(self.settings.service_token) and self.settings.service_token != "CHANGE_ME",
            "database_driver": self.settings.database_url.split(":", 1)[0],
            "token_fingerprint": _fingerprint(self.settings.service_token),
        }

    def errors_view(self, limit: int = 20) -> dict[str, Any]:
        items = error_buffer.snapshot(max(1, min(int(limit), 50)))
        return {
            "generated_at": utcnow().isoformat(),
            "items": [
                {
                    "ts": item.get("ts", ""),
                    "level": item.get("level", "ERROR"),
                    "logger": item.get("logger", ""),
                    "message": _short(item.get("message", "")),
                    "request_id": item.get("request_id", "-"),
                }
                for item in items
            ],
        }

    # --- audit ----------------------------------------------------------
    def audit_log(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        admin_telegram_id: int | None = None,
        target_user_id: int | None = None,
        action: str | None = None,
        category: str | None = None,
        result: str | None = None,
    ) -> dict[str, Any]:
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 50))
        total = self.audit.count(
            admin_telegram_id=admin_telegram_id,
            target_user_id=target_user_id,
            action=action,
            category=category,
            result=result,
        )
        rows = self.audit.recent(
            limit=page_size,
            offset=(page - 1) * page_size,
            admin_telegram_id=admin_telegram_id,
            target_user_id=target_user_id,
            action=action,
            category=category,
            result=result,
        )
        return {
            "page": page,
            "total": total,
            "has_more": page * page_size < total,
            "items": [self._audit_item(row) for row in rows],
        }

    def _audit_item(self, row: AdminAuditLog) -> dict[str, Any]:
        payload = self.audit.serialize(row)
        target = self.db.get(User, row.target_user_id) if row.target_user_id else None
        admin = self.db.get(User, row.admin_user_id) if row.admin_user_id else None
        payload["target_label"] = (
            self.user_label(target)
            if target is not None
            else (str(row.target_telegram_id) if row.target_telegram_id else "-")
        )
        payload["admin_label"] = self.user_label(admin) if admin is not None else f"tg:{row.admin_telegram_id}"
        return payload
