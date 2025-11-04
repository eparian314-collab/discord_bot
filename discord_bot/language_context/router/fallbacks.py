"""
fallbacks.py

Purpose:
    Provide deterministic, testable fallback decision logic used by the language
    routing layer when incoming user input cannot be confidently routed.
    This module returns structured FallbackDecision objects describing the
    recommended action (e.g. ask clarification, route to translation, warn user)
    and a human-facing message. AI augmentation is optional and injected via
    an adapter; rule-based logic always provides a safe fallback.

Reading guide:
    - FallbackDecision: dataclass returned by the decision functions describing
      what the router should do next.
    - decide_fallback(): synchronous, rule-first decision function. Does not
      call external services unless an AI adapter is provided and usable.
    - decide_fallback_async(): async version which can await an AI adapter via
      the shared ai_bridge.generate_response interface.
    - Helpers: several small, pure helper functions implement heuristics
      (language routing, profanity detection hook, intent-score handling).
    - AI optionality: if an AI adapter is provided, the async function will
      attempt to request a polished clarifying question / suggestion. If the
      AI call fails or is not supplied, deterministic rules are used.

Responsibilities (kept intentionally small):
    - Make a single, local routing fallback decision and produce a message.
    - Do not perform actual routing, persistence, or I/O beyond optionally
      calling injected AI adapters.
    - Keep logic injection-friendly: accept callables for profanity checking and
      intent resolution.

Notes:
    - Use typing and dataclasses for clarity and testability.
    - If this module depends on future modules, see TODOs below for instructions.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Local import to reuse BridgeResult/AIRequest and the adapter Protocol.
# This import is safe because ai_bridge does not import fallbacks.
from .ai_bridge import AIAdapter, AIRequest, generate_response  # type: ignore

logger = logging.getLogger(__name__)

# ----------------------------
# Types and dataclasses
# ----------------------------


@dataclass(frozen=True)
class FallbackDecision:
    """
    A structured decision produced by the fallback engine.

    Fields:
    - action: short machine-friendly action name, e.g. "route_to_language", "clarify", "warn_user"
    - message: human-facing message to send to the user or use as a clarification prompt
    - confidence: 0.0-1.0 estimate of how confident the rule engine is in this decision
    - suggested_language: optional language code suggested for routing/translation
    - metadata: free-form dict for downstream systems (provenance, intent scores, ai results)
    """
    action: str
    message: str
    confidence: float
    suggested_language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type for profanity checker: returns True when text is profane
ProfanityChecker = Callable[[str], bool]

# Type for intent scores map: { "intent_name": score }
IntentScores = Dict[str, float]


# ----------------------------
# Small deterministic heuristics
# ----------------------------


_question_words = ("how", "what", "why", "who", "where", "when")
_short_message_threshold = 20  # characters considered "short" heuristically
_command_prefixes = ("!", "/", ".")  # common command prefixes


def _looks_like_command(text: str) -> bool:
    """Return True if the text looks like a bot/CLI command."""
    text = (text or "").strip()
    if not text:
        return False
    if text.startswith(_command_prefixes):
        return True
    # short imperative sentences or "help" common cases
    if text.lower().startswith(("help", "commands")):
        return True
    return False


def _looks_like_question(text: str) -> bool:
    """Heuristic to detect questions or clarifying prompts."""
    if not text:
        return False
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    first_word = stripped.split(None, 1)[0].lower() if stripped.split(None, 1) else ""
    if first_word in _question_words:
        return True
    return False


def _top_intent(intent_scores: Optional[IntentScores]) -> Optional[Tuple[str, float]]:
    """Return (intent, score) for highest scoring intent, or None."""
    if not intent_scores:
        return None
    items = sorted(intent_scores.items(), key=lambda kv: kv[1], reverse=True)
    return items[0]


# ----------------------------
# Core rule-based decision logic
# ----------------------------


def decide_fallback(
    text: str,
    *,
    detected_language: Optional[str] = None,
    available_language_routes: Optional[Sequence[str]] = None,
    intent_scores: Optional[IntentScores] = None,
    profanity_checker: Optional[ProfanityChecker] = None,
) -> FallbackDecision:
    """
    Synchronous, rule-first fallback decision.

    Parameters:
    - text: raw or normalized text (caller may use Normalizer before calling)
    - detected_language: optional short language code hint (e.g. "en", "es")
    - available_language_routes: sequence of language codes supported by the router
    - intent_scores: optional map of intent->score from an intent classifier
    - profanity_checker: optional callable that returns True if text is profane

    Returns:
    - FallbackDecision: recommended action, message and metadata

    Behavior (priority order):
    1. Profanity -> warn_user
    2. Exact language route available -> route_to_language
    3. Strong intent (score >= 0.8) -> route_by_intent
    4. Looks like a command -> route_to_command_help
    5. Looks like a question / short text -> clarify_intent (ask for more detail)
    6. Default -> ask_rephrase
    """
    normalized = (text or "").strip()
    metadata: Dict[str, Any] = {}

    # 1) Profanity detection (if provided)
    try:
        if profanity_checker and profanity_checker(normalized):
            msg = "Please avoid offensive language. I can still help if you rephrase your request."
            return FallbackDecision(action="warn_user", message=msg, confidence=0.95, metadata={"reason": "profanity"})
    except Exception as ex:
        logger.debug("Profnity checker threw an exception; ignoring: %s", ex)

    # 2) Language routing
    if detected_language and available_language_routes:
        if detected_language in available_language_routes:
            msg = f"Routing to {detected_language} handler."
            return FallbackDecision(action="route_to_language", message=msg, confidence=0.98, suggested_language=detected_language, metadata={"detected_language": detected_language})

    # 3) Strong intent score
    top = _top_intent(intent_scores)
    if top:
        intent_name, score = top
        metadata["top_intent"] = {intent_name: score}
        if score >= 0.80:
            msg = f"Routing to intent: {intent_name}."
            return FallbackDecision(action="route_by_intent", message=msg, confidence=float(score), metadata=metadata)

    # 4) Commands
    if _looks_like_command(normalized):
        msg = "It looks like you're using a command. Use 'help' to list available bot commands."
        return FallbackDecision(action="route_to_command_help", message=msg, confidence=0.85, metadata={"example_help": "help"})

    # 5) Questions / short messages -> ask for clarification
    if _looks_like_question(normalized) or len(normalized) <= _short_message_threshold:
        msg = "I didn't catch that. Could you please provide a bit more detail or specify what you'd like?"
        return FallbackDecision(action="clarify_intent", message=msg, confidence=0.6, metadata={"hint": "add details"})

    # 6) Default fallback
    snippet = normalized if len(normalized) <= 120 else normalized[:117] + "..."
    msg = f"Sorry, I couldn't route your request reliably. You said: \"{snippet}\" - could you rephrase or add a language hint?"
    return FallbackDecision(action="ask_rephrase", message=msg, confidence=0.4, metadata={})


# ----------------------------
# Async decision with optional AI augmentation
# ----------------------------


async def decide_fallback_async(
    text: str,
    *,
    detected_language: Optional[str] = None,
    available_language_routes: Optional[Sequence[str]] = None,
    intent_scores: Optional[IntentScores] = None,
    profanity_checker: Optional[ProfanityChecker] = None,
    ai_adapter: Optional[AIAdapter] = None,
    ai_timeout: float = 1.0,
) -> FallbackDecision:
    """
    Async version of `decide_fallback` that will attempt to use an injected AI
    adapter to produce a short, polished clarifying question or suggestion.

    Behavior:
    - Compute a rule-based decision first.
    - If the rule-based decision is "clarify_intent" or "ask_rephrase" and an
      AI adapter is provided, ask the adapter to rewrite the user's text into
      a short clarifying question. If AI fails or times out, return the rule result.
    - The returned `FallbackDecision.metadata` will include AI provenance when used.

    Notes:
    - Uses `ai_bridge.generate_response` to interface with the adapter.
    - The function never raises for adapter failures; it falls back deterministically.
    """
    rule_decision = decide_fallback(
        text,
        detected_language=detected_language,
        available_language_routes=available_language_routes,
        intent_scores=intent_scores,
        profanity_checker=profanity_checker,
    )

    # Only attempt AI augmentation for clarification-like decisions
    if ai_adapter and rule_decision.action in ("clarify_intent", "ask_rephrase"):
        prompt = (
            "Rewrite the following user input into a short, polite clarifying question "
            "a bot could ask to disambiguate intent (max 50 characters):\n\n"
            f"User: \"{text.strip()}\"\n\nClarifying question:"
        )
        try:
            ai_req = AIRequest(prompt=prompt, language_hint=detected_language, metadata={"origin_action": rule_decision.action}, timeout=ai_timeout)
            bridge_result = await generate_response(ai_adapter, ai_req)
            # If AI produced a valid response and it is not the rule-only fallback, use it
            if bridge_result and bridge_result.response and bridge_result.response.success and not bridge_result.used_fallback:
                ai_text = (bridge_result.response.text or "").strip()
                if ai_text:
                    # Overwrite message with AI suggestion, but keep metadata/provenance
                    new_meta = dict(rule_decision.metadata)
                    new_meta["ai"] = {
                        "model": bridge_result.response.model,
                        "tokens_estimate": bridge_result.response.tokens_estimate,
                        "provenance": bridge_result.provenance,
                    }
                    return FallbackDecision(
                        action=rule_decision.action,
                        message=ai_text,
                        confidence=max(rule_decision.confidence, 0.65),
                        suggested_language=rule_decision.suggested_language,
                        metadata=new_meta,
                    )
        except asyncio.TimeoutError:
            logger.info("AI adapter timed out during fallback augmentation; returning rule decision.")
        except Exception as ex:
            logger.debug("AI adapter failed during fallback augmentation: %s", ex)

    # No AI augmentation possible or not applicable: return rule-based decision
    return rule_decision


# ----------------------------
# Convenience sync wrapper for async augmentation
# ----------------------------


def decide_fallback_with_optional_ai(
    text: str,
    *,
    detected_language: Optional[str] = None,
    available_language_routes: Optional[Sequence[str]] = None,
    intent_scores: Optional[IntentScores] = None,
    profanity_checker: Optional[ProfanityChecker] = None,
    ai_adapter: Optional[AIAdapter] = None,
    ai_timeout: float = 1.0,
) -> FallbackDecision:
    """
    Synchronous convenience wrapper that will call `decide_fallback_async` when
    an AI adapter is present (which may run the event loop). If running inside
    an event loop, the call will try to use the adapter's synchronous methods
    where applicable (adapters implementing generate_sync) or fall back to the
    rule-only decision to avoid nested event loop issues.

    Note: Prefer `await decide_fallback_async(...)` from async code.
    """
    if not ai_adapter:
        return decide_fallback(text, detected_language=detected_language, available_language_routes=available_language_routes, intent_scores=intent_scores, profanity_checker=profanity_checker)

    # If there is a running event loop, avoid calling asyncio.run (which would raise).
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Attempt to call a sync generate via adapter if available to avoid blocking the loop.
        try:
            # Prepare same prompt as async function would
            base_decision = decide_fallback(text, detected_language=detected_language, available_language_routes=available_language_routes, intent_scores=intent_scores, profanity_checker=profanity_checker)
            if base_decision.action in ("clarify_intent", "ask_rephrase") and hasattr(ai_adapter, "generate_sync"):
                prompt = (
                    "Rewrite the following user input into a short, polite clarifying question "
                    "a bot could ask to disambiguate intent (max 50 characters):\n\n"
                    f"User: \"{text.strip()}\"\n\nClarifying question:"
                )
                # Call sync adapter method directly; adapters must implement generate_sync if they are sync-capable
                ai_resp = ai_adapter.generate_sync(prompt, metadata={"origin_action": base_decision.action}, timeout=ai_timeout)  # type: ignore[attr-defined]
                if ai_resp and ai_resp.success and ai_resp.text:
                    new_meta = dict(base_decision.metadata)
                    new_meta["ai"] = {"model": ai_resp.model, "provenance": "ai-adapter-sync"}
                    return FallbackDecision(action=base_decision.action, message=ai_resp.text.strip(), confidence=max(base_decision.confidence, 0.65), metadata=new_meta)
        except Exception as ex:
            logger.debug("Synchronous AI augmentation failed inside running loop: %s", ex)

        # Fall back to deterministic decision to avoid nested loop complexity
        return decide_fallback(text, detected_language=detected_language, available_language_routes=available_language_routes, intent_scores=intent_scores, profanity_checker=profanity_checker)

    # No running loop - safe to use asyncio.run
    try:
        return asyncio.run(decide_fallback_async(
            text,
            detected_language=detected_language,
            available_language_routes=available_language_routes,
            intent_scores=intent_scores,
            profanity_checker=profanity_checker,
            ai_adapter=ai_adapter,
            ai_timeout=ai_timeout,
        ))
    except Exception as ex:
        logger.debug("Async fallback with AI failed; returning rule-only decision: %s", ex)
        return decide_fallback(text, detected_language=detected_language, available_language_routes=available_language_routes, intent_scores=intent_scores, profanity_checker=profanity_checker)


# ----------------------------
# TODOs and notes
# ----------------------------
# TODO: Add unit tests for:
#   - decide_fallback rules (profanity, language routing, command detection, question detection)
#   - decide_fallback_async when AI adapter returns success / failure / timeout
#   - decide_fallback_with_optional_ai behavior while inside a running event loop
#
# TODO: Consider adding small structured enums for `action` values or migrating to an Action Enum.
#
# TODO: Integrate with cultural profanity map:
#   - Provide an injectable profanity checker that uses `language_context.culture.profanity_map`
#     for language-aware filtering.
#
# Future extensions:
#   - Add rate-limiting or circuit-breaker around AI augmentation calls to avoid overuse.
#   - Add telemetry hooks (counters/histograms) to record how often fallbacks occur and which actions are taken.
#   - Provide an option to return multiple candidate actions for downstream ranking.