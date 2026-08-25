"""Internal value objects.

These are Pydantic dataclasses (not `BaseModel`) used for internal TMDB, release,
and Gotify values. HTTP request/response schemas live in `schemas.py` and use
`BaseModel`; SQLAlchemy models live in `models.py`.
"""

from __future__ import annotations

from datetime import date

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

from .enums import EventKind, MediaType

_cfg = ConfigDict(frozen=True)


@dataclass(config=_cfg)
class TitleSnapshot:
    """Normalized, cacheable display metadata for a movie or TV title."""

    media_type: MediaType
    tmdb_id: int
    title: str
    original_title: str | None
    overview: str | None
    poster_path: str | None
    release_year: int | None


@dataclass(config=_cfg)
class MovieRelease:
    """Region-scoped movie availability derived from TMDB release dates.

    Dates exposed as availability or schedules include the configured delay.
    `next_digital_source_date` preserves the original TMDB date for reconciliation.
    """

    available_since: date | None
    next_digital_date: date | None
    next_digital_source_date: date | None


@dataclass(config=_cfg)
class ReleaseCandidate:
    """The single "current" release the daily refresh derived for a title.

    `source_event_key` groups revisions of the same real-world release; a changed
    `scheduled_date` for the same key becomes a new revision.
    """

    kind: EventKind
    source_event_key: str
    source_date: date
    scheduled_date: date
    season_number: int | None = None
    episode_number: int | None = None


@dataclass(config=_cfg)
class GotifyMessage:
    title: str
    markdown: str
    priority: int
    click_url: str
