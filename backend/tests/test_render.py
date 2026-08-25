"""Unit tests for Gotify message rendering."""

from __future__ import annotations

from datetime import date

from tmdb_reminder.enums import EventKind, MediaType
from tmdb_reminder.models import NotificationDelivery, ReleaseEvent, TrackedTitle
from tmdb_reminder.notifications.render import render_message


def _movie_event(scheduled: date) -> tuple[TrackedTitle, ReleaseEvent]:
    title = TrackedTitle(
        media_type=MediaType.MOVIE.value, tmdb_id=603, title="The Matrix", release_year=1999
    )
    event = ReleaseEvent(
        source_event_key="movie:603:digital:DE",
        revision=1,
        kind=EventKind.MOVIE_DIGITAL.value,
        source_date=scheduled,
        scheduled_date=scheduled,
    )
    return title, event


def test_movie_message_basic():
    title, event = _movie_event(date(2026, 9, 10))
    delivery = NotificationDelivery(is_revised=False)
    msg = render_message(title, event, delivery, is_late=False, priority=5)
    assert msg.title == "The Matrix"
    assert "**The Matrix** (1999)" in msg.markdown
    assert "Digital release" in msg.markdown
    assert "Expected availability: 2026-09-10" in msg.markdown
    assert "https://www.themoviedb.org/movie/603" in msg.markdown
    assert msg.priority == 5


def test_revised_label():
    title, event = _movie_event(date(2026, 9, 10))
    delivery = NotificationDelivery(is_revised=True)
    msg = render_message(title, event, delivery, is_late=False, priority=5)
    assert msg.title.startswith("[Revised]")
    assert "Revised" in msg.markdown


def test_late_label():
    title, event = _movie_event(date(2026, 9, 10))
    delivery = NotificationDelivery(is_revised=False)
    msg = render_message(title, event, delivery, is_late=True, priority=5)
    assert "[Late]" in msg.title


def test_revised_and_late_labels():
    title, event = _movie_event(date(2026, 9, 10))
    delivery = NotificationDelivery(is_revised=True)
    msg = render_message(title, event, delivery, is_late=True, priority=8)
    assert "Revised" in msg.title and "Late" in msg.title


def test_tv_identity_line():
    title = TrackedTitle(
        media_type=MediaType.TV.value, tmdb_id=1399, title="GoT", release_year=2011
    )
    event = ReleaseEvent(
        source_event_key="tv:1399:s2e5",
        revision=1,
        kind=EventKind.TV_EPISODE.value,
        source_date=date(2026, 9, 1),
        scheduled_date=date(2026, 9, 1),
        season_number=2,
        episode_number=5,
    )
    delivery = NotificationDelivery(is_revised=False)
    msg = render_message(title, event, delivery, is_late=False, priority=5)
    assert "Season 2, Episode 5" in msg.markdown
    assert "https://www.themoviedb.org/tv/1399" in msg.markdown
