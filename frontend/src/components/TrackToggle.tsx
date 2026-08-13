import { useStopTitle, useTrackTitle } from "../api/queries";
import type { MediaType, TitleStatus } from "../api/types";
import { useI18n } from "../i18n/context";
import styles from "./TrackToggle.module.css";

interface TrackToggleProps {
  mediaType: MediaType;
  tmdbId: number;
  status: TitleStatus | null;
}

/** One button that tracks, stops, or resumes a title. Both mutations disable the
 *  button while in flight so conflicting actions cannot overlap. */
export function TrackToggle({ mediaType, tmdbId, status }: TrackToggleProps) {
  const { t } = useI18n();
  const track = useTrackTitle();
  const stop = useStopTitle();
  const busy = track.isPending || stop.isPending;
  const isActive = status === "active";

  const handleClick = () => {
    const vars = { mediaType, tmdbId };
    if (isActive) {
      stop.mutate(vars);
    } else {
      track.mutate(vars);
    }
  };

  const label = isActive ? t("actions.stop") : status ? t("actions.resume") : t("actions.track");

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.button}
        data-variant={isActive ? "stop" : "track"}
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
