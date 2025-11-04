"""
Google Translate Adapter - Free tier fallback translator
Uses deep-translator library (more stable than googletrans)
Supports 100+ languages as a third-tier fallback
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, List

logger = logging.getLogger("hippo_bot.google_translate_adapter")

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    logger.warning("deep-translator not installed - Google Translate adapter disabled")


class GoogleTranslateAdapter:
    """
    Adapter for Google Translate (free tier via deep-translator library).
    This is the third-tier fallback for languages not supported by DeepL or MyMemory.
    Supports 100+ languages.
    """

    def __init__(self):
        self.translator = None  # Created per-translation with specific source/target
        self._supported_langs: Optional[List[str]] = None
        
        if not TRANSLATOR_AVAILABLE:
            logger.error("GoogleTranslateAdapter initialized but deep-translator not available")

    def supported_languages(self) -> List[str]:
        """
        Return list of supported language codes.
        Google Translate supports 100+ languages.
        """
        if self._supported_langs is not None:
            return self._supported_langs

        # Comprehensive list of Google Translate supported languages
        self._supported_langs = [
            'af', 'sq', 'am', 'ar', 'hy', 'az', 'eu', 'be', 'bn', 'bs',
            'bg', 'ca', 'ceb', 'ny', 'zh', 'zh-cn', 'zh-tw', 'co', 'hr', 'cs',
            'da', 'nl', 'en', 'eo', 'et', 'tl', 'fi', 'fr', 'fy', 'gl',
            'ka', 'de', 'el', 'gu', 'ht', 'ha', 'haw', 'he', 'iw', 'hi',
            'hmn', 'hu', 'is', 'ig', 'id', 'ga', 'it', 'ja', 'jw', 'kn',
            'kk', 'km', 'ko', 'ku', 'ky', 'lo', 'la', 'lv', 'lt', 'lb',
            'mk', 'mg', 'ms', 'ml', 'mt', 'mi', 'mr', 'mn', 'my', 'ne',
            'no', 'ps', 'fa', 'pl', 'pt', 'pa', 'ro', 'ru', 'sm', 'gd',
            'sr', 'st', 'sn', 'sd', 'si', 'sk', 'sl', 'so', 'es', 'su',
            'sw', 'sv', 'tg', 'ta', 'te', 'th', 'tr', 'uk', 'ur', 'uz',
            'vi', 'cy', 'xh', 'yi', 'yo', 'zu'
        ]
        return self._supported_langs

    async def translate_async(self, text: str, src: str, tgt: str) -> Optional[str]:
        """
        Async wrapper for Google Translate.
        
        Args:
            text: Text to translate
            src: Source language code
            tgt: Target language code
            
        Returns:
            Translated text or None on failure
        """
        if not TRANSLATOR_AVAILABLE:
            logger.debug("Google Translate not available")
            return None

        if not text or not text.strip():
            return None

        try:
            # Normalize language codes
            src_normalized = src.lower().strip()
            tgt_normalized = tgt.lower().strip()

            # Handle special cases
            if tgt_normalized in ['zh', 'zh-cn']:
                tgt_normalized = 'zh-cn'
            elif tgt_normalized == 'zh-tw':
                tgt_normalized = 'zh-tw'

            # Create translator instance for this translation
            # deep-translator uses auto-detect when src='auto'
            translator = GoogleTranslator(
                source='auto' if src_normalized == 'auto' else src_normalized,
                target=tgt_normalized
            )

            # Run translation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(
                None,
                lambda: translator.translate(text)
            )

            if translated:
                translated = translated.strip()
                logger.info(
                    "Google Translate: %s -> %s (input_len=%d, output_len=%d)",
                    src, tgt, len(text), len(translated)
                )
                return translated

            logger.warning("Google Translate returned empty result")
            return None

        except Exception as exc:
            logger.warning(
                "Google Translate failed for %s -> %s: %s",
                src, tgt, exc,
                exc_info=True
            )
            return None

    def translate(self, text: str, src: str, tgt: str) -> Optional[str]:
        """
        Synchronous translation method (for compatibility).
        Note: This will block the event loop - prefer translate_async.
        """
        if not TRANSLATOR_AVAILABLE:
            return None

        try:
            translator = GoogleTranslator(source=src, target=tgt)
            return translator.translate(text)
        except Exception as exc:
            logger.warning("Google Translate sync failed: %s", exc)
            return None


def create_google_translate_adapter() -> Optional[GoogleTranslateAdapter]:
    """
    Factory function to create Google Translate adapter.
    Returns None if deep-translator library is not available.
    """
    if not TRANSLATOR_AVAILABLE:
        logger.info("Google Translate adapter not available (install deep-translator)")
        return None
    
    try:
        adapter = GoogleTranslateAdapter()
        logger.info("Google Translate adapter initialized (100+ languages)")
        return adapter
    except Exception as exc:
        logger.error("Failed to create Google Translate adapter: %s", exc)
        return None


