"""
ai_bridge.py

Purpose:
    Provide a small, injection-friendly bridge between the language routing layer
    and any AI/LLM adapters. This module defines stable request/response dataclasses,
    a minimal adapter Protocol, safe async/sync orchestration helpers, and a
    rule-based fallback engine used when no AI adapter is supplied or available.

Reading guide:
    - AIAdapter (Protocol): implement this to plug an actual LLM/AI adapter.
      Both async and sync generate methods are optional; async is preferred.
    - AIRequest / AIResponse / BridgeResult: typed dataclasses used across the bridge.
    - select_engine(): choose the provided adapter or fall back to RuleBasedFallbackEngine.
    - generate_response() / generate_response_sync(): small async/sync helpers that return BridgeResult.
    - RuleBasedFallbackEngine: deterministic rule-based responses (always available).
    - normalize_prompt(): small normalizer for prompt pre-processing (rule-based).
    - TODOs are provided for real adapter integration and tests.

Design notes:
    - Rule-based logic is explicit and documented; ML/AI hooks are optional and injected.
    - No hard imports of external LLM libraries; adapters are provided by the caller.
    - Keep responsibilities narrow: this module does NOT perform routing, persistence,
      or side effects like network calls itself (except delegating through adapters).
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

# ----------------------------
# Types and Protocols
# ----------------------------


class AIAdapter(Protocol):
    """
    Minimal adapter protocol for AI/LLM integrations.

    Implementers should prefer providing `generate` (async). If only synchronous
    generation is available, implement `generate_sync` instead. The bridge will
    attempt to call async then sync as a fallback.

    Example implementation TODO (not in this file):
      class OpenAIAdapter:
          async def generate(self, prompt: str, metadata: Optional[dict] = None, timeout: Optional[float] = None) -> AIResponse:
              ...
    """

    async def generate(self, prompt: str, *, metadata: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> "AIResponse":
        ...

    def generate_sync(self, prompt: str, *, metadata: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> "AIResponse":
        ...


@dataclass
class AIRequest:
    """
    Represents a request to the AI bridge.

    - `prompt`: the pre-normalized text to send to the AI or rule engine.
    - `language_hint`: optional language or locale hint, e.g. "en", "es".
    - `metadata`: optional free-form dict (conversation id, user id, etc.).
    - `timeout`: optional per-request timeout in seconds.
    """
    prompt: str
    language_hint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = None


@dataclass
class AIResponse:
    """
    Standardized response returned by adapters and the rule engine.

    - `text`: the main textual response.
    - `tokens_estimate`: optional tokens estimate (adapter may set).
    - `model`: optional model identifier string.
    - `success`: whether generation succeeded.
    - `error`: optional error string if not successful.
    """
    text: str
    tokens_estimate: Optional[int] = None
    model: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class BridgeResult:
    """
    The canonical result returned from the ai_bridge orchestration functions.

    - `success`: whether any generation succeeded.
    - `response`: AIResponse returned.
    - `used_fallback`: True when the rule engine produced the response.
    - `provenance`: short description of which engine produced the result.
    """
    success: bool
    response: AIResponse
    used_fallback: bool
    provenance: str


# ----------------------------
# Normalization helpers
# ----------------------------


def normalize_prompt(text: str) -> str:
    """
    Lightweight normalization applied before sending text to an adapter or fallback.

    Rules applied:
    - Unicode NFC normalization.
    - Strip leading/trailing whitespace.
    - Collapse consecutive whitespace to single spaces.
    - Remove control characters (except common newline/space).
    - Lowercasing is intentionally NOT applied (preserve proper nouns); callers may choose.

    This function is intentionally small and deterministic - ML-based normalization
    can be performed downstream by adapters if needed.
    """
    if text is None:
        return ""

    # Unicode normalization
    text = unicodedata.normalize("NFC", text)

    # Remove control characters except newline and tab
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ----------------------------
# Rule-based fallback engine
# ----------------------------


class RuleBasedFallbackEngine:
    """
    A minimal rule-based engine used when no AI adapter is supplied or available.

    Characteristics:
    - Deterministic, local, fast.
    - Safe default: never makes network calls.
    - Designed to be easily extended with more rules or swapped with a smarter
      rule engine using dependency injection.

    Current rule set (simple examples):
    - If prompt contains "help" or "commands" -> short help text.
    - If prompt contains "translate to <lang>:" or "translate <text> to <lang>" -> simple placeholder translation.
    - If prompt starts with "repeat:" -> echo the text after the colon.
    - Otherwise returns a polite fallback message and echoes a shortened prompt.
    """

    def __init__(self) -> None:
        # Small internal map; callers may subclass or replace this engine.
        self._help_phrases = ("help", "commands", "what can you do", "usage")
        self._translate_re = re.compile(
            r"(?:translate(?:\s+to)?\s+)(?P<lang>[a-zA-Z\-]{2,10})[:\s]+(?P<text>.+)|(?P<text2>.+?)\s+to\s+(?P<lang2>[a-zA-Z\-]{2,10})$",
            flags=re.IGNORECASE,
        )

    def _translate_placeholder(self, text: str, lang: str) -> str:
        # Rule-based placeholder translation - deterministic and explicit.
        # Real translation adapters should be injected in production.
        return f"[translated to {lang}]: {text}"

    def _help_text(self) -> str:
        return (
            "Happy Hippo (fallback) - available commands: 'translate to <lang>: <text>', "
            "'repeat: <text>', or ask for 'help'. For full capabilities enable an AI adapter."
        )

    def generate_sync(self, prompt: str, *, metadata: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> AIResponse:
        """
        Synchronous generation entry point for the rule engine.
        """
        try:
            normalized = normalize_prompt(prompt)
            lower = normalized.lower()

            # Help
            if any(phrase in lower for phrase in self._help_phrases):
                return AIResponse(text=self._help_text(), success=True, model="rule-fallback")

            # Repeat pattern: "repeat: hello world"
            if lower.startswith("repeat:"):
                _, _, rest = normalized.partition(":")
                return AIResponse(text=rest.strip() or "Nothing to repeat.", success=True, model="rule-fallback")

            # Translate patterns
            m = self._translate_re.search(normalized)
            if m:
                lang = m.group("lang") or m.group("lang2") or "unknown"
                text = m.group("text") or m.group("text2") or normalized
                text = text.strip()
                translated = self._translate_placeholder(text=text, lang=lang)
                return AIResponse(text=translated, success=True, model=f"rule-fallback/translate:{lang}")

            # Default fallback: echo short summary
            snippet = normalized if len(normalized) <= 200 else normalized[:197] + "..."
            fallback_text = f"[fallback] I cannot access an AI. Echo: {snippet}"
            return AIResponse(text=fallback_text, success=True, model="rule-fallback")
        except Exception as ex:
            logger.exception("RuleBasedFallbackEngine failed: %s", ex)
            return AIResponse(text="Fallback engine error.", success=False, error=str(ex), model="rule-fallback")


# ----------------------------
# Orchestration helpers
# ----------------------------


def select_engine(adapter: Optional[AIAdapter]) -> AIAdapter:
    """
    Return the provided adapter if not None, otherwise return the rule-based engine.

    This keeps downstream modules free of conditional logic for 'is adapter present'.
    """
    if adapter is None:
        return RuleBasedFallbackEngine()
    return adapter


async def _call_async_adapter(adapter: AIAdapter, prompt: str, *, metadata: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> AIResponse:
    """
    Attempt to call adapter.generate asynchronously respecting timeout.
    Raises exceptions from adapter through to callers.
    """
    coro = adapter.generate(prompt, metadata=metadata, timeout=timeout)
    if timeout is not None:
        return await asyncio.wait_for(coro, timeout=timeout)
    return await coro


def _call_sync_adapter(adapter: AIAdapter, prompt: str, *, metadata: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> AIResponse:
    """
    Attempt to call adapter.generate_sync synchronously. If not implemented,
    raise AttributeError to allow caller to fallback.
    """
    if not hasattr(adapter, "generate_sync"):
        raise AttributeError("Adapter has no generate_sync method")
    return adapter.generate_sync(prompt, metadata=metadata, timeout=timeout)


async def generate_response(adapter: Optional[AIAdapter], request: AIRequest) -> BridgeResult:
    """
    High-level async entry point used by routing layers.

    Behavior:
    - Normalize request.prompt.
    - If adapter is provided, try its async generate; on failure try sync generate.
    - If adapter is None or all adapter calls fail, use rule-based fallback.
    - Returns BridgeResult with provenance info and used_fallback flag.
    """
    engine = select_engine(adapter)
    normalized_prompt = normalize_prompt(request.prompt)

    # If engine is the rule-based instance, call it synchronously on the event loop to avoid blocking semantics.
    if isinstance(engine, RuleBasedFallbackEngine):
        response = engine.generate_sync(normalized_prompt, metadata=request.metadata, timeout=request.timeout)
        return BridgeResult(success=response.success, response=response, used_fallback=True, provenance="rule-fallback")

    # Try async first
    try:
        response = await _call_async_adapter(engine, normalized_prompt, metadata=request.metadata, timeout=request.timeout)
        return BridgeResult(success=response.success, response=response, used_fallback=False, provenance=getattr(response, "model", "ai-adapter"))
    except (AttributeError, NotImplementedError) as ex:
        logger.debug("Adapter missing async method or not implemented: %s; attempting sync: %s", type(ex).__name__, ex)
    except asyncio.TimeoutError:
        logger.warning("AI adapter async call timed out; falling back to rule engine.")
        # fall through to fallback below
    except Exception as ex:
        logger.exception("AI adapter async generation failed: %s", ex)
        # fall through to fallback below

    # Try sync method (may block; caller should be aware)
    try:
        response = _call_sync_adapter(engine, normalized_prompt, metadata=request.metadata, timeout=request.timeout)
        return BridgeResult(success=response.success, response=response, used_fallback=False, provenance=getattr(response, "model", "ai-adapter-sync"))
    except Exception as ex:
        logger.debug("Sync adapter call failed: %s", ex)

    # Final fallback: use rule engine
    fallback = RuleBasedFallbackEngine()
    response = fallback.generate_sync(normalized_prompt, metadata=request.metadata, timeout=request.timeout)
    return BridgeResult(success=response.success, response=response, used_fallback=True, provenance="rule-fallback")


def generate_response_sync(adapter: Optional[AIAdapter], request: AIRequest) -> BridgeResult:
    """
    Synchronous wrapper that runs the async generate_response function.

    Note: If an injected adapter has only async methods, this function will run
    the event loop temporarily and may not be suitable for contexts where nested
    event loops are disallowed. Prefer using `await generate_response(...)`.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an event loop; call underlying sync adapter if present, else run fallback sync.
        engine = select_engine(adapter)
        if isinstance(engine, RuleBasedFallbackEngine):
            response = engine.generate_sync(request.prompt, metadata=request.metadata, timeout=request.timeout)
            return BridgeResult(success=response.success, response=response, used_fallback=True, provenance="rule-fallback")
        try:
            response = _call_sync_adapter(engine, normalize_prompt(request.prompt), metadata=request.metadata, timeout=request.timeout)
            return BridgeResult(success=response.success, response=response, used_fallback=False, provenance=getattr(response, "model", "ai-adapter-sync"))
        except Exception as ex:
            logger.debug("generate_response_sync inside running loop failed: %s", ex)
            fallback = RuleBasedFallbackEngine()
            response = fallback.generate_sync(normalize_prompt(request.prompt), metadata=request.metadata, timeout=request.timeout)
            return BridgeResult(success=response.success, response=response, used_fallback=True, provenance="rule-fallback")

    # No running loop; run the async function normally
    return asyncio.run(generate_response(adapter, request))


# ----------------------------
# Small utilities
# ----------------------------


def detect_ai_available(adapter: Optional[AIAdapter]) -> bool:
    """
    Lightweight check whether an adapter likely provides AI capabilities.

    Does not attempt network calls. The presence of an adapter is treated as 'available'.
    """
    return adapter is not None


# ----------------------------
# TODOs and notes
# ----------------------------
# TODO: Provide example adapter implementations in a separate module, e.g.
#   - discord_bot.language_context.adapters.openai_adapter.OpenAIAdapter
#   - discord_bot.language_context.adapters.huggingface_adapter.HFAdapter
# Each should implement AIAdapter and handle authentication, rate limiting, retry policies, etc.
#
# TODO: Add unit tests for:
#   - normalize_prompt edge cases (unicode, control chars)
#   - RuleBasedFallbackEngine patterns and edge cases
#   - generate_response behavior with a fake async adapter that raises, times out, etc.
#
# TODO: Consider adding metrics/provenance headers to BridgeResult for observability.
#
# Future ML/AI hooks:
#   - Adapters may perform safety checks, profanity filtering, and post-processing.
#   - This module intentionally keeps those responsibilities in adapters to preserve separation
#     of concerns.