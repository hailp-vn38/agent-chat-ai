import { atom } from "jotai";

/**
 * Get initial language from localStorage (set by i18next detector)
 * Falls back to 'en' if not found
 */
const getInitialLanguage = (): "en" | "vi" => {
  const stored = localStorage.getItem("i18n");
  if (stored === "vi" || stored === "en") {
    return stored;
  }
  return "en";
};

/**
 * Language preference atom
 * Stores the currently active language ('en' or 'vi')
 * Initialized from localStorage and kept in sync with i18next
 */
export const languageAtom = atom<"en" | "vi">(getInitialLanguage());
