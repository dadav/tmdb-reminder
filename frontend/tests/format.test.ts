import { describe, expect, it } from "vitest";

import type { NextRelease } from "../src/api/types";
import type { Translate } from "../src/i18n/context";
import { createI18n } from "../src/i18n/instance";
import {
  availabilityLabel,
  calendarDayDiff,
  formatCalendarDate,
  formatInstant,
  formatNumber,
  formatReminderTime,
  mediaReleaseLabel,
  nextReleaseLabel,
  relativeDayLabel,
} from "../src/lib/format";

function tFor(language: "en" | "de"): Translate {
  return createI18n(language).getFixedT(language) as Translate;
}

const de = tFor("de");
const en = tFor("en");

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

  it("falls back to the browser locale for an invalid configured locale", () => {
    expect(formatCalendarDate("2026-08-13", "invalid!")).toBe(formatCalendarDate("2026-08-13"));
  });
});

describe("nextReleaseLabel", () => {
  it("localizes a movie digital date in German", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-08-13" };
    expect(nextReleaseLabel(next, "de-DE", de)).toBe("Digital · 13.08.2026");
  });

  it("localizes a TV episode date", () => {
    const next: NextRelease = {
      kind: "tv_episode",
      scheduled_date: "2026-08-13",
      season_number: 1,
      episode_number: 2,
    };
    expect(nextReleaseLabel(next, "de-DE", de)).toBe("S01E02 · 13.08.2026");
  });

  it("returns a localized placeholder when there is no release", () => {
    expect(nextReleaseLabel(null, "de-DE", de)).toBe("Noch kein Datum");
    expect(nextReleaseLabel(null, "en-US", en)).toBe("No date yet");
  });

  it("appends a German relative label when a context is given", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-09-10" };
    const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Europe/Berlin" };
    expect(nextReleaseLabel(next, "de-DE", de, context)).toBe("Digital · 10.09.2026 · in 28 Tagen");
  });

  it("appends an English relative label when a context is given", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-09-10" };
    const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Europe/Berlin" };
    expect(nextReleaseLabel(next, "en-US", en, context)).toBe("Digital · 09/10/2026 · in 28 days");
  });

  it("omits the relative label for an invalid timezone", () => {
    const next: NextRelease = { kind: "movie_digital", scheduled_date: "2026-09-10" };
    const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Not/AZone" };
    expect(nextReleaseLabel(next, "de-DE", de, context)).toBe("Digital · 10.09.2026");
  });
});

describe("availabilityLabel", () => {
  const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Europe/Berlin" };

  it("labels the current day as available today (both languages)", () => {
    expect(availabilityLabel("2026-08-13", "de-DE", de, context)).toBe("Heute verfügbar");
    expect(availabilityLabel("2026-08-13", "en-US", en, context)).toBe("Available today");
  });

  it("labels a past date with the localized date and no relative suffix", () => {
    expect(availabilityLabel("2026-08-01", "de-DE", de, context)).toBe("Verfügbar seit 01.08.2026");
    expect(availabilityLabel("2026-08-01", "en-US", en, context)).toBe("Available since 08/01/2026");
  });
});

describe("mediaReleaseLabel", () => {
  const context = { now: new Date("2026-08-13T10:00:00Z"), timeZone: "Europe/Berlin" };
  const movie = (over: Partial<Parameters<typeof mediaReleaseLabel>[0]> = {}) => ({
    mediaType: "movie" as const,
    tracked: true,
    availableSince: null,
    nextRelease: null,
    ...over,
  });

  it("shows availability for an available tracked movie", () => {
    expect(mediaReleaseLabel(movie({ availableSince: "2026-08-01" }), "en-US", en, context)).toBe(
      "Available since 08/01/2026",
    );
  });

  it("prefers availability over a next release date", () => {
    const params = movie({
      availableSince: "2026-08-01",
      nextRelease: { kind: "movie_digital", scheduled_date: "2026-11-01" },
    });
    expect(mediaReleaseLabel(params, "de-DE", de, context)).toBe("Verfügbar seit 01.08.2026");
  });

  it("shows an unknown placeholder for a tracked movie with no date", () => {
    expect(mediaReleaseLabel(movie(), "de-DE", de, context)).toBe("Verfügbarkeit unbekannt");
    expect(mediaReleaseLabel(movie(), "en-US", en, context)).toBe("Availability unknown");
  });

  it("shows the future digital date for a tracked movie", () => {
    const params = movie({ nextRelease: { kind: "movie_digital", scheduled_date: "2026-09-10" } });
    expect(mediaReleaseLabel(params, "en-US", en, context)).toBe(
      "Digital · 09/10/2026 · in 28 days",
    );
  });

  it("keeps the next-release wording for TV", () => {
    const params = movie({
      mediaType: "tv",
      nextRelease: {
        kind: "tv_episode",
        scheduled_date: "2026-08-13",
        season_number: 1,
        episode_number: 2,
      },
    });
    expect(mediaReleaseLabel(params, "de-DE", de)).toBe("S01E02 · 13.08.2026");
  });

  it("keeps the untracked-movie placeholder", () => {
    expect(mediaReleaseLabel(movie({ tracked: false }), "de-DE", de)).toBe("Noch kein Datum");
  });
});

describe("relativeDayLabel", () => {
  const BERLIN = "Europe/Berlin";
  const now = new Date("2026-08-13T10:00:00Z");

  it("labels the same calendar day as today (both languages)", () => {
    expect(relativeDayLabel("2026-08-13", { now, timeZone: BERLIN }, de)).toBe("heute");
    expect(relativeDayLabel("2026-08-13", { now, timeZone: BERLIN }, en)).toBe("today");
  });

  it("labels a single future day in the singular", () => {
    expect(relativeDayLabel("2026-08-14", { now, timeZone: BERLIN }, de)).toBe("in 1 Tag");
    expect(relativeDayLabel("2026-08-14", { now, timeZone: BERLIN }, en)).toBe("in 1 day");
  });

  it("labels multiple future days in the plural", () => {
    expect(relativeDayLabel("2026-08-20", { now, timeZone: BERLIN }, de)).toBe("in 7 Tagen");
    expect(relativeDayLabel("2026-08-20", { now, timeZone: BERLIN }, en)).toBe("in 7 days");
  });

  it("labels a single past day in the singular", () => {
    expect(relativeDayLabel("2026-08-12", { now, timeZone: BERLIN }, de)).toBe("vor 1 Tag");
    expect(relativeDayLabel("2026-08-12", { now, timeZone: BERLIN }, en)).toBe("1 day ago");
  });

  it("labels multiple past days in the plural", () => {
    expect(relativeDayLabel("2026-08-06", { now, timeZone: BERLIN }, de)).toBe("vor 7 Tagen");
    expect(relativeDayLabel("2026-08-06", { now, timeZone: BERLIN }, en)).toBe("7 days ago");
  });

  it("counts calendar days in the app timezone, not 24-hour periods", () => {
    const late = new Date("2026-08-13T23:30:00Z");
    expect(relativeDayLabel("2026-08-14", { now: late, timeZone: BERLIN }, de)).toBe("heute");
    expect(relativeDayLabel("2026-08-14", { now: late, timeZone: "UTC" }, de)).toBe("in 1 Tag");
  });

  it("returns null for a malformed date", () => {
    expect(relativeDayLabel("not-a-date", { now, timeZone: BERLIN }, de)).toBeNull();
  });

  it("returns null for an invalid timezone", () => {
    expect(relativeDayLabel("2026-08-14", { now, timeZone: "Not/AZone" }, de)).toBeNull();
  });
});

describe("calendarDayDiff", () => {
  const now = new Date("2026-08-13T10:00:00Z");
  it("returns a signed calendar-day difference", () => {
    expect(calendarDayDiff("2026-08-20", { now, timeZone: "Europe/Berlin" })).toBe(7);
    expect(calendarDayDiff("2026-08-06", { now, timeZone: "Europe/Berlin" })).toBe(-7);
  });
  it("returns null for invalid inputs", () => {
    expect(calendarDayDiff("nope", { now, timeZone: "Europe/Berlin" })).toBeNull();
  });
});

describe("formatReminderTime", () => {
  it("formats a 24-hour wall clock for German without timezone shift", () => {
    expect(formatReminderTime("09:00", "de-DE")).toBe("09:00");
  });

  it("formats a 12-hour wall clock for US English", () => {
    expect(formatReminderTime("09:00", "en-US")).toBe("9:00 AM");
  });

  it("returns the raw value for malformed or impossible times", () => {
    expect(formatReminderTime("nope", "de-DE")).toBe("nope");
    expect(formatReminderTime("25:00", "de-DE")).toBe("25:00");
  });
});

describe("formatNumber", () => {
  it("uses the complete regional locale", () => {
    expect(formatNumber(1234567, "de-DE")).toBe("1.234.567");
    expect(formatNumber(1234567, "en-US")).toBe("1,234,567");
  });

  it("falls back to the raw value for an invalid locale", () => {
    expect(formatNumber(1234, "invalid!")).toBe("1234");
  });
});

describe("formatInstant", () => {
  it("returns a localized 'never' when empty", () => {
    expect(formatInstant(null, "de-DE", "Europe/Berlin", de)).toBe("nie");
    expect(formatInstant(undefined, "en-US", "Europe/Berlin", en)).toBe("never");
  });

  it("formats an instant in the configured locale and timezone", () => {
    // 07:00 UTC is 09:00 in Europe/Berlin (CEST) in August.
    const value = "2026-08-12T07:00:00Z";
    expect(formatInstant(value, "de-DE", "Europe/Berlin", de)).toContain("09:00");
    expect(formatInstant(value, "de-DE", "UTC", de)).toContain("07:00");
  });

  it("returns the raw value for an unparseable instant", () => {
    expect(formatInstant("not-a-date", "de-DE", "Europe/Berlin", de)).toBe("not-a-date");
  });
});
