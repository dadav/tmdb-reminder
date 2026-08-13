import { MIN_QUERY_LENGTH, useSearch } from "../api/queries";
import { ResultCard } from "./ResultCard";
import styles from "./SearchResults.module.css";
import { Section } from "./Section";
import { StateMessage } from "./StateMessage";

interface SearchResultsProps {
  rawQuery: string;
  debouncedQuery: string;
  dateLocale?: string;
}

export function SearchResults({ rawQuery, debouncedQuery, dateLocale }: SearchResultsProps) {
  const search = useSearch(debouncedQuery);
  const trimmed = debouncedQuery.trim();
  const results = search.data?.pages.flatMap((page) => page.results) ?? [];
  const degraded = search.data?.pages.some((page) => page.degraded) ?? false;

  const tooShort = rawQuery.trim().length > 0 && rawQuery.trim().length < MIN_QUERY_LENGTH;

  return (
    <Section title="Search">
      {tooShort && (
        <StateMessage tone="info" title={`Type at least ${MIN_QUERY_LENGTH} characters to search.`} />
      )}

      {trimmed.length < MIN_QUERY_LENGTH && !tooShort && (
        <StateMessage
          tone="muted"
          title="Find something to track"
          detail="Search TMDB for a movie or TV show, then start tracking it."
        />
      )}

      {trimmed.length >= MIN_QUERY_LENGTH && search.isPending && (
        <StateMessage tone="muted" title="Searching…" />
      )}

      {search.isError && (
        <StateMessage
          tone="error"
          title="Search failed."
          detail="TMDB might be unavailable."
          action={
            <button type="button" onClick={() => void search.refetch()}>
              Retry
            </button>
          }
        />
      )}

      {degraded && (
        <StateMessage
          tone="warning"
          title="Search is unavailable."
          detail="TMDB credentials are not configured on the server."
        />
      )}

      {search.isSuccess && !degraded && results.length === 0 && (
        <StateMessage tone="muted" title="No results." detail={`Nothing matched “${trimmed}”.`} />
      )}

      {results.length > 0 && (
        <>
          <div className={styles.grid}>
            {results.map((item) => (
              <ResultCard
                key={`${item.media_type}-${item.tmdb_id}`}
                item={item}
                dateLocale={dateLocale}
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
              {search.isFetchingNextPage ? "Loading…" : "Load more"}
            </button>
          )}
        </>
      )}
    </Section>
  );
}
