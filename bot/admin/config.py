"""Admin configuration for the Telegram panel.

There is deliberately **no** second admin-id setting. The bot reads the very same
``ADMIN_TELEGRAM_IDS`` environment variable the backend uses, so both sides agree
by construction, and the backend still verifies the id on every single request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

ENV_ADMIN_IDS = "ADMIN_TELEGRAM_IDS"
ENV_SERVICE_TOKEN = "SERVICE_TOKEN"


def _parse_admin_ids(raw: str | None) -> frozenset[int]:
    """Parse the comma-separated admin id list, ignoring junk entries."""
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        # Tolerate "-1001234" style group ids and stray whitespace/dashes.
        cleaned = cleaned.lstrip("-") if cleaned.startswith("-") and cleaned[1:].isdigit() else cleaned
        if cleaned.isdigit():
            ids.add(int(cleaned))
    return frozenset(ids)


@dataclass(frozen=True, slots=True)
class AdminConfig:
    """Static configuration for the panel."""

    admin_ids: frozenset[int] = field(default_factory=frozenset)
    service_token: str = ""
    backend_url: str = "http://localhost:8000"
    request_timeout: float = 20.0

    def is_admin(self, telegram_id: int | None) -> bool:
        """Server-side ids and the configured allow list must both match."""
        if telegram_id is None:
            return False
        return int(telegram_id) in self.admin_ids

    @property
    def enabled(self) -> bool:
        return bool(self.admin_ids) and bool(self.service_token)


def load_config() -> AdminConfig:
    return AdminConfig(
        admin_ids=_parse_admin_ids(os.getenv(ENV_ADMIN_IDS)),
        service_token=(os.getenv(ENV_SERVICE_TOKEN) or "").strip(),
        backend_url=(os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/"),
        request_timeout=float(os.getenv("ADMIN_API_TIMEOUT") or "20"),
    )


# Message shown to everyone who is not an admin. Deliberately generic: it must
# not confirm whether an id is an admin, nor reveal who is.
ACCESS_DENIED_TEXT = "⛔ Access denied."

# Commands the bot advertises. ``/admin`` is added at runtime for admins only.
USER_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Start / play"),
    ("help", "Help"),
)

ADMIN_COMMANDS: tuple[tuple[str, str], ...] = (
    ("admin", "Admin control centre"),
    ("panel", "Admin control centre"),
    ("a", "Admin control centre"),
)


__all__ = [
    "ACCESS_DENIED_TEXT",
    "ADMIN_COMMANDS",
    "ENV_ADMIN_IDS",
    "ENV_SERVICE_TOKEN",
    "USER_COMMANDS",
    "AdminConfig",
    "load_config",
]