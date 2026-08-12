"""Worker jobs: daily refresh and delivery evaluation.

Each run records a `job_runs` row with a correlation id, outcome, processed
count, and a sanitized failure summary. A single title's TMDB failure never
aborts the batch; the run is marked ``partial`` instead.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from ..config import Settings
from ..db import Database
from ..enums import JobName, JobOutcome, SyncStatus, TitleStatus
from ..errors import AppError
from ..logging_config import correlation_id, sanitize
from ..models import JobRun, TrackedTitle
from ..notifications.delivery import DeliveryService
from ..time_utils import local_date, utc_now
from ..tracking import repository as repo
from ..tracking.service import TrackingService

log = logging.getLogger("tmdb_reminder.jobs")


class Jobs:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        tracking: TrackingService,
        delivery: DeliveryService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.tracking = tracking
        self.delivery = delivery
        self.tz = settings.timezone

    async def _open_run(self, session, job_name: JobName, cid: str, now: datetime) -> JobRun:
        run = JobRun(job_name=job_name.value, correlation_id=cid, started_at=now)
        session.add(run)
        await session.commit()
        return run

    async def run_refresh(self, now: datetime | None = None) -> JobRun:
        now = now or utc_now()
        cid = uuid.uuid4().hex
        token = correlation_id.set(cid)
        try:
            async with self.db.session_factory() as session:
                run = await self._open_run(session, JobName.REFRESH, cid, now)
                titles = await repo.titles_for_refresh(
                    session, now, self.settings.dormant_refresh_days
                )
            processed = 0
            failures = 0
            last_error: str | None = None
            for title in titles:
                ok, err = await self._refresh_one(title.id, now)
                processed += 1
                if not ok:
                    failures += 1
                    last_error = err
            outcome = _outcome(processed, failures)
            await self._close_run(run.id, now, outcome, processed, last_error if failures else None)
            log.info(
                "refresh job finished",
                extra={"processed": processed, "failures": failures, "outcome": outcome.value},
            )
            async with self.db.session_factory() as session:
                return await session.get(JobRun, run.id)  # type: ignore[return-value]
        finally:
            correlation_id.reset(token)

    async def _refresh_one(self, title_id: int, now: datetime) -> tuple[bool, str | None]:
        async with self.db.session_factory() as session:
            title = await session.get(TrackedTitle, title_id)
            if title is None:
                return True, None
            try:
                await self.tracking.refresh_title(
                    session,
                    title,
                    now,
                    metadata_only=title.status == TitleStatus.STOPPED.value,
                )
                await session.commit()
                return True, None
            except AppError as exc:
                await session.rollback()
                fresh = await session.get(TrackedTitle, title_id)
                if fresh is not None:
                    fresh.last_sync_status = SyncStatus.ERROR.value
                    fresh.last_sync_at = now
                    fresh.last_sync_error = str(sanitize(exc.message))
                    await session.commit()
                log.warning(
                    "title refresh failed",
                    extra={"title_id": title_id, "error_code": exc.code},
                )
                return False, exc.code

    async def run_delivery(self, now: datetime | None = None) -> JobRun:
        now = now or utc_now()
        cid = uuid.uuid4().hex
        token = correlation_id.set(cid)
        try:
            async with self.db.session_factory() as session:
                run = await self._open_run(session, JobName.DELIVERY, cid, now)
                counts = await self.delivery.evaluate_due(session, now)
            outcome = JobOutcome.PARTIAL if counts.failed else JobOutcome.SUCCESS
            summary = ",".join(counts.errors) if counts.errors else None
            await self._close_run(run.id, now, outcome, counts.processed, summary)
            log.info("delivery job finished", extra={"counts": counts.__dict__})
            async with self.db.session_factory() as session:
                return await session.get(JobRun, run.id)  # type: ignore[return-value]
        finally:
            correlation_id.reset(token)

    async def _close_run(
        self,
        run_id: int,
        now: datetime,
        outcome: JobOutcome,
        processed: int,
        summary: str | None,
    ) -> None:
        async with self.db.session_factory() as session:
            run = await session.get(JobRun, run_id)
            if run is None:
                return
            run.finished_at = utc_now()
            run.outcome = outcome.value
            run.processed_count = processed
            run.failure_summary = summary
            await session.commit()

    async def startup_catchup(self, now: datetime | None = None) -> None:
        """Run refresh once per local day if missed, then always evaluate deliveries."""
        now = now or utc_now()
        async with self.db.session_factory() as session:
            last = await repo.last_successful_refresh(session)
        last_started = last.started_at if last is not None else None
        if should_run_refresh(last_started, now, self.tz):
            log.info("startup catch-up: running missed refresh")
            await self.run_refresh(now)
        await self.run_delivery(now)


def should_run_refresh(last_started, now: datetime, tz) -> bool:
    """The daily refresh runs at startup only if it has not already run today
    (in the configured local timezone)."""
    if last_started is None:
        return True
    return local_date(tz, last_started) < local_date(tz, now)


def _outcome(processed: int, failures: int) -> JobOutcome:
    if failures == 0:
        return JobOutcome.SUCCESS
    if failures < processed:
        return JobOutcome.PARTIAL
    return JobOutcome.FAILURE
