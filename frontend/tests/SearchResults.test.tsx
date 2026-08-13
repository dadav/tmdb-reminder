import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchResults } from "../src/components/SearchResults";
import { installFetch, pathIs, renderWithClient, type Route } from "./utils";

afterEach(() => vi.unstubAllGlobals());

function searchItem(id: number, title: string) {
  return {
    media_type: "movie",
    tmdb_id: id,
    title,
    overview: "overview",
    poster_url: null,
    release_year: 2026,
    tmdb_url: `https://www.themoviedb.org/movie/${id}`,
    tracking_status: null,
    next_release: null,
  };
}

function searchPayload(page: number, items: unknown[], totalPages = 1) {
  return { results: items, page, total_pages: totalPages, total_results: items.length, degraded: false };
}

const SEARCH = "/api/v1/search";

describe("SearchResults (German)", () => {
  it("prompts to type more when the query is too short", () => {
    installFetch([]);
    renderWithClient(<SearchResults rawQuery="a" debouncedQuery="a" />);
    expect(screen.getByText(/mindestens 2 zeichen/i)).toBeInTheDocument();
  });

  it("renders results returned by the API", async () => {
    installFetch([
      { method: "GET", match: pathIs(SEARCH), json: searchPayload(1, [searchItem(603, "The Matrix")]) },
    ]);
    renderWithClient(<SearchResults rawQuery="matrix" debouncedQuery="matrix" />);
    expect(await screen.findByText("The Matrix")).toBeInTheDocument();
  });

  it("shows an empty state when there are no results", async () => {
    installFetch([{ method: "GET", match: pathIs(SEARCH), json: searchPayload(1, []) }]);
    renderWithClient(<SearchResults rawQuery="zzz" debouncedQuery="zzz" />);
    expect(await screen.findByText(/keine ergebnisse/i)).toBeInTheDocument();
  });

  it("shows a degraded warning when TMDB is not configured", async () => {
    installFetch([
      {
        method: "GET",
        match: pathIs(SEARCH),
        json: { results: [], page: 1, total_pages: 0, total_results: 0, degraded: true },
      },
    ]);
    renderWithClient(<SearchResults rawQuery="matrix" debouncedQuery="matrix" />);
    expect(await screen.findByText(/suche nicht verfügbar/i)).toBeInTheDocument();
  });

  it("shows a retryable error state on failure", async () => {
    installFetch([
      {
        method: "GET",
        match: pathIs(SEARCH),
        status: 502,
        json: { error: { code: "tmdb_unavailable", message: "down", retryable: true }, request_id: "t" },
      },
    ]);
    renderWithClient(<SearchResults rawQuery="matrix" debouncedQuery="matrix" />);
    expect(await screen.findByText(/suche fehlgeschlagen/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /erneut versuchen/i })).toBeInTheDocument();
  });

  it("loads more pages on demand", async () => {
    const routes: Route[] = [
      {
        method: "GET",
        match: (url) => url.pathname === SEARCH && url.searchParams.get("page") === "1",
        json: searchPayload(1, [searchItem(1, "First")], 2),
      },
      {
        method: "GET",
        match: (url) => url.pathname === SEARCH && url.searchParams.get("page") === "2",
        json: searchPayload(2, [searchItem(2, "Second")], 2),
      },
    ];
    installFetch(routes);
    renderWithClient(<SearchResults rawQuery="matrix" debouncedQuery="matrix" />);
    expect(await screen.findByText("First")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /mehr laden/i }));
    await waitFor(() => expect(screen.getByText("Second")).toBeInTheDocument());
  });

  it("passes an AbortSignal so stale requests can be cancelled", async () => {
    const { calls } = installFetch([
      { method: "GET", match: pathIs(SEARCH), json: searchPayload(1, []) },
    ]);
    renderWithClient(<SearchResults rawQuery="matrix" debouncedQuery="matrix" />);
    await screen.findByText(/keine ergebnisse/i);
    const searchCall = calls.find((c) => c.url.pathname === SEARCH);
    expect(searchCall?.signal).toBeInstanceOf(AbortSignal);
  });
});
