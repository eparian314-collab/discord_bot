# DeepLAdapter: lightweight, injection-friendly translation adapter for DeepL
#
# READING GUIDE:
# - Use `DeepLAdapter` to perform translations. Prefer injecting a `translator` instance for testing.
# - Call `await adapter.translate_async(text, src, tgt)` for async code, or `adapter.translate(text, src, tgt)` for sync code.
# - The adapter returns a `TranslationResult` dataclass or `None` on failure.
#
# PURPOSE & SCOPE:
# - This module wraps the DeepL client but does not perform routing, I/O, or command handling.
# - It is rule-first and deterministic. No AI is used here; ML belongs to other components.
# - The adapter is designed to be easily unit-testable (inject a fake `translator`), and to fail gracefully.
#
# DESIGN NOTES:
# - Avoids hard runtime dependency on the `deepl` package by allowing an injected client.
# - Provides both sync and async entrypoints. If the injected client's translate method is synchronous,
#   async calls are executed in a thread with `asyncio.to_thread`.
# - Minimal retry/backoff is implemented; this is tunable and replaceable by callers if needed.
#
# TODOs are included at the bottom describing future extensions (timeouts, circuit-breaker, telemetry).
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = ["DeepLAdapter", "TranslationResult"]


@dataclass(frozen=True)
class TranslationResult:
    """
    Simple structured result for translations.
    - translated_text: the translated string (primary output)
    - detected_source_language: language code if provided by provider, otherwise None
    - raw: raw provider response object for downstream diagnostics (may be None)
    - provider: the adapter/provider name ("deepl")
    - elapsed_seconds: approximate time spent performing the translation call
    """
    translated_text: str
    detected_source_language: Optional[str] = None
    raw: Optional[Any] = None
    provider: str = "deepl"
    elapsed_seconds: Optional[float] = None


class DeepLAdapter:
    """
    Adapter for DeepL translation.

    Construction:
    - Provide either `translator` (injected client) OR `api_key` to create a realtime client.
      If both are provided, `translator` takes precedence.

    Example uses:
    - Sync:
        adapter = DeepLAdapter(api_key="...")
        res = adapter.translate("Hello", src="EN", tgt="DE")
    - Async (in async context):
        adapter = DeepLAdapter(translator=my_deepl_client)
        res = await adapter.translate_async("Hello", src="EN", tgt="DE")

    Notes:
    - The adapter will uppercase language codes to match common provider expectations.
    - The adapter handles common variations of client method signatures by trying keyword args
      first and falling back to positional invocation.
    """

    # DeepL supported target languages (as of 2024)
    # Source: https://www.deepl.com/docs-api/general/get-languages/
    SUPPORTED_TARGET_LANGUAGES = {
        "bg", "cs", "da", "de", "el", "en", "en-gb", "en-us",
        "es", "et", "fi", "fr", "hu", "id", "it", "ja",
        "ko", "lt", "lv", "nb", "nl", "pl", "pt", "pt-br", "pt-pt",
        "ro", "ru", "sk", "sl", "sv", "tr", "uk", "zh", "zh-hans", "zh-hant"
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        translator: Optional[Any] = None,
        max_retries: int = 1,
        retry_backoff: float = 0.2,
        default_timeout: Optional[float] = None,
    ) -> None:
        """
        Parameters:
        - api_key: optional DeepL API key (used only if `translator` not injected)
        - translator: optional injected translator instance (preferred in tests)
        - max_retries: number of total attempts (1 = no retry)
        - retry_backoff: base backoff seconds between retries (simple linear backoff)
        - default_timeout: optional timeout for a single translation call in seconds (adapter-level)
        """
        self._translator = translator
        self._api_key = api_key
        self.max_retries = max(1, int(max_retries))
        self.retry_backoff = float(retry_backoff)
        self.default_timeout = None if default_timeout is None else float(default_timeout)

        if self._translator is None:
            if not api_key:
                # Keep behavior friendly for tests: require either translator or api_key.
                raise ValueError("DeepLAdapter requires either an injected 'translator' or an 'api_key'.")
            # Lazy import to avoid hard dependency during import-time (helps test environments without deepl).
            try:
                import deepl  # type: ignore
            except Exception as exc:  # pragma: no cover - environment dependent
                raise RuntimeError("Failed to import 'deepl' package. Install deepl or inject a translator.") from exc
            # Create a translator instance from deepl SDK.
            # Note: depending on the deepl SDK version the class name may vary, but typically deepl.Translator exists.
            self._translator = deepl.Translator(api_key)

    # ---- Public API -----------------------------------------------------------------

    def supported_languages(self) -> list[str]:
        """
        Return list of supported target language codes.
        
        Returns lowercase language codes that DeepL can translate to.
        """
        return list(self.SUPPORTED_TARGET_LANGUAGES)

    def translate(self, text: str, src: Optional[str], tgt: str) -> Optional[TranslationResult]:
        """
        Synchronous translation entrypoint.

        Returns TranslationResult on success or None on failure.
        """
        return asyncio.get_event_loop().run_until_complete(self.translate_async(text, src, tgt))

    async def translate_async(self, text: str, src: Optional[str], tgt: str) -> Optional[TranslationResult]:
        """
        Asynchronous translation entrypoint. If underlying translator is sync, this will run in a thread.
        """
        if not text:
            return None

        # Normalize language codes (DeepL commonly expects uppercase codes).
        src_lang = src.upper() if src else None
        tgt_lang = tgt.upper() if tgt else None
        
        # DeepL requires EN-GB or EN-US instead of EN
        if tgt_lang == "EN":
            tgt_lang = "EN-US"

        attempt = 0
        last_exc: Optional[BaseException] = None
        while attempt < self.max_retries:
            attempt += 1
            start = time.perf_counter()
            try:
                # If translator provides an async method, call it directly.
                translate_callable = getattr(self._translator, "translate_text", None)
                if translate_callable is None:
                    raise AttributeError("Injected translator does not have 'translate_text' method.")

                # Decide whether to run in thread or await directly based on callable inspect.
                if inspect.iscoroutinefunction(translate_callable):
                    # Async provider
                    resp = await self._invoke_translate_async(translate_callable, text, src_lang, tgt_lang)
                else:
                    # Synchronous provider: run in thread to avoid blocking
                    resp = await asyncio.to_thread(self._invoke_translate_sync, translate_callable, text, src_lang, tgt_lang)

                elapsed = time.perf_counter() - start
                if resp is None:
                    return None

                # Attempt to extract textual attributes commonly provided by SDKs
                translated_text = getattr(resp, "text", None) or getattr(resp, "translated_text", None) or (resp if isinstance(resp, str) else None)
                detected_src = getattr(resp, "detected_source_language", None) or getattr(resp, "source_lang", None)

                if translated_text is None:
                    # Response shape unexpected; include raw response for diagnostics.
                    logger.debug("DeepLAdapter: unexpected response shape: %r", resp)
                    return TranslationResult(
                        translated_text=str(resp),
                        detected_source_language=detected_src,
                        raw=resp,
                        elapsed_seconds=elapsed,
                    )

                return TranslationResult(
                    translated_text=str(translated_text),
                    detected_source_language=(detected_src.upper() if isinstance(detected_src, str) else detected_src),
                    raw=resp,
                    elapsed_seconds=elapsed,
                )
            except Exception as exc:
                last_exc = exc
                logger.debug("DeepLAdapter: translate attempt %d failed: %s", attempt, exc, exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff * attempt)
                else:
                    logger.warning("DeepLAdapter: all %d attempts failed", self.max_retries)

        # If we exit loop with failure, return None (caller may inspect logs). Avoid raising for resilience.
        if last_exc:
            logger.info("DeepLAdapter: translation failed: %s", last_exc)
        return None

    # ---- Internal helpers -----------------------------------------------------------

    async def _invoke_translate_async(self, translate_callable: Callable[..., Any], text: str, src_lang: Optional[str], tgt_lang: Optional[str]) -> Any:
        """
        Call an async translate callable with best-effort parameter binding.
        """
        sig = inspect.signature(translate_callable)
        kwargs = {}
        # Prefer parameter names 'source_lang'/'target_lang' as used by deepl SDKs
        if "source_lang" in sig.parameters:
            kwargs["source_lang"] = src_lang
        if "target_lang" in sig.parameters:
            kwargs["target_lang"] = tgt_lang
        # Some SDKs may accept 'source_lang' as 'source_lang' or 'source_lang_code'; best-effort only.
        try:
            return await translate_callable(text, **{k: v for k, v in kwargs.items() if v is not None})
        except TypeError:
            # Fallback to positional invocation
            if src_lang is not None and tgt_lang is not None:
                return await translate_callable(text, src_lang, tgt_lang)
            return await translate_callable(text)

    def _invoke_translate_sync(self, translate_callable: Callable[..., Any], text: str, src_lang: Optional[str], tgt_lang: Optional[str]) -> Any:
        """
        Call a synchronous translate callable with best-effort parameter binding.
        """
        sig = inspect.signature(translate_callable)
        kwargs = {}
        if "source_lang" in sig.parameters:
            kwargs["source_lang"] = src_lang
        if "target_lang" in sig.parameters:
            kwargs["target_lang"] = tgt_lang
        try:
            return translate_callable(text, **{k: v for k, v in kwargs.items() if v is not None})
        except TypeError:
            # Fallback to positional invocation
            if src_lang is not None and tgt_lang is not None:
                return translate_callable(text, src_lang, tgt_lang)
            return translate_callable(text)


# ---- End of module ----------------------------------------------------------------

# Future Extensions / TODOs:
# - TODO: Add adapter-level timeout enforcement (e.g., use `asyncio.wait_for` around individual attempts) and
#   surface a clear TimeoutError to callers if configured.
# - TODO: Add circuit-breaker / bulkhead pattern to avoid calling the provider when repeated failures occur.
# - TODO: Expose a small Protocol for the injected `translator` to tighten typing and improve developer DX.
# - TODO: Integrate telemetry (request counts, latencies, error rates) via an injectable metrics client.
# - TODO: Add optional response language mapping using project's `language_map.json` to normalize codes.
# - TODO: Add unit tests that inject a fake `translator` implementing both sync and async `translate_text` variants.
#
# Notes:
# - This adapter intentionally returns `None` on failure to keep calling code simple and resilient. If callers
#   require exceptions, they can wrap calls and re-raise based on returned `None` and logs.