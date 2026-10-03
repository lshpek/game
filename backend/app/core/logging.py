"""Structured JSON logging plus a request-id aware context."""

from __future__ import annotations

import json
import logging
import sys
from collections import deque
from contextvars import ContextVar
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        for key in ("user_id", "telegram_id", "path", "method", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger exactly once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.addHandler(error_buffer)
    root.setLevel(level.upper())

    # Uvicorn keeps its own handlers; align them with ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class ErrorBuffer(logging.Handler):
    """Keeps the most recent error records so the admin API can surface them.

    Bounded by design: never grows without limit, never blocks the request path.
    """

    def __init__(self, capacity: int = 200) -> None:
        super().__init__(level=logging.ERROR)
        self.capacity = capacity
        self._records: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - trivial
        try:
            self._records.append(
                {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "request_id": request_id_ctx.get(),
                    "exception": self.formatException(record.exc_info) if record.exc_info else None,
                }
            )
        except Exception:
            pass

    def snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        items = list(self._records)
        return items[-limit:][::-1]


error_buffer = ErrorBuffer()
