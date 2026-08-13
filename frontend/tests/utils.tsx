import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";

import { LocaleProvider } from "../src/i18n/LocaleProvider";
import { createI18n } from "../src/i18n/instance";
import type { ResolvedLocale, SupportedLanguage } from "../src/lib/locale";

export interface Route {
  method: string;
  match: (url: URL) => boolean;
  json: unknown;
  status?: number;
  delayMs?: number;
}

/** Install a fetch mock that routes by method + URL predicate. Returns the spy
 *  and a list of recorded calls (so tests can assert AbortSignal usage etc). */
export function installFetch(routes: Route[]) {
  const calls: { url: URL; method: string; signal?: AbortSignal | null }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    // openapi-fetch passes a Request object; direct callers may pass a string.
    const isRequest = typeof input === "object" && "url" in input;
    const raw = typeof input === "string" ? input : isRequest ? input.url : input.toString();
    const url = new URL(raw, "http://localhost");
    const method = (init?.method ?? (isRequest ? input.method : "GET")).toUpperCase();
    const signal = init?.signal ?? (isRequest ? input.signal : undefined);
    calls.push({ url, method, signal });
    const route = routes.find((r) => r.method === method && r.match(url));
    if (!route) {
      return new Response(
        JSON.stringify({ error: { code: "not_found", message: "no route", retryable: false }, request_id: "t" }),
        { status: 404, headers: { "content-type": "application/json" } },
      );
    }
    if (route.delayMs) {
      await new Promise((resolve) => setTimeout(resolve, route.delayMs));
    }
    return new Response(JSON.stringify(route.json), {
      status: route.status ?? 200,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

export function pathIs(path: string) {
  return (url: URL) => url.pathname === path;
}

const LOCALES: Record<SupportedLanguage, ResolvedLocale> = {
  en: { language: "en", formatLocale: "en-US" },
  de: { language: "de", formatLocale: "de-DE" },
};

/** Render inside an isolated locale provider (default German) and a fresh query
 *  client, so component tests can assert localized visible text. */
export function renderWithClient(
  ui: ReactElement,
  { language = "de" }: { language?: SupportedLanguage } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const i18n = createI18n(language);
  return {
    queryClient,
    i18n,
    ...render(
      <QueryClientProvider client={queryClient}>
        <LocaleProvider locale={LOCALES[language]} i18n={i18n}>
          {ui}
        </LocaleProvider>
      </QueryClientProvider>,
    ),
  };
}
