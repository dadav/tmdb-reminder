import type { MediaType, NextRelease, TitleStatus } from "../api/types";
import type { Translate } from "../i18n/context";

export function mediaTypeLabel(mediaType: MediaType, t: Translate): string {
  return t(mediaType === "tv" ? "media.tv" : "media.movie");
}

export function statusLabel(status: TitleStatus, t: Translate): string {
  // Known statuses are translated; unknown backend values remain visible as-is.
  return t(`status.${status}`, { defaultValue: status });
}

export function jobNameLabel(name: string, t: Translate): string {
  const keys: Record<string, string> = { refresh: "jobs.refresh", delivery: "jobs.delivery" };
  return keys[name] ? t(keys[name]) : t("jobs.unknown");
}

export function outcomeLabel(outcome: string | null | undefined, t: Translate): string {
  if (!outcome) {
    return t("outcomes.running");
  }
  const keys: Record<string, string> = {
    success: "outcomes.success",
    partial: "outcomes.partial",
    failure: "outcomes.failure",
  };
  return keys[outcome] ? t(keys[outcome]) : t("outcomes.unknown");
}

export function isKnownJobName(name: string): boolean {
  return name === "refresh" || name === "delivery";
}

export function isKnownOutcome(outcome: string | null | undefined): boolean {
  return outcome == null || outcome === "success" || outcome === "partial" || outcome === "failure";
}

/** Locale-aware number formatting with a deterministic raw fallback. */
export function formatNumber(value: number, formatLocale?: string): string {
  try {
    return new Intl.NumberFormat(formatLocale).format(value);
  } catch {
    return String(value);
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

/** Signed difference in calendar days (APP_TIMEZONE), not elapsed 24-hour
 *  periods. Null when either date is unparseable or the timezone is invalid. */
export function calendarDayDiff(isoDate: string, context: RelativeDateContext): number | null {
  const target = parseCalendarDate(isoDate);
  if (target === null) {
    return null;
  }
  const today = calendarDayInZone(context.now, context.timeZone);
  if (today === null) {
    return null;
  }
  return Math.round((target.getTime() - today.getTime()) / MS_PER_DAY);
}

/** Localized relative-day label with singular/plural forms, or null when the
 *  difference cannot be computed. */
export function relativeDayLabel(
  isoDate: string,
  context: RelativeDateContext,
  t: Translate,
): string | null {
  const diff = calendarDayDiff(isoDate, context);
  if (diff === null) {
    return null;
  }
  if (diff === 0) {
    return t("release.today");
  }
  if (diff > 0) {
    return t("release.inDays", { count: diff });
  }
  return t("release.daysAgo", { count: -diff });
}

export function nextReleaseLabel(
  next: NextRelease | null | undefined,
  formatLocale: string | undefined,
  t: Translate,
  context?: RelativeDateContext,
): string {
  if (!next) {
    return t("release.none");
  }
  const date = formatCalendarDate(next.scheduled_date, formatLocale);
  let base: string;
  if (next.kind === "tv_episode" && next.season_number != null && next.episode_number != null) {
    const s = String(next.season_number).padStart(2, "0");
    const e = String(next.episode_number).padStart(2, "0");
    base = `S${s}E${e} · ${date}`;
  } else {
    base = `${t("release.digital")} · ${date}`;
  }
  if (context) {
    const relative = relativeDayLabel(next.scheduled_date, context, t);
    if (relative !== null) {
      return `${base} · ${relative}`;
    }
  }
  return base;
}

/** Localized availability label for an already-available movie. `availableSince`
 *  is a historical (<= today) calendar date, so no relative-day suffix is added.
 *  Shows "Available today" when the date is the current day in the app timezone. */
export function availabilityLabel(
  availableSince: string,
  formatLocale: string | undefined,
  t: Translate,
  context?: RelativeDateContext,
): string {
  if (context && calendarDayDiff(availableSince, context) === 0) {
    return t("release.availableToday");
  }
  return t("release.availableSince", { date: formatCalendarDate(availableSince, formatLocale) });
}

/** Release label for a media card. Tracked movies show availability (or an
 *  "Availability unknown" placeholder when neither availability nor a future
 *  digital date is known); TV and untracked results keep the next-release copy. */
export function mediaReleaseLabel(
  params: {
    mediaType: MediaType;
    tracked: boolean;
    availableSince: string | null | undefined;
    nextRelease: NextRelease | null | undefined;
  },
  formatLocale: string | undefined,
  t: Translate,
  context?: RelativeDateContext,
): string {
  const { mediaType, tracked, availableSince, nextRelease } = params;
  if (mediaType === "movie" && tracked) {
    if (availableSince) {
      return availabilityLabel(availableSince, formatLocale, t, context);
    }
    if (!nextRelease) {
      return t("release.availabilityUnknown");
    }
  }
  return nextReleaseLabel(nextRelease, formatLocale, t, context);
}

/** Format a wall-clock HH:MM time (no timezone conversion) in the given locale.
 *  Returns the raw value unchanged when it is not a valid HH:MM string. */
export function formatReminderTime(hhmm: string, formatLocale?: string): string {
  const match = /^(\d{2}):(\d{2})$/.exec(hhmm);
  if (!match) {
    return hhmm;
  }
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) {
    return hhmm;
  }
  // Anchor to a fixed UTC instant and format in UTC so no zone shift occurs.
  // timeStyle lets the locale decide 12/24-hour and hour padding.
  const anchored = new Date(Date.UTC(2000, 0, 1, hour, minute));
  const options: Intl.DateTimeFormatOptions = {
    timeStyle: "short",
    timeZone: "UTC",
  };
  try {
    return new Intl.DateTimeFormat(formatLocale, options).format(anchored);
  } catch {
    return new Intl.DateTimeFormat(undefined, options).format(anchored);
  }
}

/** Format a diagnostic instant using the full locale and APP_TIMEZONE. Returns a
 *  localized "never" when empty, and the raw value when it cannot be parsed. */
export function formatInstant(
  value: string | null | undefined,
  formatLocale: string | undefined,
  timeZone: string | undefined,
  t: Translate,
): string {
  if (!value) {
    return t("diagnostics.never");
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const options: Intl.DateTimeFormatOptions = {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  };
  try {
    return new Intl.DateTimeFormat(formatLocale, options).format(parsed);
  } catch {
    // An invalid locale or timezone throws a RangeError; retry without them.
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
      parsed,
    );
  }
}
