import { useEffect, useMemo, useState } from "react";

import { useStatus } from "./api/queries";
import styles from "./App.module.css";
import { Diagnostics } from "./components/Diagnostics";
import { Footer } from "./components/Footer";
import { SearchBar } from "./components/SearchBar";
import { SearchResults } from "./components/SearchResults";
import { TrackedPanel } from "./components/TrackedPanel";
import { useDebouncedValue } from "./hooks/useDebouncedValue";
import { useI18n } from "./i18n/context";
import { LocaleProvider } from "./i18n/LocaleProvider";
import type { RelativeDateContext } from "./lib/format";
import { browserLanguages, resolveBrowserLocale, resolveLocale } from "./lib/locale";

const SEARCH_DEBOUNCE_MS = 350;
const NOW_REFRESH_MS = 60_000;

/** Bootstraps localization: the browser locale seeds the shell, then
 *  TMDB_LANGUAGE from status becomes authoritative once it loads. */
export function Root() {
  const status = useStatus();
  const locale = useMemo(
    () =>
      status.data
        ? resolveLocale(status.data.config.tmdb_language)
        : resolveBrowserLocale(browserLanguages()),
    [status.data],
  );
  return (
    <LocaleProvider locale={locale}>
      <App />
    </LocaleProvider>
  );
}

export function App() {
  const { t } = useI18n();
  const status = useStatus();
  const timeZone = status.data?.config.app_timezone;

  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), NOW_REFRESH_MS);
    return () => clearInterval(id);
  }, []);
  const relativeDateContext: RelativeDateContext | undefined = timeZone
    ? { now, timeZone }
    : undefined;

  const [rawQuery, setRawQuery] = useState("");
  const debouncedQuery = useDebouncedValue(rawQuery, SEARCH_DEBOUNCE_MS);

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.brand}>{t("app.brand")}</h1>
        <p className={styles.tagline}>{t("app.tagline")}</p>
      </header>

      <main className={styles.main}>
        <SearchBar value={rawQuery} onChange={setRawQuery} />
        <SearchResults
          rawQuery={rawQuery}
          debouncedQuery={debouncedQuery}
          relativeDateContext={relativeDateContext}
        />
        <TrackedPanel
          view="active"
          title={t("tracking.activeSection")}
          emptyMessage={t("tracking.activeEmpty")}
          relativeDateContext={relativeDateContext}
        />
        <TrackedPanel
          view="history"
          title={t("tracking.historySection")}
          emptyMessage={t("tracking.historyEmpty")}
          collapsible
          relativeDateContext={relativeDateContext}
        />
        <Diagnostics />
      </main>

      <Footer />
    </div>
  );
}
