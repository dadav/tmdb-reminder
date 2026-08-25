"""Integration tests for the tracking service (require PostgreSQL)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from conftest import integration, make_settings
from factories import FakeAdapter, movie_details, movie_providers, tv_details
from tmdb_reminder.enums import (
    AvailabilitySource,
    DeliveryStatus,
    EventState,
    MediaType,
    TitleStatus,
)
from tmdb_reminder.errors import CapacityExceededError, TmdbUnavailableError
from tmdb_reminder.models import NotificationDelivery, ReleaseEvent, TrackedTitle
from tmdb_reminder.time_utils import start_of_local_day_utc
from tmdb_reminder.tracking import repository as repo
from tmdb_reminder.tracking.service import TrackingService

pytestmark = integration

NOW = datetime(2026, 8, 12, 6, 0, tzinfo=UTC)


def _service(adapter: FakeAdapter, **over) -> TrackingService:
    return TrackingService(make_settings(**over), adapter)


async def _events(session, key: str) -> list[ReleaseEvent]:
    stmt = (
        select(ReleaseEvent)
        .where(ReleaseEvent.source_event_key == key)
        .order_by(ReleaseEvent.revision)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _deliveries(session) -> list[NotificationDelivery]:
    return list((await session.execute(select(NotificationDelivery))).scalars().all())


async def test_track_movie_creates_event_and_delivery(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)

    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    assert title.status == TitleStatus.ACTIVE.value
    assert title.title == "The Matrix"
    events = await _events(session, "movie:603:digital:DE")
    assert len(events) == 1
    assert events[0].source_date == date(2026, 9, 10)
    assert events[0].scheduled_date == date(2026, 9, 10)
    deliveries = await _deliveries(session)
    assert len(deliveries) == 1
    assert deliveries[0].status == DeliveryStatus.PENDING.value


async def test_track_movie_applies_availability_delay(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=NOW.date())
    svc = _service(adapter, availability_delay_days=2)

    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    event = (await _events(session, "movie:603:digital:DE"))[0]
    assert title.status == TitleStatus.ACTIVE.value
    assert event.source_date == date(2026, 8, 12)
    assert event.scheduled_date == date(2026, 8, 14)


async def test_offset_change_creates_normal_movie_revision(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    await _service(adapter).track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    first_delivery = (await _deliveries(session))[0]
    first_delivery.status = DeliveryStatus.SENT.value
    await session.commit()

    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await _service(adapter, availability_delay_days=2).refresh_title(session, title, NOW)
    await session.commit()

    events = await _events(session, "movie:603:digital:DE")
    assert [event.scheduled_date for event in events] == [
        date(2026, 9, 10),
        date(2026, 9, 12),
    ]
    assert events[1].source_date == date(2026, 9, 10)
    new_delivery = next(
        delivery
        for delivery in await _deliveries(session)
        if delivery.status == DeliveryStatus.PENDING.value
    )
    assert new_delivery.is_revised is True


async def test_track_is_idempotent(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)

    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    titles = (await session.execute(select(TrackedTitle))).scalars().all()
    assert len(titles) == 1
    assert len(await _events(session, "movie:603:digital:DE")) == 1
    assert len(await _deliveries(session)) == 1


async def test_date_change_creates_revision_and_cancels_unsent(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    # New digital date discovered.
    adapter.movies[603] = movie_details(603, digital=date(2026, 10, 1))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    events = await _events(session, "movie:603:digital:DE")
    assert len(events) == 2
    assert events[0].state == EventState.SUPERSEDED.value
    assert events[1].state == EventState.CURRENT.value
    assert events[1].revision == 2
    deliveries = await _deliveries(session)
    statuses = sorted(d.status for d in deliveries)
    assert statuses == [DeliveryStatus.CANCELLED.value, DeliveryStatus.PENDING.value]


async def test_revised_flag_when_prior_revision_delivered(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    # Mark the first delivery as sent.
    delivery = (await _deliveries(session))[0]
    delivery.status = DeliveryStatus.SENT.value
    await session.commit()

    adapter.movies[603] = movie_details(603, digital=date(2026, 10, 1))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    new_delivery = next(
        d for d in await _deliveries(session) if d.status == DeliveryStatus.PENDING.value
    )
    assert new_delivery.is_revised is True


async def test_date_removal_withdraws_movie_event(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    adapter.movies[603] = movie_details(603, digital=None)
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    events = await _events(session, "movie:603:digital:DE")
    assert events[0].state == EventState.WITHDRAWN.value
    assert (await _deliveries(session))[0].status == DeliveryStatus.CANCELLED.value
    # Title remains active and eligible for polling.
    assert (await repo.get_title(session, MediaType.MOVIE, 603)).status == TitleStatus.ACTIVE.value


async def test_completion_and_reopen_on_new_date(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    # Complete the movie (as the delivery job would after send).
    svc.complete_movie(title, date(2026, 9, 10), NOW)
    await session.commit()
    assert title.status == TitleStatus.COMPLETED.value
    assert title.revision_watch_until is not None

    # A brand-new future date reopens tracking.
    adapter.movies[603] = movie_details(603, digital=date(2027, 1, 5))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    result = await svc.refresh_title(session, title, NOW)
    await session.commit()
    assert result.created is True
    assert title.status == TitleStatus.ACTIVE.value
    assert title.revision_watch_until is None


async def test_stop_and_reactivate(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    await svc.stop(session, MediaType.MOVIE, 603)
    await session.commit()
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    assert title.status == TitleStatus.STOPPED.value
    # Unsent delivery cancelled, but the event history is preserved.
    assert (await _deliveries(session))[0].status == DeliveryStatus.CANCELLED.value
    assert len(await _events(session, "movie:603:digital:DE")) == 1

    # Reactivate through the same idempotent track operation.
    reactivated = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    assert reactivated.status == TitleStatus.ACTIVE.value


async def test_capacity_limit(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    adapter.movies[604] = movie_details(604, digital=date(2026, 9, 11))
    svc = _service(adapter, max_tracked_titles=1)

    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    with pytest.raises(CapacityExceededError):
        await svc.track(session, MediaType.MOVIE, 604, NOW)


async def test_failed_initial_fetch_creates_no_record(session):
    adapter = FakeAdapter()
    adapter.fail_ids.add(999)
    svc = _service(adapter)

    with pytest.raises(TmdbUnavailableError):
        await svc.track(session, MediaType.MOVIE, 999, NOW)
    await session.rollback()
    titles = (await session.execute(select(TrackedTitle))).scalars().all()
    assert len(titles) == 0


async def test_tv_episode_events_and_no_autocompletion(session):
    adapter = FakeAdapter()
    adapter.tvs[1399] = tv_details(1399, air_date=date(2026, 9, 1), season=2, episode=5)
    svc = _service(adapter)
    title = await svc.track(session, MediaType.TV, 1399, NOW)
    await session.commit()
    assert len(await _events(session, "tv:1399:s2e5")) == 1

    # Next episode becomes a distinct event; TV stays active.
    adapter.tvs[1399] = tv_details(1399, air_date=date(2026, 9, 8), season=2, episode=6)
    title = await repo.get_title(session, MediaType.TV, 1399)
    await svc.refresh_title(session, title, NOW)
    await session.commit()
    assert len(await _events(session, "tv:1399:s2e6")) == 1
    previous = (await _events(session, "tv:1399:s2e5"))[0]
    assert previous.state == EventState.CURRENT.value
    assert (await _deliveries(session))[0].status == DeliveryStatus.PENDING.value
    assert (await repo.latest_current_event_for_title(session, title.id)).source_event_key == (
        "tv:1399:s2e5"
    )
    assert title.status == TitleStatus.ACTIVE.value


async def test_offset_change_rebases_retained_tv_episode(session):
    adapter = FakeAdapter()
    adapter.tvs[1399] = tv_details(1399, air_date=date(2026, 8, 13), season=2, episode=5)
    await _service(adapter, availability_delay_days=1).track(session, MediaType.TV, 1399, NOW)
    await session.commit()

    adapter.tvs[1399] = tv_details(1399, air_date=date(2026, 8, 20), season=2, episode=6)
    title = await repo.get_title(session, MediaType.TV, 1399)
    await _service(adapter, availability_delay_days=3).refresh_title(session, title, NOW)
    await session.commit()

    episode_five = await _events(session, "tv:1399:s2e5")
    assert len(episode_five) == 2
    assert episode_five[0].state == EventState.SUPERSEDED.value
    assert episode_five[1].state == EventState.CURRENT.value
    assert episode_five[1].source_date == date(2026, 8, 13)
    assert episode_five[1].scheduled_date == date(2026, 8, 16)
    episode_six = await _events(session, "tv:1399:s2e6")
    assert episode_six[0].scheduled_date == date(2026, 8, 23)


async def test_metadata_only_refresh_of_stopped_title_creates_no_delivery(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    await svc.stop(session, MediaType.MOVIE, 603)
    await session.commit()

    adapter.movies[603] = movie_details(603, title="Updated title", digital=date(2026, 10, 1))
    await svc.refresh_title(session, title, NOW, metadata_only=True)
    await session.commit()

    assert title.status == TitleStatus.STOPPED.value
    assert title.title == "Updated title"
    assert len(await _deliveries(session)) == 1
    assert (await _deliveries(session))[0].status == DeliveryStatus.CANCELLED.value


async def test_track_available_movie_completes_without_delivery(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    svc = _service(adapter)

    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    assert title.status == TitleStatus.COMPLETED.value
    assert title.available_since == date(2026, 8, 1)
    expected_watch_day = date(2026, 8, 1) + timedelta(days=svc.settings.revision_watch_days + 1)
    assert title.revision_watch_until == start_of_local_day_utc(svc.tz, expected_watch_day)
    assert len(await _events(session, "movie:603:digital:DE")) == 0
    assert len(await _deliveries(session)) == 0


async def test_availability_cancels_existing_future_reminder(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    assert (await _deliveries(session))[0].status == DeliveryStatus.PENDING.value

    # The movie becomes available; availability outranks the pending digital date.
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 5))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert title.status == TitleStatus.COMPLETED.value
    assert title.available_since == date(2026, 8, 5)
    events = await _events(session, "movie:603:digital:DE")
    assert events[0].state == EventState.WITHDRAWN.value
    assert (await _deliveries(session))[0].status == DeliveryStatus.CANCELLED.value


async def test_availability_date_correction_updates_watch(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    first_watch = title.revision_watch_until

    adapter.movies[603] = movie_details(603, available=date(2026, 7, 1))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert title.available_since == date(2026, 7, 1)
    assert title.revision_watch_until is not None
    assert title.revision_watch_until != first_watch


async def test_availability_removal_reopens_with_future_digital(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    # Availability disappears but a future digital date appears.
    adapter.movies[603] = movie_details(603, digital=date(2026, 11, 1))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    result = await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert result.created is True
    assert title.status == TitleStatus.ACTIVE.value
    assert title.available_since is None
    assert title.revision_watch_until is None
    events = await _events(session, "movie:603:digital:DE")
    assert events[-1].state == EventState.CURRENT.value
    assert any(d.status == DeliveryStatus.PENDING.value for d in await _deliveries(session))


async def test_availability_removal_reopens_unknown(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    # Availability disappears with no future digital date: reopen in unknown state.
    adapter.movies[603] = movie_details(603)
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert title.status == TitleStatus.ACTIVE.value
    assert title.available_since is None
    assert title.revision_watch_until is None
    assert len(await _deliveries(session)) == 0


async def test_stopped_title_metadata_refresh_updates_available_since(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    await svc.stop(session, MediaType.MOVIE, 603)
    await session.commit()

    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    await svc.refresh_title(session, title, NOW, metadata_only=True)
    await session.commit()

    assert title.status == TitleStatus.STOPPED.value
    assert title.available_since == date(2026, 8, 1)
    # No reminder reconciliation for a stopped title: the cancelled delivery stays.
    assert (await _deliveries(session))[0].status == DeliveryStatus.CANCELLED.value


async def test_provider_request_skipped_when_release_has_future_date(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    adapter.providers[603] = movie_providers()
    svc = _service(adapter)

    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    assert adapter.watch_provider_calls == []


async def test_provider_request_skipped_when_release_available(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    adapter.providers[603] = movie_providers()
    svc = _service(adapter)

    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    assert adapter.watch_provider_calls == []


async def test_provider_availability_completes_without_date_event_or_delivery(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)  # no dates at all
    adapter.providers[603] = movie_providers(offering="flatrate")
    svc = _service(adapter)

    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    assert adapter.watch_provider_calls == [603]
    assert title.status == TitleStatus.COMPLETED.value
    assert title.available_since is None
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
    assert title.revision_watch_until is not None
    assert len(await _events(session, "movie:603:digital:DE")) == 0
    assert len(await _deliveries(session)) == 0


async def test_provider_unavailable_leaves_unknown_state(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers(link_only=True)  # link only, not available
    svc = _service(adapter)

    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    assert adapter.watch_provider_calls == [603]
    assert title.status == TitleStatus.ACTIVE.value
    assert title.availability_source is None
    assert title.available_since is None
    assert len(await _deliveries(session)) == 0


async def test_provider_failure_creates_no_record(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)  # no dates -> provider fallback consulted
    adapter.provider_fail_ids.add(603)
    svc = _service(adapter)

    with pytest.raises(TmdbUnavailableError):
        await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.rollback()

    titles = (await session.execute(select(TrackedTitle))).scalars().all()
    assert len(titles) == 0


async def test_provider_failure_preserves_existing_state(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    assert (await _deliveries(session))[0].status == DeliveryStatus.PENDING.value

    # Date disappears and providers fail: the refresh raises and leaves prior state.
    adapter.movies[603] = movie_details(603)
    adapter.provider_fail_ids.add(603)
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    with pytest.raises(TmdbUnavailableError):
        await svc.refresh_title(session, title, NOW)
    await session.rollback()

    title = await repo.get_title(session, MediaType.MOVIE, 603)
    assert title.status == TitleStatus.ACTIVE.value
    events = await _events(session, "movie:603:digital:DE")
    assert events[0].state == EventState.CURRENT.value
    assert (await _deliveries(session))[0].status == DeliveryStatus.PENDING.value


async def test_provider_availability_sticky_after_disappearance(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers()
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    watch = title.revision_watch_until

    # Providers disappear, still no dates: availability stays sticky.
    adapter.providers[603] = movie_providers(link_only=True)
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert title.status == TitleStatus.COMPLETED.value
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
    assert title.revision_watch_until == watch  # window not reset


async def test_provider_availability_sticky_against_future_digital(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers()
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()

    # A future digital date appears; sticky provider availability blocks a reminder.
    adapter.movies[603] = movie_details(603, digital=date(2026, 12, 1))
    for _ in range(2):
        title = await repo.get_title(session, MediaType.MOVIE, 603)
        await svc.refresh_title(session, title, NOW)
        await session.commit()

    assert title.status == TitleStatus.COMPLETED.value
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
    assert len(await _events(session, "movie:603:digital:DE")) == 0
    assert len(await _deliveries(session)) == 0


async def test_provider_availability_upgraded_by_past_release_date(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers()
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value

    # A past release date now exists: upgrade to dated availability.
    adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert title.status == TitleStatus.COMPLETED.value
    assert title.available_since == date(2026, 8, 1)
    assert title.availability_source == AvailabilitySource.RELEASE_DATE.value


async def test_provider_discovery_withdraws_existing_reminder(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    assert (await _deliveries(session))[0].status == DeliveryStatus.PENDING.value

    # Date removed, providers now carry the movie: withdraw the reminder.
    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers()
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    await svc.refresh_title(session, title, NOW)
    await session.commit()

    assert title.status == TitleStatus.COMPLETED.value
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
    events = await _events(session, "movie:603:digital:DE")
    assert events[0].state == EventState.WITHDRAWN.value
    assert (await _deliveries(session))[0].status == DeliveryStatus.CANCELLED.value


async def test_metadata_only_refresh_stores_provider_availability(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    await svc.stop(session, MediaType.MOVIE, 603)
    await session.commit()

    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers()
    await svc.refresh_title(session, title, NOW, metadata_only=True)
    await session.commit()

    assert title.status == TitleStatus.STOPPED.value
    assert title.available_since is None
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value


async def test_metadata_only_refresh_keeps_provider_availability_sticky(session):
    adapter = FakeAdapter()
    adapter.movies[603] = movie_details(603)
    adapter.providers[603] = movie_providers()
    svc = _service(adapter)
    title = await svc.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    await svc.stop(session, MediaType.MOVIE, 603)
    await session.commit()

    # Provider disappearance does not erase the historical release signal.
    adapter.providers[603] = movie_providers(link_only=True)
    await svc.refresh_title(session, title, NOW, metadata_only=True)
    await session.commit()
    assert title.status == TitleStatus.STOPPED.value
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value

    # A later future date also cannot replace sticky provider availability.
    adapter.movies[603] = movie_details(603, digital=date(2026, 12, 1))
    await svc.refresh_title(session, title, NOW, metadata_only=True)
    await session.commit()
    assert title.status == TitleStatus.STOPPED.value
    assert title.available_since is None
    assert title.availability_source == AvailabilitySource.WATCH_PROVIDER.value
    assert len(await _events(session, "movie:603:digital:DE")) == 0
    assert len(await _deliveries(session)) == 0


async def test_tv_unknown_date_keeps_active_without_event(session):
    adapter = FakeAdapter()
    adapter.tvs[1399] = tv_details(1399, air_date=None)
    svc = _service(adapter)
    title = await svc.track(session, MediaType.TV, 1399, NOW)
    await session.commit()
    assert title.status == TitleStatus.ACTIVE.value
    assert len(await _deliveries(session)) == 0
