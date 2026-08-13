import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrackedPanel } from "../src/components/TrackedPanel";
import { installFetch, renderWithClient } from "./utils";

describe("TrackedPanel localization", () => {
  it("localizes poster accessibility and pagination with formatted counts", async () => {
    installFetch([
      {
        method: "GET",
        match: (url) => url.pathname === "/api/v1/tracked-titles",
        json: {
          items: [
            {
              id: 1,
              media_type: "movie",
              tmdb_id: 603,
              title: "The Matrix",
              overview: null,
              poster_url: null,
              release_year: 2026,
              status: "active",
              tmdb_url: "https://www.themoviedb.org/movie/603",
              next_release: null,
              last_sync_status: "ok",
              updated_at: "2026-08-12T00:00:00Z",
            },
          ],
          view: "active",
          offset: 0,
          limit: 20,
          total: 1234,
        },
      },
    ]);

    renderWithClient(
      <TrackedPanel view="active" title="Merkliste" emptyMessage="Noch nichts gemerkt." />,
    );

    expect(
      await screen.findByRole("img", { name: "Poster von The Matrix (kein Poster verfügbar)" }),
    ).toHaveTextContent("Kein Poster");
    expect(screen.getByRole("button", { name: "Zurück" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Weiter" })).toBeEnabled();
    expect(screen.getByText("1–20 von 1.234")).toBeInTheDocument();
  });
});
