import { describe, expect, it } from "vitest";

import type { NextRelease } from "../src/api/types";
import { formatCalendarDate, nextReleaseLabel } from "../src/lib/format";

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
});
