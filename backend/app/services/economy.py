"""Ledger-based economy.

The wallet balance is a derived value: every mutation writes a
``wallet_transactions`` row first, then updates the cached balance on the
wallet in the same transaction. Nothing else in the codebase is allowed to
touch ``Wallet.coins`` directly.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InsufficientFundsError, NotFoundError
from app.core.timeutils import utcnow
from app.models.enums import TransactionType
from app.models.user import Wallet, WalletTransaction

Direction = Literal["credit", "debit"]


class EconomyService:
    """Credits, debits and balance queries with idempotency support."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- reads ---------------------------------------------------------
    def get_wallet(self, user_id: int, *, create: bool = True, for_update: bool = False) -> Wallet:
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        wallet = self.db.execute(stmt).scalar_one_or_none()
        if wallet is None:
            if not create:
                raise NotFoundError("Wallet not found.")
            wallet = Wallet(user_id=user_id, coins=0, total_earned=0, total_spent=0)
            self.db.add(wallet)
            self.db.flush()
        return wallet

    def balance(self, user_id: int) -> int:
        wallet = self.db.execute(select(Wallet.coins).where(Wallet.user_id == user_id)).scalar_one_or_none()
        return int(wallet or 0)

    def last_transactions(self, user_id: int, limit: int = 20) -> list[WalletTransaction]:
        stmt = (
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    # --- writes --------------------------------------------------------
    def _existing_by_key(self, key: str | None) -> WalletTransaction | None:
        if not key:
            return None
        return self.db.execute(
            select(WalletTransaction).where(WalletTransaction.idempotency_key == key)
        ).scalar_one_or_none()

    def credit(
        self,
        user_id: int,
        amount: int,
        tx_type: TransactionType | str,
        *,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        meta: dict[str, Any] | None = None,
        wallet: Wallet | None = None,
    ) -> WalletTransaction:
        """Add COINS to a wallet. Idempotent when a key is supplied."""
        if amount < 0:
            raise ValueError("Credit amount must not be negative.")

        existing = self._existing_by_key(idempotency_key)
        if existing is not None:
            return existing

        target = wallet or self.get_wallet(user_id)
        target.coins = int(target.coins) + int(amount)
        target.total_earned = int(target.total_earned) + int(amount)

        tx = WalletTransaction(
            user_id=user_id,
            type=str(tx_type),
            amount=int(amount),
            balance_after=int(target.coins),
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            idempotency_key=idempotency_key,
            meta=meta,
            created_at=utcnow(),
        )
        self.db.add(tx)
        self.db.flush()
        return tx

    def debit(
        self,
        user_id: int,
        amount: int,
        tx_type: TransactionType | str,
        *,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        meta: dict[str, Any] | None = None,
        wallet: Wallet | None = None,
    ) -> WalletTransaction:
        """Remove COINS from a wallet, raising when the balance is too low."""
        if amount < 0:
            raise ValueError("Debit amount must not be negative.")

        existing = self._existing_by_key(idempotency_key)
        if existing is not None:
            return existing

        target = wallet or self.get_wallet(user_id)
        if int(target.coins) < amount:
            raise InsufficientFundsError(
                "Not enough Coins.",
                details={"required": amount, "balance": int(target.coins)},
            )

        target.coins = int(target.coins) - int(amount)
        target.total_spent = int(target.total_spent) + int(amount)

        tx = WalletTransaction(
            user_id=user_id,
            type=str(tx_type),
            amount=-int(amount),
            balance_after=int(target.coins),
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            idempotency_key=idempotency_key,
            meta=meta,
            created_at=utcnow(),
        )
        self.db.add(tx)
        self.db.flush()
        return tx

    def admin_adjust(self, user_id: int, delta: int, *, reason: str, admin_telegram_id: int) -> WalletTransaction:
        """Manual balance correction by an administrator (fully audited)."""
        meta = {"reason": reason, "admin_telegram_id": admin_telegram_id}
        if delta >= 0:
            return self.credit(
                user_id,
                delta,
                TransactionType.ADMIN_ADJUSTMENT,
                reference_type="admin",
                reference_id=str(admin_telegram_id),
                meta=meta,
            )
        return self.debit(
            user_id,
            abs(delta),
            TransactionType.ADMIN_ADJUSTMENT,
            reference_type="admin",
            reference_id=str(admin_telegram_id),
            meta=meta,
        )
