"""Data-access queries for tracked titles, events, and deliveries.

Thin async functions over an `AsyncSession`. Business rules live in `service.py`
and the delivery module; this file only reads and writes rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select, text

from ..enums import DeliveryStatus, EventState, JobName, MediaType, TitleStatus
from ..models import JobRun, NotificationDelivery, ReleaseEvent, TrackedTitle


async def get_title(session, media_type: MediaType, tmdb_id: int) -> TrackedTitle | None:
    stmt = select(TrackedTitle).where(
        TrackedTitle.media_type == media_type.value,
        TrackedTitle.tmdb_id == tmdb_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def lock_title_identity(session, media_type: MediaType, tmdb_id: int) -> None:
    """Serialize creates for one TMDB identity within the current transaction."""
    media_key = 1 if media_type == MediaType.MOVIE else 2
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:media_key, :tmdb_id)"),
        {"media_key": media_key, "tmdb_id": tmdb_id},
    )


async def get_title_by_id(session, title_id: int) -> TrackedTitle | None:
    return await session.get(TrackedTitle, title_id)


def _list_stmt(view: str) -> Select:
    stmt = select(TrackedTitle)
    if view == "active":
        return stmt.where(TrackedTitle.status == TitleStatus.ACTIVE.value)
    return stmt.where(TrackedTitle.status != TitleStatus.ACTIVE.value)


def _soonest_current_date_subquery():
    return (
        select(func.min(ReleaseEvent.scheduled_date))
        .where(
            ReleaseEvent.tracked_title_id == TrackedTitle.id,
            ReleaseEvent.state == EventState.CURRENT.value,
        )
        .correlate(TrackedTitle)
        .scalar_subquery()
    )


async def list_titles(session, view: str, offset: int, limit: int) -> list[TrackedTitle]:
    stmt = _list_stmt(view)
    if view == "active":
        # Active sorted by nearest release; undated titles last, recent activity as tiebreak.
        soonest = _soonest_current_date_subquery()
        stmt = stmt.order_by(soonest.asc().nulls_last(), TrackedTitle.updated_at.desc())
    else:
        # History sorted by most recent activity.
        stmt = stmt.order_by(TrackedTitle.updated_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def count_titles(session, view: str) -> int:
    stmt = select(func.count()).select_from(_list_stmt(view).subquery())
    return int((await session.execute(stmt)).scalar_one())


async def count_by_status(session, status: TitleStatus) -> int:
    stmt = select(func.count()).where(TrackedTitle.status == status.value)
    return int((await session.execute(stmt)).scalar_one())


async def current_event(session, source_event_key: str) -> ReleaseEvent | None:
    stmt = select(ReleaseEvent).where(
        ReleaseEvent.source_event_key == source_event_key,
        ReleaseEvent.state == EventState.CURRENT.value,
    )
    return (await session.execute(stmt)).scalars().first()


async def latest_current_event_for_title(session, title_id: int) -> ReleaseEvent | None:
    """The soonest current release for a title (for list display)."""
    stmt = (
        select(ReleaseEvent)
        .where(
            ReleaseEvent.tracked_title_id == title_id,
            ReleaseEvent.state == EventState.CURRENT.value,
        )
        .order_by(ReleaseEvent.scheduled_date.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def soonest_current_events_map(session, title_ids: list[int]) -> dict[int, ReleaseEvent]:
    """Map each title id to its soonest current release event (for display)."""
    if not title_ids:
        return {}
    stmt = (
        select(ReleaseEvent)
        .where(
            ReleaseEvent.tracked_title_id.in_(title_ids),
            ReleaseEvent.state == EventState.CURRENT.value,
        )
        .order_by(ReleaseEvent.scheduled_date.asc())
    )
    result: dict[int, ReleaseEvent] = {}
    for event in (await session.execute(stmt)).scalars().all():
        result.setdefault(event.tracked_title_id, event)
    return result


async def titles_by_identity(
    session, pairs: list[tuple[str, int]]
) -> dict[tuple[str, int], TrackedTitle]:
    """Look up existing tracked titles for a set of (media_type, tmdb_id) pairs."""
    if not pairs:
        return {}
    tmdb_ids = list({p[1] for p in pairs})
    stmt = select(TrackedTitle).where(TrackedTitle.tmdb_id.in_(tmdb_ids))
    wanted = set(pairs)
    result: dict[tuple[str, int], TrackedTitle] = {}
    for title in (await session.execute(stmt)).scalars().all():
        key = (title.media_type, title.tmdb_id)
        if key in wanted:
            result[key] = title
    return result


async def max_revision(session, source_event_key: str) -> int:
    stmt = select(func.max(ReleaseEvent.revision)).where(
        ReleaseEvent.source_event_key == source_event_key
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def any_revision_delivered(session, source_event_key: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(NotificationDelivery)
        .join(ReleaseEvent, NotificationDelivery.release_event_id == ReleaseEvent.id)
        .where(
            ReleaseEvent.source_event_key == source_event_key,
            NotificationDelivery.status == DeliveryStatus.SENT.value,
        )
    )
    return int((await session.execute(stmt)).scalar_one()) > 0


async def event_ids_for_title(session, title_id: int) -> list[int]:
    stmt = select(ReleaseEvent.id).where(ReleaseEvent.tracked_title_id == title_id)
    return list((await session.execute(stmt)).scalars().all())


async def current_events_for_title(session, title_id: int) -> list[ReleaseEvent]:
    stmt = select(ReleaseEvent).where(
        ReleaseEvent.tracked_title_id == title_id,
        ReleaseEvent.state == EventState.CURRENT.value,
    )
    return list((await session.execute(stmt)).scalars().all())


async def unsent_deliveries_for_event(session, event_id: int) -> list[NotificationDelivery]:
    stmt = select(NotificationDelivery).where(
        NotificationDelivery.release_event_id == event_id,
        NotificationDelivery.status.in_(
            [DeliveryStatus.PENDING.value, DeliveryStatus.CLAIMED.value]
        ),
    )
    return list((await session.execute(stmt)).scalars().all())


async def titles_for_refresh(session, now: datetime, dormant_days: int) -> list[TrackedTitle]:
    """Titles eligible for the daily refresh.

    - all active titles,
    - completed movies still inside their revision-watch window,
    - dormant (stopped/completed) titles whose metadata is older than the cache
      refresh window (default 150 days).
    """
    dormant_cutoff = now - timedelta(days=dormant_days)
    stmt = select(TrackedTitle).where(
        or_(
            TrackedTitle.status == TitleStatus.ACTIVE.value,
            and_(
                TrackedTitle.revision_watch_until.is_not(None),
                TrackedTitle.revision_watch_until >= now,
            ),
            TrackedTitle.metadata_refreshed_at.is_(None),
            TrackedTitle.metadata_refreshed_at < dormant_cutoff,
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def due_deliveries(session, now: datetime, limit: int = 100) -> list[NotificationDelivery]:
    """Pending or lease-expired deliveries whose due time has arrived."""
    stmt = (
        select(NotificationDelivery)
        .where(
            NotificationDelivery.status.in_(
                [DeliveryStatus.PENDING.value, DeliveryStatus.CLAIMED.value]
            ),
            NotificationDelivery.due_at <= now,
        )
        .order_by(NotificationDelivery.due_at.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_pending_deliveries(session) -> int:
    stmt = select(func.count()).where(
        NotificationDelivery.status.in_(
            [DeliveryStatus.PENDING.value, DeliveryStatus.CLAIMED.value]
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def latest_job_runs(session) -> dict[str, JobRun]:
    """Most recent run per job name (Postgres DISTINCT ON)."""
    stmt = (
        select(JobRun).order_by(JobRun.job_name, JobRun.started_at.desc()).distinct(JobRun.job_name)
    )
    return {run.job_name: run for run in (await session.execute(stmt)).scalars().all()}


async def last_successful_refresh(session) -> JobRun | None:
    stmt = (
        select(JobRun)
        .where(JobRun.job_name == JobName.REFRESH.value, JobRun.outcome != "failure")
        .order_by(JobRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def count_recent_delivery_errors(session, since: datetime) -> int:
    stmt = select(func.count()).where(
        NotificationDelivery.last_error.is_not(None),
        NotificationDelivery.status != DeliveryStatus.SENT.value,
        NotificationDelivery.due_at >= since,
    )
    return int((await session.execute(stmt)).scalar_one())
