import type { MediaType, NextRelease, TitleStatus } from "../api/types";

export function mediaTypeLabel(mediaType: MediaType): string {
  return mediaType === "tv" ? "TV" : "Movie";
}

export function statusLabel(status: TitleStatus): string {
  switch (status) {
    case "active":
      return "Tracking";
    case "completed":
      return "Completed";
    case "stopped":
      return "Stopped";
    default:
      return status;
  }
}

const CALENDAR_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  // Format in UTC: scheduled_date is a calendar date, and parsing/formatting in
  // the local zone would shift it across midnight for negative UTC offsets.
  timeZone: "UTC",
};

const MS_PER_DAY = 86_400_000;

function parseCalendarDate(isoDate: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    return null;
  }
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== isoDate) {
    return null;
  }
  return parsed;
}

function calendarDayInZone(now: Date, timeZone: string): Date | null {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now);
    const year = parts.find((p) => p.type === "year")?.value;
    const month = parts.find((p) => p.type === "month")?.value;
    const day = parts.find((p) => p.type === "day")?.value;
    if (!year || !month || !day) {
      return null;
    }
    return parseCalendarDate(`${year}-${month}-${day}`);
  } catch {
    // An invalid timezone or instant throws a RangeError.
    return null;
  }
}

/** Format a calendar date (YYYY-MM-DD) for display in the given locale.
 *  Falls back to the browser locale when `locale` is undefined or invalid, and
 *  returns the raw API value unchanged when the date cannot be parsed. */
export function formatCalendarDate(isoDate: string, locale?: string): string {
  const parsed = parseCalendarDate(isoDate);
  if (parsed === null) {
    return isoDate;
  }
  try {
    return new Intl.DateTimeFormat(locale, CALENDAR_DATE_OPTIONS).format(parsed);
  } catch {
    // An invalid configured locale throws a RangeError; retry with the browser locale.
    return new Intl.DateTimeFormat(undefined, CALENDAR_DATE_OPTIONS).format(parsed);
  }
}

export interface RelativeDateContext {
  now: Date;
  timeZone: string;
}

/** Differences count calendar days in APP_TIMEZONE, not elapsed 24-hour periods. */
export function relativeDayLabel(isoDate: string, context: RelativeDateContext): string | null {
  const target = parseCalendarDate(isoDate);
  if (target === null) {
    return null;
  }
  const today = calendarDayInZone(context.now, context.timeZone);
  if (today === null) {
    return null;
  }
  const diff = Math.round((target.getTime() - today.getTime()) / MS_PER_DAY);
  if (diff === 0) {
    return "today";
  }
  if (diff === 1) {
    return "in 1 day";
  }
  if (diff > 1) {
    return `in ${diff} days`;
  }
  if (diff === -1) {
    return "1 day ago";
  }
  return `${-diff} days ago`;
}

export function nextReleaseLabel(
  next: NextRelease | null | undefined,
  locale?: string,
  context?: RelativeDateContext,
): string {
  if (!next) {
    return "No date yet";
  }
  const date = formatCalendarDate(next.scheduled_date, locale);
  let base: string;
  if (next.kind === "tv_episode" && next.season_number != null && next.episode_number != null) {
    const s = String(next.season_number).padStart(2, "0");
    const e = String(next.episode_number).padStart(2, "0");
    base = `S${s}E${e} · ${date}`;
  } else {
    base = `Digital · ${date}`;
  }
  if (context) {
    const relative = relativeDayLabel(next.scheduled_date, context);
    if (relative !== null) {
      return `${base} · ${relative}`;
    }
  }
  return base;
}
