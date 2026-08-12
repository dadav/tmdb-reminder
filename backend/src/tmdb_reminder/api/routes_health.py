"""Liveness and readiness probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from ..models import TrackedTitle
from ..schemas import LivenessResponse, ReadinessResponse
from .deps import SessionDep

router = APIRouter(tags=["health"])
log = logging.getLogger("tmdb_reminder.health")


@router.get("/health/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/health/ready")
async def ready(session: SessionDep) -> JSONResponse:
    database = False
    schema_ready = False
    try:
        await session.execute(text("SELECT 1"))
        database = True
        await session.execute(select(TrackedTitle.id).limit(1))
        schema_ready = True
    except Exception:
        log.warning("readiness check failed", exc_info=True)

    body = ReadinessResponse(
        status="ok" if (database and schema_ready) else "unready",
        database=database,
        schema_ready=schema_ready,
    )
    code = 200 if body.status == "ok" else 503
    return JSONResponse(status_code=code, content=body.model_dump())
