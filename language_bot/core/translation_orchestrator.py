"""High level translation workflow for LanguageBot.

The :class:`TranslationOrchestrator` provides a single entrypoint for the rest
of the bot to request translations. It coordinates language detection,
provider selection, and failover between multiple upstream translation
services (DeepL, MyMemory, OpenAI, ...).

The orchestrator purposely keeps the transport logic small and depends only on
``httpx``/``openai`` so it can run independently from discord.py and remain
easy to unit test.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import logging
import math
import os
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import quote

import httpx
from langdetect import DetectorFactory, detect, LangDetectException

try:  # OpenAI is optional because not everyone wires the key
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover - best effort import
    AsyncOpenAI = None  # type: ignore


if TYPE_CHECKING:  # pragma: no cover
    from language_bot.config import LanguageBotConfig


logger = logging.getLogger(__name__)
COMMON_SHORT_WORDS = {"yes", "no", "ok", "hi", "bye", "thanks", "lol", "gg"}


@dataclass(slots=True)
class TranslationResult:
    """Container describing a translated string."""

    provider: str
    translated_text: str
    target_language: str
    source_language: str
    confidence: Optional[float] = None


class TranslationError(RuntimeError):
    """Raised when no translation provider succeeds."""


class TranslationOrchestrator:
    """Detects source language and fans-out to upstream providers."""

    # Cache recent language detections per channel/user (LRU, last 5)
    _recent_language_cache = defaultdict(lambda: deque(maxlen=5))  # key: channel_id, value: deque of (user_id, lang)

    def __init__(self, config: "LanguageBotConfig") -> None:
        from language_bot.config import LanguageBotConfig as _LanguageBotConfig  # Local import to avoid cycles

        if not isinstance(config, _LanguageBotConfig):  # pragma: no cover - guardrail
            raise TypeError("config must be LanguageBotConfig")

        self._config = config
        self._provider_order: List[str] = config.provider_order

        # Langdetect relies on a global state – setting a seed keeps detections
        # deterministic across processes/tests.
        DetectorFactory.seed = int(os.getenv("LANGDETECT_SEED", "31337"))

        self._openai_client: Optional[AsyncOpenAI] = None
        if config.openai_api_key and AsyncOpenAI is not None:
            self._openai_client = AsyncOpenAI(api_key=config.openai_api_key)

        self._policy_repo = getattr(config, "policy_repo", None)  # Optional: PolicyRepository instance

    def detect_language(self, text: str, channel_id: Optional[int] = None, user_id: Optional[int] = None) -> Optional[str]:
        """Best-effort guess of the input language, returning a BCP47 code."""

        cleaned = (text or "").strip()
        if self._should_skip_detection(cleaned):
            return None
        try:
            code = detect(cleaned)
        except LangDetectException:
            code = None
        lang = (code or "").split("-", 1)[0].lower() or None
        # Cache detection
        if channel_id is not None and user_id is not None and lang:
            self._recent_language_cache[channel_id].append((user_id, lang))
        return lang

    async def translate(
        self,
        *,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        allow_identical: bool = False,
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        mention_roles: Optional[list] = None,
    ) -> TranslationResult:
        """Translate ``text`` into ``target_language`` with provider failover."""

        cleaned_text = (text or "").strip()
        self._ensure_translatable_text(cleaned_text)

        resolved_source = self._resolve_source_language(cleaned_text, source_language, channel_id, user_id)
        normalized_source, normalized_target = self._normalize_language_pair(resolved_source, target_language)

        # Smart context: skip translation if mention roles already include detected language
        if mention_roles and normalized_source in mention_roles:
            return TranslationResult(
                provider="noop",
                translated_text=text,
                target_language=normalized_target,
                source_language=normalized_source,
                confidence=1.0,
            )

        short_circuit = self._maybe_short_circuit(
            text=text,
            normalized_source=normalized_source,
            normalized_target=normalized_target,
            allow_identical=allow_identical,
        )
        if short_circuit:
            return short_circuit

        return await self._run_provider_pipeline(
            text=text,
            normalized_source=normalized_source,
            normalized_target=normalized_target,
            channel_id=channel_id,
        )

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _translate_via_deepl(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> Optional[TranslationResult]:
        if not self._config.deepl_api_key:
            return None
        data = {
            "auth_key": self._config.deepl_api_key,
            "text": text,
            "source_lang": source_language,
            "target_lang": target_language,
        }
        endpoint = self._config.deepl_endpoint
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(endpoint, data=data)
            response.raise_for_status()
            payload = response.json()
        translations = payload.get("translations") or []
        if not translations:
            raise TranslationError("DeepL returned no translations")
        translated_text = translations[0].get("text", "")
        detected = translations[0].get("detected_source_language") or source_language
        return TranslationResult(
            provider="deepl",
            translated_text=translated_text,
            target_language=target_language,
            source_language=detected,
            confidence=self._extract_confidence(translations[0]),
        )

    async def _translate_via_mymemory(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> Optional[TranslationResult]:
        params = {
            "q": text,
            "langpair": f"{source_language}|{target_language}",
        }
        if self._config.my_memory_email:
            params["de"] = self._config.my_memory_email
        if self._config.my_memory_api_key:
            params["key"] = self._config.my_memory_api_key
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://api.mymemory.translated.net/get", params=params)
            response.raise_for_status()
            payload = response.json()
        matches = payload.get("matches") or []
        if not matches:
            translated = payload.get("responseData", {}).get("translatedText")
            confidence = payload.get("responseData", {}).get("match")
            if not translated:
                raise TranslationError("MyMemory returned no data")
            matches = [{"translation": translated, "match": confidence, "reference": "responseData"}]
        best = max(matches, key=lambda item: float(item.get("match") or 0))
        translated_text = best.get("translation", "").strip()
        confidence = best.get("match")
        return TranslationResult(
            provider="mymemory",
            translated_text=translated_text,
            target_language=target_language,
            source_language=source_language,
            confidence=float(confidence) if confidence not in (None, "") else None,
        )

    async def _translate_via_openai(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> Optional[TranslationResult]:
        if not self._config.openai_api_key or not self._openai_client:
            return None

        system_prompt = "You are a translation engine. Reply ONLY with the translated text."
        user_prompt = (
            "Translate the following message from {src} into {dst}. "
            "Do not add notes, explanations, or quotes.\n\n{body}"
        ).format(src=source_language, dst=target_language, body=text)
        completion = await self._openai_client.chat.completions.create(
            model=self._config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        choice = completion.choices[0]
        content = getattr(choice.message, "content", "") or ""
        translated_text = content.strip()
        return TranslationResult(
            provider="openai",
            translated_text=translated_text,
            target_language=target_language,
            source_language=source_language,
            confidence=None,
        )

    async def _translate_via_google(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> Optional[TranslationResult]:
        # Simple Google Translate API via unofficial endpoint
        encoded = quote(text)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={source_language}&tl={target_language}&dt=t&q={encoded}"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            translated_text = data[0][0][0] if data and data[0] and data[0][0] else ""
            return TranslationResult(
                provider="google",
                translated_text=translated_text,
                target_language=target_language,
                source_language=source_language,
                confidence=None,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_confidence(payload: dict) -> Optional[float]:
        confidence = payload.get("confidence") or payload.get("match")
        try:
            if confidence is None:
                return None
            value = float(confidence)
            return value if not math.isnan(value) else None
        except Exception:
            return None

    @staticmethod
    def _should_skip_detection(cleaned: str) -> bool:
        if not cleaned or len(cleaned) < 3:
            return True
        if all(not char.isalpha() for char in cleaned):
            return True
        if len(cleaned.split()) == 1 and cleaned.lower() in COMMON_SHORT_WORDS:
            return True
        return False

    @staticmethod
    def _ensure_translatable_text(cleaned: str) -> None:
        if not cleaned or len(cleaned) < 3:
            raise TranslationError("Text too short or ambiguous to translate")
        if all(not char.isalpha() for char in cleaned):
            raise TranslationError("Text is emoji or non-alphabetic, skipping translation")
        if len(cleaned.split()) == 1 and cleaned.lower() in COMMON_SHORT_WORDS:
            raise TranslationError("Single common word, skipping translation")

    def _resolve_source_language(self, text: str, explicit_source: Optional[str], channel_id: Optional[int] = None, user_id: Optional[int] = None) -> str:
        detected = explicit_source or self.detect_language(text, channel_id, user_id)
        # If detection is None, try to bias from recent cache
        if not detected and channel_id is not None:
            recent = [lang for _, lang in self._recent_language_cache[channel_id]]
            if recent:
                # Use most common recent language
                detected = max(set(recent), key=recent.count)
        return detected or self._config.default_fallback_language

    @staticmethod
    def _normalize_language_pair(source_language: str, target_language: str) -> tuple[str, str]:
        def normalize(value: str) -> str:
            return value.split("-", 1)[0].upper()

        return normalize(source_language), normalize(target_language)

    @staticmethod
    def _maybe_short_circuit(
        *,
        text: str,
        normalized_source: str,
        normalized_target: str,
        allow_identical: bool,
    ) -> Optional[TranslationResult]:
        if allow_identical or normalized_source != normalized_target:
            return None
        return TranslationResult(
            provider="noop",
            translated_text=text,
            target_language=normalized_target,
            source_language=normalized_source,
            confidence=1.0,
        )

    async def _run_provider_pipeline(
        self,
        *,
        text: str,
        normalized_source: str,
        normalized_target: str,
        channel_id: Optional[int] = None,
    ) -> TranslationResult:
        errors: List[str] = []
        # Policy-driven provider order override
        provider_order = self._provider_order
        if self._policy_repo and channel_id is not None:
            custom_order = self._policy_repo.get_provider_order_for_channel(channel_id)
            if custom_order:
                provider_order = custom_order
        for provider_name in provider_order:
            translator = getattr(self, f"_translate_via_{provider_name}", None)
            if not translator:
                continue
            try:
                result = await translator(text, normalized_source, normalized_target)
                if result:
                    return result
            except Exception as exc:  # pragma: no cover - network errors hard to mock comprehensively
                logger.warning("Translation provider %s failed: %s", provider_name, exc)
                errors.append(f"{provider_name}: {exc}")
        joined = "; ".join(errors) or "no providers available"
        raise TranslationError(f"Unable to translate text after trying providers – {joined}")


__all__ = ["TranslationOrchestrator", "TranslationResult", "TranslationError"]
