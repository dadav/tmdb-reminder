"""Async Gotify push client (HTTPX).

Authenticates with the `X-Gotify-Key` header. Markdown rendering is requested
via the documented `client::display` extra. Transient failures raise a retryable
`GotifyUnavailableError`; auth failures are non-retryable.
"""

from __future__ import annotations

import logging

import httpx

from ..config import Settings
from ..errors import GotifyUnavailableError, NotConfiguredError
from ..value_objects import GotifyMessage

log = logging.getLogger("tmdb_reminder.gotify")

_MARKDOWN_EXTRAS = {"client::display": {"contentType": "text/markdown"}}


class GotifyClient:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _require_configured(self) -> None:
        if not self._settings.gotify_configured:
            raise NotConfiguredError("Gotify is not configured")

    def _headers(self) -> dict[str, str]:
        assert self._settings.gotify_token is not None
        return {"X-Gotify-Key": self._settings.gotify_token.get_secret_value()}

    async def _post_message(self, payload: dict) -> int:
        self._require_configured()
        url = f"{self._settings.gotify_url}/message"
        try:
            resp = await self._client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise GotifyUnavailableError("Gotify network failure") from exc
        if resp.status_code in (401, 403):
            raise GotifyUnavailableError("Gotify rejected the application token", retryable=False)
        if resp.status_code >= 500:
            raise GotifyUnavailableError(f"Gotify server error {resp.status_code}")
        if resp.status_code >= 400:
            raise GotifyUnavailableError(f"Gotify client error {resp.status_code}", retryable=False)
        data = resp.json()
        message_id = int(data["id"])
        return message_id

    async def send(self, message: GotifyMessage) -> int:
        payload = {
            "title": message.title,
            "message": message.markdown,
            "priority": message.priority,
            "extras": _MARKDOWN_EXTRAS,
        }
        message_id = await self._post_message(payload)
        log.info(
            "gotify message sent",
            extra={"gotify_message_id": message_id, "priority": message.priority},
        )
        return message_id

    async def send_test(self) -> int:
        payload = {
            "title": "TMDB Reminder test",
            "message": "This is a test notification from TMDB Reminder.",
            "priority": self._settings.gotify_priority,
            "extras": _MARKDOWN_EXTRAS,
        }
        return await self._post_message(payload)

    async def check_connectivity(self) -> bool:
        """Check that the configured Gotify server is reachable without sending a message."""
        self._require_configured()
        try:
            response = await self._client.get(f"{self._settings.gotify_url}/health")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GotifyUnavailableError("Gotify health check failed") from exc
        return True
