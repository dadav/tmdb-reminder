"""API entrypoint (`uvicorn tmdb_reminder.main_api:app`)."""

from __future__ import annotations

import os

import uvicorn

from .api.app import create_app

app = create_app()


def main() -> None:
    uvicorn.run(
        "tmdb_reminder.main_api:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        log_config=None,
    )


if __name__ == "__main__":
    main()
