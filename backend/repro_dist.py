"""Sample the plate rarity distribution to design a statistical test."""
from __future__ import annotations

import os
import tempfile
from collections import Counter
from pathlib import Path

TEST_SECRET_KEY = "test-secret-key-0123456789abcdefghij"
TEST_BOT_TOKEN = "123456:test-bot-token-for-telegram-initdata"
TEST_FRONTEND_URL = "http://localhost:5173"
_TMP_DIR = tempfile.mkdtemp(prefix="numora-dist-")

os.environ.update(
    {
        "APP_ENV": "test",
        "DEBUG": "false",
        "SECRET_KEY": TEST_SECRET_KEY,
        "DATABASE_URL": f"sqlite:///{(Path(_TMP_DIR) / 'test.db').as_posix()}",
        "AUTO_MIGRATE": "false",
        "AUTO_SEED": "false",
        "ALLOW_DEV_LOGIN": "true",
        "ADMIN_TELEGRAM_IDS": "900001",
        "SERVICE_TOKEN": "test-service-token-abcdef0123456789",
        "RATE_LIMIT_ENABLED": "false",
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
from app.game.plate_generator import PlateGenerator
from app.game.rarity import Rarity, load_rarity_weights
from app.game.rng import roll_rarity

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_all(db)

with SessionLocal() as db:
    ctx = snapshot(db, settings.rarity_weights).context
    weights = load_rarity_weights()
    total = sum(weights.values())
    expected = {r.value: weights.get(r.value, 0.0) / total for r in Rarity}
    print("Configured weights (normalized):")
    for r in Rarity:
        print(f"  {r.value:12s}: weight={weights.get(r.value, 0.0):>8.4f}  expected~={expected[r.value]:.6f}")

    N = 40_000
    counts = Counter()
    rng = random.Random(20240607)
    for _ in range(N):
        luck = roll_rarity(settings.rarity_weights, rng)
        plate = PlateGenerator(ctx, rng).generate(luck=luck)
        counts[plate.rarity.value] += 1

    print(f"\nObserved distribution over {N} rolls:")
    print(f"  {'rarity':12s} {'expected%':>10s} {'observed%':>10s} {'chi2_contrib':>14s}")
    chi2 = 0.0
    for r in Rarity:
        code = r.value
        exp_pct = expected[code]
        obs_pct = counts.get(code, 0) / N
        exp_count = exp_pct * N
        obs_count = counts.get(code, 0)
        contrib = (obs_count - exp_count) ** 2 / exp_count if exp_count else 0
        chi2 += contrib
        print(f"  {code:12s} {exp_pct:>10.4%} {obs_pct:>10.4%} {contrib:>14.1f}")
    print(f"\nChi-square statistic: {chi2:.1f}")
    print(f"Degrees of freedom: {len(Rarity) - 1}")

Base.metadata.drop_all(bind=engine)
