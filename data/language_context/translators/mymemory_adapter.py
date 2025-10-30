# MyMemoryAdapter: async, resilient adapter for MyMemory (mymemory.translated.net)
#
# READING GUIDE:
# - The ProcessingEngine expects to call this adapter as an awaitable: `await adapter(job)`.
#   The adapter returns a dict matching the engine's expected shape:
#       { "ok": bool, "text": Optional[str], "engine_used": "mymemory", "latency_ms": int, "error": Optional[str], "src": Optional[str], "tgt": Optional[str] }
# - Use `MyMemoryAdapter(...)` to construct. Prefer injecting an `aiohttp.ClientSession` for connection pooling in long-lived services.
# - This module is rule-first and I/O-only; it does not perform routing or downstream transformations.
#
# PURPOSE & SCOPE:
# - Provide an injection-friendly, testable adapter for MyMemory API with:
#     - async requests, optional session injection
#     - retries with exponential backoff and jitter
#     - light rate-limiting (token-slot style) with asyncio lock for concurrency safety
#     - graceful failure (returns failure dict rather than raising)
# - Keep integration points minimal: an optional `get_error_engine()` is used if present in the project for error reporting.
#
# NOTES:
# - The adapter returns plain dicts so downstream ProcessingEngine code does not need changing.
# - AI is not used here. Any ML-based improvements belong in other components.
# - If you need to change return shapes to a dataclass, update ProcessingEngine normalization accordingly.
#
# TODOs at bottom indicate possible future improvements (timeouts, circuit-breaker, telemetry).
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Optional: if your project exposes get_error_engine, import it; otherwise provide a noop.
try:
    from discord_bot.core.engines.error_engine import get_error_engine  # type: ignore
except Exception:
    def get_error_engine():
        return None  # type: ignore


# Public API names
__all__ = ["MyMemoryAdapter", "TranslationDict", "TranslationResult"]


@dataclass(frozen=True)
class TranslationResult:
    """
    Structured representation of a translation attempt.

    Note: ProcessingEngine currently expects a dict; use `to_dict()` to convert.
    """
    ok: bool
    text: Optional[str]
    engine_used: str
    latency_ms: int
    error: Optional[str]
    src: Optional[str]
    tgt: Optional[str]
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "text": self.text,
            "engine_used": self.engine_used,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "src": self.src,
            "tgt": self.tgt,
            "raw": self.raw,
        }


# Keep backward-compatible alias to the dict shape expected by ProcessingEngine
TranslationDict = Dict[str, Any]


class MyMemoryAdapter:
    """
    Production-grade MyMemory adapter (async, retries, backoff, light rate-limit).

    Construction parameters:
    - user_email: optional email used for MyMemory 'de' identity param
    - api_key: optional API key issued by MyMemory (mutually compatible with user_email)
    - timeout_s: per-request timeout in seconds
    - max_retries: number of retries (0 means single attempt)
    - initial_backoff_s: initial backoff base in seconds (exponential backoff applied)
    - per_sec_limit: approximate allowed requests per second (simple slot-based throttle)
    - session: optional aiohttp.ClientSession injected by caller (preferred for reuse)

    Usage:
        adapter = MyMemoryAdapter(user_email="bot@example.com")
        result_dict = await adapter(job)  # job must have attributes: text, src, tgt

    The adapter is resilient: it returns a failure dict on error rather than raising.
    """

    BASE_URL = "https://api.mymemory.translated.net/get"
    PROVIDER = "mymemory"

    def __init__(
        self,
        *,
        user_email: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_s: float = 8.0,
        max_retries: int = 3,
        initial_backoff_s: float = 0.5,
        per_sec_limit: float = 4.0,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self.user_email = user_email
        self.api_key = api_key
        self.timeout_s = max(1.0, float(timeout_s))
        self.max_retries = max(0, int(max_retries))
        self.initial_backoff_s = max(0.05, float(initial_backoff_s))
        self.per_sec_limit = max(0.5, float(per_sec_limit))
        self._session = session
        self._err = get_error_engine()

        # token slot: next allowed timestamp for a single token
        self._next_slot_ts = 0.0
        # lock to protect _next_slot_ts in concurrent usage
        self._slot_lock = asyncio.Lock()

    # ------------------------------------------------------------
    # Public API (ProcessingEngine will call this)
    # ------------------------------------------------------------
    
    def supported_languages(self) -> list[str]:
        """
        Return list of supported target language codes.
        
        MyMemory supports a very broad range of languages. This list includes
        major world languages that MyMemory can translate to. For rare languages,
        Google Translate (tier 3) may provide better coverage.
        """
        # MyMemory supports many languages - this is a curated list of well-supported ones
        return [
            "ar", "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr",
            "he", "hi", "hr", "hu", "id", "it", "ja", "ko", "lt", "lv", "ms",
            "mt", "nl", "no", "pl", "pt", "ro", "ru", "sk", "sl", "sq", "sr",
            "sv", "th", "tl", "tr", "uk", "vi", "zh", "zh-cn", "zh-tw"
        ]
    
    async def translate_async(self, text: str, src: Optional[str], tgt: str) -> Optional[str]:
        """
        Translate text asynchronously.
        
        Args:
            text: Text to translate
            src: Source language code (or None for auto-detect)
            tgt: Target language code
            
        Returns:
            Translated text string or None on failure
        """
        # Create a minimal job object that __call__ expects
        class Job:
            pass
        
        job = Job()
        job.text = text
        job.src = src
        job.tgt = tgt
        
        result_dict = await self(job)
        
        # Extract text from result dict
        if result_dict.get("ok"):
            return result_dict.get("text")
        return None
    
    async def __call__(self, job: Any) -> TranslationDict:
        """
        Perform a translation job.

        job: an object with attributes `text`, `src`, `tgt`
        Returns: dict shaped result (see READING GUIDE).
        """
        started = time.perf_counter()

        text = getattr(job, "text", None) or ""
        src = self._normalize_lang(getattr(job, "src", None))
        tgt = self._normalize_lang(getattr(job, "tgt", None))

        if not text or not tgt:
            return self._fail_result("missing text or target language", started, src, tgt)

        params = {
            "q": text,
            "langpair": f"{src or 'auto'}|{tgt}",
        }
        if self.user_email:
            params["de"] = self.user_email
        if self.api_key:
            params["key"] = self.api_key

        # Throttle to respect per_sec_limit
        await self._throttle()

        backoff = self.initial_backoff_s
        last_error: Optional[str] = None
        owns_session = False
        session = self._session

        if session is None:
            session = aiohttp.ClientSession()
            owns_session = True

        try:
            # Perform attempts: initial try + max_retries
            for attempt in range(self.max_retries + 1):
                attempt_start = time.perf_counter()
                try:
                    timeout = aiohttp.ClientTimeout(total=self.timeout_s)
                    async with session.get(self.BASE_URL, params=params, timeout=timeout) as resp:
                        status = resp.status
                        # allow APIs that return non-json content-type header; pass content_type=None to parse heuristically
                        data = await resp.json(content_type=None)
                        # Expected payload:
                        #  {
                        #    "responseData":{"translatedText":"..."},
                        #    "quotaFinished": False,
                        #    "responseStatus":200,
                        #    "responseDetails":""
                        #  }
                        if status == 200 and data:
                            code = int(data.get("responseStatus", status))
                            if code == 200:
                                translated = (data.get("responseData", {}) or {}).get("translatedText") or ""
                                return self._ok_result(translated, started, src, tgt, raw=data)
                            else:
                                last_error = f"HTTP 200 but API status {code}: {data.get('responseDetails')}"
                        else:
                            last_error = f"HTTP {status}"
                except asyncio.TimeoutError:
                    last_error = "timeout"
                except aiohttp.ClientError as ce:
                    last_error = f"client_error: {type(ce).__name__}: {ce}"
                except Exception as e:
                    last_error = f"unexpected: {type(e).__name__}: {e}"

                # If we will retry, sleep with jitter
                if attempt < self.max_retries:
                    sleep_for = backoff + random.uniform(0, min(backoff, 0.5))
                    logger.debug("MyMemoryAdapter: attempt %d failed (%s), backing off %.2fs", attempt + 1, last_error, sleep_for)
                    await asyncio.sleep(sleep_for)
                    backoff *= 2.0
                else:
                    # final failure
                    break

            # Log failure to project's error engine if available (best-effort)
            if self._err and hasattr(self._err, "log_error"):
                try:
                    # prefer an async log_error; support sync as well
                    maybe_coro = self._err.log_error(Exception(last_error or "mymemory failed"), source=self.PROVIDER, category="adapter",
                                                    context={"src": src, "tgt": tgt})
                    if asyncio.iscoroutine(maybe_coro):
                        await maybe_coro
                except Exception:
                    # avoid failing adapter because of logging problems
                    logger.debug("MyMemoryAdapter: error engine logging failed", exc_info=True)

            return self._fail_result(last_error or "adapter failed", started, src, tgt)
        finally:
            if owns_session:
                try:
                    await session.close()
                except Exception:
                    logger.debug("MyMemoryAdapter: closing session failed", exc_info=True)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _ok_result(self, text: str, started: float, src: Optional[str], tgt: Optional[str], raw: Optional[Dict[str, Any]] = None) -> TranslationDict:
        latency_ms = int((time.perf_counter() - started) * 1000)
        res = TranslationResult(
            ok=True,
            text=text,
            engine_used=self.PROVIDER,
            latency_ms=latency_ms,
            error=None,
            src=src,
            tgt=tgt,
            raw=raw,
        )
        return res.to_dict()

    def _fail_result(self, msg: str, started: float, src: Optional[str], tgt: Optional[str], raw: Optional[Dict[str, Any]] = None) -> TranslationDict:
        latency_ms = int((time.perf_counter() - started) * 1000)
        res = TranslationResult(
            ok=False,
            text=None,
            engine_used=self.PROVIDER,
            latency_ms=latency_ms,
            error=msg,
            src=src,
            tgt=tgt,
            raw=raw,
        )
        return res.to_dict()

    async def _throttle(self) -> None:
        """
        Very light rate limit: at most ~per_sec_limit requests/sec.

        Implemented with a slot timestamp and an asyncio.Lock to make access concurrency-safe.
        """
        interval = 1.0 / self.per_sec_limit
        async with self._slot_lock:
            now = time.time()
            if now < self._next_slot_ts:
                sleep_for = self._next_slot_ts - now
                logger.debug("MyMemoryAdapter: throttle sleeping %.3fs to respect per_sec_limit", sleep_for)
                await asyncio.sleep(sleep_for)
                now = time.time()
            # consume the next slot
            self._next_slot_ts = max(now, self._next_slot_ts) + interval

    def _normalize_lang(self, code: Optional[str]) -> Optional[str]:
        """
        Normalize common language tags into MyMemory-friendly codes.
        MyMemory expects mostly ISO-639-1 (e.g., 'en', 'es', 'ja', 'zh-CN', 'pt').
        """
        if not code:
            return None
        c = code.strip().lower()

        MAP = {
            "en-us": "en", "en-gb": "en", "en_usa": "en", "en_uk": "en",
            "pt-br": "pt", "pt_pt": "pt",
            "zh": "zh-CN", "zh-cn": "zh-CN", "zh_tw": "zh-TW", "zh-hans": "zh-CN", "zh-hant": "zh-TW",
        }
        return MAP.get(c, c)

# Future Extensions (TODO):
# - TODO: Add adapter-level timeout enforcement via `asyncio.wait_for` for each attempt (careful with session timeouts).
# - TODO: Add circuit-breaker or bulkhead pattern to avoid hammering the provider after repeated failures.
# - TODO: Expose hooks for telemetry (latency, success/failure counts) via an injectable metrics client.
# - TODO: Support batching or request coalescing for repeated identical translations to reduce calls.
# - TODO: Add unit tests that inject a fake `aiohttp.ClientSession` to simulate success, HTTP errors, and timeouts.
#
# Testing notes:
# - Tests should verify throttle behavior under concurrency by creating multiple concurrent `__call__` invocations.
# - Tests should mock responses with non-standard payload shapes to ensure diagnostics are returned in the `raw` field.
#
# Security note:
# - Be careful not to log or persist sensitive user text. If required, sanitize logs or avoid logging full payloads.
