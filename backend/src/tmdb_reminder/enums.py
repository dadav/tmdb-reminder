"""String enums for the domain model.

Stored as plain strings with database CHECK constraints (see models.py), not
PostgreSQL-native enum types, so values can be added or migrated without DDL on
an enum type.
"""

from __future__ import annotations

from enum import StrEnum


class MediaType(StrEnum):
    MOVIE = "movie"
    TV = "tv"


class TitleStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    STOPPED = "stopped"


class AvailabilitySource(StrEnum):
    """How a movie's availability was established.

    `release_date` is a dated availability (a type 4/5/6 release at or before
    today) and always carries an exact `available_since`. `watch_provider` is an
    undated fallback derived from TMDB watch providers and carries no date. A null
    source means availability is unknown.
    """

    RELEASE_DATE = "release_date"
    WATCH_PROVIDER = "watch_provider"


class EventKind(StrEnum):
    MOVIE_DIGITAL = "movie_digital"
    TV_EPISODE = "tv_episode"


class EventState(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class JobName(StrEnum):
    REFRESH = "refresh"
    DELIVERY = "delivery"


class JobOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class SyncStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
