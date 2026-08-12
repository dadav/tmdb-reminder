import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TrackToggle } from "../src/components/TrackToggle";
import { installFetch, renderWithClient } from "./utils";

afterEach(() => vi.unstubAllGlobals());

const TRACK_PATH = "/api/v1/tracked-titles/movie/603";

function titleView(status: string) {
  return {
    id: 1,
    media_type: "movie",
    tmdb_id: 603,
    title: "The Matrix",
    status,
    tmdb_url: "https://www.themoviedb.org/movie/603",
    updated_at: "2026-08-12T00:00:00Z",
  };
}

describe("TrackToggle", () => {
  it("labels the action Track when the title is untracked", () => {
    installFetch([]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status={null} />);
    expect(screen.getByRole("button", { name: /track/i })).toBeInTheDocument();
  });

  it("labels the action Resume for a stopped title", () => {
    installFetch([]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status="stopped" />);
    expect(screen.getByRole("button", { name: /resume/i })).toBeInTheDocument();
  });

  it("labels the action Stop for an active title", () => {
    installFetch([]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status="active" />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("issues a PUT when tracking and disables the button while pending", async () => {
    const { calls } = installFetch([
      { method: "PUT", match: (url) => url.pathname === TRACK_PATH, json: titleView("active"), delayMs: 20 },
    ]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status={null} />);
    const button = screen.getByRole("button", { name: /track/i });
    await userEvent.click(button);
    expect(button).toBeDisabled();
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  });

  it("issues a DELETE when stopping", async () => {
    const { calls } = installFetch([
      { method: "DELETE", match: (url) => url.pathname === TRACK_PATH, json: titleView("stopped") },
    ]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status="active" />);
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });

  it("surfaces an error when the mutation fails", async () => {
    installFetch([
      {
        method: "PUT",
        match: (url) => url.pathname === TRACK_PATH,
        status: 502,
        json: { error: { code: "tmdb_unavailable", message: "down", retryable: true }, request_id: "t" },
      },
    ]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status={null} />);
    await userEvent.click(screen.getByRole("button", { name: /track/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/action failed/i);
  });
});
