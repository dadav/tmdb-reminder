import { useEffect, useState } from "react";

import { useStatus } from "./api/queries";
import styles from "./App.module.css";
import { Diagnostics } from "./components/Diagnostics";
import { Footer } from "./components/Footer";
import { SearchBar } from "./components/SearchBar";
import { SearchResults } from "./components/SearchResults";
import { TrackedPanel } from "./components/TrackedPanel";
import { useDebouncedValue } from "./hooks/useDebouncedValue";
import type { RelativeDateContext } from "./lib/format";

const SEARCH_DEBOUNCE_MS = 350;
const NOW_REFRESH_MS = 60_000;

export function App() {
  const [rawQuery, setRawQuery] = useState("");
  const debouncedQuery = useDebouncedValue(rawQuery, SEARCH_DEBOUNCE_MS);
  const status = useStatus();
  // Undefined until status loads; Intl then falls back to the browser locale.
  const dateLocale = status.data?.config.tmdb_language;
  const timeZone = status.data?.config.app_timezone;

  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), NOW_REFRESH_MS);
    return () => clearInterval(id);
  }, []);
  const relativeDateContext: RelativeDateContext | undefined = timeZone
    ? { now, timeZone }
    : undefined;

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.brand}>TMDB Reminder</h1>
        <p className={styles.tagline}>
          Track movies and TV shows and get a Gotify reminder the day before release.
        </p>
      </header>

      <main className={styles.main}>
        <SearchBar value={rawQuery} onChange={setRawQuery} />
        <SearchResults
          rawQuery={rawQuery}
          debouncedQuery={debouncedQuery}
          dateLocale={dateLocale}
          relativeDateContext={relativeDateContext}
        />
        <TrackedPanel
          view="active"
          title="Tracking"
          emptyMessage="Nothing tracked yet."
          dateLocale={dateLocale}
          relativeDateContext={relativeDateContext}
        />
        <TrackedPanel
          view="history"
          title="History"
          emptyMessage="No stopped or completed titles."
          collapsible
          dateLocale={dateLocale}
          relativeDateContext={relativeDateContext}
        />
        <Diagnostics />
      </main>

      <Footer />
    </div>
  );
}
