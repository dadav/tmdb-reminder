import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Nginx serves the SPA and proxies "/api" to the backend (same origin); in dev
// Vite proxies it. Paths in the schema already include the "/api/v1" prefix, so
// we only need the origin. Using an absolute origin keeps the request valid in
// non-browser test environments where relative URLs cannot be resolved.
// The fetch indirection resolves globalThis.fetch at call time (not creation
// time) so tests can stub it.
const baseUrl = typeof window !== "undefined" ? window.location.origin : "";

export const client = createClient<paths>({
  baseUrl,
  fetch: (input) => globalThis.fetch(input),
});

/** The standardized API error body: {error: {...}, request_id}. */
export interface ApiErrorBody {
  error: { code: string; message: string; retryable: boolean; details?: unknown };
  request_id: string;
}

export class ApiError extends Error {
  code: string;
  retryable: boolean;
  requestId: string;

  constructor(body: ApiErrorBody | undefined, status: number) {
    const message = body?.error?.message ?? `Request failed (${status})`;
    super(message);
    this.name = "ApiError";
    this.code = body?.error?.code ?? "unknown";
    this.retryable = body?.error?.retryable ?? false;
    this.requestId = body?.request_id ?? "unknown";
  }
}

/** Unwrap an openapi-fetch result, throwing a typed ApiError on failure. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (error !== undefined || !response.ok) {
    throw new ApiError(error as ApiErrorBody | undefined, response.status);
  }
  return data as T;
}
