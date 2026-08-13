import { MIN_QUERY_LENGTH, useSearch } from "../api/queries";
import { useI18n } from "../i18n/context";
import type { RelativeDateContext } from "../lib/format";
import { ResultCard } from "./ResultCard";
import styles from "./SearchResults.module.css";
import { Section } from "./Section";
import { StateMessage } from "./StateMessage";

interface SearchResultsProps {
  rawQuery: string;
  debouncedQuery: string;
  relativeDateContext?: RelativeDateContext;
}

export function SearchResults({
  rawQuery,
  debouncedQuery,
  relativeDateContext,
}: SearchResultsProps) {
  const { t } = useI18n();
  const search = useSearch(debouncedQuery);
  const trimmed = debouncedQuery.trim();
  const results = search.data?.pages.flatMap((page) => page.results) ?? [];
  const degraded = search.data?.pages.some((page) => page.degraded) ?? false;

  const tooShort = rawQuery.trim().length > 0 && rawQuery.trim().length < MIN_QUERY_LENGTH;

  return (
    <Section title={t("search.section")}>
      {tooShort && (
        <StateMessage tone="info" title={t("search.tooShort", { min: MIN_QUERY_LENGTH })} />
      )}

      {trimmed.length < MIN_QUERY_LENGTH && !tooShort && (
        <StateMessage tone="muted" title={t("search.emptyTitle")} detail={t("search.emptyDetail")} />
      )}

      {trimmed.length >= MIN_QUERY_LENGTH && search.isPending && (
        <StateMessage tone="muted" title={t("search.searching")} />
      )}

      {search.isError && (
        <StateMessage
          tone="error"
          title={t("search.failedTitle")}
          detail={t("search.failedDetail")}
          action={
            <button type="button" onClick={() => void search.refetch()}>
              {t("actions.retry")}
            </button>
          }
        />
      )}

      {degraded && (
        <StateMessage
          tone="warning"
          title={t("search.degradedTitle")}
          detail={t("search.degradedDetail")}
        />
      )}

      {search.isSuccess && !degraded && results.length === 0 && (
        <StateMessage
          tone="muted"
          title={t("search.noResultsTitle")}
          detail={t("search.noResultsDetail", { query: trimmed })}
        />
      )}

      {results.length > 0 && (
        <>
          <div className={styles.grid}>
            {results.map((item) => (
              <ResultCard
                key={`${item.media_type}-${item.tmdb_id}`}
                item={item}
                relativeDateContext={relativeDateContext}
              />
            ))}
          </div>
          {search.hasNextPage && (
            <button
              type="button"
              className={styles.loadMore}
              onClick={() => void search.fetchNextPage()}
              disabled={search.isFetchingNextPage}
            >
              {search.isFetchingNextPage ? t("search.loadingMore") : t("search.loadMore")}
            </button>
          )}
        </>
      )}
    </Section>
  );
}
