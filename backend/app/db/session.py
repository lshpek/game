"""SQLAlchemy engine / session factory.

The same models run on SQLite (development, tests) and PostgreSQL
(production). Only the connect arguments differ, never the business logic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

_engine_kwargs: dict[str, object] = {"echo": settings.db_echo, "pool_pre_ping": True}

if settings.is_sqlite:
    # SQLite needs cross-thread access because FastAPI runs sync endpoints in a
    # worker thread pool.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in settings.database_url:
        _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs["pool_size"] = settings.db_pool_size
    _engine_kwargs["max_overflow"] = settings.db_max_overflow

engine: Engine = create_engine(settings.database_url, **_engine_kwargs)

if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        # WAL keeps readers from blocking the single writer; FK enforcement is
        # off by default in SQLite.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts, the bot and background workers."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
