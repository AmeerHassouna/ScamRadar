"""
Auto-detect language and translate to English before model inference.
Uses langdetect (offline, fast) + deep-translator (Google, no API key).
Falls through silently on any error so the original text is always used.
"""

from __future__ import annotations

_LANGDETECT_OK = False
_TRANSLATOR_OK = False

try:
    from langdetect import detect, LangDetectException
    _LANGDETECT_OK = True
except ImportError:
    pass

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_OK = True
except ImportError:
    pass

# Languages we skip translation for (treat as English-compatible)
_SKIP_LANGS = {'en'}

# langdetect can be non-deterministic; seed it for reproducibility
if _LANGDETECT_OK:
    from langdetect import DetectorFactory
    DetectorFactory.seed = 42


def detect_and_translate(text: str) -> tuple[str, str | None]:
    """
    Returns (text_to_analyse, detected_lang_code | None).
    detected_lang_code is None when already English or detection failed.
    """
    if not _LANGDETECT_OK or not _TRANSLATOR_OK:
        return text, None

    try:
        lang = detect(text)
    except Exception:
        return text, None

    if lang in _SKIP_LANGS:
        return text, None

    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        if translated and translated.strip():
            return translated.strip(), lang
    except Exception:
        pass

    return text, None
