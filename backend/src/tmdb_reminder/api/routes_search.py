"""Search route: TMDB multi-search with local tracking state joined in."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..enums import MediaType, TitleStatus
from ..schemas import NextRelease, SearchResponse, SearchResultItem, poster_url
from ..tmdb.mapping import tmdb_url
from ..tracking import repository as repo
from .deps import AdapterDep, SessionDep, SettingsDep
from .views import build_available_since, build_is_available, build_visible_next_release

router = APIRouter(tags=["search"])

_ALLOWED_MEDIA = {MediaType.MOVIE.value, MediaType.TV.value}


@router.get("/search", response_model=SearchResponse)
async def search(
    settings: SettingsDep,
    adapter: AdapterDep,
    session: SessionDep,
    query: str = Query(..., min_length=2, max_length=200),
    page: int = Query(1, ge=1, le=1000),
) -> SearchResponse:
    if not settings.tmdb_configured:
        return SearchResponse(results=[], page=page, total_pages=0, total_results=0, degraded=True)

    payload = await adapter.multi_search(query, page)
    raw_results = [
        r
        for r in payload.get("results", [])
        if r.get("media_type") in _ALLOWED_MEDIA and not r.get("adult", False)
    ]

    pairs = [(r["media_type"], int(r["id"])) for r in raw_results]
    tracked = await repo.titles_by_identity(session, pairs)
    events = await repo.soonest_current_events_map(session, [t.id for t in tracked.values()])

    items: list[SearchResultItem] = []
    for r in raw_results:
        media_type = MediaType(r["media_type"])
        tmdb_id = int(r["id"])
        is_tv = media_type == MediaType.TV
        title_text = (r.get("name") if is_tv else r.get("title")) or "Untitled"
        original = r.get("original_name") if is_tv else r.get("original_title")
        date_field = r.get("first_air_date") if is_tv else r.get("release_date")
        year = int(date_field[:4]) if date_field and date_field[:4].isdigit() else None

        tracking_status: TitleStatus | None = None
        next_release: NextRelease | None = None
        is_available = False
        available_since = None
        tracked_title = tracked.get((media_type.value, tmdb_id))
        if tracked_title is not None:
            tracking_status = TitleStatus(tracked_title.status)
            is_available = build_is_available(tracked_title)
            available_since = build_available_since(tracked_title)
            next_release = build_visible_next_release(tracked_title, events.get(tracked_title.id))

        items.append(
            SearchResultItem(
                media_type=media_type,
                tmdb_id=tmdb_id,
                title=title_text,
                original_title=original,
                overview=r.get("overview") or None,
                poster_path=r.get("poster_path"),
                poster_url=poster_url(r.get("poster_path")),
                release_year=year,
                tmdb_url=tmdb_url(media_type, tmdb_id),
                tracking_status=tracking_status,
                next_release=next_release,
                is_available=is_available,
                available_since=available_since,
            )
        )

    return SearchResponse(
        results=items,
        page=int(payload.get("page", page)),
        total_pages=int(payload.get("total_pages", 1)),
        total_results=int(payload.get("total_results", len(items))),
        degraded=False,
    )
