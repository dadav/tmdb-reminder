"""Unit tests for the startup catch-up decision (no clocks, no DB)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from tmdb_reminder.worker.jobs import should_run_refresh

BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 8, 12, 6, 0, tzinfo=UTC)  # 08:00 Berlin


def test_runs_when_never_run():
    assert should_run_refresh(None, NOW, BERLIN) is True


def test_runs_when_last_was_yesterday():
    last = datetime(2026, 8, 11, 7, 0, tzinfo=UTC)
    assert should_run_refresh(last, NOW, BERLIN) is True


def test_skips_when_already_ran_today():
    last = datetime(2026, 8, 12, 5, 0, tzinfo=UTC)  # earlier today
    assert should_run_refresh(last, NOW, BERLIN) is False


def test_local_day_boundary_respected():
    # 2026-08-11 23:30 UTC is 2026-08-12 01:30 Berlin -> same local day as NOW.
    last = datetime(2026, 8, 11, 23, 30, tzinfo=UTC)
    assert should_run_refresh(last, NOW, BERLIN) is False
