"""Shared pytest fixtures.

Environment variables are set *before* any application import so the cached
``settings`` singleton picks them up.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import uuid4

TEST_SECRET_KEY = "test-secret-key-0123456789abcdefghij"
TEST_ADMIN_TELEGRAM_ID = 900001
TEST_SERVICE_TOKEN = "test-service-token-abcdef0123456789"
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
        "SERVICE_TOKEN": TEST_SERVICE_TOKEN,
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_ADMIN_BOT": "10000",
        "RATE_LIMIT_ADMIN_READ": "10000",
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


def admin_bot_headers(admin_telegram_id: int | None = None) -> dict[str, str]:
    """Service-to-service headers for ``/api/admin/bot/*``."""
    return {
        "X-Service-Token": TEST_SERVICE_TOKEN,
        "X-Admin-Telegram-Id": str(
            TEST_ADMIN_TELEGRAM_ID if admin_telegram_id is None else admin_telegram_id
        ),
    }


@pytest.fixture
def admin_bot(client: TestClient):
    """Callable wrapper: ``admin_bot.get(path, **params)`` with auth attached."""

    class AdminBotApi:
        def request(self, method: str, path: str, **kwargs):
            headers = dict(admin_bot_headers())
            headers.update(kwargs.pop("headers", {}))
            return client.request(method, f"/api/admin/bot{path}", headers=headers, **kwargs)

        def get(self, path: str, **kwargs):
            return self.request("GET", path, **kwargs)

        def post(self, path: str, **kwargs):
            return self.request("POST", path, **kwargs)

    return AdminBotApi()


@pytest.fixture
def op() -> Callable[[], str]:
    """Globally unique operation ids.

    Uniqueness matters: the backend enforces idempotency with a *unique* index on
    ``admin_audit_logs.operation_id``, so two tests must never mint the same id.
    """
    def _next() -> str:
        return f"op-{uuid4().hex[:16]}"

    return _next


@pytest.fixture
def player(client: TestClient):
    """Factory creating a real (non-admin) player plus the service that owns it."""

    def _factory(telegram_id: int, username: str = "player", first_name: str = "Player"):
        session = login(client, telegram_id, username=username, first_name=first_name)
        return int(session["user"]["id"])

    return _factory

