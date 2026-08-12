"""Unit tests for reminder-window computation, including DST boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from tmdb_reminder.time_utils import (
    local_date,
    reminder_due_at,
    reminder_expiry_at,
    start_of_local_day_utc,
)

BERLIN = ZoneInfo("Europe/Berlin")
REMINDER = time(9, 0)


def test_due_is_day_before_at_reminder_time():
    # Release 2026-09-10; due 2026-09-09 09:00 Berlin (CEST = UTC+2) -> 07:00 UTC.
    due = reminder_due_at(BERLIN, date(2026, 9, 10), REMINDER)
    assert due == datetime(2026, 9, 9, 7, 0, tzinfo=UTC)


def test_expiry_is_end_of_release_day():
    # End of 2026-09-10 = local midnight starting 2026-09-11 -> 22:00 UTC on 09-10.
    expiry = reminder_expiry_at(BERLIN, date(2026, 9, 10))
    assert expiry == datetime(2026, 9, 10, 22, 0, tzinfo=UTC)


def test_due_across_winter_uses_cet():
    # January release: CET = UTC+1, so 09:00 local -> 08:00 UTC.
    due = reminder_due_at(BERLIN, date(2027, 1, 15), REMINDER)
    assert due == datetime(2027, 1, 14, 8, 0, tzinfo=UTC)


def test_spring_dst_transition_day():
    # DST starts 2027-03-28 in Berlin (clocks jump 02:00 -> 03:00).
    # Reminder for a 2027-03-29 release fires 2027-03-28 09:00 local = 07:00 UTC (CEST).
    due = reminder_due_at(BERLIN, date(2027, 3, 29), REMINDER)
    assert due == datetime(2027, 3, 28, 7, 0, tzinfo=UTC)


def test_autumn_dst_expiry():
    # DST ends 2027-10-31 (25-hour day). End of that day = local midnight 11-01.
    expiry = reminder_expiry_at(BERLIN, date(2027, 10, 31))
    # 2027-11-01 00:00 CET (UTC+1) -> 2027-10-31 23:00 UTC.
    assert expiry == datetime(2027, 10, 31, 23, 0, tzinfo=UTC)


def test_start_of_local_day():
    start = start_of_local_day_utc(BERLIN, date(2026, 9, 10))
    assert start == datetime(2026, 9, 9, 22, 0, tzinfo=UTC)


def test_local_date_conversion():
    # 2026-09-09 23:30 UTC is already 2026-09-10 in Berlin (01:30 CEST).
    instant = datetime(2026, 9, 9, 23, 30, tzinfo=UTC)
    assert local_date(BERLIN, instant) == date(2026, 9, 10)
