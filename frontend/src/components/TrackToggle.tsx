import { useStopTitle, useTrackTitle } from "../api/queries";
import type { MediaType, TitleStatus } from "../api/types";
import styles from "./TrackToggle.module.css";

interface TrackToggleProps {
  mediaType: MediaType;
  tmdbId: number;
  status: TitleStatus | null;
}

/** One button that tracks, stops, or resumes a title. Both mutations disable the
 *  button while in flight so conflicting actions cannot overlap. */
export function TrackToggle({ mediaType, tmdbId, status }: TrackToggleProps) {
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

  const label = isActive ? "Stop" : status ? "Resume" : "Track";

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.button}
        data-variant={isActive ? "stop" : "track"}
        onClick={handleClick}
        disabled={busy}
      >
        {busy ? "Working…" : label}
      </button>
      {(track.isError || stop.isError) && (
        <span className={styles.error} role="alert">
          Action failed. Try again.
        </span>
      )}
    </div>
  );
}
