import type { TitleView } from "../api/types";
import { useI18n } from "../i18n/context";
import { mediaReleaseLabel, statusLabel, type RelativeDateContext } from "../lib/format";
import type { Badge } from "./MediaCard";
import { MediaCard } from "./MediaCard";
import { TrackToggle } from "./TrackToggle";

export function TitleCard({
  title,
  relativeDateContext,
}: {
  title: TitleView;
  relativeDateContext?: RelativeDateContext;
}) {
  const { t, formatLocale } = useI18n();
  const badges: Badge[] = [{ label: statusLabel(title.status, t), tone: title.status }];
  if (title.last_sync_status === "error") {
    badges.push({ label: t("badge.syncError"), tone: "warning" });
  }

  return (
    <MediaCard
      posterUrl={title.poster_url}
      title={title.title}
      mediaType={title.media_type}
      year={title.release_year}
      overview={title.overview}
      tmdbUrl={title.tmdb_url}
      releaseLabel={mediaReleaseLabel(
        {
          mediaType: title.media_type,
          tracked: true,
          isAvailable: title.is_available,
          availableSince: title.available_since,
          nextRelease: title.next_release,
        },
        formatLocale,
        t,
        relativeDateContext,
      )}
      badges={badges}
      actions={
        <TrackToggle
          mediaType={title.media_type}
          tmdbId={title.tmdb_id}
          status={title.status}
          isAvailable={title.is_available}
        />
      }
    />
  );
}
