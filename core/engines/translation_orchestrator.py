from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import asyncio
import logging

from discord_bot.core.engines.base.engine_plugin import EnginePlugin
from discord_bot.language_context.translation_job import TranslationJob

logger = logging.getLogger("hippo_bot.translation_orchestrator")


class TranslationOrchestratorEngine(EnginePlugin):
    """
    Lightweight orchestrator that implements a three-tier pipeline:
      1) DeepL (highest quality, ~31 languages)
      2) MyMemory (good quality fallback)
      3) Google Translate (free tier, 100+ languages, final fallback)
    This engine expects adapters to implement `translate(text, src, tgt) -> Optional[str]`
    and optional `supported_languages() -> List[str]`.
    """

    def __init__(
        self,
        *,
        deepl_adapter: Any = None,
        mymemory_adapter: Any = None,
        google_adapter: Any = None,
        detection_service: Any = None,
        nlp_processor: Any = None,
    ) -> None:
        super().__init__()
        self.deepl = deepl_adapter
        self.mymemory = mymemory_adapter
        self.google = google_adapter
        self.detector = detection_service
        self.nlp = nlp_processor

    async def _detect(self, text: str) -> Tuple[str, float]:
        if self.detector and hasattr(self.detector, "detect_language"):
            try:
                lang, conf = await self.detector.detect_language(text)
                return lang, conf or 0.0
            except Exception:
                pass
        return "en", 0.0

    def _supports(self, adapter: Any, tgt: str) -> bool:
        try:
            if not adapter:
                return False
            if hasattr(adapter, "supported_languages"):
                langs = adapter.supported_languages()
                return tgt.lower() in {l.lower() for l in langs}
            return True
        except Exception:
            return True

    def _extract_text(self, result: Any, provider: str) -> Optional[str]:
        if result is None:
            logger.debug("%s adapter returned None", provider)
            return None
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            val = result.get("translated_text") or result.get("text")
            if val is not None:
                return str(val)
        for attr in ("translated_text", "text"):
            if hasattr(result, attr):
                val = getattr(result, attr)
                if val is not None:
                    return str(val)
        # Fallback: best-effort string conversion
        try:
            return str(result)
        except Exception:
            return None

    async def _try_adapter(self, adapter: Any, text: str, src: str, tgt: str, provider: str) -> Optional[str]:
        if not adapter:
            return None
        try:
            logger.debug("Attempting %s translation (src=%s tgt=%s)", provider, src, tgt)
            translate_async = getattr(adapter, "translate_async", None)
            if callable(translate_async):
                maybe = translate_async(text, src, tgt)
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
            else:
                translate = getattr(adapter, "translate", None)
                if not callable(translate):
                    logger.debug("%s adapter missing translate entrypoint", provider)
                    return None
                maybe = translate(text, src, tgt)
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
            extracted = self._extract_text(result, provider)
            if extracted:
                logger.info("%s produced translation (len=%d)", provider, len(extracted))
            else:
                logger.debug("%s returned no text", provider)
            return extracted
        except Exception as exc:
            logger.warning("%s adapter raised %s", provider, exc, exc_info=True)
            return None

    async def translate_text_for_user(
        self, *, text: str, guild_id: int, user_id: int, tgt_lang: Optional[str] = None
    ) -> Tuple[Optional[str], str, Optional[str]]:
        """
        High-level helper: detects source, runs 3-tier pipeline, returns (translated_text, src_lang, provider_id)
        provider_id is "deepl", "mymemory", "google", or None on failure.
        """
        if not text:
            logger.debug("translate_text_for_user called with empty text")
            return None, "en", None

        pre = text
        if self.nlp and hasattr(self.nlp, "preprocess"):
            try:
                pre = self.nlp.preprocess(text)
            except Exception:
                pre = text

        src, conf = await self._detect(pre)
        logger.debug("Detection result src=%s confidence=%.2f target_hint=%s", src, conf, tgt_lang)

        tgt = (tgt_lang or "en").lower()

        # Tier 1: DeepL if it supports target (highest quality)
        if self._supports(self.deepl, tgt):
            out = await self._try_adapter(self.deepl, pre, src, tgt, "deepl")
            if out:
                if self.nlp and hasattr(self.nlp, "postprocess"):
                    out = self.nlp.postprocess(out)
                return out, src, "deepl"
        else:
            logger.debug("DeepL does not support target %s", tgt)

        # Tier 2: MyMemory (good quality fallback)
        if self._supports(self.mymemory, tgt):
            out = await self._try_adapter(self.mymemory, pre, src, tgt, "mymemory")
            if out:
                if self.nlp and hasattr(self.nlp, "postprocess"):
                    out = self.nlp.postprocess(out)
                return out, src, "mymemory"
        else:
            logger.debug("MyMemory skipped for target %s", tgt)

        # Tier 3: Google Translate (free tier, 100+ languages, final fallback)
        if self._supports(self.google, tgt):
            logger.info("Falling back to Google Translate for target=%s", tgt)
            out = await self._try_adapter(self.google, pre, src, tgt, "google")
            if out:
                if self.nlp and hasattr(self.nlp, "postprocess"):
                    out = self.nlp.postprocess(out)
                return out, src, "google"
        else:
            logger.debug("Google Translate does not support target %s", tgt)

        logger.warning("All 3 providers failed for guild=%s user=%s target=%s", guild_id, user_id, tgt)
        return None, src, None

    async def translate_job(self, job: TranslationJob) -> Optional[str]:
        """
        Backwards-compatible method: accept a TranslationJob and return translated text
        (keeps compatibility with existing processing_engine.execute_job usage).
        """
        translated, _, _ = await self.translate_text_for_user(
            text=job.text, guild_id=job.guild_id, user_id=job.author_id, tgt_lang=job.tgt_lang
        )
        return translated
