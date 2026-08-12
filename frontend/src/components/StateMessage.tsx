import type { ReactNode } from "react";

import styles from "./StateMessage.module.css";

type Tone = "info" | "muted" | "error" | "warning";

interface StateMessageProps {
  tone?: Tone;
  title: string;
  detail?: ReactNode;
  action?: ReactNode;
}

/** Explicit empty / loading / degraded / error placeholder used across panels. */
export function StateMessage({ tone = "muted", title, detail, action }: StateMessageProps) {
  return (
    <div className={styles.wrap} data-tone={tone} role="status">
      <p className={styles.title}>{title}</p>
      {detail && <p className={styles.detail}>{detail}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
