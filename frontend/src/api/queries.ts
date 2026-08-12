import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { client, unwrap } from "./client";
import type {
  GotifyTestResponse,
  MediaType,
  SearchResponse,
  StatusResponse,
  TitleView,
  TrackedListResponse,
} from "./types";

export const MIN_QUERY_LENGTH = 2;

export const queryKeys = {
  search: (query: string) => ["search", query] as const,
  tracked: (view: "active" | "history", offset: number) => ["tracked", view, offset] as const,
  status: () => ["status"] as const,
};

/** Search TMDB with cursor pagination ("load more"). Disabled until the query
 *  reaches the minimum length; stale in-flight requests are aborted via the
 *  query's AbortSignal. */
export function useSearch(query: string) {
  const trimmed = query.trim();
  return useInfiniteQuery({
    queryKey: queryKeys.search(trimmed),
    enabled: trimmed.length >= MIN_QUERY_LENGTH,
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      unwrap<SearchResponse>(
        client.GET("/api/v1/search", {
          params: { query: { query: trimmed, page: pageParam } },
          signal,
        }),
      ),
    getNextPageParam: (last) => (last.page < last.total_pages ? last.page + 1 : undefined),
  });
}

export function useTracked(view: "active" | "history", offset = 0, limit = 20, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tracked(view, offset),
    enabled,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      unwrap<TrackedListResponse>(
        client.GET("/api/v1/tracked-titles", {
          params: { query: { view, offset, limit } },
          signal,
        }),
      ),
  });
}

export function useStatus() {
  return useQuery({
    queryKey: queryKeys.status(),
    refetchInterval: 60_000,
    queryFn: ({ signal }) =>
      unwrap<StatusResponse>(client.GET("/api/v1/status", { signal })),
  });
}

function useInvalidateAfterMutation() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["search"] });
    void qc.invalidateQueries({ queryKey: ["tracked"] });
    void qc.invalidateQueries({ queryKey: ["status"] });
  };
}

export function useTrackTitle() {
  const invalidate = useInvalidateAfterMutation();
  return useMutation({
    mutationFn: (vars: { mediaType: MediaType; tmdbId: number }) =>
      unwrap<TitleView>(
        client.PUT("/api/v1/tracked-titles/{media_type}/{tmdb_id}", {
          params: { path: { media_type: vars.mediaType, tmdb_id: vars.tmdbId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useStopTitle() {
  const invalidate = useInvalidateAfterMutation();
  return useMutation({
    mutationFn: (vars: { mediaType: MediaType; tmdbId: number }) =>
      unwrap<TitleView>(
        client.DELETE("/api/v1/tracked-titles/{media_type}/{tmdb_id}", {
          params: { path: { media_type: vars.mediaType, tmdb_id: vars.tmdbId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useGotifyTest() {
  return useMutation({
    mutationFn: () =>
      unwrap<GotifyTestResponse>(client.POST("/api/v1/status/gotify-test", {})),
  });
}
