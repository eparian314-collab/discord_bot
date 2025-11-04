# OpenAIAdapter: flexible adapter for using OpenAI as a translation engine
#
# READING GUIDE:
# - Construct with either `api_key` or an injected `client` (preferred for testing).
# - Use `await adapter.translate_async(text, src, tgt)` in async code, or `adapter.translate(text, src, tgt)` synchronously.
# - Returns a `TranslationResult` on success, or `None` on failure. Raw provider response is preserved in `raw`.
#
# PURPOSE & SCOPE:
# - Wrap OpenAI chat/completion calls for translation only. Keep this module focused on calling the provider,
#   parsing responses, and returning a structured result. Do not perform routing, state management, or UI.
# - Be rule- and injection-first: no mandatory import-time dependency on `openai` SDK; accept an injected client.
#
# DESIGN NOTES:
# - Supports multiple OpenAI SDK response shapes (object with attributes or dict-like).
# - Provides limited retry/backoff with jitter and optional per-call timeout.
# - Minimal, safe prompt template designed to reduce hallucination (system directive + single user prompt).
# - Avoids raising on provider errors; returns None to keep calling code resilient.
#
# TODOs at bottom suggest telemetry, circuit-breaker, and more advanced prompt tuning.
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = ["OpenAIAdapter", "TranslationResult"]


@dataclass(frozen=True)
class TranslationResult:
    """
    Structured result for translations performed by OpenAI adapter.

    Fields:
    - translated_text: primary translated string
    - model: model name used for the call
    - provider: provider id ("openai")
    - raw: raw provider response (object or dict) for diagnostics
    - elapsed_seconds: time spent performing provider call (approx)
    """
    translated_text: str
    model: str
    provider: str = "openai"
    raw: Optional[Any] = None
    elapsed_seconds: Optional[float] = None


# Type for injected client factory/caller. Accepts a client instance created by caller.
OpenAIClient = Any


class OpenAIAdapter:
    """
    Adapter for OpenAI-based translations.

    Construction:
      - Provide `client` (an AsyncOpenAI instance or compatible object) OR `api_key`.
        If both provided, `client` is used.
      - `system_prompt` and `user_prompt_template` are configurable for testing/tuning.

    Example (async):
        adapter = OpenAIAdapter(api_key="...", model="gpt-4o-mini")
        result = await adapter.translate_async("Hello", src="EN", tgt="DE")

    Example (sync):
        adapter = OpenAIAdapter(client=my_client)
        result = adapter.translate("Hello", src="EN", tgt="DE")
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        client: Optional[OpenAIClient] = None,
        model: str = "gpt-4o-mini",
        system_prompt: str = "You are a precise translation engine. Only return the translated text.",
        user_prompt_template: str = "Translate the following text from {src} to {tgt}.\nReturn ONLY the translated text, no explanations.\n\nText: {text}",
        max_retries: int = 1,
        retry_backoff: float = 0.2,
        default_timeout: Optional[float] = None,
        temperature: float = 0.0,
    ) -> None:
        self._injected_client = client
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.max_retries = max(1, int(max_retries))
        self.retry_backoff = float(retry_backoff)
        self.default_timeout = None if default_timeout is None else float(default_timeout)
        self.temperature = float(temperature)

        # Client will be initialized lazily to avoid import-time errors in test environments.
        if self._injected_client is None and not self._api_key:
            raise ValueError("OpenAIAdapter requires either an injected `client` or an `api_key`/env var OPENAI_API_KEY.")

        self._client: Optional[OpenAIClient] = None

    # ---------------- Public API ----------------

    def _ensure_client(self) -> OpenAIClient:
        """
        Lazily create or return the client. Avoids import-time dependency on openai package.
        """
        if self._injected_client is not None:
            return self._injected_client

        if self._client is not None:
            return self._client

        # Lazy import to avoid hard dependency at module import time.
        try:
            from openai import AsyncOpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("Failed to import openai SDK. Provide an injected client or install the openai package.") from exc

        # Create client (SDK may differ across versions; using AsyncOpenAI when available)
        self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    def translate(self, text: str, src: str, tgt: str) -> Optional[TranslationResult]:
        """
        Synchronous wrapper around `translate_async`. Runs on the current event loop or creates one if needed.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an existing event loop (e.g., test frameworks). Run in a new task and wait.
            return asyncio.run(self.translate_async(text, src, tgt))  # safe in most sync contexts
        else:
            return asyncio.get_event_loop().run_until_complete(self.translate_async(text, src, tgt))

    async def translate_async(self, text: str, src: str, tgt: str) -> Optional[TranslationResult]:
        """
        Translate `text` from `src` to `tgt` using OpenAI chat/completion.

        Returns TranslationResult or None on failure.
        """
        if not text:
            return None

        client = self._ensure_client()
        prompt = self.user_prompt_template.format(src=src or "auto", tgt=tgt, text=text)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        attempt = 0
        last_exc: Optional[BaseException] = None

        while attempt < self.max_retries:
            attempt += 1
            start_ts = time.perf_counter()
            try:
                call_coro = self._invoke_chat_call(client, model=self.model, messages=messages, temperature=self.temperature)

                if self.default_timeout is not None:
                    resp = await asyncio.wait_for(call_coro, timeout=self.default_timeout)
                else:
                    resp = await call_coro

                elapsed = time.perf_counter() - start_ts

                # Parse response robustly across SDK variants
                translated_text = _extract_translated_text_from_response(resp)
                if translated_text is None:
                    # Unexpected shape; include raw response for diagnostics
                    logger.debug("OpenAIAdapter: unexpected response shape: %r", resp)
                    translated_text = _safe_str(resp)

                return TranslationResult(
                    translated_text=translated_text.strip(),
                    model=self.model,
                    provider="openai",
                    raw=resp,
                    elapsed_seconds=elapsed,
                )
            except asyncio.TimeoutError as te:
                last_exc = te
                last_err = "timeout"
                logger.debug("OpenAIAdapter: attempt %d timed out", attempt, exc_info=True)
            except Exception as exc:
                last_exc = exc
                last_err = f"{type(exc).__name__}: {exc}"
                logger.debug("OpenAIAdapter: attempt %d failed: %s", attempt, last_err, exc_info=True)

            # Retry logic with jittered backoff
            if attempt < self.max_retries:
                backoff = self.retry_backoff * (2 ** (attempt - 1))
                sleep_for = backoff + random.uniform(0, min(backoff, 0.5))
                await asyncio.sleep(sleep_for)
            else:
                break

        logger.warning("OpenAIAdapter: all %d attempts failed, last error: %s", self.max_retries, last_exc)
        return None

    # ---------------- Internal helpers ----------------

    async def _invoke_chat_call(self, client: OpenAIClient, *, model: str, messages: list, temperature: float) -> Any:
        """
        Best-effort wrapper to call a chat/completion method on the injected or constructed client.
        Supports multiple SDK shapes:
         - client.chat.completions.create(...) (async)
         - client.chat.completions.create(...) (sync) -> run in thread
         - client.chat.completions.acreate(...) (async)
         - client.create(...) directly (older wrappers)
        """
        # Common entrypoints to try in order
        # Use attribute checks rather than assumptions to support different SDKs.
        # Try async 'acreate' first, then 'create' coroutine, then sync 'create' (run in thread), then fallback.
        # Prefer the nested path client.chat.completions.create/acreate per modern SDK.
        callables = []

        # Try nested shapes
        try:
            chat = getattr(client, "chat", None)
            if chat is not None:
                completions = getattr(chat, "completions", None)
                if completions is not None:
                    acreate = getattr(completions, "acreate", None)
                    create = getattr(completions, "create", None)
                    if acreate:
                        callables.append(("acreate", acreate))
                    if create:
                        callables.append(("create", create))
        except Exception:
            pass

        # Try top-level shims used by some wrappers
        try:
            acreate_top = getattr(client, "acreate", None)
            create_top = getattr(client, "create", None)
            if acreate_top:
                callables.append(("acreate_top", acreate_top))
            if create_top:
                callables.append(("create_top", create_top))
        except Exception:
            pass

        # Finally, try legacy ChatCompletion API style: client.ChatCompletion.acreate/create
        try:
            ChatCompletion = getattr(client, "ChatCompletion", None)
            if ChatCompletion is not None:
                acreate_cc = getattr(ChatCompletion, "acreate", None)
                create_cc = getattr(ChatCompletion, "create", None)
                if acreate_cc:
                    callables.append(("ChatCompletion.acreate", acreate_cc))
                if create_cc:
                    callables.append(("ChatCompletion.create", create_cc))
        except Exception:
            pass

        if not callables:
            raise RuntimeError("OpenAIAdapter: injected client has no recognized chat/completion methods.")

        # Try callables in order until one works
        last_exc: Optional[BaseException] = None
        for name, fn in callables:
            try:
                # Determine if coroutine function
                if inspect.iscoroutinefunction(fn):
                    # Many SDKs expect named args similar to: model=..., messages=..., temperature=...
                    return await fn(model=model, messages=messages, temperature=temperature)
                else:
                    # Synchronous call: run in thread
                    return await asyncio.to_thread(fn, model=model, messages=messages, temperature=temperature)
            except TypeError:
                # Try alternate signature (older APIs may expect different param names)
                try:
                    if inspect.iscoroutinefunction(fn):
                        return await fn({"model": model, "messages": messages})
                    else:
                        return await asyncio.to_thread(fn, {"model": model, "messages": messages})
                except Exception as exc:
                    last_exc = exc
                    logger.debug("OpenAIAdapter: fallback call failed for %s: %s", name, exc, exc_info=True)
            except Exception as exc:
                last_exc = exc
                logger.debug("OpenAIAdapter: call failed for %s: %s", name, exc, exc_info=True)

        # If none of the callables succeeded, raise the last exception to be handled by caller.
        raise last_exc or RuntimeError("OpenAIAdapter: all call attempts failed")

# ---------------- Utility functions ----------------


def _extract_translated_text_from_response(resp: Any) -> Optional[str]:
    """
    Extract translated text from various response shapes returned by OpenAI SDKs.
    Accepts objects with attributes or dict-like responses.

    Common shapes:
    - resp.choices[0].message.content (object)
    - resp["choices"][0]["message"]["content"] (dict)
    - resp.choices[0].message['content']
    - resp.choices[0].text (older completion)
    """
    try:
        # Try attribute access (SDK object)
        choices = getattr(resp, "choices", None)
        if choices:
            first = choices[0]
            # message.content
            msg = getattr(first, "message", None)
            if msg is not None:
                content = getattr(msg, "content", None)
                if isinstance(content, str):
                    return content
            # direct text
            text = getattr(first, "text", None)
            if isinstance(text, str):
                return text
    except Exception:
        pass

    try:
        # Try dict-like access
        if isinstance(resp, dict):
            ch = resp.get("choices")
            if ch and len(ch) > 0:
                first = ch[0]
                # nested message dict
                msg = first.get("message") if isinstance(first, dict) else None
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str):
                        return content
                # older 'text' key
                text = first.get("text")
                if isinstance(text, str):
                    return text
    except Exception:
        pass

    return None


def _safe_str(obj: Any) -> str:
    try:
        return str(obj)
    except Exception:
        return "<unprintable>"

# Future Extensions (TODO):
# - TODO: Add adapter-level telemetry (latency, success/fail counts) via an injectable metrics client.
# - TODO: Add circuit-breaker to avoid sustained calls under failure storms.
# - TODO: Expose more fine-grained prompt templates and unit tests for edge-case translations (HTML, code, markup).
# - TODO: Consider returning a unified `TranslationResult` for all translators and update ProcessingEngine if needed.
# - TODO: Add more robust detection/normalization of `src` language (accept language hints, detect auto).