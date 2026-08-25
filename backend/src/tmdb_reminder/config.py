"""Application settings.

All configuration is environment-driven (optionally via a `.env` file). Secrets
use `SecretStr` so they are never rendered by accident in logs or repr output.

Degraded mode: TMDB and Gotify credentials are optional. When absent, the
service still starts; features that need them return a documented degraded
state. The database is mandatory because all API and job state depends on it.
"""

from __future__ import annotations

import functools
from datetime import time
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database (mandatory) ---
    database_url: str = Field(
        default="postgresql+psycopg://tmdb:tmdb@localhost:5432/tmdb_reminder",
        description="Async SQLAlchemy DSN, e.g. postgresql+psycopg://user:pw@host/db",
    )

    # --- TMDB (optional -> degraded) ---
    tmdb_api_key: SecretStr | None = None
    tmdb_region: str = "DE"
    tmdb_language: str = "en-US"
    tmdb_request_timeout: float = 10.0
    tmdb_thread_limit: int = 8
    tmdb_max_retries: int = 3

    # --- Gotify (optional -> degraded) ---
    gotify_url: str | None = None
    gotify_token: SecretStr | None = None
    gotify_priority: int = 5

    # --- Scheduling / timezone ---
    app_timezone: str = "Europe/Berlin"
    reminder_time: str = "09:00"
    availability_delay_days: int = Field(default=0, ge=0, le=30)

    # --- Lifecycle windows ---
    revision_watch_days: int = 30
    dormant_refresh_days: int = 150
    delivery_lease_minutes: int = 15
    max_tracked_titles: int = 1000

    # --- Logging ---
    log_level: str = "INFO"

    @field_validator("tmdb_region")
    @classmethod
    def _upper_region(cls, v: str) -> str:
        return v.upper()

    @field_validator("gotify_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str | None) -> str | None:
        return v.rstrip("/") if v else v

    @property
    def tmdb_configured(self) -> bool:
        return self.tmdb_api_key is not None and bool(self.tmdb_api_key.get_secret_value())

    @property
    def gotify_configured(self) -> bool:
        return bool(self.gotify_url) and self.gotify_token is not None

    @property
    def tmdb_use_bearer(self) -> bool:
        """TMDB v4 read-access tokens are JWTs (three dot-separated segments)."""
        if self.tmdb_api_key is None:
            return False
        return self.tmdb_api_key.get_secret_value().count(".") == 2

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def reminder_time_parsed(self) -> time:
        hh, mm = self.reminder_time.split(":", 1)
        return time(hour=int(hh), minute=int(mm))


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
