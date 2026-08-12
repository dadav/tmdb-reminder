"""Delivery evaluation: due windows, transactional claims, at-least-once send.

At-least-once semantics:
1. Recover stale claims whose lease expired (crash recovery).
2. Claim a due row transactionally with `SELECT ... FOR UPDATE SKIP LOCKED`,
   setting a lease and incrementing attempts.
3. Send the message *outside* the claim transaction.
4. On success, record the Gotify message id; on failure, release for retry.

A duplicate is possible only after an ambiguous network result or a crash
between send and record, which the plan accepts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, update

from ..config import Settings
from ..enums import DeliveryStatus, EventKind, EventState, TitleStatus
from ..errors import AppError
from ..logging_config import sanitize
from ..models import NotificationDelivery, ReleaseEvent, TrackedTitle
from ..time_utils import local_date
from ..tracking.service import TrackingService
from .gotify import GotifyClient
from .render import render_message

log = logging.getLogger("tmdb_reminder.delivery")


@dataclass
class DeliveryCounts:
    processed: int = 0
    sent: int = 0
    expired: int = 0
    failed: int = 0
    skipped: int = 0
    recovered: int = 0
    errors: list[str] = field(default_factory=list)


async def recover_stale_claims(session, now: datetime) -> int:
    """Reset claimed deliveries whose lease has expired back to pending."""
    stmt = (
        update(NotificationDelivery)
        .where(
            NotificationDelivery.status == DeliveryStatus.CLAIMED.value,
            NotificationDelivery.lease_expires_at.is_not(None),
            NotificationDelivery.lease_expires_at < now,
        )
        .values(status=DeliveryStatus.PENDING.value, lease_expires_at=None)
    )
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


async def claim_delivery(
    session, delivery_id: int, now: datetime, lease_minutes: int
) -> NotificationDelivery | None:
    """Transactionally claim one pending delivery. Returns None if already taken."""
    stmt = (
        select(NotificationDelivery)
        .where(
            NotificationDelivery.id == delivery_id,
            NotificationDelivery.status == DeliveryStatus.PENDING.value,
        )
        .with_for_update(skip_locked=True)
    )
    delivery = (await session.execute(stmt)).scalar_one_or_none()
    if delivery is None:
        await session.rollback()
        return None
    delivery.status = DeliveryStatus.CLAIMED.value
    delivery.lease_expires_at = now + timedelta(minutes=lease_minutes)
    delivery.attempts += 1
    await session.commit()
    return delivery


class DeliveryService:
    def __init__(self, settings: Settings, gotify: GotifyClient, tracking: TrackingService) -> None:
        self.settings = settings
        self.gotify = gotify
        self.tracking = tracking
        self.tz = settings.timezone

    async def evaluate_due(self, session, now: datetime) -> DeliveryCounts:
        counts = DeliveryCounts()
        counts.recovered = await recover_stale_claims(session, now)

        from ..tracking import repository as repo

        due = await repo.due_deliveries(session, now)
        for delivery in due:
            counts.processed += 1
            await self._process_one(session, delivery.id, now, counts)
        return counts

    async def _process_one(
        self, session, delivery_id: int, now: datetime, counts: DeliveryCounts
    ) -> None:
        delivery = await session.get(NotificationDelivery, delivery_id)
        if delivery is None or delivery.status not in (
            DeliveryStatus.PENDING.value,
            DeliveryStatus.CLAIMED.value,
        ):
            return
        event = await session.get(ReleaseEvent, delivery.release_event_id)
        title = await session.get(TrackedTitle, event.tracked_title_id) if event else None
        if event is None or title is None:
            delivery.status = DeliveryStatus.CANCELLED.value
            delivery.lease_expires_at = None
            delivery.last_error = "Referenced release event or tracked title is missing"
            counts.failed += 1
            counts.errors.append("invalid_delivery_reference")
            await session.commit()
            log.error(
                "delivery reference missing",
                extra={
                    "delivery_id": delivery.id,
                    "release_event_id": delivery.release_event_id,
                },
            )
            return

        if title.status == TitleStatus.STOPPED.value:
            delivery.status = DeliveryStatus.CANCELLED.value
            delivery.lease_expires_at = None
            counts.skipped += 1
            await session.commit()
            log.info(
                "delivery cancelled for stopped title",
                extra={"delivery_id": delivery.id, "title_id": title.id},
            )
            return

        # Expiry: past the end of release day, undelivered events expire.
        if now >= delivery.expiry_at:
            delivery.status = DeliveryStatus.EXPIRED.value
            delivery.lease_expires_at = None
            counts.expired += 1
            self._maybe_complete_movie(event, title, now)
            await session.commit()
            log.info("delivery expired", extra={"delivery_id": delivery.id, "title_id": title.id})
            return

        if not self.settings.gotify_configured:
            counts.skipped += 1
            await session.rollback()
            return

        claimed = await claim_delivery(
            session, delivery.id, now, self.settings.delivery_lease_minutes
        )
        if claimed is None:
            counts.skipped += 1
            return

        is_late = local_date(self.tz, now) >= event.scheduled_date
        message = render_message(
            title, event, claimed, is_late=is_late, priority=self.settings.gotify_priority
        )
        try:
            message_id = await self.gotify.send(message)
        except AppError as exc:
            claimed.status = DeliveryStatus.PENDING.value
            claimed.lease_expires_at = None
            claimed.last_error = str(sanitize(exc.message))
            counts.failed += 1
            counts.errors.append(exc.code)
            await session.commit()
            log.warning(
                "delivery send failed",
                extra={"delivery_id": claimed.id, "error_code": exc.code},
            )
            return

        claimed.status = DeliveryStatus.SENT.value
        claimed.sent_at = now
        claimed.sent_late = is_late
        claimed.gotify_message_id = message_id
        claimed.lease_expires_at = None
        claimed.last_error = None
        counts.sent += 1
        self._maybe_complete_movie(event, title, now)
        await session.commit()
        log.info(
            "delivery sent",
            extra={
                "delivery_id": claimed.id,
                "title_id": title.id,
                "gotify_message_id": message_id,
                "late": is_late,
            },
        )

    def _maybe_complete_movie(
        self, event: ReleaseEvent, title: TrackedTitle, now: datetime
    ) -> None:
        """Movies complete after their current digital event is delivered or expires."""
        if event.kind != EventKind.MOVIE_DIGITAL.value:
            return
        if event.state != EventState.CURRENT.value:
            return
        if title.status == TitleStatus.STOPPED.value:
            return
        self.tracking.complete_movie(title, event.scheduled_date, now)
