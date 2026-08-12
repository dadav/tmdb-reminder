import type { TitleView } from "../api/types";
import { nextReleaseLabel, statusLabel } from "../lib/format";
import type { Badge } from "./MediaCard";
import { MediaCard } from "./MediaCard";
import { TrackToggle } from "./TrackToggle";

export function TitleCard({ title }: { title: TitleView }) {
  const badges: Badge[] = [{ label: statusLabel(title.status), tone: title.status }];
  if (title.last_sync_status === "error") {
    badges.push({ label: "Sync error", tone: "warning" });
  }

  return (
    <MediaCard
      posterUrl={title.poster_url}
      title={title.title}
      mediaType={title.media_type}
      year={title.release_year}
      overview={title.overview}
      tmdbUrl={title.tmdb_url}
      releaseLabel={nextReleaseLabel(title.next_release)}
      badges={badges}
      actions={
        <TrackToggle mediaType={title.media_type} tmdbId={title.tmdb_id} status={title.status} />
      }
    />
  );
}
