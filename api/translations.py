from fastapi import APIRouter, HTTPException

from translations.loader import get_all_translations

router = APIRouter(prefix="/api/translations", tags=["translations"])


@router.get("/{lang}")
def get_translations(lang: str):
    if lang not in {"en", "sv"}:
        raise HTTPException(status_code=404, detail="Language not found")

    messages = get_all_translations(lang)
    if not messages:
        raise HTTPException(status_code=404, detail="Translations not found")

    return {
        "language": lang,
        "messages": messages,
    }
