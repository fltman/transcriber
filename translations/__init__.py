"""
Configurable translations support for multiple languages.

This module provides a flexible system to manage translations across the application.
Language folders (e.g., 'en/', 'sv/') contain language-specific literals.

Usage:
    from translations import get_translation, set_language, get_current_language
    
    # Set the application language
    set_language('sv')  # Swedish
    
    # Access translations
    speaker_text = get_translation('common.unknown_speaker')
    
    # Get current language
    current = get_current_language()
"""

import importlib
import os
from pathlib import Path
from typing import Any, Optional

# Default language
_DEFAULT_LANGUAGE = 'en'
_CURRENT_LANGUAGE = _DEFAULT_LANGUAGE

# Cache for loaded language modules
_LANGUAGE_MODULES = {}


def _get_available_languages() -> list[str]:
    """
    Get list of available languages based on subdirectories.
    
    Returns:
        List of available language codes (folder names).
    """
    translations_dir = Path(__file__).parent
    available = [
        d.name for d in translations_dir.iterdir()
        if d.is_dir() and not d.name.startswith('_')
    ]
    return sorted(available)


def set_language(language_code: str) -> None:
    """
    Set the current language for translations.
    
    Args:
        language_code: Language code (e.g., 'en', 'sv').
    
    Raises:
        ValueError: If the language is not available.
    """
    global _CURRENT_LANGUAGE
    
    available_languages = _get_available_languages()
    if language_code not in available_languages:
        raise ValueError(
            f"Language '{language_code}' not available. "
            f"Available languages: {', '.join(available_languages)}"
        )
    
    _CURRENT_LANGUAGE = language_code
    # Clear the module cache for this language to force reload if needed
    if language_code in _LANGUAGE_MODULES:
        del _LANGUAGE_MODULES[language_code]


def get_current_language() -> str:
    """
    Get the currently active language.
    
    Returns:
        Current language code.
    """
    return _CURRENT_LANGUAGE


def _load_language_module(language_code: str):
    """
    Load the literals module for a specific language.
    
    Args:
        language_code: Language code (e.g., 'en', 'sv').
    
    Returns:
        The loaded language module.
    
    Raises:
        ImportError: If the language module cannot be loaded.
    """
    if language_code in _LANGUAGE_MODULES:
        return _LANGUAGE_MODULES[language_code]
    
    try:
        module = importlib.import_module(f'translations.{language_code}.literals')
        _LANGUAGE_MODULES[language_code] = module
        return module
    except ImportError as e:
        raise ImportError(
            f"Could not load translations for language '{language_code}': {e}"
        ) from e


def get_translation(key: str, language_code: Optional[str] = None) -> str:
    """
    Get a translated string by key.
    
    Supports both JSON keys (e.g., 'common.unknown_speaker') and old-style constant names (e.g., 'UNKNOWN_SPEAKER').
    
    Args:
        key: Translation key (e.g., 'common.unknown_speaker' or 'UNKNOWN_SPEAKER').
        language_code: Optional language code. If not provided, uses current language.
    
    Returns:
        Translated string for the given key.
    
    Raises:
        KeyError: If the key is not found.
        ImportError: If the language module cannot be loaded.
    """
    target_language = language_code or _CURRENT_LANGUAGE
    
    # If key contains a dot, treat it as a JSON key and use the loader
    if '.' in key:
        from translations.loader import t
        return t(key, target_language or _DEFAULT_LANGUAGE)
    
    # Otherwise, use the old module-based approach for constant names
    try:
        module = _load_language_module(target_language)
        return getattr(module, key)
    except AttributeError:
        # Fall back to default language if key not found
        if target_language != _DEFAULT_LANGUAGE:
            try:
                default_module = _load_language_module(_DEFAULT_LANGUAGE)
                return getattr(default_module, key)
            except (ImportError, AttributeError):
                raise KeyError(f"Translation key '{key}' not found in any language module")
        raise KeyError(f"Translation key '{key}' not found in '{target_language}' language module")


def get_all_translations(language_code: Optional[str] = None) -> dict[str, Any]:
    """
    Get all translations for a specific language.
    
    Args:
        language_code: Optional language code. If not provided, uses current language.
    
    Returns:
        Dictionary of all translations for the language.
    
    Raises:
        ImportError: If the language module cannot be loaded.
    """
    target_language = language_code or _CURRENT_LANGUAGE
    module = _load_language_module(target_language)
    
    # Return all non-private attributes (not starting with _)
    return {
        key: value for key, value in vars(module).items()
        if not key.startswith('_')
    }


def list_available_languages() -> list[str]:
    """
    List all available languages.
    
    Returns:
        Sorted list of available language codes.
    """
    return _get_available_languages()
