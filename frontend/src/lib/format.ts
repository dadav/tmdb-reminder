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

/** Format a calendar date (YYYY-MM-DD) for display in the given locale.
 *  Falls back to the browser locale when `locale` is undefined or invalid, and
 *  returns the raw API value unchanged when the date cannot be parsed. */
export function formatCalendarDate(isoDate: string, locale?: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    return isoDate;
  }
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== isoDate) {
    return isoDate;
  }
  try {
    return new Intl.DateTimeFormat(locale, CALENDAR_DATE_OPTIONS).format(parsed);
  } catch {
    // An invalid configured locale throws a RangeError; retry with the browser locale.
    return new Intl.DateTimeFormat(undefined, CALENDAR_DATE_OPTIONS).format(parsed);
  }
}

export function nextReleaseLabel(
  next: NextRelease | null | undefined,
  locale?: string,
): string {
  if (!next) {
    return "No date yet";
  }
  const date = formatCalendarDate(next.scheduled_date, locale);
  if (next.kind === "tv_episode" && next.season_number != null && next.episode_number != null) {
    const s = String(next.season_number).padStart(2, "0");
    const e = String(next.episode_number).padStart(2, "0");
    return `S${s}E${e} · ${date}`;
  }
  return `Digital · ${date}`;
}
