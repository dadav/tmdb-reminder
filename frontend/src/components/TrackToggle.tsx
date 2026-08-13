import { useStopTitle, useTrackTitle } from "../api/queries";
import type { MediaType, TitleStatus } from "../api/types";
import { useI18n } from "../i18n/context";
import styles from "./TrackToggle.module.css";

interface TrackToggleProps {
  mediaType: MediaType;
  tmdbId: number;
  status: TitleStatus | null;
  availableSince?: string | null;
}

/** One button that tracks, stops, resumes, or removes a title. Both mutations
 *  disable the button while in flight so conflicting actions cannot overlap.
 *  An available completed movie offers "Remove" (the same soft-stop as "Stop"). */
export function TrackToggle({ mediaType, tmdbId, status, availableSince }: TrackToggleProps) {
  const { t } = useI18n();
  const track = useTrackTitle();
  const stop = useStopTitle();
  const busy = track.isPending || stop.isPending;
  const isActive = status === "active";
  const isAvailableCompleted = status === "completed" && availableSince != null;
  // Both branches soft-stop the title; only the button copy differs.
  const removes = isActive || isAvailableCompleted;

  const handleClick = () => {
    const vars = { mediaType, tmdbId };
    if (removes) {
      stop.mutate(vars);
    } else {
      track.mutate(vars);
    }
  };

  let label: string;
  if (isActive) {
    label = t("actions.stop");
  } else if (isAvailableCompleted) {
    label = t("actions.remove");
  } else if (status) {
    label = t("actions.resume");
  } else {
    label = t("actions.track");
  }

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.button}
        data-variant={removes ? "stop" : "track"}
        onClick={handleClick}
        disabled={busy}
      >
        {busy ? t("actions.working") : label}
      </button>
      {(track.isError || stop.isError) && (
        <span className={styles.error} role="alert">
          {t("actions.failed")}
        </span>
      )}
    </div>
  );
}
