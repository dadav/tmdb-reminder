# TMDB Reminder v1

## Summary

Build a GPL-3.0, single-user self-hosted application that searches TMDB for movies and TV shows, tracks selected titles in PostgreSQL, and sends Gotify reminders one day before:

- A movie's earliest upcoming digital release in the configured region.
- A TV show's next scheduled episode.

Use a React/Vite frontend, FastAPI backend, and dedicated scheduler worker. Deploy the system through Docker Compose behind a trusted proxy, VPN, or private network.

## Implementation Changes

### Application structure

- Create `backend`, `frontend`, and root deployment configuration.
- Backend: Python 3.13, uv, FastAPI, Pydantic v2, SQLAlchemy 2 async, psycopg 3, Alembic, tmdbsimple, HTTPX, and stable APScheduler 3.11.x.
- Frontend: Bun 1.3.x, React 19, Vite 8, TanStack Query 5, openapi-typescript, openapi-fetch, CSS modules, Vitest, Testing Library, and Playwright.
- Group code by search/catalog, tracking, notifications, diagnostics, and shared infrastructure. Keep API and worker as separate entry points in the same backend package and container image.
- Commit `uv.lock` and `bun.lock`; CI installs with `uv sync --frozen` and `bun ci`.

### TMDB and tracking behavior

- Wrap synchronous `tmdbsimple` calls behind one adapter and execute them through a bounded AnyIO thread limiter so they never block FastAPI's event loop. Configure the module-level API key and request timeout once per process, following the [tmdbsimple API-key and timeout interface](https://github.com/celiao/tmdbsimple/).
- Search TMDB multi-search after two characters and 350 ms of inactivity. Return 20 results per page, discard people and adult results, cancel stale browser requests, and preserve TMDB ordering.
- Compact result cards show poster, localized title, media type, year, overview excerpt, known next release, current tracking state, and a TMDB link.
- Tracking is idempotent and immediately fetches authoritative details. A failed initial TMDB fetch creates no partial record.
- Active titles may have no known date and remain eligible for daily polling.
- Movie events use type-4 digital release dates from the configured region and select the earliest date on or after the current local date.
- TV events use `next_episode_to_air`; identity is TMDB series ID plus season and episode numbers.
- A changed date creates a new event revision. Unsent prior revisions are cancelled. If an earlier revision was delivered, the new notification is labeled as revised.
- Movies become completed after successful delivery, or after an undelivered event expires. They remain under daily revision watch until 30 days after the scheduled release and reopen when a new date is discovered.
- TV shows remain active across episodes, seasons, and hiatuses until manually stopped.
- Stopping tracking is reversible and preserves all history. V1 has no permanent purge.
- Refresh dormant stopped or completed title metadata every 150 days to remain below TMDB's six-month cache limit.

### Scheduling and delivery

- Run stable APScheduler 3.11.x `AsyncIOScheduler`, since APScheduler 4 remains pre-release as of planning time. Use in-memory static schedules, `coalesce=True`, and `max_instances=1`; persist business and delivery state in application tables, not the scheduler job store. [APScheduler release status](https://pypi.org/project/APScheduler/)
- At worker startup, run the daily refresh only if it has not succeeded during the current local day, then always evaluate pending deliveries.
- Refresh eligible TMDB titles daily at the configured local send time. Retry transient TMDB timeouts, 429s, and 5xx responses up to three times, honoring `Retry-After`, while allowing other titles to continue.
- Evaluate Gotify deliveries at startup and hourly. A delivery becomes due at the configured time on the calendar day before release and remains retryable until the end of release day. Same-day messages are labeled late; older undelivered events expire.
- Send one Markdown Gotify message per release with title, movie or episode identity, ISO release date, late or revised label, and a clickable TMDB URL. Use the configured priority, default 5, and authenticate with `X-Gotify-Key` as documented by [Gotify](https://gotify.net/docs/pushmsg).
- Use at-least-once delivery. Claim rows transactionally with a 15-minute lease, send outside the transaction, record the Gotify message ID on success, and recover stale claims. A rare duplicate is acceptable after an ambiguous network result or process crash.
- Emit structured JSON logs with request or job correlation IDs, external boundary timing, retry details, title/event identifiers, and sanitized errors. Never log tokens, API keys, database credentials, or complete secret-bearing URLs.

### Frontend and deployment

- Build one responsive dashboard containing search, active tracking sorted by release date with undated items last, collapsed history sorted by recent activity, diagnostics, and TMDB credits.
- Resume completed or stopped titles through the same idempotent tracking operation. Disable conflicting actions while mutations run and invalidate search, active, history, and status queries after success.
- Provide explicit empty, loading, degraded, retryable-error, and unavailable-poster states. Use accessible native controls and system-selected light/dark CSS variables.
- Include the approved TMDB logo and required notice prominently in a credits/footer area, following [TMDB attribution requirements](https://developer.themoviedb.org/docs/faq).
- Docker Compose contains PostgreSQL, a one-shot Alembic migration service, FastAPI, the scheduler worker, and Nginx. Migration success gates API and worker startup.
- Nginx serves the built SPA, proxies `/api`, and provides SPA fallback. Only `127.0.0.1:${APP_PORT:-8080}` is exposed by default; PostgreSQL, API, and worker remain internal.
- Store PostgreSQL data in a named volume. Run containers as non-root users and use multi-stage locked builds.
- Services start in degraded mode when TMDB or Gotify credentials are absent. Database configuration remains mandatory because all API and job state depends on it.

## Public APIs and Persistence

### HTTP contract

| Method | Route | Behavior |
|---|---|---|
| `GET` | `/api/v1/search?query=&page=` | Search movies and TV, returning tracking state and upstream pagination |
| `GET` | `/api/v1/tracked-titles?view=active\|history&offset=&limit=` | Return paginated active or historical titles |
| `PUT` | `/api/v1/tracked-titles/{media_type}/{tmdb_id}` | Create, reactivate, or idempotently retain active tracking |
| `DELETE` | `/api/v1/tracked-titles/{media_type}/{tmdb_id}` | Soft-stop future synchronization and notifications |
| `GET` | `/api/v1/status` | Return sanitized configuration, connectivity, last-job, and delivery-error status |
| `POST` | `/api/v1/status/gotify-test` | Send an explicit Gotify test message without creating a release delivery |
| `GET` | `/api/v1/health/live` | Confirm the API process is running |
| `GET` | `/api/v1/health/ready` | Confirm PostgreSQL and schema readiness |

- Use Pydantic `BaseModel` for settings and documented request/response schemas. Use Pydantic dataclasses for internal release, TMDB, and Gotify value objects. Keep SQLAlchemy models separate.
- Standardize failures as `{error: {code, message, retryable, details?}, request_id}` and replace FastAPI's default validation-error body with this contract.
- Generate `schema.ts` from a deterministic FastAPI OpenAPI artifact using `openapi-typescript`; use `openapi-fetch` for transport. CI regenerates both and fails on a Git diff.

### PostgreSQL model

- `tracked_titles`: identity PK, `media_type`, `tmdb_id`, cached display metadata, lifecycle status, metadata timestamps, revision-watch deadline, latest sync result, and unique `(media_type, tmdb_id)`.
- `release_events`: title FK, stable source event key, revision number, kind, scheduled calendar date, season/episode fields, current/superseded/withdrawn state, and observed timestamps.
- `notification_deliveries`: event revision FK, due and expiry instants, pending/claimed/sent/cancelled/expired status, lease, attempts, last sanitized error, sent timestamp, and Gotify message ID.
- `job_runs`: job name, correlation ID, start/end timestamps, outcome, processed counts, and sanitized failure summary.
- Store instants in UTC and releases as calendar dates. Evaluate reminder windows with `zoneinfo` in the configured timezone.
- Use string enums with database checks rather than PostgreSQL-native enums. Add indexes for lifecycle lists, refresh eligibility, current events, and due delivery claims.

## Test Plan

- Unit-test digital date selection, next-episode identity, unknown dates, date removal and reappearance, revisions, movie completion/reopening, due windows, daylight-saving boundaries, late expiry, and Gotify message rendering.
- Unit-test transient retry classification, secret redaction, stale delivery-claim recovery, at-least-once ambiguity, and scheduler startup catch-up without real sleeps.
- Mock `tmdbsimple` at its requests boundary and Gotify with HTTPX test transports. Cover timeouts, 401/403, 404, 429 with `Retry-After`, 5xx, malformed payloads, and partial refresh failure.
- Run API and repository integration tests against PostgreSQL, including uniqueness races, concurrent delivery claims, transaction rollback, soft stop/reactivation, pagination, readiness, and Alembic upgrade plus `alembic check`.
- Component-test search debounce and cancellation, loading/error/empty states, tracking mutations, history resume, diagnostics, theme responsiveness, keyboard operation, and accessible names.
- Run one Chromium Playwright flow with deterministic intercepted APIs: search, load more, track a result, observe it in active tracking, stop it, and resume it from history.
- GitHub Actions runs Ruff format/check, mypy, pytest, migration drift, OpenAPI generation drift, ESLint, TypeScript checks, Vitest, Vite production build, Playwright, `docker compose config`, and container builds.

## Assumptions and Defaults

- Single user, no accounts, sessions, or built-in authentication.
- Trusted upstream access layer or VPN; the Compose web port binds to localhost.
- `TMDB_REGION=DE`, `TMDB_LANGUAGE=en-US`, `APP_TIMEZONE=Europe/Berlin`, `REMINDER_TIME=09:00`, and `GOTIFY_PRIORITY=5`.
- App-owned UI and notification labels remain English; Gotify dates use ISO `YYYY-MM-DD`.
- Secrets are environment-only and represented as Pydantic `SecretStr`; `.env.example` contains names and safe defaults but no credentials.
- Up to 1,000 retained titles, offset pagination for local lists, bounded external-call concurrency, and one API plus one worker instance.
- No theatrical, physical, or provider-availability alerts; no full-season ingestion; no manual full sync; no permanent purge; no Prometheus metrics; no image publishing.
- GPL-3.0 project licensing, noncommercial TMDB usage, dependency notices, approved TMDB branding, and the required attribution notice. TMDB-derived metadata is refreshed within the cache window specified by the [TMDB API terms](https://www.themoviedb.org/api-terms-of-use?language=en-CA).
