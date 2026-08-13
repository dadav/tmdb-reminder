import type { SearchResultItem } from "../api/types";
import { useI18n } from "../i18n/context";
import { nextReleaseLabel, statusLabel, type RelativeDateContext } from "../lib/format";
import type { Badge } from "./MediaCard";
import { MediaCard } from "./MediaCard";
import { TrackToggle } from "./TrackToggle";

export function ResultCard({
  item,
  relativeDateContext,
}: {
  item: SearchResultItem;
  relativeDateContext?: RelativeDateContext;
}) {
  const { t, formatLocale } = useI18n();
  const badges: Badge[] = item.tracking_status
    ? [{ label: statusLabel(item.tracking_status, t), tone: item.tracking_status }]
    : [];

  return (
    <MediaCard
      posterUrl={item.poster_url}
      title={item.title}
      mediaType={item.media_type}
      year={item.release_year}
      overview={item.overview}
      tmdbUrl={item.tmdb_url}
      releaseLabel={nextReleaseLabel(item.next_release, formatLocale, t, relativeDateContext)}
      badges={badges}
      actions={
        <TrackToggle
          mediaType={item.media_type}
          tmdbId={item.tmdb_id}
          status={item.tracking_status ?? null}
        />
      }
    />
  );
}
