import { useState } from "react";

import { useI18n } from "../i18n/context";
import styles from "./Poster.module.css";

interface PosterProps {
  url: string | null | undefined;
  title: string;
}

/** Poster image with an explicit fallback for missing or broken images. */
export function Poster({ url, title }: PosterProps) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    return (
      <div className={styles.fallback} role="img" aria-label={t("card.posterFallbackAlt", { title })}>
        {t("card.posterFallback")}
      </div>
    );
  }

  return (
    <img
      className={styles.image}
      src={url}
      alt={t("card.posterAlt", { title })}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
