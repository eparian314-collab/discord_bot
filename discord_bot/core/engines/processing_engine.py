from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Dict, List, Optional, Union

from discord_bot.language_context.translation_job import TranslationJob
from discord_bot.core.engines.base.logging_utils import get_logger

_logger = get_logger("processing_engine")


class ProcessingEngine:
    """
    Executes TranslationJob objects using translator adapters.

    Features:
      - Optional `orchestrator` injection: if provided, ProcessingEngine will prefer
        calling the orchestrator's translation API (job- or text-based) and will
        only fall back to the adapter chain if orchestrator is absent or fails.
      - adapters can be registered with optional metadata: provider_id, timeout, priority
      - adapter.translate may be async or sync; both are supported
      - adapter may return a plain string, a dict-like (with 'text'), or an object with `.text`
      - per-adapter timeout applied (default_timeout used when not specified)
      - errors are reported to error_engine.log_error() if present (sync or async)
      - returns translated string on success; falls back to original job.text on failure
    """

    def __init__(
        self,
        *,
        cache_manager: Any = None,
        error_engine: Any = None,
        orchestrator: Optional[Any] = None,
        default_timeout: float = 6.0,
    ) -> None:
        self.cache = cache_manager
        self.error_engine = error_engine
        self.orchestrator = orchestrator
        self.default_timeout = float(default_timeout or 6.0)

        # Internal adapter registry: list of dicts { adapter, provider_id, timeout, priority }
        self._adapters: List[Dict[str, Any]] = []

    # -----------------------
    # Registration / wiring
    # -----------------------
    def add_adapter(self, adapter: Any, *, provider_id: Optional[str] = None, timeout: Optional[float] = None, priority: int = 100) -> None:
        """
        Register an adapter with optional metadata. Backwards-compatible with simple adapter objects.
        """
        entry = {"adapter": adapter, "provider_id": provider_id or getattr(adapter, "provider_id", None), "timeout": timeout, "priority": int(priority)}
        self._adapters.append(entry)

    def set_adapters(self, adapters: List[Union[Any, Dict[str, Any]]]) -> None:
        """
        Replace adapters list. Accepts either adapter objects or dict entries with metadata.
        """
        self._adapters = []
        for a in adapters:
            if isinstance(a, dict):
                self._adapters.append(a)
            else:
                self.add_adapter(a)

    def set_orchestrator(self, orchestrator: Optional[Any]) -> None:
        """Attach or replace the orchestrator used by this engine."""
        self.orchestrator = orchestrator

    # -----------------------
    # Error logging helper
    # -----------------------
    async def _safe_log_error(self, exc: Exception, *, context: Optional[str] = None) -> None:
        """
        Call error_engine.log_error safely whether it's sync or async.
        """
        try:
            if not self.error_engine:
                _logger.exception("adapter/orchestrator error (%s): %s", context or "processing", exc)
                return
            log_fn = getattr(self.error_engine, "log_error", None)
            if not log_fn:
                _logger.exception("adapter/orchestrator error (%s): %s", context or "processing", exc)
                return
            maybe = log_fn(exc, context=context)
            if asyncio.iscoroutine(maybe):
                await maybe
        except Exception:
            _logger.exception("error_engine.log_error raised while handling exception")

    # -----------------------
    # Adapter invocation
    # -----------------------
    async def _invoke_adapter(self, adapter: Any, text: str, src: str, tgt: str, timeout: Optional[float]) -> Any:
        """
        Invoke adapter.translate in a safe way. Accepts async/sync and applies timeout.
        Returns raw adapter return value or raises exception.
        """
        effective_timeout = float(timeout) if timeout is not None else self.default_timeout
        try:
            translate_async = getattr(adapter, "translate_async", None)
            if callable(translate_async):
                maybe = translate_async(text, src, tgt)
                if inspect.isawaitable(maybe):
                    return await asyncio.wait_for(maybe, timeout=effective_timeout)
                return maybe

            translate_fn = getattr(adapter, "translate", None)
            call = translate_fn if callable(translate_fn) else adapter

            # coroutine function
            if asyncio.iscoroutinefunction(call):
                coro = call(text, src, tgt)
                return await asyncio.wait_for(coro, timeout=effective_timeout)

            # callable but sync -> run in executor
            if callable(call):
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(loop.run_in_executor(None, lambda: call(text, src, tgt)), timeout=effective_timeout)
                return result

            # call may be a coroutine object
            if asyncio.iscoroutine(call):
                return await asyncio.wait_for(call, timeout=effective_timeout)

            raise TypeError("adapter has no callable translate interface")
        except Exception:
            raise

    def _normalize_adapter_result(self, raw: Any) -> Optional[str]:
        """
        Try to extract a string translation from various adapter/orchestrator return shapes.
        """
        if raw is None:
            return None
        # plain string
        if isinstance(raw, str):
            return raw
        # dict-like
        if isinstance(raw, dict):
            for k in ("text", "translated", "translatedText", "translation"):
                v = raw.get(k)
                if isinstance(v, str) and v:
                    return v
            for v in raw.values():
                if isinstance(v, str) and v:
                    return v
            return None
        # object with attribute 'text' or 'translated'
        text_attr = getattr(raw, "text", None)
        if isinstance(text_attr, str) and text_attr:
            return text_attr
        translated_attr = getattr(raw, "translated", None)
        if isinstance(translated_attr, str) and translated_attr:
            return translated_attr
        # last resort: string conversion if non-empty
        try:
            s = str(raw)
            if s:
                return s
        except Exception:
            pass
        return None

    # -----------------------
    # Orchestrator invocation
    # -----------------------
    async def _invoke_orchestrator(self, job: TranslationJob, timeout: Optional[float]) -> Any:
        """
        Call the attached orchestrator, supporting both job-based and text-based APIs.
        Returns raw orchestrator result (various shapes).
        """
        if not self.orchestrator:
            return None

        # Guard: avoid calling orchestrator if it appears to directly call back to this engine's execute_job
        # (best effort; avoid infinite recursion)
        try:
            # if orchestrator.translate_job is this.execute_job (unlikely), skip
            if getattr(self.orchestrator, "translate_job", None) is getattr(self, "execute_job", None):
                _logger.debug("orchestrator.translate_job appears to be bound to ProcessingEngine.execute_job; skipping to avoid recursion")
                return None
        except Exception:
            # ignore guard failures and attempt call
            pass

        # Prefer job-based API
        try:
            if hasattr(self.orchestrator, "translate_job"):
                maybe = self.orchestrator.translate_job(job)
                if asyncio.iscoroutine(maybe):
                    return await asyncio.wait_for(maybe, timeout=timeout or self.default_timeout)
                return maybe

            # Fallback to text-oriented API
            if hasattr(self.orchestrator, "translate_text_for_user"):
                maybe = self.orchestrator.translate_text_for_user(text=job.text, guild_id=job.guild_id, user_id=job.author_id, tgt_lang=job.tgt_lang)
                if asyncio.iscoroutine(maybe):
                    return await asyncio.wait_for(maybe, timeout=timeout or self.default_timeout)
                return maybe

        except asyncio.TimeoutError:
            raise
        except Exception:
            raise

        return None

    # -----------------------
    # Main execution entry
    # -----------------------
    async def execute_job(self, job: TranslationJob, *, timeout: Optional[float] = None) -> Optional[str]:
        """
        Execute the TranslationJob by calling the orchestrator (preferred) or
        registered adapters in priority order. Returns the translated string on
        success or the original job.text on complete failure. Returns None if job falsy.
        """
        if not job or not job.text:
            return None

        text = job.text
        # Support both older TranslationJob (src/tgt) and newer (src_lang/tgt_lang)
        src = getattr(job, "src_lang", None) or getattr(job, "src", None)
        tgt = getattr(job, "tgt_lang", None) or getattr(job, "tgt", None)
        metadata = job.metadata if isinstance(getattr(job, "metadata", None), dict) else {}
        preferred_providers = [str(p).lower() for p in metadata.get("preferred_providers", []) if isinstance(p, str) and p]
        _logger.info(
            "📝 execute_job start: job=%s len=%d src=%s tgt=%s guild=%s user=%s",
            job.short(),
            len(text),
            src,
            tgt,
            job.guild_id,
            job.author_id,
        )

        # 1) Try orchestrator path first (if configured)
        if self.orchestrator:
            orchestrator_name = getattr(self.orchestrator, "__class__", type(self.orchestrator)).__name__
            started = time.perf_counter()
            try:
                raw = await self._invoke_orchestrator(job, timeout)
                elapsed = time.perf_counter() - started
                translated = self._normalize_adapter_result(raw)
                if translated:
                    _logger.info(
                        "🧠 orchestrator success: job=%s provider=%s elapsed=%.2fs len=%d",
                        job.short(),
                        orchestrator_name,
                        elapsed,
                        len(translated),
                    )
                    return translated
                _logger.debug(
                    "orchestrator empty result: job=%s provider=%s elapsed=%.2fs",
                    job.short(),
                    orchestrator_name,
                    elapsed,
                )
            except asyncio.TimeoutError:
                elapsed = time.perf_counter() - started
                _logger.warning(
                    "orchestrator timeout: job=%s provider=%s elapsed=%.2fs",
                    job.short(),
                    orchestrator_name,
                    elapsed,
                )
                try:
                    await self._safe_log_error(asyncio.TimeoutError("orchestrator timeout"), context="orchestrator")
                except Exception:
                    pass
                # fallthrough to adapters
            except Exception as e:
                elapsed = time.perf_counter() - started
                _logger.warning(
                    "orchestrator error: job=%s provider=%s elapsed=%.2fs err=%s",
                    job.short(),
                    orchestrator_name,
                    elapsed,
                    type(e).__name__,
                )
                try:
                    await self._safe_log_error(e, context="orchestrator")
                except Exception:
                    pass
                # fallthrough to adapters

        # 2) Try adapters in priority order
        def _provider_label(entry: Dict[str, Any]) -> str:
            adapter = entry.get("adapter")
            raw_provider = entry.get("provider_id") or getattr(adapter, "provider_id", None)
            if isinstance(raw_provider, type):
                label = raw_provider.__name__
            elif isinstance(raw_provider, str) and raw_provider:
                label = raw_provider
            elif hasattr(adapter, "__class__"):
                label = adapter.__class__.__name__
            else:
                label = type(adapter).__name__
            return str(label)

        def _adapter_sort_key(entry: Dict[str, Any]) -> tuple:
            label = _provider_label(entry).lower()
            try:
                pref_index = preferred_providers.index(label)
            except ValueError:
                pref_index = len(preferred_providers)
            return (pref_index, int(entry.get("priority", 100)))

        adapters_sorted = sorted(self._adapters, key=_adapter_sort_key)
        for entry in adapters_sorted:
            adapter = entry.get("adapter")
            timeout_option = entry.get("timeout", None)
            provider_label = _provider_label(entry)
            started = time.perf_counter()
            try:
                raw = await self._invoke_adapter(adapter, text, src, tgt, timeout_option)
                elapsed = time.perf_counter() - started
                translated = self._normalize_adapter_result(raw)
                if translated:
                    _logger.info(
                        "🌐 adapter success: job=%s provider=%s elapsed=%.2fs len=%d",
                        job.short(),
                        provider_label,
                        elapsed,
                        len(translated),
                    )
                    return translated
                _logger.debug(
                    "adapter empty result: job=%s provider=%s elapsed=%.2fs",
                    job.short(),
                    provider_label,
                    elapsed,
                )
            except Exception as e:
                elapsed = time.perf_counter() - started
                _logger.warning(
                    "adapter error: job=%s provider=%s elapsed=%.2fs err=%s",
                    job.short(),
                    provider_label,
                    elapsed,
                    type(e).__name__,
                )
                ctx = f"adapter.{provider_label}"
                try:
                    await self._safe_log_error(e, context=ctx)
                except Exception:
                    _logger.exception("failed to log adapter error for %s", ctx)
                continue

        # 3) All providers failed; return None to indicate failure
        _logger.warning("all translation providers failed; returning None for job=%s", job.short())
        return None
