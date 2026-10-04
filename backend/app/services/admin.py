"""Admin control service.

One façade over the internal tooling:

* :class:`AdminReadsMixin` - dashboard, user lookup, ledger, catalogue,
  leaderboards, analytics, system health and the audit viewer (read-only);
* :class:`AdminActionsMixin` - every mutation, each claimed in
  ``admin_audit_logs`` under a caller-supplied operation id before it runs;
* :class:`~app.services.admin_base.AdminServiceBase` - collaborators, the audit
  claim/finish cycle and the shared state snapshot.

Splitting the reads from the writes keeps both files reviewable while callers
still see a single ``AdminService``.
"""

from __future__ import annotations

from app.services.admin_actions import AdminActionsMixin
from app.services.admin_base import (
    ANALYTICS_PERIODS,
    GLOBAL_LOCK_ID,
    AdminActor,
    AdminServiceBase,
)
from app.services.admin_reads import AdminReadsMixin


class AdminService(AdminReadsMixin, AdminActionsMixin, AdminServiceBase):
    """Read models and audited mutations for the internal control surfaces.

    Authorisation is *not* handled here: an :class:`AdminActor` must be built
    from a verified service token plus a Telegram id present in
    ``settings.admin_telegram_ids`` (see :func:`app.api.deps.get_admin_actor`).
    """


__all__ = [
    "ANALYTICS_PERIODS",
    "GLOBAL_LOCK_ID",
    "AdminActionsMixin",
    "AdminActor",
    "AdminReadsMixin",
    "AdminService",
    "AdminServiceBase",
]
