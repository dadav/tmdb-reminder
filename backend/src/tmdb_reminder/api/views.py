"""Build API response schemas from ORM rows."""

from __future__ import annotations

from datetime import date

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


def build_is_available(title: TrackedTitle) -> bool:
    """A movie is available when its availability source is set (dated or undated)."""
    if MediaType(title.media_type) != MediaType.MOVIE:
        return False
    return title.availability_source is not None


def build_visible_next_release(
    title: TrackedTitle, event: ReleaseEvent | None
) -> NextRelease | None:
    """Availability replaces an upcoming release only for available movies."""
    if build_is_available(title):
        return None
    return build_next_release(event)


def build_available_since(title: TrackedTitle) -> date | None:
    """Expose the availability date only for movies, even if stored data is
    inconsistent. Undated (provider) availability returns None."""
    if MediaType(title.media_type) != MediaType.MOVIE:
        return None
    return title.available_since


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
        next_release=build_visible_next_release(title, event),
        is_available=build_is_available(title),
        available_since=build_available_since(title),
        last_sync_status=title.last_sync_status,
        last_sync_at=title.last_sync_at,
        updated_at=title.updated_at,
    )
