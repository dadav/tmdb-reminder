"""APScheduler wiring.

Uses the stable AsyncIOScheduler (APScheduler 3.11.x). Schedules are static and
in-memory; all business and delivery state lives in application tables, not the
scheduler job store. Jobs coalesce and never overlap (`max_instances=1`).
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import Settings
from .jobs import Jobs


def build_scheduler(settings: Settings, jobs: Jobs) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    reminder = settings.reminder_time_parsed
    scheduler.add_job(
        jobs.run_refresh,
        CronTrigger(hour=reminder.hour, minute=reminder.minute, timezone=settings.timezone),
        id="daily_refresh",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        jobs.run_delivery,
        IntervalTrigger(hours=1),
        id="hourly_delivery",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    return scheduler
