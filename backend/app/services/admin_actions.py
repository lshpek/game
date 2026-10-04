"""Audited mutations for the admin control surfaces.

Every method here follows the same contract:

* the caller supplies an operation id, which becomes the audit row key, so a
  duplicated Telegram callback can never execute twice;
* the mutation itself is delegated to an existing game service, never to a raw
  ORM write;
* the result is stored on the audit row and echoed back to the panel.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.core.locks import user_lock
from app.core.timeutils import as_aware, utcnow
from app.models.enums import AdminAction, AdminCategory
from app.models.numora import Cosmetic, GameEvent
from app.models.plates import Country
from app.models.progression import Achievement, UserAchievement
from app.services.admin_base import AdminActor, AdminServiceBase, collection_amount
from app.services.progression import level_for_xp, xp_for_level

__all__ = ["AdminActionsMixin"]


class AdminActionsMixin(AdminServiceBase):
    """Mutations, each one claimed in the audit log before it runs."""

    # economy
    # ==================================================================
    def adjust_coins(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        delta: int,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        if int(delta) == 0:
            raise ValidationError("Amount cannot be zero.", code="INVALID_AMOUNT")
        amount = int(delta)

        def work() -> dict[str, Any]:
            before = int(self.economy.balance(user.id))
            tx = self.economy.admin_adjust(
                user.id,
                amount,
                reason=reason,
                admin_telegram_id=actor.telegram_id,
                source="telegram_admin_panel",
                operation_id=operation_id,
                idempotency_key=f"admin:{operation_id}",
            )
            return {
                "user_id": user.id,
                "delta": amount,
                "balance_before": before,
                "balance": int(tx.balance_after),
                "transaction_id": tx.id,
            }

        return self._mutate(
            actor,
            action=AdminAction.COIN_ADJUST,
            category=AdminCategory.ECONOMY,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=amount,
            reason=reason,
            metadata={"source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def set_balance(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        target: int,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        target = int(target)
        if target < 0:
            raise ValidationError("Balance cannot be negative.", code="INVALID_BALANCE")

        def work() -> dict[str, Any]:
            wallet = self.economy.get_wallet(user.id, for_update=True)
            before = int(wallet.coins)
            delta = target - before
            tx = self.economy.admin_adjust(
                user.id,
                delta,
                reason=reason,
                admin_telegram_id=actor.telegram_id,
                source="telegram_admin_panel",
                operation_id=operation_id,
                idempotency_key=f"admin:{operation_id}",
            )
            return {
                "user_id": user.id,
                "target": target,
                "delta": delta,
                "balance_before": before,
                "balance": int(tx.balance_after),
                "transaction_id": tx.id,
            }

        return self._mutate(
            actor,
            action=AdminAction.BALANCE_SET,
            category=AdminCategory.ECONOMY,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=target,
            reason=reason,
            metadata={"source": "telegram_admin_panel", "target_balance": target},
            request_id=request_id,
        )

    # ==================================================================
    # rolls
    # ==================================================================
    def grant_rolls(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        amount: int,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        amount = int(amount)
        if amount <= 0:
            raise ValidationError("Roll amount must be positive.", code="INVALID_AMOUNT")
        if amount > 1000:
            raise ValidationError("Roll amount is too large.", code="INVALID_AMOUNT")

        def work() -> dict[str, Any]:
            before = int(user.bonus_rolls)
            self.daily.grant_bonus_rolls(user, amount)
            allowance = self.daily.status(user)
            return {
                "user_id": user.id,
                "amount": amount,
                "bonus_rolls_before": before,
                "bonus_rolls": int(user.bonus_rolls),
                "rolls_remaining": allowance.rolls_remaining,
                "daily_allowance": allowance.daily_allowance,
            }

        return self._mutate(
            actor,
            action=AdminAction.ROLL_GRANT,
            category=AdminCategory.ROLLS,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=amount,
            reason=reason,
            metadata={"source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def reset_daily_rolls(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)

        def work() -> dict[str, Any]:
            refunded = self.daily.reset_daily_usage(user)
            allowance = self.daily.status(user)
            return {
                "user_id": user.id,
                "refunded": refunded,
                "daily_rolls_used": int(user.daily_rolls_used),
                "rolls_remaining": allowance.rolls_remaining,
            }

        return self._mutate(
            actor,
            action=AdminAction.ROLLS_RESET_DAILY,
            category=AdminCategory.ROLLS,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=None,
            reason=reason,
            metadata={"dangerous": True, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    # ==================================================================
    # progression
    # ==================================================================
    def change_xp(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        delta: int | None = None,
        exact: int | None = None,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)

        def work() -> dict[str, Any]:
            before_xp = int(user.collection_xp)
            before_level = int(user.collector_level)
            if exact is not None:
                self.progression.set_xp(user, int(exact))
            else:
                amount = int(delta or 0)
                if amount == 0:
                    raise ValidationError("Amount cannot be zero.", code="INVALID_AMOUNT")
                if amount < 0:
                    # XP cannot go below zero; the level is re-derived either way.
                    user.collection_xp = max(0, before_xp + amount)
                    user.collector_level = level_for_xp(int(user.collection_xp))
                    self.db.flush()
                else:
                    self.progression.add_xp(user, amount)
            return {
                "user_id": user.id,
                "delta": int(user.collection_xp) - before_xp,
                "xp_before": before_xp,
                "xp": int(user.collection_xp),
                "level_before": before_level,
                "level": int(user.collector_level),
                "title": self.progression.current_level(user).title_ru,
                "xp_for_level": xp_for_level(int(user.collector_level)),
            }

        return self._mutate(
            actor,
            action=AdminAction.XP_CHANGE,
            category=AdminCategory.PROGRESSION,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=int(delta if delta is not None else (exact or 0)),
            reason=reason,
            metadata={"source": "telegram_admin_panel", "mode": "exact" if exact is not None else "delta"},
            request_id=request_id,
        )

    def set_level(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        level: int,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        target = max(1, int(level))

        def work() -> dict[str, Any]:
            before_xp = int(user.collection_xp)
            before_level = int(user.collector_level)
            new_level = self.progression.set_level(user, target)
            return {
                "user_id": user.id,
                "level_before": before_level,
                "level": int(new_level),
                "xp_before": before_xp,
                "xp": int(user.collection_xp),
            }

        return self._mutate(
            actor,
            action=AdminAction.LEVEL_SET,
            category=AdminCategory.PROGRESSION,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=target,
            reason=reason,
            metadata={"source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def set_streak(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        current: int | None = None,
        longest: int | None = None,
        reset: bool = False,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)

        def work() -> dict[str, Any]:
            before = self.progression.set_streak(user, current=current, longest=longest)
            if reset:
                user.current_streak = 0
                user.longest_streak = 0
                self.db.flush()
            return {
                "user_id": user.id,
                "before": before,
                "current_streak": int(user.current_streak),
                "longest_streak": int(user.longest_streak),
            }

        return self._mutate(
            actor,
            action=AdminAction.STREAK_SET,
            category=AdminCategory.PROGRESSION,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=int(current) if current is not None else None,
            reason=reason,
            metadata={"dangerous": bool(reset), "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def reset_progression(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)

        def work() -> dict[str, Any]:
            before = self.progression.reset(user)
            return {"user_id": user.id, "before": before, **self._user_state(user)}

        return self._mutate(
            actor,
            action=AdminAction.PROGRESSION_RESET,
            category=AdminCategory.PROGRESSION,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={"dangerous": True, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    # ==================================================================
    # missions / achievements
    # ==================================================================
    def missions_board(self, user_id: int) -> dict[str, Any]:
        user = self.require_user(user_id)
        board = self.missions.board(user)
        paid = self.missions.reward_paid_flags(user.id)
        return {
            "user_id": user.id,
            "telegram_id": int(user.telegram_id),
            "items": [
                {
                    "code": item.code,
                    "name_ru": item.name_ru,
                    "progress": item.progress,
                    "target": item.target,
                    "completed": item.completed,
                    "reward_coins": item.reward_coins,
                    "reward_rolls": item.reward_rolls,
                    "reward_xp": item.reward_xp,
                    "reward_paid": bool(paid.get(item.code, False)),
                }
                for item in board
            ],
        }

    def mission_action(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        code: str,
        action: str,
        amount: int = 0,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        action = str(action).lower()
        mapping = {
            "progress": (AdminAction.MISSION_PROGRESS, self.missions.add_progress),
            "complete": (AdminAction.MISSION_COMPLETE, self.missions.complete),
            "reset": (AdminAction.MISSION_RESET, self.missions.reset),
        }
        if action not in mapping:
            raise ValidationError("Unknown mission action.", code="BAD_MISSION_ACTION")
        code_enum, handler = mapping[action]

        def work() -> dict[str, Any]:
            before = int(self.economy.balance(user.id))
            outcome = handler(user, code, int(amount or 1)) if action == "progress" else handler(user, code)
            return {
                "user_id": user.id,
                "code": outcome.code,
                "progress": outcome.progress,
                "target": outcome.target,
                "completed": outcome.completed,
                "reward_paid_now": outcome.just_completed,
                "balance_before": before,
                "balance": int(self.economy.balance(user.id)),
            }

        return self._mutate(
            actor,
            action=code_enum,
            category=AdminCategory.MISSIONS,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=int(amount) if action == "progress" else None,
            reason=reason,
            metadata={"dangerous": action == "reset", "mission": code, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def achievements_board(self, user_id: int) -> dict[str, Any]:
        user = self.require_user(user_id)
        unlocked = {
            int(row.achievement_id)
            for row in self.db.execute(
                select(UserAchievement).where(
                    UserAchievement.user_id == user.id, UserAchievement.unlocked_at.isnot(None)
                )
            ).scalars()
        }
        definitions = self.db.execute(
            select(Achievement).where(Achievement.is_active.is_(True)).order_by(Achievement.sort_order, Achievement.id)
        ).scalars()
        return {
            "user_id": user.id,
            "telegram_id": int(user.telegram_id),
            "unlocked_count": len(unlocked),
            "items": [
                {
                    "id": row.id,
                    "code": row.code,
                    "name": row.name,
                    "icon": row.icon,
                    "threshold": int(row.threshold),
                    "reward_coins": int(row.reward_coins),
                    "unlocked": row.id in unlocked,
                }
                for row in definitions
            ],
        }

    def grant_achievement(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        code: str,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        wanted = str(code).upper()
        definition = self.db.execute(select(Achievement).where(Achievement.code == wanted)).scalar_one_or_none()
        if definition is None:
            raise NotFoundError("Achievement not found.", code="ACHIEVEMENT_NOT_FOUND")

        def work() -> dict[str, Any]:
            row = self.db.execute(
                select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == definition.id,
                )
            ).scalar_one_or_none()
            created = row is None
            if row is None:
                row = UserAchievement(
                    user_id=user.id,
                    achievement_id=definition.id,
                    progress=int(definition.threshold),
                    unlocked_at=utcnow(),
                )
                self.db.add(row)
            else:
                row.progress = max(int(row.progress), int(definition.threshold))
                if row.unlocked_at is None:
                    row.unlocked_at = utcnow()
            self.db.flush()
            return {
                "user_id": user.id,
                "achievement_id": definition.id,
                "code": definition.code,
                "created": created,
                "coins": int(self.economy.balance(user.id)),
            }

        return self._mutate(
            actor,
            action=AdminAction.ACHIEVEMENT_GRANT,
            category=AdminCategory.ACHIEVEMENTS,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={"achievement": definition.code, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def revoke_achievement(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        code: str,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove the unlock row. Derived state only - the reward is not clawed back."""
        user = self.require_user(user_id)
        wanted = str(code).upper()
        definition = self.db.execute(select(Achievement).where(Achievement.code == wanted)).scalar_one_or_none()
        if definition is None:
            raise NotFoundError("Achievement not found.", code="ACHIEVEMENT_NOT_FOUND")

        def work() -> dict[str, Any]:
            row = self.db.execute(
                select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == definition.id,
                )
            ).scalar_one_or_none()
            removed = row is not None
            if row is not None:
                self.db.delete(row)
            self.db.flush()
            return {
                "user_id": user.id,
                "achievement_id": definition.id,
                "code": definition.code,
                "removed": removed,
            }

        return self._mutate(
            actor,
            action=AdminAction.ACHIEVEMENT_REVOKE,
            category=AdminCategory.ACHIEVEMENTS,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={"dangerous": True, "achievement": definition.code, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    # ==================================================================
    # cosmetics / rewards / premium
    # ==================================================================
    def cosmetics_catalogue(self, *, query: str | None = None, kind: str | None = None) -> dict[str, Any]:
        stmt = select(Cosmetic).where(Cosmetic.is_active.is_(True))
        cleaned = (query or "").strip().lstrip("@")
        if cleaned:
            stmt = stmt.where(
                or_(
                    Cosmetic.code.ilike(f"%{cleaned}%"),
                    Cosmetic.name_en.ilike(f"%{cleaned}%"),
                    Cosmetic.name_ru.ilike(f"%{cleaned}%"),
                )
            )
        if kind:
            stmt = stmt.where(Cosmetic.kind == str(kind).upper())
        rows = self.db.execute(stmt.order_by(Cosmetic.sort_order, Cosmetic.id).limit(60)).scalars()
        return {
            "items": [
                {
                    "code": row.code,
                    "kind": row.kind,
                    "name_en": row.name_en,
                    "name_ru": row.name_ru,
                    "rarity": row.rarity_code,
                    "price_stars": int(row.price_stars),
                    "price_numora": int(row.price_numora),
                }
                for row in rows
            ]
        }

    def cosmetic_action(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        code: str,
        action: str,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        action = str(action).lower()
        wanted = str(code).strip()
        actions = {
            "grant": (AdminAction.COSMETIC_GRANT, AdminCategory.COSMETICS, False),
            "equip": (AdminAction.COSMETIC_EQUIP, AdminCategory.COSMETICS, False),
            "unequip": (AdminAction.COSMETIC_UNEQUIP, AdminCategory.COSMETICS, False),
        }
        if action not in actions:
            raise ValidationError("Unknown cosmetic action.", code="BAD_COSMETIC_ACTION")
        action_code, category, dangerous = actions[action]

        def work() -> dict[str, Any]:
            if action == "grant":
                self.cosmetics.grant(user, wanted, source="ADMIN")
                owned = True
                equipped = False
            elif action == "equip":
                self.cosmetics.equip(user, wanted)
                owned = True
                equipped = True
            else:
                self.cosmetics.unequip(user, wanted)
                owned = wanted in self.cosmetics.owned_codes(user.id)
                equipped = False
            return {
                "user_id": user.id,
                "code": wanted,
                "owned": owned,
                "equipped": equipped,
                "equipped_codes": self.cosmetics.equipped_codes(user.id),
                "equipped_title": user.equipped_title or "",
            }

        return self._mutate(
            actor,
            action=action_code,
            category=category,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={"code": wanted, "dangerous": dangerous, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def grant_title(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        title: str,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        value = str(title).strip()[:64]
        if not value:
            raise ValidationError("Title is empty.", code="INVALID_TITLE")

        def work() -> dict[str, Any]:
            self.cosmetics.grant_title(user, value, source="ADMIN")
            return {
                "user_id": user.id,
                "title": value,
                "titles": [item["title"] for item in self.cosmetics.titles(user.id)],
            }

        return self._mutate(
            actor,
            action=AdminAction.TITLE_GRANT,
            category=AdminCategory.COSMETICS,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={"title": value, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def premium_status(self, user_id: int) -> dict[str, Any]:
        user = self.require_user(user_id)
        entitlement = self.premium.active_entitlement(user.id)
        expires = as_aware(entitlement.expires_at) if entitlement else None
        return {
            "user_id": user.id,
            "telegram_id": int(user.telegram_id),
            "active": entitlement is not None,
            "tier": entitlement.tier if entitlement else None,
            "starts_at": as_aware(entitlement.starts_at).isoformat() if entitlement and entitlement.starts_at else None,
            "expires_at": expires.isoformat() if expires else None,
            "perks": self.premium.perks(user.id),
            "daily_rolls_bonus": self.premium.daily_rolls_bonus(user.id),
            "duplicate_multiplier": self.premium.duplicate_coin_multiplier(user.id),
        }

    def premium_action(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        days: int | None = None,
        revoke: bool = False,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)

        def work() -> dict[str, Any]:
            if revoke:
                removed = self.premium.revoke(user.id)
                return {"user_id": user.id, "revoked": removed, "active": False, "tier": None}
            days_value = max(1, int(days or 30))
            if days_value > 3650:
                raise ValidationError("Duration is too long.", code="INVALID_DURATION")
            before = self.premium.active_entitlement(user.id)
            before_expiry = as_aware(before.expires_at) if before else None
            entitlement = self.premium.grant(user.id, tier="PRO", days=days_value, source="ADMIN")
            expires = as_aware(entitlement.expires_at)
            return {
                "user_id": user.id,
                "tier": entitlement.tier,
                "days": days_value,
                "expires_at": expires.isoformat() if expires else None,
                "previous_expires_at": before_expiry.isoformat() if before_expiry else None,
                "perks": self.premium.perks(user.id),
            }

        return self._mutate(
            actor,
            action=AdminAction.PREMIUM_REVOKE if revoke else AdminAction.PREMIUM_GRANT,
            category=AdminCategory.PREMIUM,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=int(days) if days else None,
            reason=reason,
            metadata={"dangerous": bool(revoke), "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def grant_reward(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        kind: str,
        amount: int = 0,
        code: str = "",
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """One quick-grant entry point. Every branch reuses an existing service."""
        user = self.require_user(user_id)
        kind = str(kind).lower()

        if kind == "coins":
            result = self.adjust_coins(
                actor,
                user_id=user_id,
                delta=int(amount),
                reason=reason,
                operation_id=operation_id,
                request_id=request_id,
            )
            result["kind"] = kind
            return result
        if kind == "rolls":
            result = self.grant_rolls(
                actor,
                user_id=user_id,
                amount=int(amount),
                reason=reason,
                operation_id=operation_id,
                request_id=request_id,
            )
            result["kind"] = kind
            return result
        if kind == "xp":
            result = self.change_xp(
                actor,
                user_id=user_id,
                delta=int(amount),
                reason=reason,
                operation_id=operation_id,
                request_id=request_id,
            )
            result["kind"] = kind
            return result
        if kind == "premium":
            result = self.premium_action(
                actor,
                user_id=user_id,
                days=int(amount or 30),
                reason=reason,
                operation_id=operation_id,
                request_id=request_id,
            )
            result["kind"] = kind
            return result
        if kind == "cosmetic":
            result = self.cosmetic_action(
                actor,
                user_id=user_id,
                code=code,
                action="grant",
                reason=reason,
                operation_id=operation_id,
                request_id=request_id,
            )
            result["kind"] = kind
            return result
        if kind == "title":
            result = self.grant_title(
                actor,
                user_id=user_id,
                title=code,
                reason=reason,
                operation_id=operation_id,
                request_id=request_id,
            )
            result["kind"] = kind
            return result
        if kind == "season_pass":
            return self._mutate(
                actor,
                action=AdminAction.REWARD_GRANT,
                category=AdminCategory.REWARDS,
                operation_id=operation_id,
                work=lambda: {
                    "user_id": user.id,
                    "kind": "season_pass",
                    **self.season_service.grant_season_pass(user),
                },
                target_user=user,
                reason=reason,
                metadata={"kind": "season_pass", "source": "telegram_admin_panel"},
                request_id=request_id,
            )

        raise ValidationError("Unknown reward kind.", code="BAD_REWARD_KIND")

    # ==================================================================
    # plates
    # ==================================================================
    def grant_plate(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        plate_id: int,
        reason: str,
        operation_id: str,
        mark_first_discovery: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        plate = self.plates.require_plate(plate_id)
        before_count = int(user.plates_count)

        def work() -> dict[str, Any]:
            with user_lock(user.id, "plate-grant"):
                grant = self.plates.grant(plate, user)
                is_first = self.plates.record_discovery(plate, user, source="ADMIN")
                if mark_first_discovery and not is_first:
                    self.plates.set_first_discoverer(plate, user, source="ADMIN", override=True)
                    is_first = True
                self.test_lab._update_user_best(user, plate)
                self.progression.recompute_counters(user)
                collection = self.plates.collection_size(user.id)
            return {
                "user_id": user.id,
                "plate_id": plate.id,
                "plate_text": plate.plate_text,
                "country_code": plate.country_code,
                "rarity": plate.rarity,
                "is_new": not grant.is_duplicate,
                "duplicates": int(grant.user_plate.duplicate_count),
                "is_first_discovery": is_first,
                "plates_count": collection,
                "plates_count_before": before_count,
                "dealer_value": int(plate.dealer_value),
            }

        return self._mutate(
            actor,
            action=AdminAction.PLATE_GRANT,
            category=AdminCategory.PLATES,
            operation_id=operation_id,
            work=work,
            target_user=user,
            amount=collection_amount(plate.dealer_value),
            reason=reason,
            metadata={"plate_id": plate.id, "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    def set_first_discovery(
        self,
        actor: AdminActor,
        *,
        plate_id: int,
        user_id: int,
        override: bool,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        plate = self.plates.require_plate(plate_id)

        def work() -> dict[str, Any]:
            outcome = self.plates.set_first_discoverer(plate, user, source="ADMIN", override=override)
            return {
                "plate_id": plate.id,
                "plate_text": plate.plate_text,
                "country_code": plate.country_code,
                "rarity": plate.rarity,
                "user_id": user.id,
                "username": user.username,
                **outcome,
                "first_discoveries_count": int(user.first_discoveries_count),
                "discovery_count": int(plate.discovery_count),
            }

        return self._mutate(
            actor,
            action=AdminAction.FIRST_DISCOVERY,
            category=AdminCategory.PLATES,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={
                "dangerous": True,
                "plate_id": plate.id,
                "override": bool(override),
                "source": "telegram_admin_panel",
            },
            request_id=request_id,
        )

    # ==================================================================
    # test lab
    # ==================================================================
    def simulate_roll(
        self,
        actor: AdminActor,
        *,
        country_code: str | None = None,
        region_code: str | None = None,
        template_code: str | None = None,
        rarity: str | None = None,
        preset: str | None = None,
        require_trait: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Read-only preview. Still audited, still never mutates game state."""
        payload = self.test_lab.simulate(
            country_code=country_code,
            region_code=region_code,
            template_code=template_code,
            rarity=rarity,
            preset=preset,
            require_trait=require_trait,
        )
        row = self.audit.record(
            action=AdminAction.SIMULATE_ROLL,
            category=AdminCategory.TEST_LAB,
            admin_telegram_id=actor.telegram_id,
            admin_user_id=actor.user_id,
            metadata={
                "source": "telegram_admin_panel",
                "country_code": payload["plate"]["country_code"],
                "rarity": payload["plate"]["rarity"],
                "preset": preset,
                "mode": "SIMULATION",
            },
            request_id=request_id,
        )
        self.db.commit()
        return {"audit_id": row.id, **payload}

    def live_test_roll(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        country_code: str | None = None,
        region_code: str | None = None,
        template_code: str | None = None,
        rarity: str | None = None,
        preset: str | None = None,
        require_trait: str | None = None,
        mark_first_discovery: bool = False,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)

        def work() -> dict[str, Any]:
            return self.test_lab.live_roll(
                user,
                country_code=country_code,
                region_code=region_code,
                template_code=template_code,
                rarity=rarity,
                preset=preset,
                require_trait=require_trait,
                mark_first_discovery=mark_first_discovery,
            )

        return self._mutate(
            actor,
            action=AdminAction.FORCE_ROLL,
            category=AdminCategory.TEST_LAB,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={
                "dangerous": True,
                "country_code": country_code,
                "rarity": rarity,
                "preset": preset,
                "mode": "LIVE",
                "source": "telegram_admin_panel",
            },
            request_id=request_id,
        )

    def force_plate(
        self,
        actor: AdminActor,
        *,
        plate_text: str,
        user_id: int | None,
        country_code: str | None = None,
        rarity: str | None = None,
        mark_first_discovery: bool = False,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        grant_to = self.require_user(user_id) if user_id else None

        def work() -> dict[str, Any]:
            return self.test_lab.force_plate(
                plate_text,
                country_code=country_code,
                rarity=rarity,
                grant_to=grant_to,
                mark_first_discovery=mark_first_discovery,
            )

        return self._mutate(
            actor,
            action=AdminAction.FORCE_PLATE,
            category=AdminCategory.TEST_LAB,
            operation_id=operation_id,
            work=work,
            target_user=grant_to,
            reason=reason,
            metadata={
                "dangerous": grant_to is not None,
                "plate_text": str(plate_text)[:32],
                "country_code": country_code,
                "rarity": rarity,
                "source": "telegram_admin_panel",
            },
            request_id=request_id,
        )

    def test_lab_catalog(self) -> dict[str, Any]:
        return {
            "countries": self.test_lab.countries(),
            "rarities": self.test_lab.rarities(),
            "presets": self.test_lab.presets(),
        }

    # ==================================================================
    # moderation
    # ==================================================================
    def set_ban(
        self,
        actor: AdminActor,
        *,
        user_id: int,
        banned: bool,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        user = self.require_user(user_id)
        if banned and self._is_protected_admin(user):
            raise PermissionDeniedError("Configured admins cannot be banned from this panel.", code="PROTECTED_ADMIN")
        if int(user.telegram_id) == int(actor.telegram_id) and banned:
            raise PermissionDeniedError("You cannot ban yourself.", code="SELF_BAN")

        def work() -> dict[str, Any]:
            before = bool(user.is_banned)
            user.is_banned = bool(banned)
            self.db.flush()
            return {
                "user_id": user.id,
                "telegram_id": int(user.telegram_id),
                "username": user.username,
                "is_banned": bool(user.is_banned),
                "changed": before != bool(user.is_banned),
            }

        return self._mutate(
            actor,
            action=AdminAction.BAN if banned else AdminAction.UNBAN,
            category=AdminCategory.MODERATION,
            operation_id=operation_id,
            work=work,
            target_user=user,
            reason=reason,
            metadata={"dangerous": bool(banned), "source": "telegram_admin_panel"},
            request_id=request_id,
        )

    # ==================================================================
    # world config
    # ==================================================================
    def toggle_country(
        self,
        actor: AdminActor,
        *,
        country_id: int,
        active: bool,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        country = self.db.get(Country, int(country_id))
        if country is None:
            raise NotFoundError("Country not found.", code="COUNTRY_NOT_FOUND")
        from app.services import catalog

        def work() -> dict[str, Any]:
            before = bool(country.is_active)
            country.is_active = bool(active)
            self.db.flush()
            catalog.invalidate()
            return {
                "country_id": country.id,
                "code": country.code,
                "is_active": bool(country.is_active),
                "changed": before != bool(country.is_active),
            }

        return self._mutate(
            actor,
            action=AdminAction.COUNTRY_CHANGE,
            category=AdminCategory.WORLD,
            operation_id=operation_id,
            work=work,
            amount=None,
            reason=reason,
            metadata={"dangerous": True, "code": country.code, "active": bool(active)},
            request_id=request_id,
        )

    def toggle_event(
        self,
        actor: AdminActor,
        *,
        event_id: int,
        active: bool,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        event = self.db.get(GameEvent, int(event_id))
        if event is None:
            raise NotFoundError("Event not found.", code="EVENT_NOT_FOUND")

        def work() -> dict[str, Any]:
            before = bool(event.is_active)
            if active:
                # Exactly one persisted event may drive the game.
                for other in self.db.execute(select(GameEvent)).scalars():
                    other.is_active = other.id == event.id
            else:
                event.is_active = False
            self.db.flush()
            return {
                "event_id": event.id,
                "code": event.code,
                "is_active": bool(event.is_active),
                "changed": before != bool(event.is_active),
                "country_multipliers": dict(event.country_multipliers or {}),
            }

        return self._mutate(
            actor,
            action=AdminAction.EVENT_CHANGE,
            category=AdminCategory.WORLD,
            operation_id=operation_id,
            work=work,
            reason=reason,
            metadata={"dangerous": True, "code": event.code, "active": bool(active)},
            request_id=request_id,
        )

    def toggle_season(
        self,
        actor: AdminActor,
        *,
        code: str,
        active: bool,
        reason: str,
        operation_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        season = self.season_service.get(code)

        def work() -> dict[str, Any]:
            before = bool(season.is_active)
            if active:
                self.season_service.activate(code)
            else:
                season.is_active = False
                self.db.flush()
            return {
                "code": season.code,
                "is_active": bool(season.is_active),
                "changed": before != bool(season.is_active),
            }

        return self._mutate(
            actor,
            action=AdminAction.SEASON_CHANGE,
            category=AdminCategory.WORLD,
            operation_id=operation_id,
            work=work,
            reason=reason,
            request_id=request_id,
        )
