"""Write the FastAPI OpenAPI schema to a deterministic JSON artifact.

Deterministic (sorted keys, trailing newline) so CI can regenerate it and the
TypeScript client and fail on any uncommitted drift.

Usage: uv run python scripts/export_openapi.py [output_path]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The app builds settings from env; provide a harmless DB URL so import succeeds
# without a real database (no connection is made just to render the schema).
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pw@localhost/db")

from tmdb_reminder.api.app import create_app  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    schema = create_app().openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
