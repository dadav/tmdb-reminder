import { expect, test, type Route } from "@playwright/test";

// In-memory tracking state driven by the intercepted API. Search results and the
// tracked/history lists all derive from it, so the UI behaves like the real app.
type TrackState = "active" | "stopped" | "completed";

interface ApiMockOptions {
  initialTracked?: Iterable<readonly [number, TrackState]>;
  catalog?: Record<number, string>;
  syncErrorIds?: ReadonlySet<number>;
  // Drives both TMDB content and the browser UI language once status loads.
  tmdbLanguage?: string;
}

function makeApiMock({
  initialTracked = [],
  catalog: catalogOverrides = {},
  syncErrorIds = new Set<number>(),
  tmdbLanguage = "de-DE",
}: ApiMockOptions = {}) {
  const tracked = new Map<number, TrackState>(initialTracked);
  const catalog: Record<number, string> = {
    603: "The Matrix",
    604: "The Matrix Reloaded",
    ...catalogOverrides,
  };

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
    last_sync_status: syncErrorIds.has(id) ? "error" : "ok",
    updated_at: "2026-08-12T00:00:00Z",
  });

  const searchItem = (id: number) => ({
    media_type: "movie",
    tmdb_id: id,
    title: catalog[id],
    overview: "An overview.",
    poster_url: null,
    release_year: 2026,
    tmdb_url: `https://www.themoviedb.org/movie/${id}`,
    tracking_status: tracked.get(id) ?? null,
    next_release: { kind: "movie_digital", scheduled_date: "2026-09-10" },
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
          tmdb_language: tmdbLanguage,
          app_timezone: "Europe/Berlin",
          reminder_time: "09:00",
          availability_delay_days: 0,
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

test("German status drives the UI language, tracking flow, and attribution", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-08-13T10:00:00Z"));
  await page.route("**/api/v1/**", makeApiMock());
  await page.goto("/");

  // Status is de-DE, so the document language and UI switch to German.
  await expect(page.locator("html")).toHaveAttribute("lang", "de");

  // Bilingual attribution: German translation plus the exact English sentence.
  const footer = page.locator("footer");
  await expect(footer).toContainText(
    "Dieses Produkt verwendet die TMDB-API, wird aber nicht von TMDB unterstützt oder zertifiziert.",
  );
  await expect(footer).toContainText(
    "This product uses the TMDB API but is not endorsed or certified by TMDB.",
  );
  await expect(footer.getByRole("link", { name: "The Movie Database (TMDB)" })).toBeVisible();

  // Search and load a second page.
  await page.getByRole("searchbox").fill("matrix");
  await expect(page.getByRole("heading", { name: "The Matrix" })).toBeVisible();
  await page.getByRole("button", { name: /mehr laden/i }).click();
  await expect(page.getByRole("heading", { name: "The Matrix Reloaded" })).toBeVisible();

  const searchSection = page.getByRole("region", { name: "Suche" });
  await expect(
    searchSection.getByRole("article").filter({ hasText: "The Matrix" }).first(),
  ).toContainText("Digital · 10.09.2026 · in 28 Tagen");

  // Track ("Merken") the first result from its card.
  await searchSection
    .getByRole("article")
    .filter({ hasText: "The Matrix" })
    .first()
    .getByRole("button", { name: /^Merken$/ })
    .click();

  const trackingSection = page.getByRole("region", { name: "Merkliste" });
  await expect(trackingSection.getByRole("heading", { name: "The Matrix" })).toBeVisible();
  const trackedCard = trackingSection
    .getByRole("article")
    .filter({ hasText: "The Matrix" })
    .first();
  await expect(trackedCard).toContainText("Digital · 10.09.2026 · in 28 Tagen");

  // At the default desktop viewport, content stays on the original horizontal rows.
  const desktopPositions = await trackedCard.evaluate((card) => {
    const title = card.querySelector("h3");
    const badge = card.querySelector('[data-tone="active"]');
    const link = card.querySelector("a");
    const button = card.querySelector("button");
    if (!title || !badge || !link || !button) {
      throw new Error("Expected title, active badge, TMDB link, and action button");
    }
    return {
      titleRight: title.getBoundingClientRect().right,
      badgeLeft: badge.getBoundingClientRect().left,
      linkRight: link.getBoundingClientRect().right,
      buttonLeft: button.getBoundingClientRect().left,
    };
  });
  expect(desktopPositions.badgeLeft).toBeGreaterThanOrEqual(desktopPositions.titleRight);
  expect(desktopPositions.buttonLeft).toBeGreaterThanOrEqual(desktopPositions.linkRight);

  // Stop ("Entfernen") it from the tracking card.
  await trackingSection.getByRole("button", { name: /^Entfernen$/ }).click();
  await expect(trackingSection.getByRole("heading", { name: "The Matrix" })).toBeHidden();

  const historySection = page.getByRole("region", { name: "Verlauf" });
  await historySection.getByRole("group").getByText(/verlauf anzeigen/i).click();
  await expect(historySection.getByRole("heading", { name: "The Matrix" })).toBeVisible();
  await expect(
    historySection.getByRole("article").filter({ hasText: "The Matrix" }).first(),
  ).toContainText("Digital · 10.09.2026 · in 28 Tagen");
  await historySection.getByRole("button", { name: /^Erneut merken$/ }).click();

  // Back under the Merkliste.
  await expect(trackingSection.getByRole("heading", { name: "The Matrix" })).toBeVisible();
});

test("an unsupported TMDB language falls back to the English UI", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-08-13T10:00:00Z"));
  await page.route("**/api/v1/**", makeApiMock({ tmdbLanguage: "fr-FR" }));
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("region", { name: "Search" })).toBeVisible();
  await expect(
    page.getByRole("searchbox", { name: /search movies and tv shows/i }),
  ).toBeVisible();
  await expect(page.locator("footer")).toContainText(
    "This product uses the TMDB API but is not endorsed or certified by TMDB.",
  );
});

test("cards stay inside their grid at a 320px phone width", async ({ page }) => {
  // Worst case for horizontal overflow: a narrow phone, a long title with an
  // unbreakable word, two badges (status + sync error), the TMDB link, and an
  // action button all competing for the same row.
  const longTitle =
    "The Matrix Resurrections Ultimate Pneumonoultramicroscopicsilicovolcanoconiosis Edition";

  await page.setViewportSize({ width: 320, height: 800 });
  await page.clock.setFixedTime(new Date("2026-08-13T10:00:00Z"));
  await page.route(
    "**/api/v1/**",
    makeApiMock({
      initialTracked: [[42, "active"]],
      catalog: { 42: longTitle },
      syncErrorIds: new Set([42]),
    }),
  );
  await page.goto("/");

  const card = page
    .getByRole("region", { name: "Merkliste" })
    .getByRole("article")
    .filter({ hasText: "The Matrix Resurrections" })
    .first();
  await expect(card).toBeVisible();
  await expect(card.getByText("Sync-Fehler")).toBeVisible();
  await expect(card.getByRole("link", { name: /auf tmdb ansehen/i })).toBeVisible();
  await expect(card.getByRole("button", { name: /^Entfernen$/ })).toBeVisible();

  // The document must not scroll horizontally at any narrow width.
  const overflow = await page.evaluate(() => {
    const el = document.scrollingElement ?? document.documentElement;
    return { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth };
  });
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);

  // Every card must fit within its grid container's right edge.
  const rightOverflow = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll("article"));
    return cards.map((cardEl) => {
      const gridRight = (cardEl.parentElement as HTMLElement).getBoundingClientRect().right;
      return cardEl.getBoundingClientRect().right - gridRight;
    });
  });
  for (const delta of rightOverflow) {
    expect(delta).toBeLessThanOrEqual(0.5);
  }
});

test("relative day label rolls over across midnight in Europe/Berlin", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-09-09T21:59:00Z") });
  await page.route("**/api/v1/**", makeApiMock());
  await page.goto("/");

  await page.getByRole("searchbox").fill("matrix");
  await page.clock.fastForward(500); // Fire the 350ms search debounce.

  const card = page
    .getByRole("region", { name: "Suche" })
    .getByRole("article")
    .filter({ hasText: "The Matrix" })
    .first();
  await expect(card).toContainText("Digital · 10.09.2026 · in 1 Tag");

  await page.clock.fastForward(120_000);
  await expect(card).toContainText("Digital · 10.09.2026 · heute");
});
