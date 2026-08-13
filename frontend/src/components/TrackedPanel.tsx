import { useState } from "react";

import { useTracked } from "../api/queries";
import { useI18n } from "../i18n/context";
import { formatNumber, type RelativeDateContext } from "../lib/format";
import { Section } from "./Section";
import { StateMessage } from "./StateMessage";
import { TitleCard } from "./TitleCard";
import styles from "./TrackedPanel.module.css";

const LIMIT = 20;

interface TrackedPanelProps {
  view: "active" | "history";
  title: string;
  emptyMessage: string;
  collapsible?: boolean;
  relativeDateContext?: RelativeDateContext;
}

export function TrackedPanel({
  view,
  title,
  emptyMessage,
  collapsible = false,
  relativeDateContext,
}: TrackedPanelProps) {
  const { t, formatLocale } = useI18n();
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(!collapsible);
  const query = useTracked(view, offset, LIMIT, open);

  const total = query.data?.total ?? 0;
  const items = query.data?.items ?? [];
  const hasPrev = offset > 0;
  const hasNext = offset + LIMIT < total;

  const content = (
    <>
      {query.isPending && <StateMessage tone="muted" title={t("tracking.loading")} />}
      {query.isError && (
        <StateMessage
          tone="error"
          title={t("tracking.loadFailed")}
          action={
            <button type="button" onClick={() => void query.refetch()}>
              {t("actions.retry")}
            </button>
          }
        />
      )}
      {query.isSuccess && items.length === 0 && <StateMessage tone="muted" title={emptyMessage} />}
      {items.length > 0 && (
        <>
          <div className={styles.grid}>
            {items.map((item) => (
              <TitleCard
                key={item.id}
                title={item}
                relativeDateContext={relativeDateContext}
              />
            ))}
          </div>
          {(hasPrev || hasNext) && (
            <div className={styles.pager}>
              <button
                type="button"
                disabled={!hasPrev}
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
              >
                {t("pagination.previous")}
              </button>
              <span className={styles.pageInfo}>
                {t("pagination.pageInfo", {
                  from: formatNumber(offset + 1, formatLocale),
                  to: formatNumber(Math.min(offset + LIMIT, total), formatLocale),
                  total: formatNumber(total, formatLocale),
                })}
              </span>
              <button type="button" disabled={!hasNext} onClick={() => setOffset((o) => o + LIMIT)}>
                {t("pagination.next")}
              </button>
            </div>
          )}
        </>
      )}
    </>
  );

  if (collapsible) {
    return (
      <Section title={title} count={open ? formatNumber(total, formatLocale) : undefined}>
        <details
          className={styles.details}
          onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}
        >
          <summary className={styles.summary}>
            {open ? t("tracking.hideHistory") : t("tracking.showHistory")}
          </summary>
          <div className={styles.detailsBody}>{content}</div>
        </details>
      </Section>
    );
  }

  return (
    <Section title={title} count={formatNumber(total, formatLocale)}>
      {content}
    </Section>
  );
}
