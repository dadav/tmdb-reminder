import type { ReactNode } from "react";

import styles from "./Section.module.css";

interface SectionProps {
  title: string;
  count?: ReactNode;
  children: ReactNode;
  headerExtra?: ReactNode;
}

export function Section({ title, count, children, headerExtra }: SectionProps) {
  return (
    <section className={styles.section} aria-label={title}>
      <header className={styles.header}>
        <h2 className={styles.title}>
          {title}
          {count != null && <span className={styles.count}>{count}</span>}
        </h2>
        {headerExtra}
      </header>
      {children}
    </section>
  );
}
