"""API integration tests (require PostgreSQL).

The app runs under its real lifespan against the test database, but the TMDB
adapter and Gotify client are replaced with in-memory fakes after startup.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import text

from conftest import integration, make_settings
from factories import FakeAdapter, FakeGotify, movie_details, movie_providers
from tmdb_reminder.api.app import create_app
from tmdb_reminder.tracking.service import TrackingService

pytestmark = integration

_ALL_TABLES = "tracked_titles, release_events, notification_deliveries, job_runs"


@asynccontextmanager
async def make_api(database, **settings_over):
    settings = make_settings(**settings_over)
    app = create_app(settings)
    adapter = FakeAdapter()
    gotify = FakeGotify()
    try:
        async with LifespanManager(app):
            app.state.adapter = adapter
            app.state.gotify = gotify
            app.state.tracking = TrackingService(settings, adapter)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, adapter, gotify
    finally:
        async with database.engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {_ALL_TABLES} RESTART IDENTITY CASCADE"))


async def test_track_list_stop_resume_flow(database):
    async with make_api(database) as (client, adapter, _gotify):
        adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))

        r = await client.put("/api/v1/tracked-titles/movie/603")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "active"
        assert body["next_release"]["scheduled_date"] == "2026-09-10"

        # Idempotent.
        r2 = await client.put("/api/v1/tracked-titles/movie/603")
        assert r2.status_code == 200

        r3 = await client.get("/api/v1/tracked-titles", params={"view": "active"})
        assert r3.json()["total"] == 1

        r4 = await client.delete("/api/v1/tracked-titles/movie/603")
        assert r4.json()["status"] == "stopped"

        hist = await client.get("/api/v1/tracked-titles", params={"view": "history"})
        assert hist.json()["total"] == 1
        active = await client.get("/api/v1/tracked-titles", params={"view": "active"})
        assert active.json()["total"] == 0

        # Resume from history via the same idempotent PUT.
        r5 = await client.put("/api/v1/tracked-titles/movie/603")
        assert r5.json()["status"] == "active"


async def test_concurrent_track_requests_are_idempotent(database):
    async with make_api(database) as (client, adapter, _gotify):
        adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))

        first, second = await asyncio.gather(
            client.put("/api/v1/tracked-titles/movie/603"),
            client.put("/api/v1/tracked-titles/movie/603"),
        )

        assert first.status_code == 200
        assert second.status_code == 200
        tracked = await client.get("/api/v1/tracked-titles", params={"view": "active"})
        assert tracked.json()["total"] == 1


async def test_api_exposes_effective_date_and_delay_configuration(database):
    async with make_api(database, availability_delay_days=2) as (client, adapter, _gotify):
        adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))

        tracked = await client.put("/api/v1/tracked-titles/movie/603")
        status = await client.get("/api/v1/status")

        assert tracked.json()["next_release"]["scheduled_date"] == "2026-09-12"
        assert status.json()["config"]["availability_delay_days"] == 2


async def test_pagination(database):
    async with make_api(database) as (client, adapter, _gotify):
        for i in range(5):
            adapter.movies[600 + i] = movie_details(600 + i, digital=date(2026, 9, 10 + i))
            await client.put(f"/api/v1/tracked-titles/movie/{600 + i}")
        page = await client.get(
            "/api/v1/tracked-titles", params={"view": "active", "offset": 0, "limit": 2}
        )
        data = page.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        # Soonest release first.
        assert data["items"][0]["next_release"]["scheduled_date"] == "2026-09-10"


async def test_search_filters_and_maps_tracking(database):
    async with make_api(database) as (client, adapter, _gotify):
        adapter.movies[603] = movie_details(603, digital=date(2026, 9, 10))
        await client.put("/api/v1/tracked-titles/movie/603")

        adapter.search_payload = {
            "page": 1,
            "total_pages": 1,
            "total_results": 4,
            "results": [
                {
                    "id": 603,
                    "media_type": "movie",
                    "title": "The Matrix",
                    "release_date": "1999-03-31",
                },
                {"id": 1399, "media_type": "tv", "name": "GoT", "first_air_date": "2011-04-17"},
                {"id": 500, "media_type": "person", "name": "Actor"},
                {"id": 66, "media_type": "movie", "title": "XXX", "adult": True},
            ],
        }
        r = await client.get("/api/v1/search", params={"query": "matrix"})
        assert r.status_code == 200
        data = r.json()
        # Person and adult dropped; order preserved.
        assert [i["tmdb_id"] for i in data["results"]] == [603, 1399]
        matrix = data["results"][0]
        assert matrix["tracking_status"] == "active"
        assert matrix["next_release"]["scheduled_date"] == "2026-09-10"
        assert data["results"][1]["tracking_status"] is None


async def test_available_movie_surfaces_availability_and_suppresses_next_release(database):
    async with make_api(database) as (client, adapter, _gotify):
        adapter.movies[603] = movie_details(603, available=date(2026, 8, 1))

        r = await client.put("/api/v1/tracked-titles/movie/603")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
        assert body["is_available"] is True
        assert body["available_since"] == "2026-08-01"
        assert body["next_release"] is None

        # History listing carries the availability date, no next release.
        hist = await client.get("/api/v1/tracked-titles", params={"view": "history"})
        item = hist.json()["items"][0]
        assert item["is_available"] is True
        assert item["available_since"] == "2026-08-01"
        assert item["next_release"] is None

        # Search reflects the tracked availability and suppresses next_release.
        adapter.search_payload = {
            "page": 1,
            "total_pages": 1,
            "total_results": 1,
            "results": [
                {"id": 603, "media_type": "movie", "title": "The Matrix"},
            ],
        }
        s = await client.get("/api/v1/search", params={"query": "matrix"})
        result = s.json()["results"][0]
        assert result["is_available"] is True
        assert result["available_since"] == "2026-08-01"
        assert result["next_release"] is None


async def test_provider_available_movie_is_available_without_date(database):
    async with make_api(database) as (client, adapter, _gotify):
        # No release dates; watch providers establish undated availability.
        adapter.movies[603] = movie_details(603)
        adapter.providers[603] = movie_providers()

        r = await client.put("/api/v1/tracked-titles/movie/603")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
        assert body["is_available"] is True
        assert body["available_since"] is None
        assert body["next_release"] is None

        hist = await client.get("/api/v1/tracked-titles", params={"view": "history"})
        item = hist.json()["items"][0]
        assert item["is_available"] is True
        assert item["available_since"] is None


async def test_unknown_availability_movie_not_available(database):
    async with make_api(database) as (client, adapter, _gotify):
        # No dates and no providers: availability unknown, still active.
        adapter.movies[603] = movie_details(603)

        r = await client.put("/api/v1/tracked-titles/movie/603")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "active"
        assert body["is_available"] is False
        assert body["available_since"] is None


async def test_untracked_and_tv_have_null_availability(database):
    async with make_api(database) as (client, adapter, _gotify):
        adapter.search_payload = {
            "page": 1,
            "total_pages": 1,
            "total_results": 2,
            "results": [
                {"id": 603, "media_type": "movie", "title": "The Matrix"},
                {"id": 1399, "media_type": "tv", "name": "GoT"},
            ],
        }
        r = await client.get("/api/v1/search", params={"query": "matrix"})
        for item in r.json()["results"]:
            assert item["is_available"] is False
            assert item["available_since"] is None


async def test_search_degraded_without_tmdb(database):
    async with make_api(database, tmdb_api_key=None) as (client, _adapter, _gotify):
        r = await client.get("/api/v1/search", params={"query": "matrix"})
        assert r.status_code == 200
        data = r.json()
        assert data["degraded"] is True
        assert data["results"] == []


async def test_search_rejects_one_character_query(database):
    async with make_api(database) as (client, _adapter, _gotify):
        response = await client.get("/api/v1/search", params={"query": "x"})
        assert response.status_code == 422


async def test_status_and_gotify_test(database):
    async with make_api(database) as (client, _adapter, gotify):
        r = await client.get("/api/v1/status")
        data = r.json()
        assert data["config"]["tmdb_region"] == "DE"
        assert data["config"]["gotify_configured"] is True
        assert data["config"]["availability_delay_days"] == 0
        assert "tmdb_api_key" not in str(data)

        t = await client.post("/api/v1/status/gotify-test")
        assert t.json()["sent"] is True
        assert len(gotify.sent) == 1


async def test_gotify_test_degraded(database):
    async with make_api(database, gotify_url=None, gotify_token=None) as (client, _a, _g):
        t = await client.post("/api/v1/status/gotify-test")
        assert t.json()["sent"] is False


async def test_health_endpoints(database):
    async with make_api(database) as (client, _adapter, _gotify):
        assert (await client.get("/api/v1/health/live")).json()["status"] == "ok"
        ready = await client.get("/api/v1/health/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] is True


async def test_error_contract_on_missing_title(database):
    async with make_api(database) as (client, _adapter, _gotify):
        r = await client.delete("/api/v1/tracked-titles/movie/999999")
        assert r.status_code == 404
        body = r.json()
        assert body["error"]["code"] == "title_not_found"
        assert body["error"]["retryable"] is False
        assert "request_id" in body


async def test_error_contract_on_tmdb_failure(database):
    async with make_api(database) as (client, adapter, _gotify):
        adapter.fail_ids.add(603)
        r = await client.put("/api/v1/tracked-titles/movie/603")
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "tmdb_unavailable"
        assert r.json()["error"]["retryable"] is True


async def test_validation_error_contract(database):
    async with make_api(database) as (client, _adapter, _gotify):
        # Missing required query.
        r = await client.get("/api/v1/search")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"
        # Invalid media_type enum.
        r2 = await client.put("/api/v1/tracked-titles/book/1")
        assert r2.status_code == 422


@pytest.mark.parametrize("view", ["active", "history"])
async def test_empty_lists(database, view):
    async with make_api(database) as (client, _adapter, _gotify):
        r = await client.get("/api/v1/tracked-titles", params={"view": view})
        assert r.json() == {"items": [], "view": view, "offset": 0, "limit": 20, "total": 0}
