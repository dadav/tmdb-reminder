"""HTTP request/response schemas (Pydantic BaseModel).

These are the documented public contract rendered into the OpenAPI artifact and
consumed by the generated frontend client.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .enums import EventKind, MediaType, TitleStatus

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


def poster_url(poster_path: str | None, size: str = "w342") -> str | None:
    if not poster_path:
        return None
    return f"{TMDB_IMAGE_BASE}/{size}{poster_path}"


class NextRelease(BaseModel):
    kind: EventKind
    scheduled_date: date
    season_number: int | None = None
    episode_number: int | None = None


class SearchResultItem(BaseModel):
    media_type: MediaType
    tmdb_id: int
    title: str
    original_title: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    poster_url: str | None = None
    release_year: int | None = None
    tmdb_url: str
    tracking_status: TitleStatus | None = None
    next_release: NextRelease | None = None
    # Whether a tracked movie is available now (dated or undated). False for TV and
    # untracked matches.
    is_available: bool = False
    # Region-scoped movie availability date. Null for undated (provider) availability.
    available_since: date | None = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    page: int
    total_pages: int
    total_results: int
    degraded: bool = False


class TitleView(BaseModel):
    id: int
    media_type: MediaType
    tmdb_id: int
    title: str
    original_title: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    poster_url: str | None = None
    release_year: int | None = None
    status: TitleStatus
    tmdb_url: str
    next_release: NextRelease | None = None
    # Whether the movie is available now (dated or undated). False for TV.
    is_available: bool = False
    # Region-scoped movie availability date; null for TV, unavailable movies, and
    # undated (provider) availability.
    available_since: date | None = None
    last_sync_status: str | None = None
    last_sync_at: datetime | None = None
    updated_at: datetime


class TrackedListResponse(BaseModel):
    items: list[TitleView]
    view: str
    offset: int
    limit: int
    total: int


class JobStatus(BaseModel):
    job_name: str
    outcome: str | None = None
    finished_at: datetime | None = None
    started_at: datetime | None = None
    processed_count: int = 0
    failure_summary: str | None = None


class ConfigStatus(BaseModel):
    tmdb_configured: bool
    gotify_configured: bool
    tmdb_region: str
    tmdb_language: str
    app_timezone: str
    reminder_time: str
    availability_delay_days: int
    gotify_priority: int


class StatusResponse(BaseModel):
    degraded: bool
    config: ConfigStatus
    tmdb_ok: bool | None = None
    gotify_ok: bool | None = None
    last_jobs: list[JobStatus] = Field(default_factory=list)
    tracked_active: int = 0
    tracked_history: int = 0
    pending_deliveries: int = 0
    recent_delivery_errors: int = 0


class GotifyTestResponse(BaseModel):
    sent: bool
    message_id: int | None = None
    error: str | None = None


class LivenessResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str
    database: bool
    schema_ready: bool
