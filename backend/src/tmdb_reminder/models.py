"""SQLAlchemy ORM models.

Design notes:
- Enums are stored as strings guarded by CHECK constraints (not native PG enums)
  so values evolve without enum-type DDL.
- Instants are timezone-aware UTC (`TIMESTAMP WITH TIME ZONE`); releases are
  calendar `DATE`s.
- Indexes target the hot paths: lifecycle lists, refresh eligibility, current
  events, and due-delivery claims.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import (
    DeliveryStatus,
    EventKind,
    EventState,
    JobName,
    MediaType,
    TitleStatus,
)
from .time_utils import utc_now


def _check(name: str, enum_cls: type[StrEnum], column: str) -> CheckConstraint:
    allowed = ", ".join(f"'{m.value}'" for m in enum_cls)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


class TrackedTitle(Base):
    __tablename__ = "tracked_titles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    media_type: Mapped[str] = mapped_column(String(8))
    tmdb_id: Mapped[int] = mapped_column(BigInteger)

    # Cached display metadata.
    title: Mapped[str] = mapped_column(String(500))
    original_title: Mapped[str | None] = mapped_column(String(500))
    overview: Mapped[str | None] = mapped_column(Text)
    poster_path: Mapped[str | None] = mapped_column(String(255))
    release_year: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(16), default=TitleStatus.ACTIVE.value)

    # Region-scoped movie availability (digital/physical/TV release at or before
    # today). Null for movies not yet available and for all TV titles.
    available_since: Mapped[date | None] = mapped_column(Date)

    # How availability was established (see AvailabilitySource). Null means unknown.
    # Coupled with `available_since` by a CHECK constraint: `release_date` carries a
    # date, `watch_provider` carries none.
    availability_source: Mapped[str | None] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    metadata_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Completed movies stay under daily revision watch until this instant.
    revision_watch_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    last_sync_status: Mapped[str | None] = mapped_column(String(16))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text)

    events: Mapped[list[ReleaseEvent]] = relationship(
        back_populates="title", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("media_type", "tmdb_id", name="uq_tracked_titles_identity"),
        _check("ck_tracked_titles_media_type", MediaType, "media_type"),
        _check("ck_tracked_titles_status", TitleStatus, "status"),
        CheckConstraint(
            "last_sync_status IS NULL OR last_sync_status IN ('ok','error')",
            name="ck_tracked_titles_sync_status",
        ),
        CheckConstraint(
            "(availability_source IS NULL AND available_since IS NULL) "
            "OR (availability_source = 'release_date' AND available_since IS NOT NULL) "
            "OR (availability_source = 'watch_provider' AND available_since IS NULL)",
            name="ck_tracked_titles_availability_source",
        ),
        Index("ix_tracked_titles_status", "status"),
        Index("ix_tracked_titles_refresh", "status", "metadata_refreshed_at"),
    )


class ReleaseEvent(Base):
    __tablename__ = "release_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tracked_title_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_titles.id", ondelete="CASCADE")
    )

    source_event_key: Mapped[str] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(20))

    scheduled_date: Mapped[date] = mapped_column(Date)
    season_number: Mapped[int | None] = mapped_column(Integer)
    episode_number: Mapped[int | None] = mapped_column(Integer)

    state: Mapped[str] = mapped_column(String(16), default=EventState.CURRENT.value)

    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    title: Mapped[TrackedTitle] = relationship(back_populates="events")
    deliveries: Mapped[list[NotificationDelivery]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source_event_key", "revision", name="uq_release_events_revision"),
        _check("ck_release_events_kind", EventKind, "kind"),
        _check("ck_release_events_state", EventState, "state"),
        Index("ix_release_events_title", "tracked_title_id"),
        Index("ix_release_events_current", "source_event_key", "state"),
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    release_event_id: Mapped[int] = mapped_column(
        ForeignKey("release_events.id", ondelete="CASCADE")
    )

    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(16), default=DeliveryStatus.PENDING.value)
    is_revised: Mapped[bool] = mapped_column(default=False)

    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_late: Mapped[bool] = mapped_column(default=False)
    gotify_message_id: Mapped[int | None] = mapped_column(BigInteger)

    event: Mapped[ReleaseEvent] = relationship(back_populates="deliveries")

    __table_args__ = (
        _check("ck_deliveries_status", DeliveryStatus, "status"),
        Index("ix_deliveries_due", "status", "due_at"),
        Index("ix_deliveries_event", "release_event_id"),
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(20))
    correlation_id: Mapped[str] = mapped_column(String(64))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(16))
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_summary: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        _check("ck_job_runs_name", JobName, "job_name"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('success','partial','failure')",
            name="ck_job_runs_outcome",
        ),
        Index("ix_job_runs_name_started", "job_name", "started_at"),
    )
