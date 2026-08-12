"""Unit tests for secret redaction in structured logs."""

from __future__ import annotations

from tmdb_reminder.logging_config import sanitize


def test_masks_secret_keys():
    out = sanitize({"api_key": "abc", "tmdb_api_key": "z", "safe": "value"})
    assert out["api_key"] == "***"
    assert out["tmdb_api_key"] == "***"
    assert out["safe"] == "value"


def test_masks_url_credentials():
    out = sanitize("postgresql://user:supersecret@db:5432/app")
    assert "supersecret" not in out
    assert "user:***@" in out


def test_masks_bearer_token():
    out = sanitize("Authorization: Bearer eyJhbGciheader.payload.sig")
    assert "eyJhbGci" not in out
    assert "Bearer ***" in out


def test_masks_gotify_token_query():
    out = sanitize("http://gotify/message?token=AbCdEf123&x=1")
    assert "AbCdEf123" not in out
    assert "token=***" in out


def test_nested_structures():
    out = sanitize({"outer": {"password": "p", "list": ["Bearer secrettoken"]}})
    assert out["outer"]["password"] == "***"
    assert "secrettoken" not in out["outer"]["list"][0]


def test_authorization_key_masked_case_insensitive():
    out = sanitize({"Authorization": "Bearer x"})
    assert out["Authorization"] == "***"
