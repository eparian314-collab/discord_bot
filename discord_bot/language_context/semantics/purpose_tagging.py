# Purpose: Tag message purpose (ask ? translate / ask ? define / ask ? generate response)
#
# READING GUIDE:
# - Use `tag_purpose(text, ai_classifier=None, language_hint=None)` to get a `PurposeTag`.
# - The module is rule-based by default; supply `ai_classifier` to override low-confidence cases.
# - Small helpers (`is_question`, `tag_batch`) are provided for common cases.
#
# Responsibilities:
# - Classify a single message's communicative purpose into a small set of well-defined categories.
# - Be rule-first and deterministic; provide an optional AI hook for improved accuracy.
# - Remain independent from downstream routers, pipelines, or I/O concerns.
#
# Design notes:
# - Rule-based patterns use lightweight regexes and a weighted scoring heuristic.
# - Normalization keeps question marks (used to detect questions) but strips other punctuation.
# - The module surfaces clear TODOs where integration with language detection, tokenizer, or ML
#   classifiers could be added; such integrations must be injected, not imported here.
#
# Examples:
# - "Can you translate 'hello' into Spanish?" -> Purpose.TRANSLATE
# - "What does 'serendipity' mean?" -> Purpose.DEFINE
# - "Write me a short poem about autumn." -> Purpose.GENERATE
#
# Note: Keep this module focused � routing of tagged messages and actual processing (translate/define/generate)
# belongs to other components in the system.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, Iterable, List, Optional, Tuple

# Public API
__all__ = [
    "Purpose",
    "PurposeTag",
    "tag_purpose",
    "tag_batch",
    "is_question",
]

# Type for AI classifier injection: takes text and returns PurposeTag or a tuple (Purpose, confidence, reason).
AIClassifier = Callable[[str], "PurposeTag"]  # duck-typed; other return shapes are tolerated via adapters below


class Purpose(Enum):
    TRANSLATE = auto()
    DEFINE = auto()
    GENERATE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class PurposeTag:
    """
    Immutable result of purpose-tagging.

    Fields:
    - purpose: the enumerated purpose
    - confidence: float in [0.0, 1.0] representing confidence in the tag
    - reason: short human-readable explanation of why the tag was selected
    - metadata: optional dictionary for downstream systems (e.g., matched_patterns)
    """
    purpose: Purpose
    confidence: float
    reason: str
    metadata: Dict[str, object] = field(default_factory=dict)


# --- Normalization & simple utilities -------------------------------------------------

def _normalize_text(text: str) -> str:
    """
    Normalize text for pattern matching:
    - Lowercase
    - Collapse whitespace
    - Remove punctuation except question marks (which help detect interrogatives)
    """
    text = text.lower().strip()
    # Keep question marks, remove other punctuation characters.
    # Preserve letters, digits, whitespace and '?'
    text = re.sub(r"[^\w\s\?]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def is_question(text: str) -> bool:
    """
    Heuristic to detect questions:
    - Presence of a question mark OR leading interrogative words ("what", "why", "how", "when", "where", "who", "which").
    """
    if "?" in text:
        return True
    normalized = _normalize_text(text)
    return bool(re.match(r"^(what|why|how|when|where|who|which)\b", normalized))


# --- Rule-based patterns with weights ------------------------------------------------
# Patterns are applied in priority order (higher weight wins). Patterns are simple regexes
# using word boundaries to avoid accidental matches.
#
# If you add or tune patterns, prefer explicit words/phrases over trying to catch all grammar.

_DEFAULT_PATTERNS: Dict[Purpose, List[Tuple[str, float]]] = {
    Purpose.TRANSLATE: [
        (r"\btranslate\b", 1.0),
        (r"\bhow do you say\b", 0.9),
        (r"\bhow to say\b", 0.9),
        (r"\bhow (do|would) i say\b", 0.9),
        (r"\binto (spanish|french|german|italian|chinese|japanese|portuguese)\b", 0.8),
        (r"\bin (spanish|french|german|italian|chinese|japanese|portuguese)\b", 0.6),
        (r"\bwhat's that in\b", 0.8),
        (r"\btraduce\b", 1.0),  # Spanish command
        (r"\btraduction\b", 1.0),  # French
    ],
    Purpose.DEFINE: [
        (r"\bdefine\b", 1.0),
        (r"\bdefinition\b", 1.0),
        (r"\bwhat does\b.*\bmean\b", 1.0),
        (r"\bwhat is\b", 0.8),
        (r"\bmeaning of\b", 1.0),
        (r"\bmeaning\b", 0.6),
        (r"\bexplain\b", 0.7),
    ],
    Purpose.GENERATE: [
        (r"\bwrite\b", 0.9),
        (r"\bgenerate\b", 0.9),
        (r"\bcreate\b", 0.8),
        (r"\bcompose\b", 0.8),
        (r"\bdraft\b", 0.8),
        (r"\bgive me\b", 0.7),
        (r"\bsuggest\b", 0.6),
        (r"\bexample\b", 0.6),
        (r"\breply to\b", 0.9),
        (r"\brespond to\b", 0.9),
        (r"\bcan you\b", 0.5),  # low weight � ambiguous without more context
    ],
}


def _score_with_patterns(text: str, patterns: Dict[Purpose, List[Tuple[str, float]]]) -> Tuple[Purpose, float, List[str]]:
    """
    Compute the best-matching Purpose using weighted pattern matches.
    Returns: (best_purpose, confidence_score, matched_patterns_list)
    - confidence_score is normalized to [0.0, 1.0], but not a calibrated probability.
    """
    normalized = _normalize_text(text)
    best_purpose = Purpose.UNKNOWN
    best_score = 0.0
    matched_patterns: List[str] = []

    for purpose, rules in patterns.items():
        purpose_score = 0.0
        matched_for_purpose: List[str] = []
        for pattern, weight in rules:
            if re.search(pattern, normalized):
                purpose_score = max(purpose_score, weight)  # take max weight match per purpose
                matched_for_purpose.append(pattern)
        if purpose_score > best_score:
            best_score = purpose_score
            best_purpose = purpose
            matched_patterns = matched_for_purpose

    # If nothing matched, but the text looks like a question, bump GENERATE slightly
    if best_purpose is Purpose.UNKNOWN and is_question(text):
        # Many user questions are general queries (generate/explain) rather than translations/definitions.
        return Purpose.GENERATE, 0.45, ["heuristic:question_no_match"]
    return best_purpose, float(best_score), matched_patterns


# --- Public API ---------------------------------------------------------------------


def tag_purpose(
    text: str,
    *,
    ai_classifier: Optional[AIClassifier] = None,
    language_hint: Optional[str] = None,
    patterns: Optional[Dict[Purpose, List[Tuple[str, float]]]] = None,
) -> PurposeTag:
    """
    Tag the purpose of `text`.

    Parameters:
    - text: the user input to tag
    - ai_classifier: optional callable injected by the caller for ML classification. It should accept
      the raw text and return a PurposeTag (preferred) or a tuple (Purpose, confidence, reason).
      This classifier is used only when rule-based confidence is low.
    - language_hint: optional string to hint at target/source language (not used by default rules).
    - patterns: optional override for default patterns (useful for tests or domain-specific tuning).

    Returns:
    - PurposeTag with purpose, confidence (0..1), and reason + metadata including matched_patterns.
    """
    if not text or not text.strip():
        return PurposeTag(
            purpose=Purpose.UNKNOWN,
            confidence=0.0,
            reason="empty input",
        )

    patterns_to_use = patterns if patterns is not None else _DEFAULT_PATTERNS

    # 1) Rule-based pass
    purpose, score, matched_patterns = _score_with_patterns(text, patterns_to_use)
    reason = f"rule:{purpose.name.lower() if purpose is not None else 'unknown'} (score={score:.2f})"
    metadata = {"matched_patterns": matched_patterns, "language_hint": language_hint}

    # If the rule gives a strong signal, return immediately.
    STRONG_THRESHOLD = 0.6
    if score >= STRONG_THRESHOLD and purpose is not None and purpose is not Purpose.UNKNOWN:
        return PurposeTag(purpose=purpose, confidence=score, reason=reason, metadata=metadata)

    # 2) If AI classifier is provided, consult it for low-confidence cases.
    if ai_classifier is not None:
        try:
            candidate = ai_classifier(text)
            # Accept several return shapes to be friendly to adapters:
            if isinstance(candidate, PurposeTag):
                return candidate
            if isinstance(candidate, tuple) and len(candidate) >= 2:
                cand_purpose = candidate[0]
                cand_conf = float(candidate[1])
                cand_reason = candidate[2] if len(candidate) > 2 else "ai:classifier"
                # Normalize cand_purpose if passed as string
                if isinstance(cand_purpose, str):
                    try:
                        cand_purpose = Purpose[cand_purpose.upper()]
                    except Exception:
                        cand_purpose = Purpose.UNKNOWN
                return PurposeTag(
                    purpose=cand_purpose if isinstance(cand_purpose, Purpose) else Purpose.UNKNOWN,
                    confidence=max(0.0, min(1.0, cand_conf)),
                    reason=str(cand_reason),
                    metadata={**metadata, "ai_used": True},
                )
            # Fallback if return shape is unexpected
        except Exception:
            # Avoid throwing if AI hook fails � fall back to rule result.
            pass

    # 3) Rule-based fallback: if some score exists return it; otherwise mark unknown/question heuristic.
    if purpose is not None and purpose is not Purpose.UNKNOWN and score > 0.0:
        return PurposeTag(purpose=purpose, confidence=score, reason=reason, metadata=metadata)

    # Final fallback: unknown or weak heuristic
    # If it's a question, prefer GENERATE with low confidence.
    if is_question(text):
        return PurposeTag(
            purpose=Purpose.GENERATE,
            confidence=0.45,
            reason="fallback:question_heuristic",
            metadata=metadata,
        )

    return PurposeTag(purpose=Purpose.UNKNOWN, confidence=0.0, reason="fallback:unknown", metadata=metadata)


def tag_batch(
    messages: Iterable[str],
    *,
    ai_classifier: Optional[AIClassifier] = None,
    language_hint: Optional[str] = None,
) -> List[PurposeTag]:
    """
    Tag a batch of messages. Keeps ordering of input messages.
    """
    return [tag_purpose(m, ai_classifier=ai_classifier, language_hint=language_hint) for m in messages]


# --- End of module ------------------------------------------------------------------

# Future Extensions (TODOs):
# - TODO: Integrate with the project's tokenizer and language detector (language_context/tokenizer.py and
#   a language detection component). Accept language hints to improve translate-pattern detection.
# - TODO: Add a small calibration layer to map rule weights to calibrated probabilities (requires dataset).
# - TODO: Provide a lightweight Protocol type for ai_classifier to make static typing stricter once typing.Protocol
#   is acceptable in the codebase.
# - TODO: Add more i18n patterns (non-English trigger words) and allow external pattern packs to be loaded
#   by the calling code rather than importing them here.
#
# Notes on testing:
# - Unit tests should exercise combinations of inputs that trigger conflicting patterns (e.g., "How do you say 'hello' and what does 'bonjour' mean?")
#   and assert deterministic priority behaviour. Keep AI classifier mocked during tests.

