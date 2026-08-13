import type { i18n as I18nInstance } from "i18next";
import { useEffect, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";

import type { ResolvedLocale } from "../lib/locale";
import { LocaleContext } from "./context";
import { createI18n } from "./instance";

interface LocaleProviderProps {
  locale: ResolvedLocale;
  // Tests inject an isolated instance; production creates one per provider.
  i18n?: I18nInstance;
  children: ReactNode;
}

export function LocaleProvider({ locale, i18n: injected, children }: LocaleProviderProps) {
  // Create once with the initial language so the first paint is already correct.
  const [i18n] = useState(() => injected ?? createI18n(locale.language));

  useEffect(() => {
    void i18n.changeLanguage(locale.language);
    document.documentElement.lang = locale.language;
    document.title = i18n.getFixedT(locale.language)("app.documentTitle");
  }, [i18n, locale.language]);

  return (
    <I18nextProvider i18n={i18n}>
      <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>
    </I18nextProvider>
  );
}
