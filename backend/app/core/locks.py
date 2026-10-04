"""In-process keyed locks.

Guarantees that concurrent requests for the same user are serialised inside a
single worker process. Combined with database transactions (and ``SELECT ...
FOR UPDATE`` on PostgreSQL) this removes the roll race condition where one
roll could yield more than one reward.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_registry_lock = threading.Lock()
_locks: dict[str, threading.RLock] = {}


def _get_lock(key: str) -> threading.RLock:
    with _registry_lock:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


@contextmanager
def user_lock(user_id: int, scope: str = "user") -> Iterator[None]:
    """Serialise critical sections for a single user."""
    lock = _get_lock(f"{scope}:{user_id}")
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


@contextmanager
def payment_lock(payment_id: int) -> Iterator[None]:
    """Serialise the grant step of one payment.

    A Telegram webhook and a client poll can arrive for the same payment at the
    same moment. Serialising on the *payment* (not the user) keeps two different
    purchases from blocking each other while making a double delivery harmless.
    """
    lock = _get_lock(f"payment:{payment_id}")
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def reset_locks() -> None:
    """Test helper: drop all registered locks."""
    with _registry_lock:
        _locks.clear()
