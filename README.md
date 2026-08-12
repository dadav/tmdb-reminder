# TMDB Reminder

Self-hosted, single-user application that searches [TMDB](https://www.themoviedb.org/)
for movies and TV shows, tracks the ones you pick, and sends a [Gotify](https://gotify.net/)
reminder the day before:

- a movie's earliest upcoming **digital** release in your configured region, or
- a TV show's **next scheduled episode**.

It is a React + FastAPI app with a dedicated scheduler worker, deployed with
Docker Compose behind a trusted proxy, VPN, or private network. Licensed
**GPL-3.0-or-later**.

## Architecture

```
Browser ─▶ Nginx (web) ─┬─▶ SPA (static build)
                        └─▶ /api ─▶ FastAPI (api)
                                     │
Worker (APScheduler) ────────────────┼─▶ PostgreSQL (db)
   daily refresh + hourly delivery   │
                                     ▼
                               Gotify + TMDB
```

- **backend/**: Python 3.13, FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic,
  APScheduler 3.11, tmdbsimple, HTTPX. One package, two entrypoints
  (`tmdb-reminder-api`, `tmdb-reminder-worker`), one image.
- **frontend/**: Bun, React 19, Vite, TanStack Query, a client generated from
  the API's OpenAPI schema (`openapi-typescript` + `openapi-fetch`), CSS modules.
- Business and delivery state lives in PostgreSQL, never in the scheduler job
  store. Instants are stored in UTC; reminder windows are evaluated in the
  configured local timezone.

## How it works

- Search calls TMDB multi-search, discards people and adult results, and shows
  each title's current tracking state.
- Tracking is idempotent: it immediately fetches authoritative details. A failed
  first fetch leaves no partial record.
- **Movies**: the earliest type-4 (digital) release on/after today in your region.
  After delivery or expiry a movie is *completed* but stays under daily
  revision-watch for 30 days, and reopens if a new date appears.
- **TV**: uses `next_episode_to_air`; identity is series id + season + episode.
  TV stays active across seasons and hiatuses until you stop it.
- A changed date creates a new event **revision**; unsent prior reminders are
  cancelled and, if an earlier one was already delivered, the new one is labeled
  *revised*. A same-day reminder is labeled *late*.
- Delivery is **at-least-once**: rows are claimed transactionally with a 15-minute
  lease, sent outside the transaction, and the Gotify message id is recorded on
  success. Stale claims are recovered.
- **Degraded mode**: without TMDB or Gotify credentials the app still starts;
  affected features report a documented degraded state. The database is required.

## Quick start (Docker Compose)

```bash
cp .env.example .env       # set POSTGRES_PASSWORD, TMDB_API_KEY, GOTIFY_* etc.
docker compose up -d        # pulls the published images from GHCR
# open http://127.0.0.1:8080
```

Compose pulls prebuilt images from GHCR
(`ghcr.io/dadav/tmdb-reminder-backend`, `ghcr.io/dadav/tmdb-reminder-web`),
published by CI on every push to `main` and every `v*` tag. No local build
is needed.

GHCR packages are private when first created. After the first successful image
workflow, an owner must open each package on GitHub, select **Package settings**,
then **Change visibility**, and make both `tmdb-reminder-backend` and
`tmdb-reminder-web` public. This one-time step enables the anonymous pulls used
by the Compose quick start. Until then, deployment hosts must authenticate to
`ghcr.io` before running Compose.

Only `127.0.0.1:${APP_PORT:-8080}` is published. PostgreSQL, the API, and the
worker stay internal. Migration success gates the API and worker.

### Image tags

`IMAGE_TAG` in `.env` selects one tag for both images (default `latest`):

- `latest` tracks the newest `main` build.
- `sha-<short-commit>` identifies the commit CI built.
- `v<version>` identifies a released version tag.

For a pinned deployment, select a `sha-*` or `v*` tag rather than `latest`, then
run `docker compose up -d`. Container tags can be moved; use an image digest
when content-level immutability is required.

`TMDB_API_KEY` accepts a v3 API key or a v4 read-access bearer token (auto-detected).

## Configuration

See [`.env.example`](.env.example). Defaults: `TMDB_REGION=DE`,
`TMDB_LANGUAGE=en-US`, `APP_TIMEZONE=Europe/Berlin`, `REMINDER_TIME=09:00`,
`GOTIFY_PRIORITY=5`. Secrets are environment-only.

## Development

### Backend

```bash
cd backend
uv sync
uv run ruff check . && uv run mypy && uv run ruff format --check .
# Integration tests need a PostgreSQL; point DATABASE_URL_TEST at one:
DATABASE_URL_TEST=postgresql+psycopg://tmdb:tmdb@localhost:5432/tmdb_reminder uv run pytest
```

Regenerate the committed OpenAPI artifact after changing schemas:

```bash
uv run python scripts/export_openapi.py   # writes frontend/openapi.json
```

Create a migration after model changes, then verify no drift:

```bash
DATABASE_URL=postgresql+psycopg://tmdb:tmdb@localhost:5432/tmdb_reminder \
  uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head && uv run alembic check
```

### Frontend

```bash
cd frontend
bun install
bun run gen:api      # regenerate src/api/schema.ts from frontend/openapi.json
bun run lint && bun run typecheck && bun run test
bun run build
bun run e2e          # Playwright (Chromium), fully intercepted APIs
```

`frontend/openapi.json` and `frontend/src/api/schema.ts` are committed; CI
regenerates both and fails on any diff.

## Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB. TMDB
branding and the required notice appear in the app footer.
