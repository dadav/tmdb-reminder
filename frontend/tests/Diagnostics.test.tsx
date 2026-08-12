import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Diagnostics } from "../src/components/Diagnostics";
import { installFetch, pathIs, renderWithClient } from "./utils";

afterEach(() => vi.unstubAllGlobals());

const STATUS = "/api/v1/status";
const GOTIFY_TEST = "/api/v1/status/gotify-test";

function statusPayload(overrides: Record<string, unknown> = {}) {
  return {
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
    last_jobs: [
      { job_name: "refresh", outcome: "success", finished_at: "2026-08-12T07:00:00Z", processed_count: 3 },
    ],
    tracked_active: 2,
    tracked_history: 1,
    pending_deliveries: 0,
    recent_delivery_errors: 0,
    ...overrides,
  };
}

describe("Diagnostics", () => {
  it("renders sanitized configuration and activity", async () => {
    installFetch([{ method: "GET", match: pathIs(STATUS), json: statusPayload() }]);
    renderWithClient(<Diagnostics />);
    expect(await screen.findByText("Europe/Berlin")).toBeInTheDocument();
    expect(screen.getByText("refresh")).toBeInTheDocument();
  });

  it("sends a Gotify test and reports success", async () => {
    installFetch([
      { method: "GET", match: pathIs(STATUS), json: statusPayload() },
      { method: "POST", match: pathIs(GOTIFY_TEST), json: { sent: true, message_id: 42 } },
    ]);
    renderWithClient(<Diagnostics />);
    await screen.findByText("Europe/Berlin");
    await userEvent.click(screen.getByRole("button", { name: /send gotify test/i }));
    await waitFor(() => expect(screen.getByText(/message #42/i)).toBeInTheDocument());
  });

  it("disables the test button when Gotify is not configured", async () => {
    installFetch([
      {
        method: "GET",
        match: pathIs(STATUS),
        json: statusPayload({ config: { ...statusPayload().config, gotify_configured: false } }),
      },
    ]);
    renderWithClient(<Diagnostics />);
    await screen.findByText("Europe/Berlin");
    expect(screen.getByRole("button", { name: /send gotify test/i })).toBeDisabled();
  });
});
