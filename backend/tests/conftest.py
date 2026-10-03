"""Shared pytest fixtures.

Environment variables are set *before* any application import so the cached
``settings`` singleton picks them up.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

TEST_SECRET_KEY = "test-secret-key-0123456789abcdefghij"
TEST_ADMIN_TELEGRAM_ID = 900001
_TMP_DIR = tempfile.mkdtemp(prefix="numbergame-tests-")

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
        "RATE_LIMIT_ENABLED": "true",
        "PAYMENT_PROVIDER": "mock",
        "TELEGRAM_BOT_USERNAME": "test_bot",
        "BACKEND_URL": "http://localhost:8000",
    }
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.main import app
from app.seed import seed_all


@pytest.fixture(scope="session", autouse=True)
def _database() -> Generator[None, None, None]:
    """Create the schema once and seed the catalogue data."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_all(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """A session that is always rolled back, so tests stay isolated."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _override_get_db() -> Generator[Session, None, None]:
    """Drop-in replacement for the FastAPI ``get_db`` dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Generator[None, None, None]:
    """Each test starts with an empty rate-limit bucket."""
    from app.api.deps import rate_limiter

    rate_limiter.reset()
    yield
    rate_limiter.reset()


def login(client: TestClient, telegram_id: int, **kwargs: object) -> dict[str, object]:
    """Authenticate through the development endpoint and return the payload."""
    body = {"telegram_id": telegram_id, "first_name": kwargs.get("first_name", "Tester")}
    if "username" in kwargs:
        body["username"] = kwargs["username"]
    if "start_param" in kwargs:
        body["start_param"] = kwargs["start_param"]

    response = client.post("/api/auth/dev", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


@pytest.fixture
def authed(client: TestClient):
    """Factory fixture: returns a function creating authenticated headers."""

    def _factory(telegram_id: int = 5550001, **kwargs) -> dict:
        return login(client, telegram_id, **kwargs)

    return _factory


@pytest.fixture
def admin_authed(client: TestClient) -> dict:
    return login(client, TEST_ADMIN_TELEGRAM_ID, username="admin")
