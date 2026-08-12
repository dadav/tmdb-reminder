"""Tracked-title routes: list, idempotent track (PUT), soft-stop (DELETE)."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query

from ..enums import MediaType
from ..schemas import TitleView, TrackedListResponse
from ..time_utils import utc_now
from ..tracking import repository as repo
from .deps import SessionDep, TrackingDep
from .views import build_title_view

router = APIRouter(tags=["tracked-titles"])


@router.get("/tracked-titles", response_model=TrackedListResponse)
async def list_tracked(
    session: SessionDep,
    view: str = Query("active", pattern="^(active|history)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TrackedListResponse:
    titles = await repo.list_titles(session, view, offset, limit)
    events = await repo.soonest_current_events_map(session, [t.id for t in titles])
    total = await repo.count_titles(session, view)
    items = [build_title_view(t, events.get(t.id)) for t in titles]
    return TrackedListResponse(items=items, view=view, offset=offset, limit=limit, total=total)


@router.put("/tracked-titles/{media_type}/{tmdb_id}", response_model=TitleView)
async def track_title(
    session: SessionDep,
    tracking: TrackingDep,
    media_type: MediaType = Path(...),
    tmdb_id: int = Path(..., ge=1),
) -> TitleView:
    now = utc_now()
    title = await tracking.track(session, media_type, tmdb_id, now)
    await session.commit()
    event = await repo.latest_current_event_for_title(session, title.id)
    return build_title_view(title, event)


@router.delete("/tracked-titles/{media_type}/{tmdb_id}", response_model=TitleView)
async def stop_title(
    session: SessionDep,
    tracking: TrackingDep,
    media_type: MediaType = Path(...),
    tmdb_id: int = Path(..., ge=1),
) -> TitleView:
    title = await tracking.stop(session, media_type, tmdb_id)
    await session.commit()
    event = await repo.latest_current_event_for_title(session, title.id)
    return build_title_view(title, event)
