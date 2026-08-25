"""Unit tests for TMDB mapping and release-selection rules."""

from __future__ import annotations

from datetime import date

import pytest

from tmdb_reminder.enums import EventKind, MediaType
from tmdb_reminder.tmdb.mapping import (
    movie_available_from_providers,
    movie_release_candidate,
    select_movie_release,
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


def test_future_digital_selected_in_region():
    payload = _release_dates(
        {
            "DE": [
                {"type": 3, "release_date": "2026-08-01T00:00:00.000Z"},  # theatrical
                {"type": 4, "release_date": "2026-09-10T00:00:00.000Z"},  # digital
            ],
            "US": [{"type": 4, "release_date": "2026-08-15T00:00:00.000Z"}],
        }
    )
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since is None
    assert rel.next_digital_date == date(2026, 9, 10)
    assert rel.next_digital_source_date == date(2026, 9, 10)


def test_next_digital_picks_earliest_future():
    payload = _release_dates(
        {
            "DE": [
                {"type": 4, "release_date": "2026-12-01"},
                {"type": 4, "release_date": "2026-09-05"},
            ]
        }
    )
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since is None
    assert rel.next_digital_date == date(2026, 9, 5)


@pytest.mark.parametrize("release_type", [4, 5, 6])
def test_available_when_qualifying_type_at_or_before_today(release_type):
    payload = _release_dates({"DE": [{"type": release_type, "release_date": "2026-07-01"}]})
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since == date(2026, 7, 1)
    assert rel.next_digital_date is None


def test_digital_today_is_availability_not_reminder():
    payload = _release_dates({"DE": [{"type": 4, "release_date": "2026-08-12"}]})
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since == TODAY
    assert rel.next_digital_date is None


@pytest.mark.parametrize("release_type", [4, 5, 6])
def test_delay_shifts_all_movie_availability_types(release_type):
    payload = _release_dates({"DE": [{"type": release_type, "release_date": "2026-08-12"}]})
    rel = select_movie_release(payload, "DE", TODAY, availability_delay_days=1)
    assert rel.available_since is None
    if release_type == 4:
        assert rel.next_digital_source_date == TODAY
        assert rel.next_digital_date == date(2026, 8, 13)
    else:
        assert rel.next_digital_source_date is None
        assert rel.next_digital_date is None


def test_shifted_movie_date_becomes_available_on_effective_day():
    payload = _release_dates({"DE": [{"type": 4, "release_date": "2026-08-11"}]})
    rel = select_movie_release(payload, "DE", TODAY, availability_delay_days=1)
    assert rel.available_since == TODAY
    assert rel.next_digital_date is None


def test_availability_picks_earliest_past_qualifying_date():
    payload = _release_dates(
        {
            "DE": [
                {"type": 5, "release_date": "2026-06-01"},  # physical
                {"type": 4, "release_date": "2026-05-01"},  # earlier digital
                {"type": 6, "release_date": "2026-07-01"},  # tv
            ]
        }
    )
    assert select_movie_release(payload, "DE", TODAY).available_since == date(2026, 5, 1)


def test_availability_outranks_future_digital():
    payload = _release_dates(
        {
            "DE": [
                {"type": 4, "release_date": "2026-05-01"},  # already available
                {"type": 4, "release_date": "2027-01-01"},  # later digital ignored
            ]
        }
    )
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since == date(2026, 5, 1)
    assert rel.next_digital_date is None


def test_release_ignores_theatrical_types_for_availability():
    payload = _release_dates(
        {
            "DE": [
                {"type": 1, "release_date": "2026-01-01"},  # premiere
                {"type": 2, "release_date": "2026-02-01"},  # theatrical limited
                {"type": 3, "release_date": "2026-03-01"},  # theatrical
            ]
        }
    )
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since is None
    assert rel.next_digital_date is None


def test_release_ignores_other_regions_and_malformed_dates():
    payload = _release_dates(
        {
            "DE": [
                {"type": 4, "release_date": "not-a-date"},
                {"type": 5, "release_date": None},
            ],
            "US": [{"type": 4, "release_date": "2026-05-01"}],
        }
    )
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since is None
    assert rel.next_digital_date is None


def test_release_empty_when_no_qualifying_entries():
    payload = _release_dates({"DE": [{"type": 3, "release_date": "2027-01-01"}]})
    rel = select_movie_release(payload, "DE", TODAY)
    assert rel.available_since is None
    assert rel.next_digital_date is None


@pytest.mark.parametrize("offering", ["flatrate", "free", "ads", "rent", "buy"])
def test_providers_available_for_each_offering_category(offering):
    payload = {"results": {"DE": {"link": "https://x", offering: [{"provider_id": 8}]}}}
    assert movie_available_from_providers(payload, "DE") is True


def test_providers_ignores_other_regions():
    payload = {"results": {"US": {"flatrate": [{"provider_id": 8}]}}}
    assert movie_available_from_providers(payload, "DE") is False


def test_providers_link_only_entry_not_available():
    payload = {"results": {"DE": {"link": "https://x"}}}
    assert movie_available_from_providers(payload, "DE") is False


def test_providers_empty_offering_list_not_available():
    payload = {"results": {"DE": {"link": "https://x", "flatrate": []}}}
    assert movie_available_from_providers(payload, "DE") is False


def test_providers_malformed_payloads_not_available():
    assert movie_available_from_providers({}, "DE") is False
    assert movie_available_from_providers({"results": None}, "DE") is False
    assert movie_available_from_providers({"results": {"DE": "nope"}}, "DE") is False
    assert movie_available_from_providers({"results": {"DE": {"flatrate": "nope"}}}, "DE") is False


def test_providers_multiple_regions_selects_configured_region():
    payload = {
        "results": {
            "US": {"flatrate": [{"provider_id": 8}]},
            "DE": {"link": "https://x"},  # link only, not available
        }
    }
    assert movie_available_from_providers(payload, "DE") is False
    assert movie_available_from_providers(payload, "US") is True


def test_movie_candidate_key_and_kind():
    source = date(2026, 9, 4)
    effective = date(2026, 9, 5)
    cand = movie_release_candidate(603, source, effective, "DE")
    assert cand is not None
    assert cand.kind == EventKind.MOVIE_DIGITAL
    assert cand.source_event_key == "movie:603:digital:DE"
    assert cand.source_date == source
    assert cand.scheduled_date == effective


def test_movie_candidate_none_without_date():
    assert movie_release_candidate(603, None, None, "DE") is None


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
    assert cand.source_date == date(2026, 9, 1)
    assert cand.scheduled_date == date(2026, 9, 1)


def test_tv_candidate_uses_effective_date_after_source_date_passes():
    details = {
        "next_episode_to_air": {
            "air_date": "2026-08-11",
            "season_number": 2,
            "episode_number": 5,
        }
    }
    cand = tv_release_candidate(1399, details, TODAY, availability_delay_days=2)
    assert cand is not None
    assert cand.source_date == date(2026, 8, 11)
    assert cand.scheduled_date == date(2026, 8, 13)


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
