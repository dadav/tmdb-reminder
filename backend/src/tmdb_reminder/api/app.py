"""FastAPI application factory.

Wires shared resources onto `app.state` during lifespan, installs a request-id
middleware and the standardized error contract, and mounts the v1 routers.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..db import Database
from ..errors import AppError, ValidationError
from ..logging_config import configure_logging, correlation_id
from ..notifications.gotify import GotifyClient
from ..tmdb.adapter import TmdbAdapter
from ..tracking.service import TrackingService
from .routes_health import router as health_router
from .routes_search import router as search_router
from .routes_status import router as status_router
from .routes_tracked import router as tracked_router

log = logging.getLogger("tmdb_reminder.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    app.state.db = Database(settings.database_url)
    app.state.adapter = TmdbAdapter(settings)
    app.state.gotify = GotifyClient(settings)
    app.state.tracking = TrackingService(settings, app.state.adapter)
    log.info(
        "api starting",
        extra={
            "tmdb_configured": settings.tmdb_configured,
            "gotify_configured": settings.gotify_configured,
        },
    )
    try:
        yield
    finally:
        await app.state.gotify.aclose()
        await app.state.db.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="TMDB Reminder API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        token = correlation_id.set(request_id)
        started = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            log.info(
                "request finished",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code if response is not None else 500,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            correlation_id.reset(token)

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        log.warning("app error", extra={"error_code": exc.code, "status": exc.http_status})
        return JSONResponse(status_code=exc.http_status, content=exc.to_body(request_id))

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        err = ValidationError("Request validation failed", details={"errors": exc.errors()})
        return JSONResponse(status_code=err.http_status, content=err.to_body(request_id))

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        log.exception("unhandled error")
        generic = AppError("Internal server error")
        return JSONResponse(status_code=500, content=generic.to_body(request_id))

    app.include_router(search_router, prefix="/api/v1")
    app.include_router(tracked_router, prefix="/api/v1")
    app.include_router(status_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    return app
