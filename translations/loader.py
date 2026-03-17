"""
Translation loader that reads from frontend JSON files.
Provides a unified translation system for both backend and frontend.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class TranslationLoader:
    """Loads translations from frontend JSON files."""

    def __init__(self):
        """Initialize the loader and load all translation files."""
        # Path to frontend translations
        self.base_path = Path(__file__).parent.parent / "frontend" / "src" / "translations"
        self.translations: dict[str, dict[str, Any]] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load all translation JSON files."""
        for lang in ["en", "sv"]:
            file_path = self.base_path / f"{lang}.json"
            if file_path.exists():
                try:
                    with open(file_path, encoding="utf-8") as f:
                        self.translations[lang] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Failed to load {lang} translations: {e}")
                    self.translations[lang] = {}

    def reload(self) -> None:
        """Reload translation JSON files from disk."""
        self._load_translations()

    def get(
        self, key: str, lang: str = "en", **replacements: str | int | float
    ) -> str:
        """
        Get a translation by dot-notation key.

        Args:
            key: Translation key using dot notation (e.g., 'common.save' or 'export.formats.pdf.label')
            lang: Language code ('en' or 'sv'). Defaults to 'en'.
            **replacements: Values to replace in the string (e.g., t('progress.step', d=1))
                           Placeholders in JSON should be %key% format

        Returns:
            Translated string, or the key itself if not found.

        Example:
            >>> t('common.save', lang='sv')
            'Spara'
            >>> t('progress.step', lang='sv', d=1)
            'Steg 1 av 3'
        """
        # Navigate through nested keys
        parts = key.split(".")
        value = self.translations.get(lang, {})

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break

        # Fallback to English if key not found in requested language
        if value is None and lang != "en":
            value = self.translations.get("en", {})
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break

        # If still not found, return the key itself
        if value is None:
            return key

        # Handle string interpolation with %key% placeholders
        if isinstance(value, str) and replacements:
            for k, v in replacements.items():
                placeholder = f"%{k}%"
                if placeholder in value:
                    value = value.replace(placeholder, str(v))

        return value if isinstance(value, str) else key

    def get_nested(self, key: str, lang: str = "en") -> Any:
        """
        Get a nested translation object (dict or list).
        Useful for getting entire sections like export formats.

        Args:
            key: Translation key using dot notation
            lang: Language code

        Returns:
            Dictionary, list, or string depending on what's at that key

        Example:
            >>> formats = loader.get_nested('export.formats', lang='en')
            >>> formats['pdf']['label']
            'PDF'
        """
        parts = key.split(".")
        value = self.translations.get(lang, {})

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value if value else None

    def keys(self, lang: str = "en") -> list[str]:
        """Get all translation keys for a language."""
        return list(self.translations.get(lang, {}).keys())

    def languages(self) -> list[str]:
        """Get list of available languages."""
        return list(self.translations.keys())


# Global loader instance
_loader = TranslationLoader()


def t(key: str, lang: str = "en", **kwargs: str | int | float) -> str:
    """
    Get a translation. Standalone function version.

    This is the main function to use for translations.

    Args:
        key: Translation key (e.g., 'common.save')
        lang: Language code ('en' or 'sv')
        **kwargs: String replacements

    Returns:
        Translated string

    Example:
        >>> from translations.loader import t
        >>> t('meetings.title', lang='sv')
        'Möten'
    """
    return _loader.get(key, lang, **kwargs)


def get_translation(key: str, lang: str = "en") -> str:
    """Alias for t() - Get a translation by key."""
    return _loader.get(key, lang)


def is_available_key(key: str, lang: str = "en") -> bool:
    """Check if a translation key exists."""
    return _loader.get(key, lang) != key


def get_all_translations(lang: str = "en") -> dict[str, Any]:
    """Get all translations for a language."""
    _loader.reload()
    return _loader.translations.get(lang, {})


# For backwards compatibility with existing code that imports from literals.py
# These help with gradual migration
def load_from_json(lang: str = "en") -> dict[str, str]:
    """
    Load all translations as a flat dictionary for backwards compatibility.
    Only returns string values (not nested dicts).

    Example:
        >>> strings = load_from_json('en')
        >>> strings['UNKNOWN_SPEAKER']
        'Unknown'
    """
    result = {}

    def flatten(obj: Any, prefix: str = "") -> None:
        for key, value in obj.items():
            full_key = f"{prefix}_{key}".upper() if prefix else key.upper()
            if isinstance(value, dict):
                flatten(value, full_key)
            elif isinstance(value, str):
                result[full_key] = value

    flatten(_loader.translations.get(lang, {}))
    return result
