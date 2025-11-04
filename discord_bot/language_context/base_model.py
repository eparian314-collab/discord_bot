from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Optional, Union, Coroutine


@dataclass
class TranslationResult:
    """
    Structured translation result returned by provider adapters or by the
    orchestrator when wrapping provider responses.

    Matches shape used elsewhere in the project:
      {
        "text": "<translated string or null>",
        "src": "<detected src code>",
        "tgt": "<target code>",
        "provider": "<deepl|mymemory|null>",
        "confidence": 0.0,
        "meta": { "error": "...", "timings": {...}, "provider_info": {...} }
      }
    """
    text: Optional[str]
    src: str
    tgt: str
    provider: Optional[str]
    confidence: float = 0.0
    meta: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalize_code(code: Optional[str]) -> str:
    if not code:
        return "en"
    s = str(code).strip().lower()
    if "-" in s:
        return s.split("-", 1)[0]
    return s


class BaseModel:
    """
    Base helper for translation provider adapters and higher-level wrapper logic.

    Responsibilities:
    - Provide a small, consistent execution wrapper for calling provider adapters
      with timeout, timing, and error normalization.
    - Produce a `TranslationResult` from adapter output (or failure).
    - Offer small utilities such as language code normalization.

    Subclasses (or adapter wrappers) should call `self.run_translate_call(...)`
    or implement `async def translate(self, text, src, tgt)` and return either a
    raw string or a `TranslationResult`.
    """

    def __init__(self, provider_id: str, *, timeout: float = 6.0) -> None:
        self.provider_id = provider_id
        self.timeout = float(timeout or 6.0)
        self.logger = logging.getLogger(f"translation.{provider_id}")

    async def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        """
        Default entrypoint expected from orchestrator-compatible adapters.
        Override in concrete adapters when custom behavior is needed.

        The default implementation assumes a subclass or wrapper will call
        `self._invoke_adapter(...)` or `self.run_translate_call(...)` and
        return a TranslationResult.
        """
        raise NotImplementedError("translate must be implemented by adapter or wrapper")

    async def _invoke_adapter_call(
        self,
        call: Union[Callable[..., Any], Coroutine],
        *args,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Invoke a callable or coroutine with a timeout and return its result.

        Accepts:
          - coroutine function or coroutine object
          - synchronous callable (runs via asyncio.to_thread)

        Raises underlying exceptions (including asyncio.TimeoutError) to caller.
        """
        effective_timeout = float(timeout) if timeout is not None else self.timeout

        try:
            if asyncio.iscoroutine(call):
                return await asyncio.wait_for(call, timeout=effective_timeout)

            if callable(call):
                if asyncio.iscoroutinefunction(call) or asyncio.iscoroutinefunction(getattr(call, "__call__", None)):
                    result = call(*args)
                    if inspect.isawaitable(result):
                        return await asyncio.wait_for(result, timeout=effective_timeout)
                    return result

                result = await asyncio.wait_for(asyncio.to_thread(call, *args), timeout=effective_timeout)
                if inspect.isawaitable(result):
                    return await asyncio.wait_for(result, timeout=effective_timeout)
                return result

            raise TypeError("Provided adapter call must be a callable or coroutine")
        except Exception:
            raise

    async def run_translate_call(
        self,
        adapter_call: Union[Callable[..., Any], Coroutine],
        text: str,
        src: Optional[str],
        tgt: Optional[str],
        *,
        confidence: float = 0.0,
        timeout: Optional[float] = None,
        provider_info: Optional[Dict[str, Any]] = None,
    ) -> TranslationResult:
        """
        High level wrapper to call an adapter, measure timings, and return a
        TranslationResult. This method will catch exceptions and return a
        well-formed result with `text=None` on failure.

        Parameters:
          - adapter_call: either a callable (e.g., adapter.translate) or a coroutine
          - text, src, tgt: translation request parameters
          - confidence: optional detection confidence to include in result
          - timeout: override per-call timeout
          - provider_info: optional provider metadata included in result.meta

        Behavior:
          - Returns TranslationResult with provider=self.provider_id on success.
          - On exception or timeout returns TranslationResult with text=None and
            meta.error populated.
        """
        start = time.monotonic()
        meta: Dict[str, Any] = {"timings": {}, "provider_info": provider_info or {}}
        try:
            result = await self._invoke_adapter_call(adapter_call, text, src, tgt, timeout=timeout)
            elapsed = time.monotonic() - start
            meta["timings"]["elapsed"] = elapsed

            # Adapter may return either a string (translated text) or a dict-like result.
            if isinstance(result, dict):
                translated = result.get("text")
                prov_info = result.get("meta", {}).get("provider_info") or result.get("provider_info") or {}
                meta["provider_info"].update(prov_info)
            else:
                translated = result

            tr = TranslationResult(
                text=translated if isinstance(translated, str) else (str(translated) if translated is not None else None),
                src=_normalize_code(src),
                tgt=_normalize_code(tgt),
                provider=self.provider_id,
                confidence=float(confidence or 0.0),
                meta=meta,
            )
            return tr
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            meta["timings"]["elapsed"] = elapsed
            meta["error"] = "timeout"
            self.logger.warning("translation timeout (provider=%s, timeout=%s)", self.provider_id, timeout or self.timeout)
            return TranslationResult(text=None, src=_normalize_code(src), tgt=_normalize_code(tgt), provider=None, confidence=float(confidence or 0.0), meta=meta)
        except Exception as exc:  # capture other adapter errors
            elapsed = time.monotonic() - start
            meta["timings"]["elapsed"] = elapsed
            meta["error"] = f"{type(exc).__name__}: {str(exc)}"
            # Attach minimal provider debug info
            meta.setdefault("provider_info", {})["error_detail"] = getattr(exc, "args", repr(exc))
            self.logger.exception("adapter call failed for provider=%s", self.provider_id)
            return TranslationResult(text=None, src=_normalize_code(src), tgt=_normalize_code(tgt), provider=None, confidence=float(confidence or 0.0), meta=meta)


