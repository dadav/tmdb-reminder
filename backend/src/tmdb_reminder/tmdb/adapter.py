"""Async adapter over the synchronous `tmdbsimple` client.

`tmdbsimple` uses blocking `requests`. Every call is executed on AnyIO's thread
pool under a bounded `CapacityLimiter` so it never blocks the event loop and the
number of concurrent upstream calls stays capped.

The module-level TMDB config (API key / bearer flag / timeout) is set once when
the first adapter is constructed. Transient failures (timeouts, 429, 5xx) are
retried up to `tmdb_max_retries`, honoring `Retry-After`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar

import anyio
import tmdbsimple as tmdb
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout

from ..config import Settings
from ..errors import NotConfiguredError, TmdbAuthError, TmdbNotFoundError, TmdbUnavailableError

log = logging.getLogger("tmdb_reminder.tmdb")

T = TypeVar("T")

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_MAX_BACKOFF_SECONDS = 30.0
_module_lock = Lock()


def _configure_module(settings: Settings) -> None:
    if not settings.tmdb_configured:
        return
    assert settings.tmdb_api_key is not None
    tmdb.API_KEY = settings.tmdb_api_key.get_secret_value()
    tmdb.USE_BEARER_AUTH = settings.tmdb_use_bearer
    tmdb.REQUESTS_TIMEOUT = settings.tmdb_request_timeout


class TmdbAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._sleeper = sleeper
        self._limiter = anyio.CapacityLimiter(settings.tmdb_thread_limit)

    def _require_configured(self) -> None:
        if not self._settings.tmdb_configured:
            raise NotConfiguredError("TMDB API key is not configured")

    async def _run(self, fn: Callable[[], T]) -> T:
        return await anyio.to_thread.run_sync(fn, limiter=self._limiter)

    def _call_with_retries(self, fn: Callable[[], T], *, op: str) -> T:
        """Blocking call with transient-error retries. Runs inside a worker thread."""
        started = time.perf_counter()
        try:
            # tmdbsimple stores credentials in module globals. Serialize configuration
            # and calls so independently composed adapters cannot leak settings.
            with _module_lock:
                _configure_module(self._settings)
                return self._call_locked_with_retries(fn, op=op)
        finally:
            log.info(
                "tmdb call finished",
                extra={"op": op, "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
            )

    def _call_locked_with_retries(self, fn: Callable[[], T], *, op: str) -> T:
        attempts = self._settings.tmdb_max_retries
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status in (401, 403):
                    raise TmdbAuthError("TMDB rejected the API credentials") from exc
                if status == 404:
                    raise TmdbNotFoundError("TMDB resource not found") from exc
                if status in _TRANSIENT_STATUS:
                    last_exc = exc
                    delay = self._retry_delay(exc, attempt)
                    log.warning(
                        "tmdb transient http error",
                        extra={"op": op, "status": status, "attempt": attempt, "delay": delay},
                    )
                    if attempt < attempts:
                        self._sleeper(delay)
                        continue
                    raise TmdbUnavailableError(f"TMDB error {status} after retries") from exc
                raise TmdbUnavailableError(f"TMDB unexpected status {status}") from exc
            except (Timeout, RequestsConnectionError) as exc:
                last_exc = exc
                delay = self._retry_delay(None, attempt)
                log.warning(
                    "tmdb network error",
                    extra={"op": op, "attempt": attempt, "delay": delay},
                )
                if attempt < attempts:
                    self._sleeper(delay)
                    continue
                raise TmdbUnavailableError("TMDB network failure after retries") from exc
            except RequestException as exc:  # pragma: no cover - defensive
                raise TmdbUnavailableError("TMDB request failed") from exc
        raise TmdbUnavailableError("TMDB call exhausted retries") from last_exc

    def _retry_delay(self, exc: HTTPError | None, attempt: int) -> float:
        if exc is not None and exc.response is not None:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
        return min(2.0 ** (attempt - 1), _MAX_BACKOFF_SECONDS)

    # --- Public operations ---

    async def multi_search(self, query: str, page: int) -> dict[str, Any]:
        self._require_configured()
        s = self._settings

        def _do() -> dict[str, Any]:
            return tmdb.Search().multi(
                query=query,
                page=page,
                include_adult=False,
                language=s.tmdb_language,
            )

        return await self._run(lambda: self._call_with_retries(_do, op="multi_search"))

    async def check_connectivity(self) -> bool:
        """Validate configured credentials with TMDB's lightweight configuration call."""
        self._require_configured()

        def _do() -> dict[str, Any]:
            return tmdb.Configuration().info()

        await self._run(lambda: self._call_with_retries(_do, op="connectivity_check"))
        return True

    async def movie_details(self, tmdb_id: int) -> dict[str, Any]:
        """Movie info with appended `release_dates` (one upstream call)."""
        self._require_configured()
        s = self._settings

        def _do() -> dict[str, Any]:
            return tmdb.Movies(tmdb_id).info(
                language=s.tmdb_language,
                append_to_response="release_dates",
            )

        return await self._run(lambda: self._call_with_retries(_do, op="movie_details"))

    async def tv_details(self, tmdb_id: int) -> dict[str, Any]:
        """TV info; the base payload already carries `next_episode_to_air`."""
        self._require_configured()
        s = self._settings

        def _do() -> dict[str, Any]:
            return tmdb.TV(tmdb_id).info(language=s.tmdb_language)

        return await self._run(lambda: self._call_with_retries(_do, op="tv_details"))
