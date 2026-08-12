import { expect, test, type Route } from "@playwright/test";

// In-memory tracking state driven by the intercepted API. Search results and the
// tracked/history lists all derive from it, so the UI behaves like the real app.
type TrackState = "active" | "stopped" | "completed";

function makeApiMock() {
  const tracked = new Map<number, TrackState>();

  const titleView = (id: number, title: string, status: TrackState) => ({
    id,
    media_type: "movie",
    tmdb_id: id,
    title,
    overview: "An overview.",
    poster_url: null,
    release_year: 2026,
    status,
    tmdb_url: `https://www.themoviedb.org/movie/${id}`,
    next_release: { kind: "movie_digital", scheduled_date: "2026-09-10" },
    last_sync_status: "ok",
    updated_at: "2026-08-12T00:00:00Z",
  });

  const catalog: Record<number, string> = { 603: "The Matrix", 604: "The Matrix Reloaded" };

  const searchItem = (id: number) => ({
    media_type: "movie",
    tmdb_id: id,
    title: catalog[id],
    overview: "An overview.",
    poster_url: null,
    release_year: 2026,
    tmdb_url: `https://www.themoviedb.org/movie/${id}`,
    tracking_status: tracked.get(id) ?? null,
    next_release: null,
  });

  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

  return async (route: Route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;

    if (path === "/api/v1/status") {
      return json(route, {
        degraded: false,
        config: {
          tmdb_configured: true,
          gotify_configured: true,
          tmdb_region: "DE",
          tmdb_language: "en-US",
          app_timezone: "Europe/Berlin",
          reminder_time: "09:00",
          gotify_priority: 5,
        },
        last_jobs: [],
        tracked_active: [...tracked.values()].filter((s) => s === "active").length,
        tracked_history: [...tracked.values()].filter((s) => s !== "active").length,
        pending_deliveries: 0,
        recent_delivery_errors: 0,
      });
    }

    if (path === "/api/v1/search") {
      const page = Number(url.searchParams.get("page") ?? "1");
      const results = page === 1 ? [searchItem(603)] : [searchItem(604)];
      return json(route, { results, page, total_pages: 2, total_results: 2, degraded: false });
    }

    if (path === "/api/v1/tracked-titles" && method === "GET") {
      const view = url.searchParams.get("view");
      const items = [...tracked.entries()]
        .filter(([, s]) => (view === "active" ? s === "active" : s !== "active"))
        .map(([id, s]) => titleView(id, catalog[id], s));
      return json(route, { items, view, offset: 0, limit: 20, total: items.length });
    }

    const putMatch = path.match(/^\/api\/v1\/tracked-titles\/movie\/(\d+)$/);
    if (putMatch) {
      const id = Number(putMatch[1]);
      if (method === "PUT") {
        tracked.set(id, "active");
        return json(route, titleView(id, catalog[id], "active"));
      }
      if (method === "DELETE") {
        tracked.set(id, "stopped");
        return json(route, titleView(id, catalog[id], "stopped"));
      }
    }

    return json(route, { error: { code: "not_found", message: "no route", retryable: false }, request_id: "e2e" }, 404);
  };
}

test("search, load more, track, stop, and resume", async ({ page }) => {
  await page.route("**/api/v1/**", makeApiMock());
  await page.goto("/");

  // Search and load a second page.
  await page.getByRole("searchbox").fill("matrix");
  await expect(page.getByRole("heading", { name: "The Matrix" })).toBeVisible();
  await page.getByRole("button", { name: /load more/i }).click();
  await expect(page.getByRole("heading", { name: "The Matrix Reloaded" })).toBeVisible();

  // Track the first result from its card.
  const searchSection = page.getByRole("region", { name: "Search" });
  await searchSection
    .getByRole("article")
    .filter({ hasText: "The Matrix" })
    .first()
    .getByRole("button", { name: /^Track$/ })
    .click();

  // It appears under Tracking (active).
  const trackingSection = page.getByRole("region", { name: "Tracking" });
  await expect(trackingSection.getByRole("heading", { name: "The Matrix" })).toBeVisible();

  // Stop it from the tracking card.
  await trackingSection.getByRole("button", { name: /^Stop$/ }).click();
  await expect(trackingSection.getByRole("heading", { name: "The Matrix" })).toBeHidden();

  // Open history and resume it.
  const historySection = page.getByRole("region", { name: "History" });
  await historySection.getByRole("group").getByText(/show history/i).click();
  await expect(historySection.getByRole("heading", { name: "The Matrix" })).toBeVisible();
  await historySection.getByRole("button", { name: /^Resume$/ }).click();

  // Back under Tracking.
  await expect(trackingSection.getByRole("heading", { name: "The Matrix" })).toBeVisible();
});
