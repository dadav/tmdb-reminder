"""Time helpers.

Instants are stored and compared in UTC. Releases are calendar dates. Reminder
windows are evaluated in the configured local timezone with `zoneinfo`, which
carries daylight-saving transitions correctly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_date(tz: ZoneInfo, at: datetime | None = None) -> date:
    """Current (or given) instant expressed as a calendar date in `tz`."""
    at = at or utc_now()
    return at.astimezone(tz).date()


def local_datetime_to_utc(tz: ZoneInfo, day: date, at_time: time) -> datetime:
    """Combine a local calendar day and wall-clock time into a UTC instant.

    Uses `fold=0`; ambiguous local times (autumn DST) resolve to the earlier
    instant, which is the safe choice for "send at or after" reminder windows.
    """
    local = datetime.combine(day, at_time, tzinfo=tz)
    return local.astimezone(UTC)


def start_of_local_day_utc(tz: ZoneInfo, day: date) -> datetime:
    """UTC instant of local midnight at the start of `day`."""
    return local_datetime_to_utc(tz, day, time(0, 0))


def reminder_due_at(tz: ZoneInfo, release_day: date, reminder: time) -> datetime:
    """Due instant: `reminder` wall-clock on the calendar day before release."""
    return local_datetime_to_utc(tz, release_day - timedelta(days=1), reminder)


def reminder_expiry_at(tz: ZoneInfo, release_day: date) -> datetime:
    """Expiry instant: end of release day = local midnight starting the next day."""
    return start_of_local_day_utc(tz, release_day + timedelta(days=1))
