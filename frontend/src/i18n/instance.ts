import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import type { SupportedLanguage } from "../lib/locale";
import { de } from "./de";
import { en } from "./en";

// Bundled catalogs only; no network-loaded translations. init() resolves
// synchronously because the resources are inline and there is no async backend.
export function createI18n(language: SupportedLanguage = "en") {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources: {
      en: { translation: en },
      de: { translation: de },
    },
    lng: language,
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    returnNull: false,
  });
  return instance;
}
