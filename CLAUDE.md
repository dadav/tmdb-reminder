# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Self-hosted, single-user app: search TMDB, track movies/TV, send a Gotify reminder the day before a movie's earliest digital release (configured region) or a TV show's next episode. GPL-3.0-or-later. Monorepo: `backend/` (Python/FastAPI/uv) + `frontend/` (React/Vite/Bun). Deployed via Docker Compose (Postgres, migrate one-shot, API, worker, Nginx). `plan.md` is the canonical product and implementation spec. `plan2.md` is the historical image-publishing amendment already incorporated into `plan.md`.

## Commands

Prefer `just` (root `justfile`) for repository workflows; recipes set the right working directory and environment. The migration workflow below includes one direct Alembic command because there is no recipe that only upgrades the test database to the existing head.

- `just`: list recipes.
- `just check`: everything CI checks, locally. Spins up and tears down a disposable test DB. Run this before returning work.
- Backend: `just backend-lint` (ruff format check + ruff check + mypy), `just backend-fix` (auto-fix), `just backend-test [args]`, `just run-api`, `just run-worker`.
- Frontend: `just frontend-check` (lint + typecheck + vitest), `just frontend-build`, `just e2e` (Playwright/Chromium, intercepted APIs), `just dev`.
- Test DB: `just test-db-up` / `just test-db-down` (throwaway Postgres on `127.0.0.1:55432`); `just backend-test-full` brings it up, runs migrate-check + tests, tears it down.
- Compose: `just up` (pulls GHCR images, no local build), `just down`, `just logs [service]`.

### Running a single test

- Backend unit test: `just backend-test tests/test_mapping.py::test_name` or `just backend-test -k pattern`. For an integration test, run `just test-db-up`, then `just backend-test tests/test_tracking_service.py::test_name`, and finish with `just test-db-down`. The `just` recipe supplies `DATABASE_URL_TEST`; `just test-db-up` cannot export variables into the caller's shell. Unit tests need no DB.
- Frontend: `cd frontend && bun run test <file>` or `bunx vitest run -t "name"`.

## Generated artifacts and schema drift

When you change the relevant source, update and verify its derived output:

1. **OpenAPI to typed client.** Backend routes and schemas are the source of truth. After changing them, run `just openapi`, then `just gen-api`. These commands rewrite the committed `frontend/openapi.json` and `frontend/src/api/schema.ts`; never hand-edit either file. CI regenerates both and fails on a Git diff. Frontend transport uses `openapi-fetch` through `frontend/src/api/client.ts` (`unwrap()` throws a typed `ApiError`).
2. **Migrations.** After changing `backend/src/tmdb_reminder/models.py`, start the test DB with `just test-db-up` and upgrade it to the existing migration head with `cd backend && DATABASE_URL=postgresql+psycopg://tmdb:tmdb@localhost:55432/tmdb_reminder uv run alembic upgrade head`. Then run `just migrate-new "message"`, manually review and adjust the generated candidate migration, run `just migrate-check`, and stop the DB with `just test-db-down`. Migrations are source code, not generated artifacts to accept blindly. CI verifies them with `alembic upgrade head` and `alembic check`, not a Git diff.

## Architecture

### Backend: one package, two entrypoints, one image

`backend/src/tmdb_reminder/` is a single package. `tmdb-reminder-api` (`main_api`) and `tmdb-reminder-worker` (`main_worker`) are separate processes built into the same container image; Compose runs both plus a `migrate` one-shot from that image. Migration success gates API and worker startup.

- **API** (`api/app.py`): app factory wires shared resources onto `app.state` in the lifespan (`Database`, `TmdbAdapter`, `GotifyClient`, `TrackingService`); `api/deps.py` exposes them as typed FastAPI dependencies (`SessionDep`, `TrackingDep`, etc.). Middleware assigns a request id (correlation id) and echoes `X-Request-ID`. All errors go through the standardized contract (see below).
- **Worker** (`main_worker.py` to `worker/scheduler.py` and `worker/jobs.py`): APScheduler 3.11 `AsyncIOScheduler`, static in-memory schedules only. `daily_refresh` runs at `REMINDER_TIME`; `hourly_delivery` every hour. At startup `Jobs.startup_catchup` runs a missed refresh (once per local day) then always evaluates deliveries. `coalesce=True`, `max_instances=1`. **No business state lives in the scheduler job store**; it all lives in application tables.

### Domain flow (the important part)

`TrackingService` (`tracking/service.py`) is the heart. TMDB payloads become domain rows:

- `tracked_titles` to `release_events` (revisions) to `notification_deliveries`; `job_runs` records each worker run.
- **Track (PUT)** is idempotent: authoritative TMDB details are fetched *before* taking the DB row lock (so a slow upstream call doesn't block a concurrent PUT), and a failed fetch makes no change; a new title never leaves a partial record.
- **Reconciliation:** a changed release date supersedes the current event and creates a new revision (cancelling that event's unsent deliveries); if any prior revision was already delivered, the new delivery is flagged `is_revised`. A disappeared movie date withdraws the current event. TV keeps already-observed episode events as history; only TMDB's latest `next_episode_to_air` stays `current`.
- **Movie lifecycle:** after its digital event is delivered or expires a movie becomes `completed` but stays under revision-watch (`revision_watch_until`, default release + 30 days) and reopens to `active` if a new date appears. TV stays `active` until stopped. Stop is a soft status change (`stopped`) that cancels unsent deliveries and preserves history; there is no purge in v1.
- **Delivery** (`notifications/delivery.py`) is **at-least-once**: recover stale claims (expired lease), claim one due row with `SELECT ... FOR UPDATE SKIP LOCKED` and a 15-minute lease, send *outside* the transaction, then record the Gotify message id on success or release for retry on failure. A due delivery fires at `REMINDER_TIME` the day before release and stays retryable until end of release day (same-day = `late`, older = `expired`). A rare duplicate after an ambiguous network result is accepted by design.

### Determinism and time

Domain functions take an explicit `now` (UTC); never call the clock inside them. Tests pass fixed instants. Instants are stored/compared in UTC; releases are calendar dates; reminder windows are computed with `zoneinfo` in `APP_TIMEZONE` (`time_utils.py`). Preserve this when adding logic.

### Conventions to follow

- **Enums** (`enums.py`) are `StrEnum` stored as plain strings with DB CHECK constraints (`models.py`), not Postgres-native enum types. Compare `title.status == TitleStatus.ACTIVE.value`.
- **TMDB adapter** (`tmdb/adapter.py`) is the only place that touches `tmdbsimple` (blocking `requests`). Calls run on AnyIO's thread pool under a bounded `CapacityLimiter`; module-level TMDB credentials are set under a lock per call. Timeouts, connection failures, 429, 500, 502, 503, and 504 retry for at most `tmdb_max_retries` total attempts, honoring numeric `Retry-After` values up to 30 seconds. Add new TMDB calls here, not in services.
- **Errors:** all failures are `AppError` subclasses (`errors.py`) serialized as `{error: {code, message, retryable, details?}, request_id}`; FastAPI's default validation body is replaced with this shape.
- **Secrets:** `tmdb_api_key` and `gotify_token` are environment-only Pydantic `SecretStr` values. `database_url` and `gotify_url` are plain strings and may contain credentials. Never log tokens, keys, database URLs, or credentialed URLs; route error text through `logging_config.sanitize`. Logs are structured JSON with a correlation id.
- **Degraded mode:** TMDB and Gotify credentials are optional; the app starts without them and affected features report a documented degraded state. The database is mandatory. Guard with `settings.tmdb_configured` / `settings.gotify_configured`.
- **Value objects:** internal TMDB, release, and Gotify shapes are Pydantic dataclasses in `value_objects.py`. `tmdb/mapping.py` contains pure mapping and release-selection functions. Request/response models are Pydantic `BaseModel` classes in `schemas.py`; SQLAlchemy models are separate in `models.py`.

### Frontend

`frontend/src/`: React 19 + TanStack Query (`api/queries.ts`) over the generated `openapi-fetch` client. Feature components under `components/`, CSS modules, system light/dark. Single dashboard: search + active tracking + collapsed history + diagnostics + TMDB attribution footer (required, do not remove). Don't hand-edit `src/api/schema.ts` (generated).

**Localization (i18next + react-i18next).** English and German are bundled, typed catalogs in `i18n/en.ts` and `i18n/de.ts`; `en.ts` exports the `Resources` type and `de.ts` is typed against it, so both must define exactly the same keys (a test also asserts key parity at runtime). All new app-owned UI copy MUST be added to both catalogs. The only exceptions are the prescribed TMDB legal notice and external data (TMDB titles, overviews, region codes, timezone names, identifiers), which are handled explicitly in code, not translated. Locale resolution lives in `lib/locale.ts` (`TMDB_LANGUAGE` is authoritative once status loads; the browser locale seeds the shell; unsupported/invalid falls back to English/en-US). Components read `{ t, formatLocale }` from `useI18n()` (`i18n/context.ts`); pure, deterministic formatting helpers in `lib/format.ts` take an explicit `t` and `formatLocale`. The footer logo is the official unmodified TMDB SVG at `src/assets/tmdb-logo.svg`.

## Deployment notes

Images are built and published to GHCR by CI (`.github/workflows/ci.yml`) on `main` and `v*` tags: `ghcr.io/dadav/tmdb-reminder-backend` and `-web`, `linux/amd64` only. PRs build without publishing. Compose pulls these images (no local build); `IMAGE_TAG` selects one tag for both (`latest`, `sha-<short>`, or `v<version>`). Only `127.0.0.1:${APP_PORT:-8080}` (Nginx) is published; Postgres/API/worker stay internal.
