// Locale resolution. The browser locale seeds the initial/error shell; once the
// backend status loads, TMDB_LANGUAGE becomes authoritative. Every resolved
// locale carries the base catalog language plus the full regional tag used for
// Intl formatting.

export type SupportedLanguage = "en" | "de";

export interface ResolvedLocale {
  language: SupportedLanguage;
  formatLocale: string;
}

const EN_FALLBACK: ResolvedLocale = { language: "en", formatLocale: "en-US" };

/** Return a resolved locale when the candidate maps to a supported base
 *  language, or null when it is unsupported, empty, or an invalid BCP-47 tag. */
function matchSupported(candidate: string | null | undefined): ResolvedLocale | null {
  if (!candidate) {
    return null;
  }
  let canonical: string | undefined;
  try {
    [canonical] = Intl.getCanonicalLocales(candidate);
  } catch {
    // A malformed tag throws a RangeError.
    return null;
  }
  if (!canonical) {
    return null;
  }
  const base = canonical.toLowerCase().split("-")[0];
  if (base === "de") {
    return { language: "de", formatLocale: canonical };
  }
  if (base === "en") {
    return { language: "en", formatLocale: canonical };
  }
  return null;
}

/** Resolve a single authoritative candidate (e.g. TMDB_LANGUAGE). Unsupported or
 *  invalid values fall back to English with en-US formatting. */
export function resolveLocale(candidate: string | null | undefined): ResolvedLocale {
  return matchSupported(candidate) ?? EN_FALLBACK;
}

/** Resolve from the ordered browser candidates, picking the first supported one. */
export function resolveBrowserLocale(languages: readonly string[]): ResolvedLocale {
  for (const language of languages) {
    const match = matchSupported(language);
    if (match) {
      return match;
    }
  }
  return EN_FALLBACK;
}

/** Ordered browser language candidates, empty when navigator is unavailable. */
export function browserLanguages(): readonly string[] {
  if (typeof navigator === "undefined") {
    return [];
  }
  if (navigator.languages && navigator.languages.length > 0) {
    return navigator.languages;
  }
  return navigator.language ? [navigator.language] : [];
}
