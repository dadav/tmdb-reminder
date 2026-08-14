import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Footer } from "../src/components/Footer";
import { renderWithClient } from "./utils";

describe("Footer attribution", () => {
  it("shows the required TMDB notice (German + exact English sentence)", () => {
    renderWithClient(<Footer />);
    expect(
      screen.getByText(/not endorsed or certified by TMDB/i),
    ).toBeInTheDocument();
  });

  it("shows a JustWatch attribution linking to justwatch.com", () => {
    renderWithClient(<Footer />);
    const link = screen.getByRole("link", { name: "JustWatch" });
    expect(link).toHaveAttribute("href", "https://www.justwatch.com/");
    expect(screen.getByText(/bereitgestellt von/i)).toBeInTheDocument();
  });

  it("shows the English JustWatch attribution when in English", () => {
    renderWithClient(<Footer />, { language: "en" });
    expect(screen.getByText(/watch-provider availability data provided by/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "JustWatch" })).toBeInTheDocument();
  });
});
