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
