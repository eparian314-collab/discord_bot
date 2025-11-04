"""Heuristic detection service used by the TranslationOrchestrator.

- Fast unicode-range heuristics for CJK, Japanese, Cyrillic, etc (high-confidence).
- Optional use of `langdetect` (if installed) for more granular detection and probabilities.
- Async API: `detect_language(text) -> (lang_code, confidence)`
"""

from __future__ import annotations

from typing import Tuple, Optional
import asyncio

try:
    # optional dependency for better detection when available
    from langdetect import detect_langs  # type: ignore
    _HAS_LANGDETECT = True
except Exception:
    _HAS_LANGDETECT = False


class HeuristicDetector:
    def __init__(self, default: str = "en") -> None:
        self.default = (default or "en").lower()

    async def detect_language(self, text: str) -> Tuple[str, float]:
        """
        Async detection entry point.

        Returns:
            (lang_code, confidence) -- lang_code is a two-letter code (lowercase).
        """
        # run synchronous detection in threadpool to keep API consistently async
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, text or "")

    def _detect_sync(self, text: str) -> Tuple[str, float]:
        t = (text or "").strip()
        if not t:
            return self.default, 0.0

        # Quick high-confidence checks using Unicode ranges
        # Japanese (Hiragana / Katakana / Full-width kana)
        if any("\u3040" <= ch <= "\u30ff" for ch in t):
            return "ja", 0.99

        # CJK Unified Ideographs (Chinese)
        if any("\u4e00" <= ch <= "\u9fff" for ch in t):
            return "zh", 0.99

        # Cyrillic (Russian, Ukrainian, etc.)
        if any("\u0400" <= ch <= "\u04FF" for ch in t):
            return "ru", 0.98

        # Basic Latin + common diacritics heuristic, try langdetect if available for better coverage
        if _HAS_LANGDETECT:
            try:
                langs = detect_langs(t)
                if langs:
                    top = langs[0]
                    code = getattr(top, "lang", None)
                    prob = getattr(top, "prob", 0.0)
                    if isinstance(code, str) and code:
                        return code.lower(), float(prob)
            except Exception:
                # fall through to heuristics
                pass

        # Fallback heuristics for some Romance languages via diacritics / characters
        # These are intentionally simple and low confidence
        if any(ch in t for ch in "��������������"):
            # likely Spanish or Portuguese; prefer 'es' as broad default
            return "es", 0.35

        if any(ch in t for ch in "�������������������������ٌ�"):
            return "fr", 0.35

        # Default fallback
        # If it's mostly ASCII letters assume English with low confidence
        ascii_letters = sum(1 for ch in t if ch.isalpha() and ord(ch) < 128)
        non_ascii = len(t) - ascii_letters
        if ascii_letters > max(10, len(t) // 2) and non_ascii == 0:
            return "en", 0.6

        return self.default, 0.2