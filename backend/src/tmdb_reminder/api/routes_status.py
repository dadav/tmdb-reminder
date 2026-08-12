"""Status and diagnostics routes."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter

from ..enums import TitleStatus
from ..errors import AppError
from ..schemas import (
    ConfigStatus,
    GotifyTestResponse,
    JobStatus,
    StatusResponse,
)
from ..time_utils import utc_now
from ..tracking import repository as repo
from .deps import AdapterDep, GotifyDep, SessionDep, SettingsDep

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def status(
    settings: SettingsDep,
    session: SessionDep,
    adapter: AdapterDep,
    gotify: GotifyDep,
) -> StatusResponse:
    config = ConfigStatus(
        tmdb_configured=settings.tmdb_configured,
        gotify_configured=settings.gotify_configured,
        tmdb_region=settings.tmdb_region,
        tmdb_language=settings.tmdb_language,
        app_timezone=settings.app_timezone,
        reminder_time=settings.reminder_time,
        gotify_priority=settings.gotify_priority,
    )
    jobs = await repo.latest_job_runs(session)
    last_jobs = [
        JobStatus(
            job_name=run.job_name,
            outcome=run.outcome,
            started_at=run.started_at,
            finished_at=run.finished_at,
            processed_count=run.processed_count,
            failure_summary=run.failure_summary,
        )
        for run in jobs.values()
    ]
    since = utc_now() - timedelta(days=7)
    tmdb_ok = await _connectivity(settings.tmdb_configured, adapter.check_connectivity)
    gotify_ok = await _connectivity(settings.gotify_configured, gotify.check_connectivity)
    return StatusResponse(
        degraded=tmdb_ok is not True or gotify_ok is not True,
        config=config,
        tmdb_ok=tmdb_ok,
        gotify_ok=gotify_ok,
        last_jobs=last_jobs,
        tracked_active=await repo.count_by_status(session, TitleStatus.ACTIVE),
        tracked_history=await repo.count_titles(session, "history"),
        pending_deliveries=await repo.count_pending_deliveries(session),
        recent_delivery_errors=await repo.count_recent_delivery_errors(session, since),
    )


@router.post("/status/gotify-test", response_model=GotifyTestResponse)
async def gotify_test(settings: SettingsDep, gotify: GotifyDep) -> GotifyTestResponse:
    if not settings.gotify_configured:
        return GotifyTestResponse(sent=False, error="Gotify is not configured")
    try:
        message_id = await gotify.send_test()
    except AppError as exc:
        return GotifyTestResponse(sent=False, error=exc.message)
    return GotifyTestResponse(sent=True, message_id=message_id)


async def _connectivity(configured: bool, check) -> bool | None:
    if not configured:
        return None
    try:
        return await check()
    except AppError:
        return False
