"""
Migration helper for loading translations from JSON files.

This module provides utilities to migrate from hardcoded Python constants
to using the unified JSON translation system.

Usage:
    # Recommended approach:
    from translations.loader import t
    speaker = t('common.unknown_speaker', lang='en')
    
    # Or get all strings mapped to old constant names for gradual migration:
    from translations.migrate import get_constants
    consts = get_constants(lang='en')
    speaker = consts['UNKNOWN_SPEAKER']
    
    # Deprecated (legacy):
    # from translations.en.literals import UNKNOWN_SPEAKER  # DON'T USE
    # Use get_constants() or loader.t() instead for new code.
"""

from typing import Dict, Any
from translations.loader import _loader


def get_constants(lang: str = "en") -> Dict[str, str]:
    """
    Get all translation strings as constants (uppercase keys).
    Useful for migrating code from literals.py.

    This flattens the JSON structure and converts keys to UPPERCASE_WITH_UNDERSCORES,
    mimicking the old constant-style imports.

    Args:
        lang: Language code ('en' or 'sv')

    Returns:
        Dictionary mapping constant names to translated strings

    Example:
        >>> consts = get_constants('sv')
        >>> consts['UNKNOWN_SPEAKER']
        'Okänd'
        >>> consts['DURATION_MINUTES']
        'minuter'

    Mapping examples:
        - common.unknown_speaker → UNKNOWN_SPEAKER
        - meetings.title → MEETINGS_TITLE
        - export.formats.pdf.label → EXPORT_FORMATS_PDF_LABEL
    """
    result: Dict[str, str] = {}

    def flatten(obj: Any, prefix: str = "") -> None:
        """Recursively flatten nested dictionaries."""
        if not isinstance(obj, dict):
            return

        for key, value in obj.items():
            # Build the constant name
            if prefix:
                const_name = f"{prefix}_{key}".upper()
            else:
                const_name = key.upper()

            if isinstance(value, dict):
                # Recursively flatten nested objects
                flatten(value, const_name)
            elif isinstance(value, str):
                # Add string values as constants
                result[const_name] = value
            # Skip non-string values (null, arrays, etc.)

    flatten(_loader.translations.get(lang, {}))
    return result


def get_prompts(lang: str = "en") -> Dict[str, str]:
    """
    Get all AI prompts from translations.

    Prompts are strings containing % placeholders for values like {intro_text},
    {num_speakers}, etc.

    Args:
        lang: Language code

    Returns:
        Dictionary of prompt strings

    Example:
        >>> prompts = get_prompts('en')
        >>> 'SUMMARY_PROMPT' in prompts
        True
    """
    consts = get_constants(lang)
    prompts = {k: v for k, v in consts.items() if "PROMPT" in k}
    return prompts


def get_error_messages(lang: str = "en") -> Dict[str, str]:
    """
    Get all error messages from translations.

    Error messages are formatted as ERROR_* constants.

    Args:
        lang: Language code

    Returns:
        Dictionary of error message strings

    Example:
        >>> errors = get_error_messages('sv')
        >>> errors['ERROR_WRONG_PASSWORD']
        'Fel lösenord'
    """
    consts = get_constants(lang)
    errors = {k: v for k, v in consts.items() if k.startswith("ERROR_")}
    return errors


# Comparison helper: show what's in JSON vs old Python files
def compare_with_literals() -> Dict[str, Any]:
    """
    Show differences between JSON translations and existing Python literals.

    Returns a dict showing:
    - keys_in_json_only: Keys that exist in JSON but not in Python literals
    - keys_in_literals_only: Keys that exist in Python literals but not in JSON
    - values_differ: Keys that exist in both but have different values

    This is useful for migration planning.

    Example:
        >>> diff = compare_with_literals()
        >>> len(diff['keys_in_json_only'])  # New translations to add to Python
    """
    try:
        import translations.en.literals as en_literals
        import translations.sv.literals as sv_literals
    except ImportError:
        return {
            "error": "Could not import literals",
            "note": "Make sure literals.py files exist",
        }

    json_consts = get_constants("en")
    py_consts = {k: v for k, v in vars(en_literals).items() if k.isupper()}

    result = {
        "keys_in_json_only": sorted(set(json_consts.keys()) - set(py_consts.keys())),
        "keys_in_python_only": sorted(set(py_consts.keys()) - set(json_consts.keys())),
        "values_match": False,  # Placeholder
    }

    # Check for value differences in common keys
    common_keys = set(json_consts.keys()) & set(py_consts.keys())
    mismatches = []
    for key in common_keys:
        if json_consts[key] != py_consts[key]:
            mismatches.append({key: {"json": json_consts[key], "python": py_consts[key]}})

    if mismatches:
        result["values_differ"] = mismatches
    else:
        result["values_match"] = True

    return result
