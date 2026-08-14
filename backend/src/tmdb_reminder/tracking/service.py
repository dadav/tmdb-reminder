"""Tracking orchestration: track / stop / refresh and release reconciliation.

This is the heart of the domain. It turns TMDB payloads into `release_events`
and `notification_deliveries`, handling revisions when a date changes and
withdrawals when a date disappears, and drives movie completion/reopening.

All functions take an explicit `now` (UTC) so tests are deterministic without
real clocks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..config import Settings
from ..enums import (
    AvailabilitySource,
    DeliveryStatus,
    EventState,
    MediaType,
    SyncStatus,
    TitleStatus,
)
from ..errors import CapacityExceededError, TitleNotFoundError
from ..models import NotificationDelivery, ReleaseEvent, TrackedTitle
from ..time_utils import (
    local_date,
    reminder_due_at,
    reminder_expiry_at,
    start_of_local_day_utc,
)
from ..tmdb.adapter import TmdbAdapter
from ..tmdb.mapping import (
    movie_available_from_providers,
    movie_release_candidate,
    select_movie_release,
    snapshot_from_movie,
    snapshot_from_tv,
    tv_release_candidate,
)
from ..value_objects import ReleaseCandidate, TitleSnapshot
from . import repository as repo

log = logging.getLogger("tmdb_reminder.tracking")


@dataclass
class ReconcileResult:
    created: bool = False
    superseded: bool = False
    withdrawn: bool = False
    unchanged: bool = False


@dataclass(frozen=True)
class FetchedTitle:
    snapshot: TitleSnapshot
    candidate: ReleaseCandidate | None
    available_since: date | None = None
    availability_source: AvailabilitySource | None = None


class TrackingService:
    def __init__(self, settings: Settings, adapter: TmdbAdapter) -> None:
        self.settings = settings
        self.adapter = adapter
        self.tz = settings.timezone

    # --- TMDB fetch ---

    async def _fetch(self, media_type: MediaType, tmdb_id: int, today) -> FetchedTitle:
        """Fetch and normalize the title state used by reconciliation.

        Release dates stay authoritative. The watch-provider fallback is consulted
        only when release selection yields neither a past availability date nor a
        future digital date. A provider fetch failure fails the whole fetch.
        """
        if media_type == MediaType.MOVIE:
            region = self.settings.tmdb_region
            details = await self.adapter.movie_details(tmdb_id)
            snapshot = snapshot_from_movie(details)
            release = select_movie_release(details.get("release_dates", {}), region, today)
            candidate = movie_release_candidate(tmdb_id, release.next_digital_date, region)
            available_since = release.available_since
            source: AvailabilitySource | None = None
            if available_since is not None:
                source = AvailabilitySource.RELEASE_DATE
            elif release.next_digital_date is None:
                providers = await self.adapter.movie_watch_providers(tmdb_id)
                if movie_available_from_providers(providers, region):
                    source = AvailabilitySource.WATCH_PROVIDER
            return FetchedTitle(snapshot, candidate, available_since, source)
        details = await self.adapter.tv_details(tmdb_id)
        snapshot = snapshot_from_tv(details)
        candidate = tv_release_candidate(tmdb_id, details, today)
        return FetchedTitle(snapshot, candidate)

    # --- Public operations ---

    async def track(
        self, session, media_type: MediaType, tmdb_id: int, now: datetime
    ) -> TrackedTitle:
        """Idempotent PUT: create, reactivate, or retain active tracking.

        Authoritative details are fetched first; a failed fetch makes no change,
        so a new title never leaves a partial record.
        """
        today = local_date(self.tz, now)
        existing = await repo.get_title(session, media_type, tmdb_id)

        if existing is None:
            total = await repo.count_titles(session, "active") + await repo.count_titles(
                session, "history"
            )
            if total >= self.settings.max_tracked_titles:
                raise CapacityExceededError(
                    f"Tracked-title limit reached ({self.settings.max_tracked_titles})"
                )

        fetched = await self._fetch(media_type, tmdb_id, today)

        # The upstream fetch intentionally happens before the database lock. This
        # keeps a slow TMDB request from blocking a concurrent idempotent PUT.
        await repo.lock_title_identity(session, media_type, tmdb_id)
        existing = await repo.get_title(session, media_type, tmdb_id)

        if existing is None:
            title = TrackedTitle(media_type=media_type.value, tmdb_id=tmdb_id)
            session.add(title)
        else:
            title = existing
            title.status = TitleStatus.ACTIVE.value
            title.revision_watch_until = None

        self._apply_snapshot(title, fetched.snapshot, now)
        await session.flush()

        candidate = self._effective_movie_candidate(title, fetched)
        result = await self._reconcile(session, title, candidate, now)
        self._apply_movie_lifecycle(title, fetched, result, now)
        await session.flush()
        log.info(
            "title tracked",
            extra={
                "media_type": media_type.value,
                "tmdb_id": tmdb_id,
                "title_id": title.id,
                "is_new": existing is None,
                "reconcile": result.__dict__,
            },
        )
        return title

    async def stop(self, session, media_type: MediaType, tmdb_id: int) -> TrackedTitle:
        """Soft-stop: preserve history, cancel unsent deliveries, no purge."""
        title = await repo.get_title(session, media_type, tmdb_id)
        if title is None:
            raise TitleNotFoundError("Title is not tracked")
        title.status = TitleStatus.STOPPED.value
        await self._cancel_unsent_for_title(session, title.id)
        await session.flush()
        log.info(
            "title stopped",
            extra={"media_type": media_type.value, "tmdb_id": tmdb_id, "title_id": title.id},
        )
        return title

    async def refresh_title(
        self,
        session,
        title: TrackedTitle,
        now: datetime,
        *,
        metadata_only: bool = False,
    ) -> ReconcileResult:
        """Re-fetch metadata and reconcile the current release. Raises on TMDB failure."""
        today = local_date(self.tz, now)
        media_type = MediaType(title.media_type)
        fetched = await self._fetch(media_type, title.tmdb_id, today)
        self._apply_snapshot(title, fetched.snapshot, now)
        if metadata_only:
            # A dormant/stopped title refreshes cached availability without
            # reconciling reminders or lifecycle. Provider-confirmed availability
            # remains sticky unless an exact past release date upgrades it.
            self._apply_metadata_availability(title, fetched)
            await session.flush()
            return ReconcileResult(unchanged=True)
        candidate = self._effective_movie_candidate(title, fetched)
        result = await self._reconcile(session, title, candidate, now)
        self._apply_movie_lifecycle(title, fetched, result, now)
        await session.flush()
        return result

    # --- Reconciliation ---

    async def _reconcile(
        self, session, title: TrackedTitle, candidate: ReleaseCandidate | None, now: datetime
    ) -> ReconcileResult:
        if candidate is None:
            return await self._reconcile_absent(session, title, now)

        if MediaType(title.media_type) == MediaType.TV:
            await self._retire_previous_tv_events(session, title.id, candidate.source_event_key)

        key = candidate.source_event_key
        cur = await repo.current_event(session, key)

        if cur is None:
            next_rev = await repo.max_revision(session, key) + 1
            revised = next_rev > 1 and await repo.any_revision_delivered(session, key)
            await self._create_event(session, title, candidate, next_rev, revised, now)
            return ReconcileResult(created=True)

        if cur.scheduled_date == candidate.scheduled_date:
            cur.last_observed_at = now
            return ReconcileResult(unchanged=True)

        # Date changed: supersede the current revision, cancel its unsent deliveries.
        cur.state = EventState.SUPERSEDED.value
        await self._cancel_unsent_for_event(session, cur.id)
        revised = await repo.any_revision_delivered(session, key)
        await self._create_event(session, title, candidate, cur.revision + 1, revised, now)
        return ReconcileResult(superseded=True, created=True)

    async def _retire_previous_tv_events(
        self, session, title_id: int, current_source_key: str
    ) -> None:
        """Only TMDB's latest next episode may remain current for a TV title."""
        for event in await repo.current_events_for_title(session, title_id):
            if event.source_event_key == current_source_key:
                continue
            event.state = EventState.SUPERSEDED.value
            await self._cancel_unsent_for_event(session, event.id)

    async def _reconcile_absent(
        self, session, title: TrackedTitle, now: datetime
    ) -> ReconcileResult:
        """No candidate date. Movies withdraw their current digital event; TV keeps
        already-observed episode events as history."""
        if MediaType(title.media_type) != MediaType.MOVIE:
            return ReconcileResult(unchanged=True)
        key = f"movie:{title.tmdb_id}:digital:{self.settings.tmdb_region}"
        cur = await repo.current_event(session, key)
        if cur is None:
            return ReconcileResult(unchanged=True)
        cur.state = EventState.WITHDRAWN.value
        await self._cancel_unsent_for_event(session, cur.id)
        return ReconcileResult(withdrawn=True)

    async def _create_event(
        self,
        session,
        title: TrackedTitle,
        candidate: ReleaseCandidate,
        revision: int,
        revised: bool,
        now: datetime,
    ) -> ReleaseEvent:
        event = ReleaseEvent(
            tracked_title_id=title.id,
            source_event_key=candidate.source_event_key,
            revision=revision,
            kind=candidate.kind.value,
            scheduled_date=candidate.scheduled_date,
            season_number=candidate.season_number,
            episode_number=candidate.episode_number,
            state=EventState.CURRENT.value,
            first_observed_at=now,
            last_observed_at=now,
        )
        session.add(event)
        await session.flush()
        delivery = NotificationDelivery(
            release_event_id=event.id,
            due_at=reminder_due_at(
                self.tz, candidate.scheduled_date, self.settings.reminder_time_parsed
            ),
            expiry_at=reminder_expiry_at(self.tz, candidate.scheduled_date),
            status=DeliveryStatus.PENDING.value,
            is_revised=revised,
        )
        session.add(delivery)
        return event

    # --- Lifecycle ---

    def _effective_movie_candidate(
        self, title: TrackedTitle, fetched: FetchedTitle
    ) -> ReleaseCandidate | None:
        """Suppress reminders after provider availability proved release occurred."""
        if (
            MediaType(title.media_type) == MediaType.MOVIE
            and title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
            and fetched.availability_source != AvailabilitySource.RELEASE_DATE
        ):
            return None
        return fetched.candidate

    def _apply_metadata_availability(self, title: TrackedTitle, fetched: FetchedTitle) -> None:
        """Persist availability metadata without changing lifecycle state."""
        if MediaType(title.media_type) != MediaType.MOVIE:
            title.available_since = None
            title.availability_source = None
            return
        if (
            title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
            and fetched.availability_source != AvailabilitySource.RELEASE_DATE
        ):
            return
        title.available_since = fetched.available_since
        title.availability_source = (
            fetched.availability_source.value if fetched.availability_source is not None else None
        )

    def _apply_movie_lifecycle(
        self,
        title: TrackedTitle,
        fetched: FetchedTitle,
        result: ReconcileResult,
        now: datetime,
    ) -> None:
        """Fold movie availability into the title lifecycle after reconciliation.

        Availability outranks a later digital release: an available movie carries
        no reminder (the reconcile withdrew any current digital event) and becomes
        completed under revision watch. Dated availability disappearing reopens the
        movie as active; provider-confirmed availability is sticky and never
        reopens. TV titles pass through unchanged.
        """
        if MediaType(title.media_type) != MediaType.MOVIE:
            return

        source = fetched.availability_source

        if source == AvailabilitySource.RELEASE_DATE:
            # Dated availability (new, corrected, or upgraded from a provider one):
            # store the date and complete under revision watch from it.
            assert fetched.available_since is not None
            title.available_since = fetched.available_since
            title.availability_source = AvailabilitySource.RELEASE_DATE.value
            self.complete_movie(title, fetched.available_since, now)
            return

        if source == AvailabilitySource.WATCH_PROVIDER:
            # Undated provider availability. On first confirmation, withdraw any
            # reminder, complete, and start the revision-watch window from today;
            # afterwards it is sticky and idempotent (no window reset).
            already_sticky = (
                title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
                and title.status == TitleStatus.COMPLETED.value
            )
            title.available_since = None
            title.availability_source = AvailabilitySource.WATCH_PROVIDER.value
            if not already_sticky:
                self.complete_movie(title, local_date(self.tz, now), now)
            return

        # No availability signal this refresh.
        if title.availability_source == AvailabilitySource.WATCH_PROVIDER.value:
            # Sticky: a later provider disappearance or future digital date keeps
            # the movie completed. Candidate suppression prevents reminder creation.
            if title.status != TitleStatus.COMPLETED.value:
                self.complete_movie(title, local_date(self.tz, now), now)
            return

        if title.available_since is not None:
            # Dated availability disappeared: reopen for its future digital reminder
            # (if the reconcile created one) or an unknown state.
            title.available_since = None
            title.availability_source = None
            title.status = TitleStatus.ACTIVE.value
            title.revision_watch_until = None
            return

        # Never available: a newly discovered date reopens a completed movie.
        if result.created and title.status == TitleStatus.COMPLETED.value:
            title.status = TitleStatus.ACTIVE.value
            title.revision_watch_until = None

    def complete_movie(self, title: TrackedTitle, release_date, now: datetime) -> None:
        """Mark a movie completed and set its revision-watch deadline."""
        if MediaType(title.media_type) != MediaType.MOVIE:
            return
        title.status = TitleStatus.COMPLETED.value
        watch_end_day = release_date + timedelta(days=self.settings.revision_watch_days + 1)
        title.revision_watch_until = start_of_local_day_utc(self.tz, watch_end_day)

    # --- Helpers ---

    def _apply_snapshot(self, title: TrackedTitle, snapshot: TitleSnapshot, now: datetime) -> None:
        title.title = snapshot.title
        title.original_title = snapshot.original_title
        title.overview = snapshot.overview
        title.poster_path = snapshot.poster_path
        title.release_year = snapshot.release_year
        title.metadata_refreshed_at = now
        title.last_sync_status = SyncStatus.OK.value
        title.last_sync_at = now
        title.last_sync_error = None

    async def _cancel_unsent_for_event(self, session, event_id: int) -> None:
        for delivery in await repo.unsent_deliveries_for_event(session, event_id):
            delivery.status = DeliveryStatus.CANCELLED.value

    async def _cancel_unsent_for_title(self, session, title_id: int) -> None:
        for eid in await repo.event_ids_for_title(session, title_id):
            await self._cancel_unsent_for_event(session, eid)
