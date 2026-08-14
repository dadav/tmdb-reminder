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

describe("TrackToggle (German)", () => {
  it("labels the action Merken when the title is untracked", () => {
    installFetch([]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status={null} />);
    expect(screen.getByRole("button", { name: "Merken" })).toBeInTheDocument();
  });

  it("labels the action Erneut merken for a stopped title", () => {
    installFetch([]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status="stopped" />);
    expect(screen.getByRole("button", { name: "Erneut merken" })).toBeInTheDocument();
  });

  it("labels the action Entfernen for an active title", () => {
    installFetch([]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status="active" />);
    expect(screen.getByRole("button", { name: "Entfernen" })).toBeInTheDocument();
  });

  it("labels an available completed movie Entfernen and soft-stops it", async () => {
    const { calls } = installFetch([
      { method: "DELETE", match: (url) => url.pathname === TRACK_PATH, json: titleView("stopped") },
    ]);
    renderWithClient(
      <TrackToggle mediaType="movie" tmdbId={603} status="completed" isAvailable={true} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Entfernen" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });

  it("labels a completed movie without availability Erneut merken", () => {
    installFetch([]);
    renderWithClient(
      <TrackToggle mediaType="movie" tmdbId={603} status="completed" isAvailable={false} />,
    );
    expect(screen.getByRole("button", { name: "Erneut merken" })).toBeInTheDocument();
  });

  it("issues a PUT when tracking and disables the button while pending", async () => {
    const { calls } = installFetch([
      { method: "PUT", match: (url) => url.pathname === TRACK_PATH, json: titleView("active"), delayMs: 20 },
    ]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status={null} />);
    const button = screen.getByRole("button", { name: "Merken" });
    await userEvent.click(button);
    expect(button).toBeDisabled();
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  });

  it("issues a DELETE when stopping", async () => {
    const { calls } = installFetch([
      { method: "DELETE", match: (url) => url.pathname === TRACK_PATH, json: titleView("stopped") },
    ]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status="active" />);
    await userEvent.click(screen.getByRole("button", { name: "Entfernen" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });

  it("surfaces a localized error when the mutation fails", async () => {
    installFetch([
      {
        method: "PUT",
        match: (url) => url.pathname === TRACK_PATH,
        status: 502,
        json: { error: { code: "tmdb_unavailable", message: "down", retryable: true }, request_id: "t" },
      },
    ]);
    renderWithClient(<TrackToggle mediaType="movie" tmdbId={603} status={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Merken" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/aktion fehlgeschlagen/i);
  });
});
