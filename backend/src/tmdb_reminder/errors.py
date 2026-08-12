"""Application error contract.

Every failure returned by the API uses the same body shape::

    {"error": {"code", "message", "retryable", "details"?}, "request_id"}

`AppError` subclasses carry an HTTP status, a stable machine code, and a
`retryable` flag so clients can distinguish transient from permanent failures.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    code: str = "internal_error"
    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        self.message = message or self.__class__.__name__
        self.details = details
        if retryable is not None:
            self.retryable = retryable
        super().__init__(self.message)

    def to_body(self, request_id: str) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            error["details"] = self.details
        return {"error": error, "request_id": request_id}


class NotConfiguredError(AppError):
    code = "not_configured"
    http_status = 503
    retryable = False


class TmdbUnavailableError(AppError):
    code = "tmdb_unavailable"
    http_status = 502
    retryable = True


class TmdbAuthError(AppError):
    code = "tmdb_auth_failed"
    http_status = 502
    retryable = False


class TmdbNotFoundError(AppError):
    code = "tmdb_not_found"
    http_status = 404
    retryable = False


class GotifyUnavailableError(AppError):
    code = "gotify_unavailable"
    http_status = 502
    retryable = True


class TitleNotFoundError(AppError):
    code = "title_not_found"
    http_status = 404
    retryable = False


class ValidationError(AppError):
    code = "validation_error"
    http_status = 422
    retryable = False


class CapacityExceededError(AppError):
    code = "capacity_exceeded"
    http_status = 409
    retryable = False
