import type { ReactNode } from "react";

import type { MediaType } from "../api/types";
import { useI18n } from "../i18n/context";
import { mediaTypeLabel } from "../lib/format";
import styles from "./MediaCard.module.css";
import { Poster } from "./Poster";

export interface Badge {
  label: string;
  tone: "neutral" | "active" | "completed" | "stopped" | "warning";
}

interface MediaCardProps {
  posterUrl: string | null | undefined;
  title: string;
  mediaType: MediaType;
  year: number | null | undefined;
  overview: string | null | undefined;
  tmdbUrl: string;
  releaseLabel: string;
  badges?: Badge[];
  actions?: ReactNode;
}

export function MediaCard({
  posterUrl,
  title,
  mediaType,
  year,
  overview,
  tmdbUrl,
  releaseLabel,
  badges = [],
  actions,
}: MediaCardProps) {
  const { t } = useI18n();
  return (
    <article className={styles.card}>
      <Poster url={posterUrl} title={title} />
      <div className={styles.body}>
        <div className={styles.headline}>
          <h3 className={styles.title}>{title}</h3>
          <div className={styles.badges}>
            {badges.map((badge) => (
              <span key={badge.label} className={styles.badge} data-tone={badge.tone}>
                {badge.label}
              </span>
            ))}
          </div>
        </div>
        <p className={styles.meta}>
          {mediaTypeLabel(mediaType, t)}
          {year ? ` · ${year}` : ""} · {releaseLabel}
        </p>
        {overview && <p className={styles.overview}>{overview}</p>}
        <div className={styles.footer}>
          <a href={tmdbUrl} target="_blank" rel="noreferrer noopener" className={styles.link}>
            {t("card.viewOnTmdb")}
          </a>
          {actions}
        </div>
      </div>
    </article>
  );
}
