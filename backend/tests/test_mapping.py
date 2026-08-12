"""Unit tests for TMDB mapping and release-selection rules."""

from __future__ import annotations

from datetime import date

from tmdb_reminder.enums import EventKind, MediaType
from tmdb_reminder.tmdb.mapping import (
    movie_release_candidate,
    select_digital_release,
    snapshot_from_movie,
    snapshot_from_tv,
    tmdb_url,
    tv_release_candidate,
)

TODAY = date(2026, 8, 12)


def _release_dates(region_entries: dict) -> dict:
    return {
        "results": [
            {"iso_3166_1": region, "release_dates": entries}
            for region, entries in region_entries.items()
        ]
    }


def test_digital_selects_type4_in_region():
    payload = _release_dates(
        {
            "DE": [
                {"type": 3, "release_date": "2026-08-01T00:00:00.000Z"},  # theatrical
                {"type": 4, "release_date": "2026-09-10T00:00:00.000Z"},  # digital
            ],
            "US": [{"type": 4, "release_date": "2026-08-15T00:00:00.000Z"}],
        }
    )
    assert select_digital_release(payload, "DE", TODAY) == date(2026, 9, 10)


def test_digital_picks_earliest_on_or_after_today():
    payload = _release_dates(
        {
            "DE": [
                {"type": 4, "release_date": "2026-07-01"},  # past -> ignored
                {"type": 4, "release_date": "2026-12-01"},
                {"type": 4, "release_date": "2026-09-05"},
            ]
        }
    )
    assert select_digital_release(payload, "DE", TODAY) == date(2026, 9, 5)


def test_digital_includes_today():
    payload = _release_dates({"DE": [{"type": 4, "release_date": "2026-08-12"}]})
    assert select_digital_release(payload, "DE", TODAY) == TODAY


def test_digital_none_when_only_past_or_other_region():
    payload = _release_dates(
        {
            "DE": [{"type": 4, "release_date": "2020-01-01"}],
            "US": [{"type": 4, "release_date": "2027-01-01"}],
        }
    )
    assert select_digital_release(payload, "DE", TODAY) is None


def test_digital_none_when_no_digital_type():
    payload = _release_dates({"DE": [{"type": 3, "release_date": "2027-01-01"}]})
    assert select_digital_release(payload, "DE", TODAY) is None


def test_movie_candidate_key_and_kind():
    cand = movie_release_candidate(603, date(2026, 9, 5), "DE")
    assert cand is not None
    assert cand.kind == EventKind.MOVIE_DIGITAL
    assert cand.source_event_key == "movie:603:digital:DE"
    assert cand.scheduled_date == date(2026, 9, 5)


def test_movie_candidate_none_without_date():
    assert movie_release_candidate(603, None, "DE") is None


def test_tv_candidate_identity():
    details = {
        "next_episode_to_air": {
            "air_date": "2026-09-01",
            "season_number": 2,
            "episode_number": 5,
            "name": "Ep",
        }
    }
    cand = tv_release_candidate(1399, details, TODAY)
    assert cand is not None
    assert cand.kind == EventKind.TV_EPISODE
    assert cand.source_event_key == "tv:1399:s2e5"
    assert cand.season_number == 2
    assert cand.episode_number == 5
    assert cand.scheduled_date == date(2026, 9, 1)


def test_tv_candidate_none_when_no_next_episode():
    assert tv_release_candidate(1399, {"next_episode_to_air": None}, TODAY) is None


def test_tv_candidate_none_when_air_date_unknown():
    details = {
        "next_episode_to_air": {
            "air_date": None,
            "season_number": 3,
            "episode_number": 1,
        }
    }
    assert tv_release_candidate(1399, details, TODAY) is None


def test_tv_candidate_none_when_air_date_past():
    details = {
        "next_episode_to_air": {
            "air_date": "2020-01-01",
            "season_number": 1,
            "episode_number": 1,
        }
    }
    assert tv_release_candidate(1399, details, TODAY) is None


def test_snapshot_from_movie():
    snap = snapshot_from_movie(
        {
            "id": 603,
            "title": "The Matrix",
            "original_title": "The Matrix",
            "overview": "Neo",
            "poster_path": "/p.jpg",
            "release_date": "1999-03-31",
        }
    )
    assert snap.media_type == MediaType.MOVIE
    assert snap.title == "The Matrix"
    assert snap.release_year == 1999


def test_snapshot_from_tv_uses_name():
    snap = snapshot_from_tv({"id": 1399, "name": "Game of Thrones", "first_air_date": "2011-04-17"})
    assert snap.media_type == MediaType.TV
    assert snap.title == "Game of Thrones"
    assert snap.release_year == 2011


def test_tmdb_url():
    assert tmdb_url(MediaType.MOVIE, 603) == "https://www.themoviedb.org/movie/603"
    assert tmdb_url(MediaType.TV, 1399) == "https://www.themoviedb.org/tv/1399"
