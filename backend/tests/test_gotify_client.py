"""Gotify client tests using an HTTPX mock transport."""

from __future__ import annotations

import json

import httpx
import pytest

from conftest import make_settings
from tmdb_reminder.errors import GotifyUnavailableError, NotConfiguredError
from tmdb_reminder.notifications.gotify import GotifyClient
from tmdb_reminder.value_objects import GotifyMessage

MESSAGE = GotifyMessage(title="t", markdown="**hi**", priority=5, click_url="http://x")


def _client(handler) -> GotifyClient:
    transport = httpx.MockTransport(handler)
    return GotifyClient(make_settings(), client=httpx.AsyncClient(transport=transport))


async def test_send_success_returns_id():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("X-Gotify-Key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 42})

    client = _client(handler)
    message_id = await client.send(MESSAGE)
    assert message_id == 42
    assert captured["auth"] == "gotify-token"
    assert captured["body"]["extras"]["client::display"]["contentType"] == "text/markdown"
    assert captured["body"]["priority"] == 5


async def test_auth_failure_non_retryable():
    client = _client(lambda r: httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(GotifyUnavailableError) as exc:
        await client.send(MESSAGE)
    assert exc.value.retryable is False


async def test_server_error_retryable():
    client = _client(lambda r: httpx.Response(500, json={}))
    with pytest.raises(GotifyUnavailableError) as exc:
        await client.send(MESSAGE)
    assert exc.value.retryable is True


async def test_client_error_non_retryable():
    client = _client(lambda r: httpx.Response(400, json={}))
    with pytest.raises(GotifyUnavailableError) as exc:
        await client.send(MESSAGE)
    assert exc.value.retryable is False


async def test_network_error_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    client = _client(handler)
    with pytest.raises(GotifyUnavailableError) as exc:
        await client.send(MESSAGE)
    assert exc.value.retryable is True


async def test_not_configured():
    client = GotifyClient(make_settings(gotify_url=None, gotify_token=None))
    with pytest.raises(NotConfiguredError):
        await client.send(MESSAGE)
    await client.aclose()


async def test_send_test_message():
    client = _client(lambda r: httpx.Response(200, json={"id": 7}))
    assert await client.send_test() == 7
