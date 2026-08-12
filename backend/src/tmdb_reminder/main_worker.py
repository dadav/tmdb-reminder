"""Scheduler worker entrypoint.

Runs the startup catch-up (missed daily refresh + pending deliveries), then
starts the APScheduler loop and blocks until a termination signal.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from .config import get_settings
from .db import Database
from .logging_config import configure_logging
from .notifications.delivery import DeliveryService
from .notifications.gotify import GotifyClient
from .tmdb.adapter import TmdbAdapter
from .tracking.service import TrackingService
from .worker.jobs import Jobs
from .worker.scheduler import build_scheduler

log = logging.getLogger("tmdb_reminder.worker")


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info(
        "worker starting",
        extra={
            "tmdb_configured": settings.tmdb_configured,
            "gotify_configured": settings.gotify_configured,
        },
    )

    db = Database(settings.database_url)
    adapter = TmdbAdapter(settings)
    gotify = GotifyClient(settings)
    tracking = TrackingService(settings, adapter)
    delivery = DeliveryService(settings, gotify, tracking)
    jobs = Jobs(settings, db, tracking, delivery)

    scheduler = None
    try:
        await jobs.startup_catchup()

        scheduler = build_scheduler(settings, jobs)
        scheduler.start()
        log.info("worker started; scheduler running")

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):  # non-unix has no signal handlers
                loop.add_signal_handler(sig, stop.set)
        await stop.wait()
    except Exception:
        log.exception("worker failed")
        raise
    finally:
        log.info("worker shutting down")
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await gotify.aclose()
        await db.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
