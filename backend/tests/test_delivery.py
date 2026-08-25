"""Integration tests for delivery evaluation (require PostgreSQL)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from conftest import integration, make_settings
from factories import FakeAdapter, FakeGotify, movie_details, tv_details
from tmdb_reminder.enums import DeliveryStatus, EventState, MediaType, TitleStatus
from tmdb_reminder.errors import GotifyUnavailableError
from tmdb_reminder.models import NotificationDelivery, ReleaseEvent, TrackedTitle
from tmdb_reminder.notifications.delivery import (
    DeliveryService,
    claim_delivery,
    recover_stale_claims,
)
from tmdb_reminder.tracking import repository as repo
from tmdb_reminder.tracking.service import TrackingService

pytestmark = integration

NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


async def _make_movie_delivery(session, adapter, gotify, *, release: date, **over):
    settings = make_settings(**over)
    tracking = TrackingService(settings, adapter)
    delivery_svc = DeliveryService(settings, gotify, tracking)
    adapter.movies[603] = movie_details(603, digital=release)
    await tracking.track(session, MediaType.MOVIE, 603, NOW)
    await session.commit()
    delivery = (await session.execute(select(NotificationDelivery))).scalar_one()
    return delivery_svc, delivery


async def test_send_success_records_id_and_completes_movie(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    # Release tomorrow -> on-time (not late).
    svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    delivery.due_at = NOW - timedelta(hours=1)
    delivery.expiry_at = NOW + timedelta(days=1)
    await session.commit()

    counts = await svc.evaluate_due(session, NOW)
    assert counts.sent == 1
    refreshed = await session.get(NotificationDelivery, delivery.id)
    assert refreshed.status == DeliveryStatus.SENT.value
    assert refreshed.gotify_message_id == 100
    assert refreshed.sent_late is False
    assert refreshed.attempts == 1
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    assert title.status == TitleStatus.COMPLETED.value


async def test_same_day_is_late(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    # Tracked while the digital date is still in the future (a same-day date would
    # be availability, not a reminder), then delivered on the release day -> late.
    svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    on_release_day = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    delivery.due_at = on_release_day - timedelta(hours=1)
    delivery.expiry_at = on_release_day + timedelta(hours=6)
    await session.commit()

    await svc.evaluate_due(session, on_release_day)
    refreshed = await session.get(NotificationDelivery, delivery.id)
    assert refreshed.status == DeliveryStatus.SENT.value
    assert refreshed.sent_late is True


async def test_sent_tv_delivery_retires_episode_event(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    settings = make_settings(availability_delay_days=2)
    tracking = TrackingService(settings, adapter)
    delivery_service = DeliveryService(settings, gotify, tracking)
    adapter.tvs[1399] = tv_details(1399, air_date=date(2026, 8, 11), season=2, episode=5)
    await tracking.track(session, MediaType.TV, 1399, NOW)
    delivery = (await session.execute(select(NotificationDelivery))).scalar_one()
    delivery.due_at = NOW - timedelta(hours=1)
    await session.commit()

    counts = await delivery_service.evaluate_due(session, NOW)

    assert counts.sent == 1
    event = (await session.execute(select(ReleaseEvent))).scalar_one()
    assert event.source_date == date(2026, 8, 11)
    assert event.scheduled_date == date(2026, 8, 13)
    assert event.state == EventState.SUPERSEDED.value


async def test_expired_delivery_completes_movie(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    delivery.due_at = NOW - timedelta(days=2)
    delivery.expiry_at = NOW - timedelta(hours=1)  # already expired
    delivery_id = delivery.id
    await session.commit()

    counts = await svc.evaluate_due(session, NOW)
    assert counts.expired == 1
    refreshed = await session.get(NotificationDelivery, delivery_id)
    assert refreshed.status == DeliveryStatus.EXPIRED.value
    assert not gotify.sent
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    assert title.status == TitleStatus.COMPLETED.value


async def test_gotify_failure_returns_to_pending_and_retries(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    delivery.due_at = NOW - timedelta(hours=1)
    delivery.expiry_at = NOW + timedelta(days=1)
    await session.commit()

    gotify.error = GotifyUnavailableError("down")
    counts = await svc.evaluate_due(session, NOW)
    assert counts.failed == 1
    refreshed = await session.get(NotificationDelivery, delivery.id)
    assert refreshed.status == DeliveryStatus.PENDING.value
    assert refreshed.last_error is not None
    assert refreshed.attempts == 1

    # At-least-once: a later run after the outage sends it (attempts increments).
    gotify.error = None
    await svc.evaluate_due(session, NOW)
    refreshed = await session.get(NotificationDelivery, delivery.id)
    assert refreshed.status == DeliveryStatus.SENT.value
    assert refreshed.attempts == 2


async def test_recover_stale_claim(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    _svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    delivery.status = DeliveryStatus.CLAIMED.value
    delivery.lease_expires_at = NOW - timedelta(minutes=1)  # expired lease
    await session.commit()

    recovered = await recover_stale_claims(session, NOW)
    assert recovered == 1
    refreshed = await session.get(NotificationDelivery, delivery.id)
    assert refreshed.status == DeliveryStatus.PENDING.value
    assert refreshed.lease_expires_at is None


async def test_gotify_not_configured_leaves_pending(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    svc, delivery = await _make_movie_delivery(
        session, adapter, gotify, release=date(2026, 8, 13), gotify_url=None, gotify_token=None
    )
    delivery.due_at = NOW - timedelta(hours=1)
    delivery.expiry_at = NOW + timedelta(days=1)
    delivery_id = delivery.id
    await session.commit()

    counts = await svc.evaluate_due(session, NOW)
    assert counts.skipped == 1
    refreshed = await session.get(NotificationDelivery, delivery_id)
    assert refreshed.status == DeliveryStatus.PENDING.value


async def test_concurrent_claim_only_one_wins(session, database):
    adapter, gotify = FakeAdapter(), FakeGotify()
    _svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    delivery.due_at = NOW - timedelta(hours=1)
    await session.commit()
    delivery_id = delivery.id

    async with database.session_factory() as sa, database.session_factory() as sb:
        # Session A locks the row without changing status (holds the lock).
        locked = (
            await sa.execute(
                select(NotificationDelivery)
                .where(NotificationDelivery.id == delivery_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one()
        assert locked is not None
        # Session B cannot claim it while A holds the lock.
        result = await claim_delivery(sb, delivery_id, NOW, 15)
        assert result is None
        await sa.rollback()

    # After the lock is released the row is still claimable.
    claimed = await claim_delivery(session, delivery_id, NOW, 15)
    assert claimed is not None
    assert claimed.status == DeliveryStatus.CLAIMED.value


async def test_soft_stopped_movie_delivery_expiry_does_not_complete(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    # A stopped title whose leftover delivery expires must not flip to completed.
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    title.status = TitleStatus.STOPPED.value
    title_id = title.id
    delivery.status = DeliveryStatus.PENDING.value
    delivery.due_at = NOW - timedelta(days=2)
    delivery.expiry_at = NOW - timedelta(hours=1)
    await session.commit()

    await svc.evaluate_due(session, NOW)
    title = await session.get(TrackedTitle, title_id)
    assert title.status == TitleStatus.STOPPED.value


async def test_stopped_title_never_sends_leftover_pending_delivery(session):
    adapter, gotify = FakeAdapter(), FakeGotify()
    svc, delivery = await _make_movie_delivery(session, adapter, gotify, release=date(2026, 8, 13))
    title = await repo.get_title(session, MediaType.MOVIE, 603)
    title.status = TitleStatus.STOPPED.value
    delivery.due_at = NOW - timedelta(hours=1)
    delivery.expiry_at = NOW + timedelta(hours=1)
    await session.commit()

    counts = await svc.evaluate_due(session, NOW)

    assert counts.skipped == 1
    assert not gotify.sent
    refreshed = await session.get(NotificationDelivery, delivery.id)
    assert refreshed.status == DeliveryStatus.CANCELLED.value
