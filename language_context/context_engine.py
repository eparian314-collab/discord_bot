from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from discord_bot.language_context.translation_job import TranslationJob
from discord_bot.language_context.context_models import (
    TranslationRequest,
    TranslationResponse,
    JobEnvironment,
)

_logger = logging.getLogger(__name__)


class ContextEngine:
    def __init__(
        self,
        *,
        role_manager,
        cache_manager,
        error_engine=None,
        alias_helper: Optional[Any] = None,
        ambiguity_resolver: Optional[Any] = None,
        localization_registry: Optional[Any] = None,
        detection_service: Optional[Any] = None,
    ) -> None:
        """
        ContextEngine coordinates language resolution and job planning.

        New/optional injections:
          - detection_service: object exposing `detect_language(text) -> (lang, confidence)` or `lang`
            (supports sync or async functions).
          - error_engine: optional engine with `log_error(exc, context)` for reporting.

        Existing injections retained:
          - role_manager
          - cache_manager
          - alias_helper
          - ambiguity_resolver
          - localization_registry
        """
        self.roles = role_manager
        self.cache = cache_manager
        self.error_engine = error_engine
        self.alias_helper = alias_helper
        self.ambiguity_resolver = ambiguity_resolver
        self.localization = localization_registry
        self.detector = detection_service

    def _log_error(self, exc: Exception, *, context: str) -> None:
        """Report errors through the injected error engine when available."""
        if not self.error_engine or not hasattr(self.error_engine, "log_error"):
            return
        try:
            result = self.error_engine.log_error(exc, context=context)
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    asyncio.run(result)
        except Exception:
            pass

    # -------------------------
    # Planning / job creation
    # -------------------------
    async def plan_for_author(
        self,
        guild_id: int,
        author_id: int,
        *,
        text: str,
        force_tgt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a TranslationJob for the author given the text and optional forced target.
        Uses the configured detector if available (async-aware).
        """
        tgt = self._resolve_target_code(guild_id, author_id, force_tgt)
        src = await self._detect_source_code(text)
        if self._equivalent_lang(src, tgt):
            return {"job": None, "context": {"src": src, "tgt": tgt}}
        job = TranslationJob(
            guild_id=guild_id,
            author_id=author_id,
            text=text,
            src_lang=src,
            tgt_lang=tgt,
        )
        return {"job": job, "context": {"src": src, "tgt": tgt}}

    async def plan_for_pair(
        self,
        guild_id: int,
        author_id: int,
        other_user_id: int,
        *,
        text: str,
        force_tgt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a TranslationJob for a message directed to another user (pair).
        """
        tgt = self._resolve_target_code(guild_id, other_user_id, force_tgt)
        src = await self._detect_source_code(text)
        if self._equivalent_lang(src, tgt):
            return {"job": None, "context": {"src": src, "tgt": tgt, "pair": True}}
        job = TranslationJob(
            guild_id=guild_id,
            author_id=author_id,
            text=text,
            src_lang=src,
            tgt_lang=tgt,
        )
        return {"job": job, "context": {"src": src, "tgt": tgt, "pair": True}}

    async def plan_for_code(
        self,
        guild_id: int,
        author_id: int,
        *,
        text: str,
        code: str,
    ) -> Dict[str, Any]:
        """
        Build a TranslationJob when a target code is provided explicitly.
        """
        tgt = self._normalize_code(code)
        src = await self._detect_source_code(text)
        if self._equivalent_lang(src, tgt):
            return {"job": None, "context": {"src": src, "tgt": tgt, "forced": True}}
        job = TranslationJob(
            guild_id=guild_id,
            author_id=author_id,
            text=text,
            src_lang=src,
            tgt_lang=tgt,
        )
        return {"job": job, "context": {"src": src, "tgt": tgt, "forced": True}}

    # -------------------------
    # Preference & role helpers
    # -------------------------
    async def get_user_preference(self, guild_id: int, user_id: int) -> Optional[str]:
        """
        Return cached user language preference if available.
        Supports sync or async cache implementations:
          - async_get_user_lang(guild_id, user_id)
          - get_user_lang(guild_id, user_id)
        """
        try:
            if hasattr(self.cache, "async_get_user_lang"):
                return await self.cache.async_get_user_lang(guild_id, user_id)
            if hasattr(self.cache, "get_user_lang"):
                return self.cache.get_user_lang(guild_id, user_id)
        except Exception as exc:
            _logger.exception("get_user_preference: cache error")
            self._log_error(exc, context="get_user_preference")
        return None

    async def set_user_preference(self, guild_id: int, user_id: int, code: str) -> None:
        """
        Persist user preference to cache if supported.
        Supports async_set_user_lang or set_user_lang.
        """
        try:
            if hasattr(self.cache, "async_set_user_lang"):
                await self.cache.async_set_user_lang(guild_id, user_id, code)
                return
            if hasattr(self.cache, "set_user_lang"):
                self.cache.set_user_lang(guild_id, user_id, code)
                return
        except Exception as exc:
            _logger.exception("set_user_preference: cache error")
            self._log_error(exc, context="set_user_preference")

    async def get_user_role_languages(self, user_id: int, guild_id: int) -> list:
        """
        Return list of language codes or role names associated with a user via role manager.
        This abstracts role_manager differences; falls back to empty list if not available.
        """
        try:
            if self.roles and hasattr(self.roles, "get_user_languages"):
                maybe = self.roles.get_user_languages(user_id, guild_id)
                if asyncio.iscoroutine(maybe):
                    return await maybe
                return maybe or []
            # some role managers might expose a sync method `get_roles_for_user`
            if self.roles and hasattr(self.roles, "get_roles_for_user"):
                maybe = self.roles.get_roles_for_user(user_id, guild_id)
                if asyncio.iscoroutine(maybe):
                    return await maybe
                # attempt to map role objects/names to language tokens if resolve_code exists
                if isinstance(maybe, (list, tuple)):
                    langs = []
                    for r in maybe:
                        try:
                            token = r.name if hasattr(r, "name") else str(r)
                        except Exception:
                            token = str(r)
                        if self.roles and hasattr(self.roles, "resolve_code"):
                            resolved = self.roles.resolve_code(token)
                            if resolved:
                                langs.append(resolved)
                        else:
                            langs.append(token)
                    return langs
        except Exception as exc:
            _logger.exception("get_user_role_languages: role manager error")
            self._log_error(exc, context="get_user_role_languages")
            return []

    # -------------------------
    # High-level convenience: assemble request & run orchestrator
    # -------------------------
    def prepare_request_from_job(self, job: TranslationJob) -> TranslationRequest:
        """
        Convert a TranslationJob -> TranslationRequest for orchestrator-friendly APIs.
        """
        return TranslationRequest.from_job(job)

    async def execute_job_with_orchestrator(
        self, job: TranslationJob, orchestrator: Optional[Any], *, timeout: Optional[float] = None
    ) -> TranslationResponse:
        """
        Given a prepared TranslationJob, call the orchestrator (if present) and
        normalize the return into a TranslationResponse dataclass.

        This method intentionally does NOT perform any output/UI work. It simply
        returns a structured response which callers (cogs/UI) can render.
        """
        # Default empty response on failures
        default_resp = TranslationResponse(text=None, src=job.src_lang or "en", tgt=job.tgt_lang or "en", provider=None, confidence=0.0, meta={})

        if not job:
            return default_resp

        # If no orchestrator provided, leave responsibility to callers to use processing_engine
        if not orchestrator:
            return default_resp

        try:
            # Prefer job-based API if present
            if hasattr(orchestrator, "translate_job"):
                maybe = orchestrator.translate_job(job)
                if asyncio.iscoroutine(maybe):
                    raw = await asyncio.wait_for(maybe, timeout) if timeout else await maybe
                else:
                    # sync-returning orchestrator.translate_job
                    raw = maybe
                return self._normalize_orchestrator_result(raw, job)

            # Fallback to text-oriented API
            if hasattr(orchestrator, "translate_text_for_user"):
                maybe = orchestrator.translate_text_for_user(text=job.text, guild_id=job.guild_id, user_id=job.author_id, tgt_lang=job.tgt_lang)
                if asyncio.iscoroutine(maybe):
                    raw = await asyncio.wait_for(maybe, timeout) if timeout else await maybe
                else:
                    raw = maybe
                return self._normalize_orchestrator_result(raw, job)

            # Unknown orchestrator interface
            _logger.debug("orchestrator provided but no known translate API found")
            return default_resp
        except asyncio.TimeoutError:
            _logger.warning("orchestrator call timed out for job: guild=%s author=%s", job.guild_id, job.author_id)
            return TranslationResponse(text=None, src=job.src_lang or "en", tgt=job.tgt_lang or "en", provider=None, confidence=0.0, meta={"error": "timeout"})
        except Exception as exc:
            _logger.exception("execute_job_with_orchestrator failed")
            self._log_error(exc, context="execute_job_with_orchestrator")
            return TranslationResponse(text=None, src=job.src_lang or "en", tgt=job.tgt_lang or "en", provider=None, confidence=0.0, meta={"error": str(exc)})

    async def translate_for_author_via_orchestrator(
        self,
        guild_id: int,
        author_id: int,
        orchestrator: Optional[Any],
        *,
        text: str,
        force_tgt: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Convenience combined flow:
          - plan_for_author -> build job
          - execute_job_with_orchestrator -> call orchestrator and return normalized response

        Returns a dict:
          {
            "job": TranslationJob | None,
            "context": { ... },
            "response": TranslationResponse
          }

        This is suitable for cogs that want a single-call high-level operation.
        """
        env = await self.plan_for_author(guild_id, author_id, text=text, force_tgt=force_tgt)
        job = env.get("job")
        context = env.get("context", {})

        if not job:
            # No translation needed � return empty response but include context
            empty = TranslationResponse(text=None, src=context.get("src", "en"), tgt=context.get("tgt", "en"), provider=None, confidence=0.0, meta={"reason": "no_translation_needed"})
            return {"job": None, "context": context, "response": empty}

        resp = await self.execute_job_with_orchestrator(job, orchestrator, timeout=timeout)
        return {"job": job, "context": context, "response": resp}

    # -------------------------
    # Internal normalizers & helpers
    # -------------------------
    def _normalize_orchestrator_result(self, raw: Any, job: TranslationJob) -> TranslationResponse:
        """
        Normalize various possible orchestrator return shapes into a TranslationResponse.

        Accepts:
          - None -> treated as failure
          - str -> translated text (no provider info)
          - dict -> expects keys like 'text','src','tgt','provider','confidence','meta'
          - dataclass/object with similar attributes (e.g., TranslationResult/TranslationResponse)
        """
        if raw is None:
            return TranslationResponse(text=None, src=job.src_lang or "en", tgt=job.tgt_lang or "en", provider=None, confidence=0.0, meta={"error": "no_result"})

        # If it's already a TranslationResponse dataclass
        if isinstance(raw, TranslationResponse):
            return raw

        # If it's a dict-like mapping
        if isinstance(raw, dict):
            text = raw.get("text")
            src = raw.get("src") or job.src_lang or "en"
            tgt = raw.get("tgt") or job.tgt_lang or "en"
            provider = raw.get("provider")
            confidence = float(raw.get("confidence") or 0.0)
            meta = raw.get("meta") or {}
            return TranslationResponse(text=text, src=src, tgt=tgt, provider=provider, confidence=confidence, meta=meta)

        # If it's a plain string
        if isinstance(raw, str):
            return TranslationResponse(text=raw, src=job.src_lang or "en", tgt=job.tgt_lang or "en", provider=None, confidence=0.0, meta={})

        # If it's an object with attributes ( TranslationResult from base_model, etc. )
        try:
            text = getattr(raw, "text", None)
            src = getattr(raw, "src", job.src_lang or "en")
            tgt = getattr(raw, "tgt", job.tgt_lang or "en")
            provider = getattr(raw, "provider", None)
            confidence = float(getattr(raw, "confidence", 0.0) or 0.0)
            meta = getattr(raw, "meta", {}) or {}
            return TranslationResponse(text=text, src=src, tgt=tgt, provider=provider, confidence=confidence, meta=meta)
        except Exception:
            _logger.exception("failed to normalize orchestrator raw result")
            return TranslationResponse(text=None, src=job.src_lang or "en", tgt=job.tgt_lang or "en", provider=None, confidence=0.0, meta={"error": "normalize_failed"})

    # -------------------------
    # Existing internal helpers (kept & slightly hardened)
    # -------------------------
    def _resolve_target_code(self, guild_id: int, user_id: int, force_tgt: Optional[str]) -> str:
        """
        Synchronous resolving of a target token (forced or cached).
        Uses alias_helper, roles.resolve_code and ambiguity resolver hooks.
        """
        if force_tgt:
            forced = self._normalize_code(force_tgt)
            resolved = self._resolve_ambiguity(forced, {"guild_id": guild_id, "user_id": user_id})
            return resolved or forced
        # Cache access kept synchronous here for compatibility; async wrappers exist above.
        try:
            cached = None
            if hasattr(self.cache, "get_user_lang"):
                cached = self.cache.get_user_lang(guild_id, user_id)
            elif hasattr(self.cache, "async_get_user_lang"):
                # if only async API exists, fall back to 'en' here and let callers use get_user_preference
                cached = None
            if cached:
                normalized = self._normalize_code(cached)
                resolved = self._resolve_ambiguity(normalized, {"guild_id": guild_id, "user_id": user_id})
                return resolved or normalized
        except Exception as exc:
            _logger.exception("_resolve_target_code: cache access failure")
            self._log_error(exc, context="_resolve_target_code")
        return "en"

    def _normalize_code(self, token: Optional[str]) -> str:
        """
        Normalize a token into a base language code string (e.g., 'en', 'pt', 'zh').
        This method will consult:
          - alias_helper.resolve(token) if provided
          - roles.resolve_code(token) if provided
        """
        t = (token or "").strip()
        if not t:
            return "en"
        # alias_helper may return canonical language name or code
        if self.alias_helper and hasattr(self.alias_helper, "resolve"):
            try:
                r = self.alias_helper.resolve(t)
                if isinstance(r, str) and r:
                    t = r
            except Exception:
                # non-fatal; keep original token for other resolution steps
                self._log_error(Exception("alias_helper.resolve failed"), context="_normalize_code")
        # role manager may map role labels to canonical codes/names
        if self.roles and hasattr(self.roles, "resolve_code"):
            try:
                r = self.roles.resolve_code(t)
                if isinstance(r, str) and r:
                    t = r
            except Exception:
                self._log_error(Exception("roles.resolve_code failed"), context="_normalize_code")
        t = t.replace("_", "-").lower()
        if "-" in t:
            parts = t.split("-")
            if parts and parts[0]:
                return parts[0]
        return t

    def _resolve_ambiguity(self, code: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Use ambiguity_resolver if available to disambiguate codes, flags, aliases, etc.
        Returns normalized code or None.
        """
        if not self.ambiguity_resolver or not hasattr(self.ambiguity_resolver, "resolve"):
            return None
        try:
            r = self.ambiguity_resolver.resolve(code, context=context or {})
            if isinstance(r, str) and r:
                return self._normalize_code(r)
        except Exception as exc:
            _logger.exception("_resolve_ambiguity failed")
            self._log_error(exc, context="_resolve_ambiguity")
        return None

    async def _detect_source_code(self, text: str) -> str:
        """
        Detect source language code for `text`.

        Behavior:
          - If a detection_service is injected and exposes `detect_language`, prefer it.
            Supports both synchronous and asynchronous detector implementations.
            Accepts detectors that return either a string code or (code, confidence).
          - Falls back to fast Unicode-range heuristics (existing behavior).
          - Returns base normalized code (two-letter/core) like 'en', 'ja', 'zh'.
        """
        t = (text or "").strip()
        if not t:
            return "en"

        # Try injected detector first if present
        if self.detector and hasattr(self.detector, "detect_language"):
            try:
                detect_fn = getattr(self.detector, "detect_language")
                # If it's a coroutine function, await directly
                if asyncio.iscoroutinefunction(detect_fn):
                    res = await detect_fn(t)
                else:
                    # If sync, run in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, detect_fn, t)

                # Detector may return (lang, confidence) or lang string
                if isinstance(res, tuple) and res:
                    lang = res[0]
                elif isinstance(res, str):
                    lang = res
                else:
                    lang = None

                if isinstance(lang, str) and lang:
                    return self._normalize_code(lang)
            except Exception as exc:
                _logger.exception("detector failed in _detect_source_code")
                self._log_error(exc, context="_detect_source_code")
                # fall through to heuristics if detector fails

        # Fallback: existing unicode-range heuristics (kept as-is)
        if any("\u3040" <= ch <= "\u30ff" for ch in t):
            return "ja"
        if any("\u4e00" <= ch <= "\u9fff" for ch in t):
            return "zh"
        if any("\u0400" <= ch <= "\u04FF" for ch in t):
            return "ru"
        if any("\u00C0" <= ch <= "\u024F" for ch in t):
            return "es"
        return "en"

    def _equivalent_lang(self, a: str, b: str) -> bool:
        """
        Return True when the normalized base codes are equal.
        """
        if not a or not b:
            return False
        na = self._normalize_code(a)
        nb = self._normalize_code(b)
        return na == nb
