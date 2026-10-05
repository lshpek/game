"""FastAPI application factory, middleware and error handling."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger, request_id_ctx
from app.core.timeutils import utcnow
from app.db.session import engine
from app.schemas.common import HealthResponse

configure_logging(settings.log_level)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run migrations / seeding before serving traffic."""
    from app.bootstrap import bootstrap

    _warn_on_misconfiguration()

    try:
        bootstrap()
    except Exception as exc:
        logger.error("Bootstrap failed: %s", exc, exc_info=True)
        if settings.is_production:
            raise
    logger.info(
        "Application started",
        extra={"path": "-", "method": "-", "status_code": 0, "duration_ms": 0},
    )
    yield
    logger.info("Application stopped")


def _warn_on_misconfiguration() -> None:
    """Surface deployment mistakes that otherwise look like a client outage.

    A missing ``CORS_ORIGINS``/``FRONTEND_URL`` makes the browser fail the
    CORS preflight, so ``fetch()`` throws and the Mini App reports
    "Network unavailable" even though the API is up. A missing ``BOT_TOKEN``
    makes every Telegram login fail signature verification. Both are
    configuration problems, not code problems, so they are reported once at
    boot instead of on every request.
    """
    if settings.is_production:
        if settings.cors_is_local_only:
            logger.warning(
                "CORS allows only loopback origins (%s). Set CORS_ORIGINS or "
                "FRONTEND_URL to the public Mini App origin, otherwise every "
                "browser client will fail with a network error.",
                settings.cors_origins,
            )
        if not settings.cors_allows_frontend:
            logger.warning(
                "FRONTEND_URL (%s) is not in CORS_ORIGINS (%s). The Mini App "
                "origin will be blocked by CORS.",
                settings.frontend_url,
                settings.cors_origins,
            )
        if not settings.bot_token or settings.bot_token == "CHANGE_ME":
            logger.warning(
                "BOT_TOKEN is not configured. POST /api/auth/telegram will "
                "reject every Telegram login with INVALID_INIT_DATA."
            )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Collectible number Telegram Mini App backend.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Service-Token"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        if request.url.path not in {"/health", "/metrics"}:
            logger.info(
                "request",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response

    # --- error handling -------------------------------------------------
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("Application error: %s", exc.message, exc_info=True)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request payload is invalid.",
                    "details": {"errors": exc.errors()[:10]},
                },
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # Never leak stack traces to the client.
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": "Something went wrong.", "details": {}},
            },
        )

    # --- routes ---------------------------------------------------------
    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        database = "ok"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            database = "unavailable"

        return HealthResponse(
            status="ok" if database == "ok" else "degraded",
            app=settings.app_name,
            version=__version__,
            environment=settings.app_env,
            database=database,
            timestamp=utcnow().isoformat(),
            rate_limit_enabled=settings.rate_limit_enabled,
            rate_limit_window_seconds=int(settings.rate_limit_window_seconds),
        )

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": __version__, "docs": "/docs"}

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
