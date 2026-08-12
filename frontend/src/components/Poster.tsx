import { useState } from "react";

import styles from "./Poster.module.css";

interface PosterProps {
  url: string | null | undefined;
  alt: string;
}

/** Poster image with an explicit fallback for missing or broken images. */
export function Poster({ url, alt }: PosterProps) {
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    return (
      <div className={styles.fallback} role="img" aria-label={`${alt} (no poster available)`}>
        No poster
      </div>
    );
  }

  return (
    <img
      className={styles.image}
      src={url}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
