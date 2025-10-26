from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import asyncio

from discord_bot.core.engines.base.engine_plugin import EnginePlugin
from discord_bot.language_context.translation_job import TranslationJob


class TranslationOrchestratorEngine(EnginePlugin):
    """
    Lightweight orchestrator that implements the 3-tier pipeline:
      1) DeepL (highest quality)
      2) MyMemory (fallback for unsupported languages)
      3) OpenAI (last-resort + enhancement)
    This engine expects adapters to implement `translate(text, src, tgt) -> Optional[str]`
    and optional `supported_languages() -> List[str]`.
    """

    def __init__(
        self,
        *,
        deepl_adapter: Any = None,
        mymemory_adapter: Any = None,
        openai_adapter: Any = None,
        detection_service: Any = None,
        nlp_processor: Any = None,
    ) -> None:
        super().__init__()
        self.deepl = deepl_adapter
        self.mymemory = mymemory_adapter
        self.openai = openai_adapter
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

    async def _try_adapter(self, adapter: Any, text: str, src: str, tgt: str) -> Optional[str]:
        if not adapter:
            return None
        try:
            # allow adapters to be sync or async
            coro = adapter.translate(text, src, tgt)
            if asyncio.iscoroutine(coro):
                return await coro
            return coro
        except Exception:
            return None

    async def translate_text_for_user(
        self, *, text: str, guild_id: int, user_id: int, tgt_lang: Optional[str] = None
    ) -> Tuple[Optional[str], str, Optional[str]]:
        """
        High-level helper: detects source, runs pipeline, returns (translated_text, src_lang, provider_id)
        provider_id is one of: "deepl", "mymemory", "openai" or None on failure.
        """
        if not text:
            return None, "en", None

        pre = text
        if self.nlp and hasattr(self.nlp, "preprocess"):
            try:
                pre = self.nlp.preprocess(text)
            except Exception:
                pre = text

        src, conf = await self._detect(pre)

        tgt = (tgt_lang or "en").lower()

        # Tier 1: DeepL if it supports target
        if self._supports(self.deepl, tgt):
            out = await self._try_adapter(self.deepl, pre, src, tgt)
            if out:
                if self.nlp and hasattr(self.nlp, "postprocess"):
                    out = self.nlp.postprocess(out)
                return out, src, "deepl"

        # Tier 2: MyMemory
        if self._supports(self.mymemory, tgt):
            out = await self._try_adapter(self.mymemory, pre, src, tgt)
            if out:
                if self.nlp and hasattr(self.nlp, "postprocess"):
                    out = self.nlp.postprocess(out)
                return out, src, "mymemory"

        # Tier 3: OpenAI (enhancement/last-resort)
        out = await self._try_adapter(self.openai, pre, src, tgt)
        if out:
            if self.nlp and hasattr(self.nlp, "postprocess"):
                out = self.nlp.postprocess(out)
            return out, src, "openai"

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