"""
intent_classifier.py

Purpose:
    Roughly detect user intent categories used by the Language Context Engine:
    - question, command, greeting, tts, sos, or unknown.
    This module is rule-first (deterministic) and provides optional AI
    augmentation via an injected adapter (non-required). Keep logic
    small, testable, and side-effect free.

READING GUIDE:
    - Use `classify_intent(text, ...)` for fast, synchronous, rule-based classification.
    - Use `classify_intent_async(text, ai_adapter=..., ...)` to ask an optional AI adapter
      to refine or rephrase the classification (async, may use network).
    - The primary return type is `IntentResult` (dataclass) containing per-intent scores,
      the top intent, a confidence score, a short human message, and metadata.
    - This module does NOT perform routing, logging, or persistence - downstream code
      should consume `IntentResult` and decide actions.
    - All normalization should be done by `language_context.normalizer.Normalizer` prior to calling,
      though classify functions will perform lightweight trimming.

Design notes:
    - Rule-based heuristics are explicit and simple (regex/keyword matches).
    - Scoring is interpretable and deterministic; AI is an optional augmentation.
    - Injection points: `custom_keywords`, `profanity_checker`, and `ai_adapter`.
    - Avoids external dependencies to keep it runnable in unit tests.

TODOs:
    - Add unit tests for corner cases (emoji-only, non-Latin scripts, code snippets).
    - Optionally add a small ML-based intent model behind an injectable interface.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Optional AI augmentation interface (import locally to avoid circular imports)
try:
    from ..router.ai_bridge import AIAdapter, AIRequest, generate_response  # type: ignore
except Exception:  # pragma: no cover - import guard for static analysis/runtime
    AIAdapter = Any  # type: ignore
    AIRequest = Any  # type: ignore
    generate_response = None  # type: ignore

logger = logging.getLogger(__name__)

# ----------------------------
# Data classes
# ----------------------------


@dataclass(frozen=True)
class IntentResult:
    """
    Structured intent classification result.

    - `scores`: map of intent name -> confidence-like score [0.0, 1.0]
    - `top_intent`: name of the highest scoring intent or None
    - `confidence`: numeric confidence for the top intent (0.0-1.0)
    - `message`: short human-facing explanation or suggestion (optional)
    - `metadata`: free-form dict for downstream uses (match details, provenance)
    """
    scores: Dict[str, float]
    top_intent: Optional[str]
    confidence: float
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ----------------------------
# Defaults & simple patterns
# ----------------------------

# Basic set of intents this classifier detects
INTENTS = ("question", "command", "greeting", "tts", "sos", "unknown")

# Heuristic keyword lists (extendable via custom_keywords parameter)
_DEFAULT_KEYWORDS: Dict[str, Sequence[str]] = {
    "greeting": ("hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings"),
    "tts": ("tts", "read aloud", "read this", "speak", "say this", "pronounce", "text to speech", "read out"),
    "sos": ("911", "help me", "help!", "save me", "emergency", "sos", "suicide", "kill myself", "hurt myself", "want to die"),
    # `command` and `question` are detected mainly by structure/prefixes rather than keyword lists
}

# Regex patterns
_QUESTION_WORDS_RE = re.compile(r"^(?:how|what|why|who|where|when|which|whom)\b", flags=re.IGNORECASE)
_COMMAND_PREFIX_RE = re.compile(r"^[!/\.]\w")  # e.g. "!play", "/translate", ".help"
_PUNCT_QUESTION_RE = re.compile(r"\?$")
_SHORT_IMPERATIVE_RE = re.compile(r"^(?:please\s+)?(show|open|play|translate|convert|send|give|list|create|delete|add)\b", flags=re.IGNORECASE)
_GREET_RE = re.compile(r"^(?:hi|hello|hey|good\s+(morning|afternoon|evening)|greetings)\b", flags=re.IGNORECASE)
_TTS_RE = re.compile(r"\b(?:tts|text to speech|read aloud|read out|pronounce|speak|say this)\b", flags=re.IGNORECASE)
_SOS_RE = re.compile(r"\b(?:911|sos|help me|save me|emergency|suicide|kill myself|hurt myself|want to die)\b", flags=re.IGNORECASE)


# ----------------------------
# Helper detection functions
# ----------------------------


def _is_question(text: str) -> float:
    """
    Heuristic score for question-likeness [0.0, 1.0].
    - +0.6 if ends with '?'
    - +0.3 if starts with a question word
    - small boost for presence of 'please explain', 'how do I', etc.
    """
    if not text:
        return 0.0
    score = 0.0
    if _PUNCT_QUESTION_RE.search(text):
        score += 0.6
    if _QUESTION_WORDS_RE.search(text):
        score += 0.3
    # presence of "how do I", "how can I"
    if re.search(r"\bhow\s+(do|can)\b", text, flags=re.IGNORECASE):
        score += 0.15
    return min(score, 1.0)


def _is_command(text: str) -> float:
    """
    Heuristic score for command-likeness.
    - +0.6 if starts with command prefix (!, /, .)
    - +0.4 for imperative verbs at start (short commands)
    - reduce score if ends with '?' (question)
    """
    if not text:
        return 0.0
    score = 0.0
    if _COMMAND_PREFIX_RE.search(text):
        score += 0.6
    if _SHORT_IMPERATIVE_RE.search(text):
        score += 0.35
    # short messages without punctuation are more likely commands in chat
    if len(text.strip()) <= 30 and not re.search(r"[?.!]\s*$", text.strip()):
        score += 0.05
    if _PUNCT_QUESTION_RE.search(text):
        score *= 0.2
    return min(score, 1.0)


def _is_greeting(text: str, keywords: Sequence[str]) -> float:
    """
    Simple keyword/regex based greeting detection.
    """
    if not text:
        return 0.0
    if _GREET_RE.search(text):
        return 0.9
    lowered = text.lower()
    for kw in keywords:
        if kw in lowered:
            return 0.8
    return 0.0


def _is_tts(text: str, keywords: Sequence[str]) -> float:
    """
    Detect requests to speak/read text aloud.
    """
    if not text:
        return 0.0
    if _TTS_RE.search(text):
        return 1.0
    lowered = text.lower()
    for kw in keywords:
        if kw in lowered:
            return 0.9
    return 0.0


def _is_sos(text: str, keywords: Sequence[str]) -> float:
    """
    Detect SOS/emergency/self-harm indicators. Always treat these with high priority.
    """
    if not text:
        return 0.0
    if _SOS_RE.search(text):
        return 1.0
    lowered = text.lower()
    for kw in keywords:
        if kw in lowered:
            return 0.9
    return 0.0


# ----------------------------
# Public classifier (sync)
# ----------------------------


def classify_intent(
    text: str,
    *,
    custom_keywords: Optional[Dict[str, Sequence[str]]] = None,
    profanity_checker: Optional[Callable[[str], bool]] = None,
    language_hint: Optional[str] = None,
) -> IntentResult:
    """
    Synchronous, rule-first intent classifier.

    Parameters:
      - text: raw or normalized text (trimming is performed)
      - custom_keywords: optional dict to override/default extend keyword lists for intents
      - profanity_checker: optional callable that returns True for profane text (affects confidence/provenance)
      - language_hint: optional language code (unused by default heuristics, left in metadata)

    Returns:
      - IntentResult (scores, top_intent, confidence, message, metadata)

    Behavior:
      - Compute simple confidence-like scores for each known intent and return the top one.
      - SOS has the highest priority; if detected, it's returned immediately with high confidence.
      - The classifier is intentionally conservative: scores are interpretable but not calibrated ML probabilities.
    """
    txt = (text or "").strip()
    metadata: Dict[str, Any] = {"raw": text, "language_hint": language_hint}

    # Prepare keyword mapping
    keywords = {k: list(v) for k, v in _DEFAULT_KEYWORDS.items()}
    if custom_keywords:
        for k, v in custom_keywords.items():
            keywords.setdefault(k, [])
            # allow overrides or extensions
            if isinstance(v, (list, tuple)):
                keywords[k] = list(v)
            else:
                # single string provided
                keywords[k] = [str(v)]

    # 1) SOS priority
    sos_score = _is_sos(txt, keywords.get("sos", []))
    if sos_score > 0.0:
        # Highest priority: return immediately with provenance
        scores = {intent: 0.0 for intent in INTENTS}
        scores["sos"] = float(sos_score)
        return IntentResult(scores=scores, top_intent="sos", confidence=float(sos_score), message="Detected potential emergency or self-harm content.", metadata={**metadata, "provenance": "rule-sos"})

    # 2) Compute other heuristic scores
    scores: Dict[str, float] = {intent: 0.0 for intent in INTENTS}
    scores["question"] = _is_question(txt)
    scores["command"] = _is_command(txt)
    scores["greeting"] = _is_greeting(txt, keywords.get("greeting", []))
    scores["tts"] = _is_tts(txt, keywords.get("tts", []))

    # Adjust via profanity if available (decrease confidence but annotate)
    if profanity_checker:
        try:
            if profanity_checker(txt):
                metadata["profanity"] = True
                # reduce confidences to encourage human moderation
                scores = {k: float(v) * 0.6 for k, v in scores.items()}
        except Exception as ex:
            logger.debug("profanity_checker raised: %s", ex)

    # Pick top intent (ignore 'unknown' initial)
    top_intent, top_score = max(((k, v) for k, v in scores.items() if k != "unknown"), key=lambda kv: kv[1], default=("unknown", 0.0))

    # If no score above a small threshold, return unknown
    if top_score < 0.2:
        scores["unknown"] = 1.0
        return IntentResult(scores=scores, top_intent="unknown", confidence=0.0, message="No strong intent detected; clarification may be required.", metadata=metadata)

    # Build a simple message hint for clarify or action
    message_map = {
        "question": "Detected a question - consider answering or asking a clarifying question.",
        "command": "Detected a command - route to command handler.",
        "greeting": "Detected a greeting - you may reply with a greeting.",
        "tts": "Detected a TTS request - consider reading text aloud.",
    }
    message = message_map.get(top_intent, None)

    return IntentResult(scores=scores, top_intent=top_intent, confidence=float(top_score), message=message, metadata=metadata)


# ----------------------------
# Async classifier with optional AI augmentation
# ----------------------------


async def classify_intent_async(
    text: str,
    *,
    ai_adapter: Optional[AIAdapter] = None,
    ai_timeout: float = 0.8,
    custom_keywords: Optional[Dict[str, Sequence[str]]] = None,
    profanity_checker: Optional[Callable[[str], bool]] = None,
    language_hint: Optional[str] = None,
) -> IntentResult:
    """
    Async classifier that first runs rule-based `classify_intent`. If the result
    is ambiguous (top confidence < 0.6) and `ai_adapter` is provided, it will
    attempt to ask the adapter to refine or rephrase the intent in a short reply.

    - Falls back to the deterministic result if AI is unavailable or fails.
    - The AI prompt is intentionally small and limited to avoid sending PII.
    """
    # Rule-based baseline
    base = classify_intent(text, custom_keywords=custom_keywords, profanity_checker=profanity_checker, language_hint=language_hint)

    # If decision is confident enough or no AI adapter given, return quickly
    if base.confidence >= 0.6 or ai_adapter is None or generate_response is None:
        return base

    # Build a concise prompt asking the AI to output one of the known intents with a short reason.
    prompt = (
        "Classify the user's intent into one of: question, command, greeting, tts, sos, unknown.\n"
        "Return a single line with: <intent>: <brief reason>\n\n"
        f"User text: \"{(text or '').strip()}\"\n\nIntent:"
    )
    try:
        ai_req = AIRequest(prompt=prompt, language_hint=language_hint, metadata={"origin": "intent_classifier"}, timeout=ai_timeout)
        bridge_result = await generate_response(ai_adapter, ai_req)  # type: ignore
        if bridge_result and bridge_result.response and bridge_result.response.success and not bridge_result.used_fallback:
            ai_text = (bridge_result.response.text or "").strip().lower()
            # Expecting format like "question: user asked about..." - simple parse
            m = re.match(r"^(question|command|greeting|tts|sos|unknown)\s*[:\-]\s*(.+)$", ai_text, flags=re.IGNORECASE)
            if m:
                intent = m.group(1).lower()
                reason = m.group(2).strip()
                # Build a conservative score from base and boost by small amount
                base_scores = dict(base.scores)
                base_scores[intent] = max(base_scores.get(intent, 0.0), 0.5)
                # Normalize scores naively to ensure top reflects AI
                top_intent = intent
                confidence = float(base_scores[intent])
                return IntentResult(scores=base_scores, top_intent=top_intent, confidence=confidence, message=f"AI suggested: {reason}", metadata={"provenance": "ai-augmented", "ai_model": bridge_result.response.model})
    except asyncio.TimeoutError:
        logger.debug("AI intent augmentation timed out.")
    except Exception as ex:
        logger.debug("AI intent augmentation failed: %s", ex)

    # Fallback to rule-based
    return base


# ----------------------------
# Utility convenience wrapper
# ----------------------------


def classify_intent_with_optional_ai(
    text: str,
    *,
    ai_adapter: Optional[AIAdapter] = None,
    ai_timeout: float = 0.8,
    custom_keywords: Optional[Dict[str, Sequence[str]]] = None,
    profanity_checker: Optional[Callable[[str], bool]] = None,
    language_hint: Optional[str] = None,
) -> IntentResult:
    """
    Synchronous wrapper that will try to call the async augmentation when an
    AI adapter is provided and there is no running event loop. If inside a running
    loop, it returns the rule-based result to avoid nested event loop issues.
    """
    if not ai_adapter:
        return classify_intent(text, custom_keywords=custom_keywords, profanity_checker=profanity_checker, language_hint=language_hint)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Avoid running asyncio.run inside a running loop; return rule-based classification
        logger.debug("Event loop running; returning rule-based intent classification.")
        return classify_intent(text, custom_keywords=custom_keywords, profanity_checker=profanity_checker, language_hint=language_hint)

    # Safe to run async augmentation
    try:
        return asyncio.run(classify_intent_async(
            text,
            ai_adapter=ai_adapter,
            ai_timeout=ai_timeout,
            custom_keywords=custom_keywords,
            profanity_checker=profanity_checker,
            language_hint=language_hint,
        ))
    except Exception as ex:
        logger.debug("AI-augmented classification failed in sync wrapper: %s", ex)
        return classify_intent(text, custom_keywords=custom_keywords, profanity_checker=profanity_checker, language_hint=language_hint)


# ----------------------------
# TODOs and Future Extensions
# ----------------------------
# TODO: Add unit tests for:
#   - greeting variations and non-Latin inputs
#   - TTS detection with many phrasing variants
#   - SOS detection edge cases and false positives
#   - classify_intent_async when AI returns unexpected formats
#
# TODO: Consider adding an Action Enum for intents to avoid relying on string constants.
#
# Future extensions (non-blocking):
#   - Add a small, pluggable ML classifier behind an interface for higher-quality detection.
#   - Integrate with Normalizer pipelines and token-level features to improve scores.
#   - Add confidence calibration and a small history-based smoothing of intent detection per session.
#