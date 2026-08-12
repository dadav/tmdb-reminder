"""Structured JSON logging.

Emits one JSON object per line at key boundaries. A `contextvars`-backed
correlation id (request id or job id) is attached to every record so API
requests and worker jobs can be traced end to end.

Secret redaction is enforced here as a last line of defense: known secret keys
and bearer-style URL credentials are masked even if a caller forgets.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from typing import Any

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_SECRET_KEYS = {
    "api_key",
    "tmdb_api_key",
    "token",
    "gotify_token",
    "password",
    "authorization",
    "secret",
    "database_url",
}
_URL_CRED = re.compile(r"(://[^:/@\s]+:)[^@/\s]+(@)")
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE)
_GOTIFY_KEY = re.compile(r"([?&]token=)[^&\s]+")


def sanitize(value: Any) -> Any:
    """Recursively mask secret-bearing values for safe logging."""
    if isinstance(value, str):
        value = _URL_CRED.sub(r"\1***\2", value)
        value = _BEARER.sub(r"\1***", value)
        value = _GOTIFY_KEY.sub(r"\1***", value)
        return value
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _SECRET_KEYS else sanitize(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    return value


_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = correlation_id.get()
        if cid is not None:
            payload["correlation_id"] = cid
        for key, val in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = sanitize(val)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Uvicorn access noise is redundant with our request-boundary logs.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
