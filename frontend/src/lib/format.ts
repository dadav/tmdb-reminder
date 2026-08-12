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

export function nextReleaseLabel(next: NextRelease | null | undefined): string {
  if (!next) {
    return "No date yet";
  }
  if (next.kind === "tv_episode" && next.season_number != null && next.episode_number != null) {
    const s = String(next.season_number).padStart(2, "0");
    const e = String(next.episode_number).padStart(2, "0");
    return `S${s}E${e} · ${next.scheduled_date}`;
  }
  return `Digital · ${next.scheduled_date}`;
}
