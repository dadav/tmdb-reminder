"""Shared test fixtures.

Unit tests need no database. Integration tests require a live PostgreSQL DSN in
`DATABASE_URL_TEST`; they are skipped when it is absent.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text

from tmdb_reminder.config import Settings
from tmdb_reminder.db import Base, Database

TEST_DSN = os.getenv("DATABASE_URL_TEST")

integration = pytest.mark.skipif(
    not TEST_DSN, reason="requires DATABASE_URL_TEST for a live PostgreSQL"
)

_ALL_TABLES = "tracked_titles, release_events, notification_deliveries, job_runs"


def make_settings(**overrides) -> Settings:
    base: dict = {
        "database_url": TEST_DSN or "postgresql+psycopg://tmdb:tmdb@localhost:5432/tmdb_reminder",
        "tmdb_api_key": "header.payload.signature",  # JWT-shaped -> bearer auth
        "tmdb_region": "DE",
        "tmdb_language": "en-US",
        "tmdb_max_retries": 3,
        "gotify_url": "http://gotify.local",
        "gotify_token": "gotify-token",
        "gotify_priority": 5,
        "app_timezone": "Europe/Berlin",
        "reminder_time": "09:00",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest_asyncio.fixture(scope="session")
async def database() -> AsyncIterator[Database]:
    assert TEST_DSN is not None
    db = Database(TEST_DSN)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield db
    await db.dispose()


@pytest_asyncio.fixture
async def session(database: Database) -> AsyncIterator:
    async with database.session_factory() as s:
        yield s
    async with database.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {_ALL_TABLES} RESTART IDENTITY CASCADE"))
