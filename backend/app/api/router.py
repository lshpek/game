"""Aggregate router mounted under the configured API prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    challenges,
    collection,
    containers,
    missions,
    payments,
    plates,
    ranking,
    referrals,
    roll,
)

api_router = APIRouter()
api_router.include_router(auth.router)
# The plate domain owns ``/roll``; the legacy number router is mounted under
# ``/legacy`` so old clients keep working while new gameplay uses plates.
api_router.include_router(plates.router)
api_router.include_router(roll.router)
api_router.include_router(missions.router)
api_router.include_router(collection.router)
api_router.include_router(containers.router)
api_router.include_router(referrals.router)
api_router.include_router(challenges.router)
api_router.include_router(ranking.router)
api_router.include_router(payments.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
