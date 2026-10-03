"""Configurable sliding-window rate limiting.

The limiter is process-local, which is correct for a single container and a
reasonable first line of defence behind a proxy. For multi-replica deployments
swap :class:`SlidingWindowRateLimiter` for a Redis-backed implementation - the
call signature stays identical.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterable

from app.core.errors import RateLimitError


class SlidingWindowRateLimiter:
    """Track request timestamps per key and enforce a rolling limit."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        """Raise :class:`RateLimitError` when ``key`` exceeded ``limit``."""
        if not self.enabled or limit <= 0:
            return

        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
                raise RateLimitError(
                    f"Too many requests. Retry in {retry_after}s.",
                    details={"retry_after": retry_after},
                )
            bucket.append(now)

    def reset(self, keys: Iterable[str] | None = None) -> None:
        """Test helper: clear counters."""
        with self._lock:
            if keys is None:
                self._hits.clear()
            else:
                for key in keys:
                    self._hits.pop(key, None)
