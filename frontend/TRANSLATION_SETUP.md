# Translation System Implementation

## What was set up:

1. **Translation files** (`/frontend/src/translations/`):
   - `en.json` - English translations
   - `sv.json` - Swedish translations
   - Both files organized in a hierarchical structure matching the app's features

2. **Translation hook** (`/frontend/src/hooks/useTranslation.tsx`):
   - `TranslationProvider` - React context provider for translations
   - `useTranslation()` hook - Access translations and language switching in components
   - Features:
     - Browser language detection (defaults to Swedish if sv, else English)
     - localStorage persistence of language preference
     - Fallback to English translations if key not found in current language
     - String replacement support (e.g., `t("key", { name: "value" })`)

3. **Updated core files**:
   - `/frontend/src/main.tsx` - Wrapped app with TranslationProvider
   - `/frontend/src/store.ts` - Added language state management
   - `/frontend/src/App.tsx` - Added language switcher button in header

## How to use translations in components:

```tsx
import { useTranslation } from "@/hooks/useTranslation";

export default function MyComponent() {
  const { t, language, setLanguage } = useTranslation();
  
  return (
    <>
      <button onClick={() => setLanguage("sv")}>{t("common.save")}</button>
      <p>{t("meetings.title")}</p>
    </>
  );
}
```

## Available translation keys (sample):
- `app.title`, `app.tagline`, `app.settings`
- `common.*` - Generic UI
- `meetings.*` - Meeting list view
- `meeting.*` - Meeting detail view
- `export.formats.*` - Export dialog
- `settings.*` - Settings panel
- `speakers.*`, `insights.*`, `actions.*` - Feature panels
- And many more organized by feature

## String replacement in translations:
```tsx
// In translation file:
"delete_profile_confirm": "Delete profile \"%s\"? This cannot be undone."

// In component:
{t("settings.delete_profile_confirm", { s: profileName })}
```

## Next steps for full implementation:
1. Update individual components to use `useTranslation()` hook
2. Replace hardcoded strings with `t("key")` calls
3. Add more translations as needed
4. Consider adding a language preference to the settings modal for persistent selection
