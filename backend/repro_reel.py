"""Reproduce the reel ValueError with the test catalogue."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_SECRET_KEY = "test-secret-key-0123456789abcdefghij"
TEST_ADMIN_TELEGRAM_ID = 900001
TEST_SERVICE_TOKEN = "test-service-token-abcdef0123456789"
TEST_BOT_TOKEN = "123456:test-bot-token-for-telegram-initdata"
TEST_FRONTEND_URL = "http://localhost:5173"
_TMP_DIR = tempfile.mkdtemp(prefix="numora-repro-")

os.environ.update(
    {
        "APP_ENV": "test",
        "DEBUG": "false",
        "SECRET_KEY": TEST_SECRET_KEY,
        "DATABASE_URL": f"sqlite:///{(Path(_TMP_DIR) / 'test.db').as_posix()}",
        "AUTO_MIGRATE": "false",
        "AUTO_SEED": "false",
        "ALLOW_DEV_LOGIN": "true",
        "ADMIN_TELEGRAM_IDS": str(TEST_ADMIN_TELEGRAM_ID),
        "SERVICE_TOKEN": TEST_SERVICE_TOKEN,
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_ADMIN_BOT": "10000",
        "RATE_LIMIT_ADMIN_READ": "10000",
        "PAYMENT_PROVIDER": "mock",
        "TELEGRAM_BOT_USERNAME": "test_bot",
        "BOT_TOKEN": TEST_BOT_TOKEN,
        "FRONTEND_URL": TEST_FRONTEND_URL,
        "CORS_ORIGINS": TEST_FRONTEND_URL,
        "BACKEND_URL": "http://localhost:8000",
    }
)

import random

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.seed import seed_all
from app.services.catalog import snapshot
from app.core.config import settings
from app.game.collectibles import CollectibleKind, kind_for_plate_type
from app.game.roll_reel import build_reel

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_all(db)

with SessionLocal() as db:
    ctx = snapshot(db, settings.rarity_weights).context

    print("=== ESP in context ===")
    print("ESP in countries:", any(c.code == "ESP" for c in ctx.countries))
    print("ESP regions:", ctx.regions_by_country.get("ESP"))
    esp_templates = ctx.templates_by_country.get("ESP", ())
    for o in esp_templates:
        print(
            "  template",
            o.code,
            "type=",
            o.plate_type,
            "kind=",
            kind_for_plate_type(o.plate_type).value,
            "requires_region=",
            o.requires_region,
            "pattern=",
            repr(o.pattern),
        )

    print()
    print("=== countries with NO vehicle templates ===")
    for c in ctx.countries:
        kinds = {kind_for_plate_type(o.plate_type) for o in ctx.templates_by_country.get(c.code, ())}
        if CollectibleKind.VEHICLE_PLATE not in kinds:
            print("  ", c.code, "kinds=", sorted(k.value for k in kinds))

    print()
    print("=== build_reel(country_code=ESP, kind=None) ===")
    try:
        frames = build_reel(ctx, country_code="ESP", rng=random.Random(42))
        print("OK frames:", len(frames))
    except Exception as exc:
        print("FAILED:", type(exc).__name__, exc)

    print()
    print("=== build_reel(kind=VEHICLE_PLATE) ===")
    try:
        frames = build_reel(ctx, kind=CollectibleKind.VEHICLE_PLATE, rng=random.Random(42))
        print("OK frames:", len(frames))
    except Exception as exc:
        print("FAILED:", type(exc).__name__, exc)

Base.metadata.drop_all(bind=engine)
