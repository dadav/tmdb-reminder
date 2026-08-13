import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Root } from "../src/App";
import { installFetch, pathIs } from "./utils";

afterEach(() => vi.unstubAllGlobals());

describe("Root locale authority", () => {
  it("uses the browser locale first, then falls back to English for an empty server locale", async () => {
    vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
    installFetch([
      {
        method: "GET",
        match: pathIs("/api/v1/status"),
        delayMs: 20,
        json: {
          degraded: false,
          config: {
            tmdb_configured: false,
            gotify_configured: false,
            tmdb_region: "DE",
            tmdb_language: "",
            app_timezone: "Europe/Berlin",
            reminder_time: "09:00",
            gotify_priority: 5,
          },
          last_jobs: [],
          tracked_active: 0,
          tracked_history: 0,
          pending_deliveries: 0,
          recent_delivery_errors: 0,
        },
      },
    ]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <Root />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("region", { name: "Suche" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("de");
    await waitFor(() => expect(screen.getByRole("region", { name: "Search" })).toBeInTheDocument());
    expect(document.documentElement.lang).toBe("en");
    expect(document.title).toBe("TMDB Reminder");
  });
});
