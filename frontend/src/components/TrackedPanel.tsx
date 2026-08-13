import { useState } from "react";

import { useTracked } from "../api/queries";
import type { RelativeDateContext } from "../lib/format";
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
  dateLocale?: string;
  relativeDateContext?: RelativeDateContext;
}

export function TrackedPanel({
  view,
  title,
  emptyMessage,
  collapsible = false,
  dateLocale,
  relativeDateContext,
}: TrackedPanelProps) {
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(!collapsible);
  const query = useTracked(view, offset, LIMIT, open);

  const total = query.data?.total ?? 0;
  const items = query.data?.items ?? [];
  const hasPrev = offset > 0;
  const hasNext = offset + LIMIT < total;

  const content = (
    <>
      {query.isPending && <StateMessage tone="muted" title="Loading…" />}
      {query.isError && (
        <StateMessage
          tone="error"
          title="Could not load titles."
          action={
            <button type="button" onClick={() => void query.refetch()}>
              Retry
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
                dateLocale={dateLocale}
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
                Previous
              </button>
              <span className={styles.pageInfo}>
                {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
              </span>
              <button type="button" disabled={!hasNext} onClick={() => setOffset((o) => o + LIMIT)}>
                Next
              </button>
            </div>
          )}
        </>
      )}
    </>
  );

  if (collapsible) {
    return (
      <Section title={title} count={open ? total : undefined}>
        <details
          className={styles.details}
          onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}
        >
          <summary className={styles.summary}>{open ? "Hide history" : "Show history"}</summary>
          <div className={styles.detailsBody}>{content}</div>
        </details>
      </Section>
    );
  }

  return (
    <Section title={title} count={total}>
      {content}
    </Section>
  );
}
