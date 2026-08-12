"""Adapter tests: mock `tmdbsimple` at its `requests` boundary with `responses`."""

from __future__ import annotations

import re

import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from conftest import make_settings
from tmdb_reminder.errors import (
    NotConfiguredError,
    TmdbAuthError,
    TmdbNotFoundError,
    TmdbUnavailableError,
)
from tmdb_reminder.tmdb.adapter import TmdbAdapter

SEARCH_URL = re.compile(r"https://api\.themoviedb\.org/3/search/multi.*")
MOVIE_URL = re.compile(r"https://api\.themoviedb\.org/3/movie/603.*")
TV_URL = re.compile(r"https://api\.themoviedb\.org/3/tv/1399.*")


def _adapter(**over) -> TmdbAdapter:
    # No-op sleeper so retry backoff never actually sleeps.
    return TmdbAdapter(make_settings(**over), sleeper=lambda _s: None)


async def test_multi_search_ok():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            SEARCH_URL,
            json={"page": 1, "results": [{"id": 1, "media_type": "movie"}], "total_pages": 1},
            status=200,
        )
        out = await adapter.multi_search("matrix", 1)
    assert out["results"][0]["id"] == 1


async def test_movie_details_ok():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, MOVIE_URL, json={"id": 603, "title": "The Matrix"}, status=200)
        out = await adapter.movie_details(603)
    assert out["title"] == "The Matrix"


async def test_tv_details_ok():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, TV_URL, json={"id": 1399, "name": "GoT"}, status=200)
        out = await adapter.tv_details(1399)
    assert out["name"] == "GoT"


async def test_auth_error_401():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, MOVIE_URL, json={"status_message": "invalid"}, status=401)
        with pytest.raises(TmdbAuthError):
            await adapter.movie_details(603)


async def test_auth_error_403():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, MOVIE_URL, json={}, status=403)
        with pytest.raises(TmdbAuthError):
            await adapter.movie_details(603)


async def test_not_found_404():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, MOVIE_URL, json={}, status=404)
        with pytest.raises(TmdbNotFoundError):
            await adapter.movie_details(603)


async def test_429_retry_after_then_success():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, SEARCH_URL, json={}, status=429, headers={"Retry-After": "1"})
        rsps.add(responses.GET, SEARCH_URL, json={"results": [], "page": 1}, status=200)
        out = await adapter.multi_search("x", 1)
    assert out["page"] == 1


async def test_5xx_retries_exhausted():
    adapter = _adapter(tmdb_max_retries=3)
    with responses.RequestsMock() as rsps:
        for _ in range(3):
            rsps.add(responses.GET, SEARCH_URL, json={}, status=503)
        with pytest.raises(TmdbUnavailableError):
            await adapter.multi_search("x", 1)


async def test_timeout_is_transient():
    adapter = _adapter(tmdb_max_retries=2)
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, SEARCH_URL, body=Timeout("slow"))
        rsps.add(responses.GET, SEARCH_URL, body=Timeout("slow"))
        with pytest.raises(TmdbUnavailableError):
            await adapter.multi_search("x", 1)


async def test_connection_error_then_recovers():
    adapter = _adapter(tmdb_max_retries=3)
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, SEARCH_URL, body=RequestsConnectionError("down"))
        rsps.add(responses.GET, SEARCH_URL, json={"results": [], "page": 1}, status=200)
        out = await adapter.multi_search("x", 1)
    assert out["page"] == 1


async def test_malformed_json_raises_unavailable():
    adapter = _adapter()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, SEARCH_URL, body="not json", status=200)
        with pytest.raises(TmdbUnavailableError):
            await adapter.multi_search("x", 1)


async def test_degraded_when_not_configured():
    adapter = TmdbAdapter(make_settings(tmdb_api_key=None), sleeper=lambda _s: None)
    with pytest.raises(NotConfiguredError):
        await adapter.multi_search("x", 1)
