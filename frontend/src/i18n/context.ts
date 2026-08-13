import { createContext, useContext } from "react";
import { useTranslation } from "react-i18next";

import type { ResolvedLocale } from "../lib/locale";

// A deliberately narrow translation type. It lets pure helpers in lib/format.ts
// take `t` without depending on i18next's generic typings, and accepts the
// react-i18next `t` at call sites.
export type Translate = (key: string, options?: Record<string, unknown>) => string;

export const LocaleContext = createContext<ResolvedLocale>({
  language: "en",
  formatLocale: "en-US",
});

/** Active translation function plus the full formatting locale and base language. */
export function useI18n(): { t: Translate; formatLocale: string; language: ResolvedLocale["language"] } {
  const { t } = useTranslation();
  const locale = useContext(LocaleContext);
  return { t: t as Translate, formatLocale: locale.formatLocale, language: locale.language };
}
