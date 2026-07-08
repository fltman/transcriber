import { createContext, useContext, ReactNode, useState, useCallback, useEffect } from "react";
import { getTranslations, type Language } from "../api";

type TranslationTree = Record<string, unknown>;

interface TranslationContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, replacements?: Record<string, string | number>) => string;
}

const TranslationContext = createContext<TranslationContextType | undefined>(undefined);

export function TranslationProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<TranslationTree>({});
  const [fallbackMessages, setFallbackMessages] = useState<TranslationTree>({});
  const [language, setLanguageState] = useState<Language>(() => {
    // Check localStorage for saved preference
    const saved = localStorage.getItem("language") as Language | null;
    if (saved && (saved === "en" || saved === "sv")) {
      return saved;
    }
    // Try to detect browser language
    const browserLang = navigator.language.split("-")[0];
    return browserLang === "sv" ? "sv" : "en";
  });

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem("language", lang);
  }, []);

  useEffect(() => {
    let isCancelled = false;

    async function loadTranslations() {
      try {
        const [currentMessages, englishMessages] = await Promise.all([
          getTranslations(language),
          getTranslations("en"),
        ]);

        if (!isCancelled) {
          setMessages(currentMessages);
          setFallbackMessages(englishMessages);
        }
      } catch {
        if (!isCancelled) {
          setMessages({});
          setFallbackMessages({});
        }
      }
    }

    loadTranslations();

    return () => {
      isCancelled = true;
    };
  }, [language]);

  const resolvePath = useCallback((tree: TranslationTree, keys: string[]): unknown => {
    let value: unknown = tree;
    for (const keyPart of keys) {
      if (value && typeof value === "object" && keyPart in value) {
        value = (value as Record<string, unknown>)[keyPart];
      } else {
        return undefined;
      }
    }
    return value;
  }, []);

  const t = useCallback(
    (key: string, replacements?: Record<string, string | number>): string => {
      const keys = key.split(".");
      let value = resolvePath(messages, keys);
      if (value === undefined) {
        value = resolvePath(fallbackMessages, keys);
      }
      if (value === undefined) {
        return key;
      }

      if (typeof value === "string" && replacements) {
        let result = value;
        for (const [oldStr, newVal] of Object.entries(replacements)) {
          result = result.replace(`%${oldStr}%`, String(newVal));
        }
        return result;
      }

      return typeof value === "string" ? value : key;
    },
    [messages, fallbackMessages, resolvePath]
  );

  return (
    <TranslationContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error("useTranslation must be used within a TranslationProvider");
  }
  return context;
}
