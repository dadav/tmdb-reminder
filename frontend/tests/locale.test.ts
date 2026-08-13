import { describe, expect, it } from "vitest";

import { resolveBrowserLocale, resolveLocale } from "../src/lib/locale";

describe("resolveLocale (server authority)", () => {
  it("resolves exact supported tags and retains the regional tag for formatting", () => {
    expect(resolveLocale("en-US")).toEqual({ language: "en", formatLocale: "en-US" });
    expect(resolveLocale("de-DE")).toEqual({ language: "de", formatLocale: "de-DE" });
  });

  it("maps regional variants to their base catalog while keeping the full tag", () => {
    expect(resolveLocale("de-AT")).toEqual({ language: "de", formatLocale: "de-AT" });
    expect(resolveLocale("en-GB")).toEqual({ language: "en", formatLocale: "en-GB" });
  });

  it("canonicalizes casing", () => {
    expect(resolveLocale("de-de")).toEqual({ language: "de", formatLocale: "de-DE" });
  });

  it("accepts a bare base language", () => {
    expect(resolveLocale("de")).toEqual({ language: "de", formatLocale: "de" });
  });

  it("falls back to English with en-US formatting for unsupported languages", () => {
    expect(resolveLocale("fr-FR")).toEqual({ language: "en", formatLocale: "en-US" });
    expect(resolveLocale("ja")).toEqual({ language: "en", formatLocale: "en-US" });
  });

  it("falls back to English for invalid or empty tags", () => {
    expect(resolveLocale("invalid!")).toEqual({ language: "en", formatLocale: "en-US" });
    expect(resolveLocale("")).toEqual({ language: "en", formatLocale: "en-US" });
    expect(resolveLocale(undefined)).toEqual({ language: "en", formatLocale: "en-US" });
    expect(resolveLocale(null)).toEqual({ language: "en", formatLocale: "en-US" });
  });
});

describe("resolveBrowserLocale (bootstrap)", () => {
  it("picks the first supported browser candidate", () => {
    expect(resolveBrowserLocale(["fr-FR", "de-DE", "en-US"])).toEqual({
      language: "de",
      formatLocale: "de-DE",
    });
  });

  it("skips unsupported and invalid candidates", () => {
    expect(resolveBrowserLocale(["ja-JP", "invalid!", "en-GB"])).toEqual({
      language: "en",
      formatLocale: "en-GB",
    });
  });

  it("falls back to English en-US when no candidate is supported", () => {
    expect(resolveBrowserLocale(["fr-FR", "ja-JP"])).toEqual({
      language: "en",
      formatLocale: "en-US",
    });
    expect(resolveBrowserLocale([])).toEqual({ language: "en", formatLocale: "en-US" });
  });
});
