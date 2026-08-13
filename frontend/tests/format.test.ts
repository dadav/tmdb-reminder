import { describe, expect, it } from "vitest";

import type { NextRelease } from "../src/api/types";
import { formatCalendarDate, nextReleaseLabel, relativeDayLabel } from "../src/lib/format";

describe("formatCalendarDate", () => {
  it("formats German dates as DD.MM.YYYY", () => {
    expect(formatCalendarDate("2026-08-13", "de-DE")).toBe("13.08.2026");
  });

  it("formats US dates as MM/DD/YYYY", () => {
    expect(formatCalendarDate("2026-08-13", "en-US")).toBe("08/13/2026");
  });

  it("preserves the raw API value for malformed dates", () => {
    expect(formatCalendarDate("not-a-date", "de-DE")).toBe("not-a-date");
  });

  it("preserves impossible calendar dates", () => {
    expect(formatCalendarDate("2026-02-30", "de-DE")).toBe("2026-02-30");
  });

  it("preserves noncanonical date strings", () => {
    expect(formatCalendarDate("2026-08-13T00:00:00Z", "de-DE")).toBe(
      "2026-08-13T00:00:00Z",
    );
  });

  it("falls back to the browser locale for an invalid configured locale", () => {
    expect(formatCalendarDate("2026-08-13", "invalid!")).toBe(formatCalendarDate("2026-08-13"));
  });
});

describe("nextReleaseLabel", () => {
  it("localizes a movie digital date", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-08-13" };
    expect(nextReleaseLabel(next, "de-DE")).toBe("Digital · 13.08.2026");
  });

  it("localizes a TV episode date", () => {
    const next: NextRelease = {
      kind: "tv_episode",
      scheduled_date: "2026-08-13",
      season_number: 1,
      episode_number: 2,
    };
    expect(nextReleaseLabel(next, "de-DE")).toBe("S01E02 · 13.08.2026");
  });

  it("returns a placeholder when there is no release", () => {
    expect(nextReleaseLabel(null, "de-DE")).toBe("No date yet");
  });

  it("appends a relative label when a context is given", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-09-10" };
    const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Europe/Berlin" };
    expect(nextReleaseLabel(next, "de-DE", context)).toBe("Digital · 10.09.2026 · in 28 days");
  });

  it("appends a relative label for TV episodes", () => {
    const next: NextRelease = {
      kind: "tv_episode",
      scheduled_date: "2026-08-13",
      season_number: 1,
      episode_number: 2,
    };
    const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Europe/Berlin" };
    expect(nextReleaseLabel(next, "de-DE", context)).toBe("S01E02 · 13.08.2026 · today");
  });

  it("omits the relative label for an invalid timezone", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-09-10" };
    const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Not/AZone" };
    expect(nextReleaseLabel(next, "de-DE", context)).toBe("Digital · 10.09.2026");
  });

  it("omits the relative label without a context", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-09-10" };
    expect(nextReleaseLabel(next, "de-DE")).toBe("Digital · 10.09.2026");
  });
});

describe("relativeDayLabel", () => {
  const BERLIN = "Europe/Berlin";
  const now = new Date("2026-08-13T10:00:00Z");

  it("labels the same calendar day as today", () => {
    expect(relativeDayLabel("2026-08-13", { now, timeZone: BERLIN })).toBe("today");
  });

  it("labels a single future day in the singular", () => {
    expect(relativeDayLabel("2026-08-14", { now, timeZone: BERLIN })).toBe("in 1 day");
  });

  it("labels multiple future days in the plural", () => {
    expect(relativeDayLabel("2026-08-20", { now, timeZone: BERLIN })).toBe("in 7 days");
  });

  it("labels a single past day in the singular", () => {
    expect(relativeDayLabel("2026-08-12", { now, timeZone: BERLIN })).toBe("1 day ago");
  });

  it("labels multiple past days in the plural", () => {
    expect(relativeDayLabel("2026-08-06", { now, timeZone: BERLIN })).toBe("7 days ago");
  });

  it("counts calendar days in the app timezone, not 24-hour periods", () => {
    const late = new Date("2026-08-13T23:30:00Z");
    expect(relativeDayLabel("2026-08-14", { now: late, timeZone: BERLIN })).toBe("today");
    expect(relativeDayLabel("2026-08-14", { now: late, timeZone: "UTC" })).toBe("in 1 day");
  });

  it("treats any time on the target calendar day as today", () => {
    const early = new Date("2026-08-12T23:30:00Z");
    expect(relativeDayLabel("2026-08-13", { now: early, timeZone: BERLIN })).toBe("today");
  });

  it("returns null for a malformed date", () => {
    expect(relativeDayLabel("not-a-date", { now, timeZone: BERLIN })).toBeNull();
  });

  it("returns null for an impossible calendar date", () => {
    expect(relativeDayLabel("2026-02-30", { now, timeZone: BERLIN })).toBeNull();
  });

  it("returns null for an invalid timezone", () => {
    expect(relativeDayLabel("2026-08-14", { now, timeZone: "Not/AZone" })).toBeNull();
  });
});
