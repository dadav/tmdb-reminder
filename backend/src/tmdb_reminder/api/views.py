"""Build API response schemas from ORM rows."""

from __future__ import annotations

from ..enums import EventKind, MediaType, TitleStatus
from ..models import ReleaseEvent, TrackedTitle
from ..schemas import NextRelease, TitleView, poster_url
from ..tmdb.mapping import tmdb_url


def build_next_release(event: ReleaseEvent | None) -> NextRelease | None:
    if event is None:
        return None
    return NextRelease(
        kind=EventKind(event.kind),
        scheduled_date=event.scheduled_date,
        season_number=event.season_number,
        episode_number=event.episode_number,
    )


def build_title_view(title: TrackedTitle, event: ReleaseEvent | None) -> TitleView:
    media_type = MediaType(title.media_type)
    return TitleView(
        id=title.id,
        media_type=media_type,
        tmdb_id=title.tmdb_id,
        title=title.title,
        original_title=title.original_title,
        overview=title.overview,
        poster_path=title.poster_path,
        poster_url=poster_url(title.poster_path),
        release_year=title.release_year,
        status=TitleStatus(title.status),
        tmdb_url=tmdb_url(media_type, title.tmdb_id),
        next_release=build_next_release(event),
        last_sync_status=title.last_sync_status,
        last_sync_at=title.last_sync_at,
        updated_at=title.updated_at,
    )
