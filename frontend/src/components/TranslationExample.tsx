import { useTranslation } from "../hooks/useTranslation";

/**
 * Example component showing how to use the translation system
 * 
 * Copy this pattern to any component that needs translated text:
 * 1. Import useTranslation hook
 * 2. Call the hook: const { t, language, setLanguage } = useTranslation();
 * 3. Use t("key") to get translated strings
 */
export default function TranslationExample() {
  const { t, language, setLanguage } = useTranslation();

  return (
    <div className="p-4 bg-slate-800 rounded-lg">
      <h2 className="text-lg font-bold mb-4">{t("app.title")}</h2>

      <div className="space-y-3">
        {/* Simple translation usage */}
        <p>{t("common.loading")}</p>

        {/* Nested key translations */}
        <p>{t("meetings.title")}</p>

        {/* Conditional translation based on current language */}
        <p className="text-sm text-slate-400">
          Current language: <span className="font-mono">{language}</span>
        </p>

        {/* Language switcher */}
        <div className="flex gap-2">
          <button
            onClick={() => setLanguage("en")}
            className={`px-3 py-1 rounded ${
              language === "en"
                ? "bg-violet-600 text-white"
                : "bg-slate-700 text-slate-300"
            }`}
          >
            English
          </button>
          <button
            onClick={() => setLanguage("sv")}
            className={`px-3 py-1 rounded ${
              language === "sv"
                ? "bg-violet-600 text-white"
                : "bg-slate-700 text-slate-300"
            }`}
          >
            Svenska
          </button>
        </div>

        {/* Example with multiple translations */}
        <div className="border-t border-slate-600 pt-3">
          <p className="font-semibold">{t("settings.title")}</p>
          <ul className="text-sm text-slate-300 mt-2">
            <li>• {t("settings.models")}</li>
            <li>• {t("settings.preferences")}</li>
            <li>• {t("settings.api_keys")}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
