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
      tmdb_language: "de-DE",
      app_timezone: "Europe/Berlin",
      reminder_time: "09:00",
      availability_delay_days: 2,
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

describe("Diagnostics (German)", () => {
  it("renders localized configuration, activity, and job names", async () => {
    installFetch([{ method: "GET", match: pathIs(STATUS), json: statusPayload() }]);
    renderWithClient(<Diagnostics />);
    // Wait for status data (external value) before asserting the rest.
    expect(await screen.findByText("Europe/Berlin")).toBeInTheDocument();
    // Section and card headings are localized.
    expect(screen.getByRole("heading", { name: "Diagnose" })).toBeInTheDocument();
    expect(screen.getByText("Konfiguration")).toBeInTheDocument();
    expect(screen.getByText("Zeitzone")).toBeInTheDocument();
    expect(screen.getByText("Verfügbarkeitsverzögerung")).toBeInTheDocument();
    expect(screen.getByText("2 Tage")).toBeInTheDocument();
    // The known job name "refresh" is translated.
    expect(screen.getByText(/Aktualisierung/)).toBeInTheDocument();
  });

  it("formats the reminder time as a wall-clock time", async () => {
    installFetch([{ method: "GET", match: pathIs(STATUS), json: statusPayload() }]);
    renderWithClient(<Diagnostics />);
    expect(await screen.findByText("09:00")).toBeInTheDocument();
  });

  it("formats numbers and labels unknown job data as technical details", async () => {
    installFetch([
      {
        method: "GET",
        match: pathIs(STATUS),
        json: statusPayload({
          tracked_active: 1234,
          last_jobs: [
            {
              job_name: "future_job",
              outcome: "future_outcome",
              finished_at: null,
              processed_count: 1234,
            },
          ],
        }),
      },
    ]);
    renderWithClient(<Diagnostics />);
    expect(await screen.findByText("1.234")).toBeInTheDocument();
    expect(screen.getByText(/Unbekannter Job/)).toBeInTheDocument();
    expect(screen.getByText(/Technische Details: future_job \/ future_outcome/)).toBeInTheDocument();
  });

  it("sends a Gotify test and reports success", async () => {
    installFetch([
      { method: "GET", match: pathIs(STATUS), json: statusPayload() },
      { method: "POST", match: pathIs(GOTIFY_TEST), json: { sent: true, message_id: 42 } },
    ]);
    renderWithClient(<Diagnostics />);
    await screen.findByText("Europe/Berlin");
    await userEvent.click(screen.getByRole("button", { name: /gotify-test senden/i }));
    await waitFor(() => expect(screen.getByText(/nachricht #42/i)).toBeInTheDocument());
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
    expect(screen.getByRole("button", { name: /gotify-test senden/i })).toBeDisabled();
  });
});
