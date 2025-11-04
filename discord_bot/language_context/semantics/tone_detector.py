# Detect conversational tone (friendly, angry, confused, etc.) using rule-based heuristics.
#
# READING GUIDE:
# - Use `detect_tone(text, ai_classifier=None)` to get a `ToneTag` for a single message.
# - Use `detect_batch(messages, ai_classifier=None)` to process multiple messages preserving order.
# - The module is rule-first and deterministic; supply `ai_classifier` to resolve low-confidence cases.
#
# Responsibilities:
# - Provide a small, deterministic tone detection component that is independent of routing, I/O,
#   or downstream business logic.
# - Be injection-friendly: accepts an optional AI classifier and pattern overrides.
# - Provide clear, testable outputs (dataclasses) and metadata for downstream components.
#
# Design notes:
# - Rule-based patterns use regexes and emoticon/unicode emoji heuristics.
# - Normalization preserves punctuation useful for tone (exclamation/question marks and emoticons).
# - AI integration is optional and must be injected by the caller.
#
# Examples:
# - "Thanks! That was helpful :)" -> Tone.FRIENDLY
# - "What do you mean?" -> Tone.CONFUSED
# - "This is unacceptable!!!" -> Tone.ANGRY
#
# TODOs are included near the bottom describing where to add richer models or i18n patterns.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, Iterable, List, Optional, Tuple

__all__ = [
    "Tone",
    "ToneTag",
    "detect_tone",
    "detect_batch",
    "is_negative_tone",
]

# Type for AI classifier injection: should accept raw text and return ToneTag or tuple (Tone, confidence, reason)
AIClassifier = Callable[[str], "ToneTag"]  # friendly duck-typing; adapters allowed


class Tone(Enum):
    FRIENDLY = auto()
    ANGRY = auto()
    CONFUSED = auto()
    NEUTRAL = auto()
    SAD = auto()
    HAPPY = auto()
    FORMAL = auto()
    INFORMAL = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class ToneTag:
    """
    Immutable result of tone detection.

    Fields:
    - tone: Tone enum
    - confidence: float [0.0, 1.0]
    - reason: short explanation (e.g., matched pattern or 'ai:classifier')
    - metadata: optional dict with matched patterns, emoticons, etc.
    """
    tone: Tone
    confidence: float
    reason: str
    metadata: Dict[str, object] = field(default_factory=dict)


# --- Normalization & helpers ---------------------------------------------------------

def _normalize_text_for_tone(text: str) -> str:
    """
    Lowercase and collapse whitespace while preserving punctuation that helps detect tone:
    - Keep: ! ? emoticons like :) :( :/ and common emoji characters.
    - Remove other special characters to simplify regex matching.
    """
    if not text:
        return ""
    text = text.strip().lower()
    # Preserve word chars, whitespace, question/exclamation marks, colons, hyphens, parentheses, and some emoji ranges.
    # Replace other punctuation with spaces.
    # Note: this is conservative - emoji are matched via explicit unicode ranges in patterns if needed.
    text = re.sub(r"[^\w\s\!\?\:\-\(\)\u263a-\U0001f64f]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_emoticons(text: str) -> List[str]:
    """
    Return a list of emoticon-like substrings found in the text.
    Recognizes common ascii emoticons and a few unicode emoji characters.
    """
    emoticon_patterns = [
        r"(:\)|:-\)|:\]|:d|:D|😊|🙂|😁|😄)",
        r"(:\(|:-\(|:\[|☹️|😢|😞)",
        r"(:/|:-/|:\\|:|/)",
        r"(;-\)|;\))",
        r"(:\||:-\|)",
    ]
    normalized = _normalize_text_for_tone(text)
    found: List[str] = []
    for p in emoticon_patterns:
        for m in re.findall(p, normalized, flags=re.IGNORECASE):
            if m:
                found.append(m)
    return found


def is_negative_tone(tag: ToneTag) -> bool:
    """
    Quick helper: returns True for tones that are typically negative (ANGRY, SAD, CONFUSED).
    """
    return tag.tone in {Tone.ANGRY, Tone.SAD, Tone.CONFUSED}


# --- Rule-based patterns ------------------------------------------------------------

# Patterns are intentionally conservative and language-focused (English). For i18n add pattern packs.
# Each tuple is (regex_pattern, weight). We use max-weight match per tone as the score.
_DEFAULT_TONE_PATTERNS: Dict[Tone, List[Tuple[str, float]]] = {
    Tone.FRIENDLY: [
        (r"\bthank(s| you)\b", 0.9),
        (r"\bappreciate\b", 0.8),
        (r"\bawesome\b", 0.8),
        (r"\bgreat\b", 0.7),
        (r"\bglad\b", 0.6),
        (r"\bpleased\b", 0.6),
        (r"\bwelcome\b", 0.5),
        (r"\bcheers\b", 0.6),
        (r"\bno problem\b", 0.6),
    ],
    Tone.HAPPY: [
        (r"\bjoy\b", 0.7),
        (r"\b(excited|yay|yayyy)\b", 0.8),
        (r"\bso happy\b", 0.9),
        (r"\blove this\b", 0.8),
    ],
    Tone.ANGRY: [
        (r"\b(unacceptable|ridiculous|outrageous|hate)\b", 0.9),
        (r"\b(this is (bull|bs)|wtf)\b", 1.0),
        (r"\bidiot\b", 0.9),
        (r"\b(annoy(ed|ing)|furious|angry|pissed)\b", 0.9),
        (r"!!!+", 0.9),
    ],
    Tone.CONFUSED: [
        (r"\bwhat do you mean\b", 1.0),
        (r"\bwhat does\b.*\bmean\b", 0.9),
        (r"\bnot sure\b", 0.7),
        (r"\bconfused\b", 0.9),
        (r"\bhow does that work\b", 0.8),
        (r"\bsorry\?\b", 0.6),
        (r"\bcan you clarify\b", 0.8),
    ],
    Tone.SAD: [
        (r"\bsad\b", 0.9),
        (r"\bunhappy\b", 0.8),
        (r"\bdepressed\b", 1.0),
        (r"\bupset\b", 0.8),
        (r"\bso sorry\b", 0.6),
    ],
    Tone.FORMAL: [
        (r"\bdear\b", 0.8),
        (r"\bregards\b", 0.9),
        (r"\bsincerely\b", 0.9),
        (r"\bplease find\b", 0.8),
    ],
    Tone.INFORMAL: [
        (r"\bums\b", 0.5),
        (r"\bhey\b", 0.6),
        (r"\byo\b", 0.7),
        (r"\bbrb\b", 0.6),
        (r"\bgotta\b", 0.6),
        (r"\blol\b", 0.6),
    ],
    Tone.NEUTRAL: [
        (r"\bokay\b", 0.5),
        (r"\bok\b", 0.5),
        (r"\bnoted\b", 0.6),
        (r"\balright\b", 0.5),
    ],
}


def _score_with_tone_patterns(text: str, patterns: Dict[Tone, List[Tuple[str, float]]]) -> Tuple[Tone, float, List[str]]:
    """
    Compute best-matching Tone using weighted pattern matches.
    Returns: (best_tone, confidence_score, matched_patterns)
    - confidence_score is taken as the maximum matched weight (not a calibrated probability).
    """
    normalized = _normalize_text_for_tone(text)
    best_tone = Tone.UNKNOWN
    best_score = 0.0
    matched_patterns: List[str] = []

    for tone, rules in patterns.items():
        tone_score = 0.0
        matched_for_tone: List[str] = []
        for pattern, weight in rules:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                tone_score = max(tone_score, weight)
                matched_for_tone.append(pattern)
        if tone_score > best_score:
            best_score = tone_score
            best_tone = tone
            matched_patterns = matched_for_tone

    # Emoticon heuristics can bump scores modestly:
    emoticons = _extract_emoticons(text)
    if emoticons:
        # Map some emoticon signals to tones
        for e in emoticons:
            emot = e.lower()
            if any(x in emot for x in [":)", ":-)", ":d", "😊", "🙂", "😁", "😄"]):
                # Friendly/happy emoticon: raise FRIENDLY/HAPPY a bit if not already high
                if best_tone not in {Tone.FRIENDLY, Tone.HAPPY} and best_score < 0.7:
                    # prefer FRIENDLY if neutral currently
                    best_tone = Tone.FRIENDLY
                    best_score = max(best_score, 0.65)
                    matched_patterns.append("emoticon:friendly")
                elif best_tone == Tone.FRIENDLY:
                    best_score = min(1.0, best_score + 0.05)
            if any(x in emot for x in [":(", ":-(", "😢", "☹️"]):
                if best_tone not in {Tone.SAD, Tone.ANGRY} and best_score < 0.7:
                    best_tone = Tone.SAD
                    best_score = max(best_score, 0.65)
                    matched_patterns.append("emoticon:sad")
                elif best_tone == Tone.SAD:
                    best_score = min(1.0, best_score + 0.05)
            if any(x in emot for x in [":/", ":-/"]):
                if best_score < 0.6:
                    best_tone = Tone.CONFUSED
                    best_score = max(best_score, 0.55)
                    matched_patterns.append("emoticon:confused")

    return best_tone, float(best_score), matched_patterns


# --- Public API ---------------------------------------------------------------------


def detect_tone(
    text: str,
    *,
    ai_classifier: Optional[AIClassifier] = None,
    patterns: Optional[Dict[Tone, List[Tuple[str, float]]]] = None,
) -> ToneTag:
    """
    Detect the conversational tone of `text`.

    Parameters:
    - text: input string to analyze.
    - ai_classifier: optional callable for ML classification (used only when rule confidence is low).
      Should return a ToneTag or a tuple (Tone, confidence, reason).
    - patterns: optional override for default patterns (useful for tests or domain tuning).

    Returns:
    - ToneTag with tone, confidence and reason. metadata includes matched_patterns and emoticons.
    """
    if not text or not text.strip():
        return ToneTag(tone=Tone.UNKNOWN, confidence=0.0, reason="empty input", metadata={})

    patterns_to_use = patterns if patterns is not None else _DEFAULT_TONE_PATTERNS

    tone, score, matched = _score_with_tone_patterns(text, patterns_to_use)
    emoticons = _extract_emoticons(text)
    metadata = {"matched_patterns": matched, "emoticons": emoticons}

    STRONG_THRESHOLD = 0.65
    # Return strong rule-based result immediately.
    if score >= STRONG_THRESHOLD and tone is not Tone.UNKNOWN:
        return ToneTag(tone=tone, confidence=score, reason=f"rule:{tone.name.lower()} (score={score:.2f})", metadata=metadata)

    # If provided, consult AI classifier for low-confidence cases.
    if ai_classifier is not None:
        try:
            candidate = ai_classifier(text)
            if isinstance(candidate, ToneTag):
                # Ensure metadata is merged non-destructively
                merged_meta = {**metadata, **candidate.metadata}
                return ToneTag(tone=candidate.tone, confidence=candidate.confidence, reason=candidate.reason, metadata=merged_meta)
            if isinstance(candidate, tuple) and len(candidate) >= 2:
                cand_tone = candidate[0]
                cand_conf = float(candidate[1])
                cand_reason = candidate[2] if len(candidate) > 2 else "ai:classifier"
                if isinstance(cand_tone, str):
                    try:
                        cand_tone = Tone[cand_tone.upper()]
                    except Exception:
                        cand_tone = Tone.UNKNOWN
                return ToneTag(
                    tone=cand_tone if isinstance(cand_tone, Tone) else Tone.UNKNOWN,
                    confidence=max(0.0, min(1.0, cand_conf)),
                    reason=str(cand_reason),
                    metadata={**metadata, "ai_used": True},
                )
        except Exception:
            # Don't raise for classifier failures; fall back to rule-based heuristics.
            pass

    # Fallback behavior: return best rule-derived tone even if low confidence, or NEUTRAL.
    if tone is not None and tone is not Tone.UNKNOWN and score > 0.0:
        return ToneTag(tone=tone, confidence=score, reason=f"rule_weak:{tone.name.lower()} (score={score:.2f})", metadata=metadata)

    # Final fallback: label as NEUTRAL with low confidence if no signal found but text is non-empty.
    return ToneTag(tone=Tone.NEUTRAL, confidence=0.25, reason="fallback:neutral", metadata=metadata)


def detect_batch(
    messages: Iterable[str],
    *,
    ai_classifier: Optional[AIClassifier] = None,
) -> List[ToneTag]:
    """
    Detect tones for a batch of messages. Preserves input order.
    """
    return [detect_tone(m, ai_classifier=ai_classifier) for m in messages]


# --- End of module ------------------------------------------------------------------

# Future Extensions (TODO):
# - TODO: Integrate a light-weight sentiment model or a hosted classifier as an injectable service (pass via ai_classifier).
#   Provide a small Protocol/typing for the classifier that enforces return types.
# - TODO: Add i18n pattern packs (non-English trigger words) that can be loaded by the caller.
# - TODO: Improve confidence calibration by mapping pattern weights to calibrated probabilities using a labeled dataset.
# - TODO: Add sarcasm detection heuristics (requires context beyond single-message heuristics) - pipeline-level work.
# - TODO: Consider exposing a diagnostics mode that returns full match details for observability during tests.
#
# Testing notes:
# - Unit tests should check deterministic behavior on messages that match multiple tones (priority is determined
#   by highest pattern weight then emoticon heuristics). Mock ai_classifier for tests covering AI fallback.

