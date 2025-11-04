"""
Reading Guide
--------------
Purpose:
- Provide normalization, lightweight tokenization, and simple language detection
  utilities for the Language Context Engine.
- Keep this module AI-optional: it works fully with deterministic, rule-based
  logic and exposes hooks to inject AI or third-party detectors/tokenizers later.

Flow:
- Instantiate `Normalizer` with optional custom components (tokenizer, detector).
- Call `normalize()` to get a `NormalizationResult` dataclass containing:
  * original text
  * normalized text
  * tokens (with positions and token types)
  * detected language (best-effort rule-based fallback)
  * optional metadata for downstream components

Design notes:
- Small, composable helpers; each step is a pure function where possible.
- No business or command logic here -- this module only processes text.
- Integrations (AI or advanced NLP libraries) should be wired via `set_*`
  methods or by passing callables into the constructor.
- Avoids heavy external dependencies; if a dependency is desired (e.g. `unidecode`
  or an ML model), plug it in later via the injection points.

TODOs & Extension Points:
- Add sentence segmentation and richer token classification (NER) by injecting a
  sentence splitter / NLP pipeline.
- Add integration loader for pluggable language models (see TODOs lower in file).
- Add tests for corner cases (emoji-only strings, code blocks, mixed-language).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Pattern, Tuple

# Public dataclasses ---------------------------------------------------------

@dataclass(frozen=True)
class Token:
    """
    A minimal token representation.
    token_type: e.g. "word", "emoji", "punct", "url"
    start/end: byte offsets (Python string indices) of token within the original text
    """
    text: str
    start: int
    end: int
    token_type: str = "word"

@dataclass
class NormalizationResult:
    """
    A container for normalization outputs that downstream components (cogs or
    engines) should consume. Keep this plain and serializable-friendly.
    """
    original: str
    normalized: str
    tokens: List[Token] = field(default_factory=list)
    language: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

# Type aliases for injection -------------------------------------------------
TokenizerFn = Callable[[str], List[Token]]
LanguageDetectorFn = Callable[[str, Optional[str]], Optional[str]]

# Constants & compiled regexes ----------------------------------------------
_WHITESPACE_RE: Pattern[str] = re.compile(r"\s+", flags=re.UNICODE)
# Match words including ASCII letters and Latin accents.
# Additional accented ranges covered in regex literal.
_WORD_RE: Pattern[str] = re.compile(
    r"[A-Za-z\u00C0-\u024F]+(?:'[A-Za-z\u00C0-\u024F]+)?", flags=re.UNICODE
)
_URL_RE: Pattern[str] = re.compile(
    r"https?://[^\s]+|www\.[^\s]+", flags=re.IGNORECASE | re.UNICODE
)
_EMOJI_RE: Pattern[str] = re.compile(
    # A small emoji heuristic using the unicode emoji ranges.
    r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0000200D\u2600-\u26FF]+",
    flags=re.UNICODE
)
_PUNCT_RE: Pattern[str] = re.compile(r"[^\w\s]", flags=re.UNICODE)

# Helper utilities ----------------------------------------------------------

def _load_language_map() -> Dict[str, List[str]]:
    """
    Attempt to load a local `language_map.json` in the same directory; this is
    optional and the function returns an empty mapping if the file can't be read.
    The expected shape (if present) might be:
      { "en": ["the", "and", "is"], "es": ["el", "la", "y"], ... }
    This is used as an optional heuristic for detection.
    """
    try:
        base = os.path.dirname(__file__)
        path = os.path.join(base, "language_map.json")
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                # Normalize values to lists of words
                return {k: (v if isinstance(v, list) else []) for k, v in data.items()}
    except Exception:
        # Silently ignore -- map is best-effort only.
        pass
    return {}

_LANGUAGE_MAP = _load_language_map()

# Script-level heuristics and lightweight keyword dictionaries help the
# confidence-aware detector remain deterministic without external libraries.
_SCRIPT_PATTERNS: Tuple[Tuple[str, Pattern[str], float], ...] = (
    ("ja", re.compile(r"[\u3040-\u30FF\u31F0-\u31FF]"), 0.99),
    ("ko", re.compile(r"[\u1100-\u11FF\uAC00-\uD7AF]"), 0.99),
    ("zh", re.compile(r"[\u4E00-\u9FFF]"), 0.99),
    ("ru", re.compile(r"[\u0400-\u04FF]"), 0.99),
    ("el", re.compile(r"[\u0370-\u03FF]"), 0.90),
)

_LANGUAGE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    # Keep these intentionally small; they act as soft signals rather than a
    # comprehensive vocabulary.
    "en": (
        "a",
        "an",
        "and",
        "are",
        "be",
        "bruh",
        "cool",
        "for",
        "friend",
        "fr",
        "funny",
        "good",
        "great",
        "hello",
        "hey",
        "idea",
        "idk",
        "is",
        "it",
        "know",
        "lol",
        "maybe",
        "nah",
        "ok",
        "project",
        "really",
        "think",
        "this",
        "ya",
        "yeah",
        "you",
    ),
    "es": (
        "amiga",
        "amigo",
        "amigos",
        "buenas",
        "buenos",
        "como",
        "contigo",
        "dias",
        "gracias",
        "hola",
        "hoy",
        "manana",
        "mi",
        "nosotros",
        "esta",
        "estas",
        "estoy",
        "usted",
        "ustedes",
        "vamos",
        "voy",
    ),
    "fr": (
        "allez",
        "ami",
        "amie",
        "aujourdhui",
        "bien",
        "bonjour",
        "comment",
        "etre",
        "ete",
        "merci",
        "non",
        "nous",
        "oui",
        "salut",
        "tres",
        "vous",
    ),
}

def _strip_accents(token: str) -> str:
    """Remove accents/diacritics for keyword comparisons."""
    normalized = unicodedata.normalize("NFKD", token)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _replace_smart_quotes(text: str) -> str:
    """Replace common smart quotes and dashes with ASCII equivalents."""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...",
    }
    return text.translate(str.maketrans(replacements))

def _strip_control_chars(text: str) -> str:
    """Remove control characters except common whitespace (tab/newline)."""
    return "".join(ch for ch in text if ch == "\t" or ch == "\n" or unicodedata.category(ch)[0] != "C")

def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()

def _unicode_normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)

def _remove_zero_width(text: str) -> str:
    return re.sub(r"[\u200B-\u200F\uFEFF]", "", text)

# Default tokenizer & detector (rule-based) --------------------------------

def default_tokenizer(text: str) -> List[Token]:
    """
    Lightweight tokenizer that returns words, urls, emojis and punctuation as tokens.
    Not intended to replace a full NLP tokenizer; this is a pragmatic default.
    """
    tokens: List[Token] = []
    i = 0
    length = len(text)

    # Simple loop scanning for URLs, emojis, words, then fall back to punctuation/other.
    while i < length:
        # Try URL
        m_url = _URL_RE.match(text, i)
        if m_url:
            tokens.append(Token(m_url.group(0), m_url.start(), m_url.end(), token_type="url"))
            i = m_url.end()
            continue

        # Try emoji
        m_emoji = _EMOJI_RE.match(text, i)
        if m_emoji:
            tokens.append(Token(m_emoji.group(0), m_emoji.start(), m_emoji.end(), token_type="emoji"))
            i = m_emoji.end()
            continue

        # Try word
        m_word = _WORD_RE.match(text, i)
        if m_word:
            tokens.append(Token(m_word.group(0), m_word.start(), m_word.end(), token_type="word"))
            i = m_word.end()
            continue

        # Single punctuation / other char
        tokens.append(Token(text[i], i, i + 1, token_type="punct"))
        i += 1

    return tokens

def default_language_detector(text: str, hint: Optional[str] = None) -> Optional[str]:
    """
    Best-effort, rule-based language detection using:
    - explicit hint if provided
    - quick unicode-range heuristics (CJK, Cyrillic)
    - frequency heuristics using `_LANGUAGE_MAP` if loaded
    Returns a short language code (e.g. "en", "es") or None if unknown.
    """
    if not text:
        return hint

    # 1) Use explicit hint if it seems valid
    if hint:
        return hint

    # 2) Quick unicode heuristics
    if re.search(r"[\u3040-\u30FF\u31F0-\u31FF]", text):
        return "ja"
    if re.search(r"[\u1100-\u11FF\uAC00-\uD7AF]", text):
        return "ko"
    # Detect CJK (assume zh unless a more specific script matched above)
    if re.search(r"[\u4E00-\u9FFF]", text):
        return "zh"
    # Detect Cyrillic
    if re.search(r"[\u0400-\u04FF]", text):
        return "ru"
    # Detect Greek
    if re.search(r"[\u0370-\u03FF]", text):
        return "el"

    # 3) ASCII proportion heuristic -> maybe English or other Latin-based language
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    ascii_prop = ascii_chars / max(1, len(text))
    if ascii_prop > 0.9:
        # Heuristic: default to English for mostly-ASCII short texts
        return "en"

    # 4) Use language map frequency overlap if available
    words = re.findall(r"\b\w+\b", text.lower(), flags=re.UNICODE)
    if words and _LANGUAGE_MAP:
        scores: Dict[str, int] = {}
        word_set = set(words)
        for lang, tokens in _LANGUAGE_MAP.items():
            if not tokens:
                continue
            overlap = len(word_set.intersection(set(t.lower() for t in tokens)))
            if overlap:
                scores[lang] = overlap
        if scores:
            # return the language with the highest overlap
            return max(scores.items(), key=lambda kv: kv[1])[0]

    # Unknown
    return None

# Normalizer class ----------------------------------------------------------

class Normalizer:
    """
    The central normalizer object for the language_context. It supports:
    - normalization pipeline (unicode normalization, smart quotes, control char removal, whitespace)
    - tokenization (injected or default)
    - language detection (injected or default)
    - AI optional hooks (pass an AI detector/tokenizer if available)

    Keep instances cheap to create in tests. The pipeline functions are pure and
    can be called individually if needed.
    """

    def __init__(
        self,
        tokenizer: Optional[TokenizerFn] = None,
        language_detector: Optional[LanguageDetectorFn] = None,
        preserve_case: bool = False,
    ) -> None:
        """
        Provide optional callables for tokenizer and language detector to allow
        easy injection for unit tests or integration with real NLP libraries.
        """
        self._tokenizer = tokenizer or default_tokenizer
        self._language_detector = language_detector or default_language_detector
        self.preserve_case = preserve_case

    # Injection convenience -------------------------------------------------
    def set_tokenizer(self, tokenizer: TokenizerFn) -> None:
        """Swap in a custom tokenizer at runtime (useful for tests/integrations)."""
        self._tokenizer = tokenizer

    def set_language_detector(self, detector: LanguageDetectorFn) -> None:
        """Swap in a custom language detector (e.g. fasttext/transformer-based)."""
        self._language_detector = detector

    # Normalization pipeline steps -----------------------------------------
    def clean_text(self, text: str) -> str:
        """
        Apply deterministic cleaning steps in order. This function is pure and
        suitable for unit testing.
        """
        text = text or ""
        text = _unicode_normalize(text)
        text = _replace_smart_quotes(text)
        text = _remove_zero_width(text)
        text = _strip_control_chars(text)
        # Optionally lower-case; keep decision at Normalizer level for flexibility
        if not self.preserve_case:
            text = text.lower()
        text = _collapse_whitespace(text)
        return text

    def tokenize(self, text: str) -> List[Token]:
        """
        Tokenizes using the injected/default tokenizer. Downstream code should
        not depend on token types beyond the minimal enum-like strings used here.
        """
        return self._tokenizer(text)

    def detect_language(self, text: str, hint: Optional[str] = None) -> Optional[str]:
        """
        Detect language using injected detector with fallback to the default detector.
        Keep this method small so it can be mocked in tests.
        """
        try:
            lang = self._language_detector(text, hint)
            return lang
        except Exception:
            # Detector must not raise for normal input; treat as unknown on failure.
            return None

    # High-level API -------------------------------------------------------
    def normalize(self, text: str, language_hint: Optional[str] = None) -> NormalizationResult:
        """
        High-level normalization pipeline:
          1) Keep original text
          2) Clean text (deterministic)
          3) Detect language (hint allowed)
          4) Tokenize normalized text
          5) Construct NormalizationResult

        This function intentionally avoids any external IO or network calls.
        """
        original = text or ""
        cleaned = self.clean_text(original)
        language = self.detect_language(cleaned, language_hint)
        tokens = self.tokenize(cleaned)

        metadata: Dict[str, object] = {
            "token_count": len(tokens),
            # Placeholders for future metrics (confidence, warnings, truncation)
        }

        return NormalizationResult(
            original=original,
            normalized=cleaned,
            tokens=tokens,
            language=language,
            metadata=metadata,
        )

    # AI-optional helper (non-blocking) -----------------------------------
    def normalize_with_optional_ai(
        self,
        text: str,
        language_hint: Optional[str] = None,
        ai_detector: Optional[LanguageDetectorFn] = None,
    ) -> NormalizationResult:
        """
        A convenience wrapper that will call an AI detector if provided, falling
        back to the configured detector otherwise. The AI detector is user-supplied
        and may call external APIs; this function never depends on external APIs.
        """
        original = text or ""
        cleaned = self.clean_text(original)

        # Use AI detector only if supplied. Keep callsite isolated to allow mocking.
        if ai_detector:
            try:
                language = ai_detector(cleaned, language_hint)
            except Exception:
                language = self.detect_language(cleaned, language_hint)
        else:
            language = self.detect_language(cleaned, language_hint)

        tokens = self.tokenize(cleaned)
        return NormalizationResult(original, cleaned, tokens, language, metadata={"token_count": len(tokens)})

# Module-level quick helpers for convenience -------------------------------

def detect_language_with_confidence(
    text: str,
    language_hint: Optional[str] = None,
) -> Tuple[Optional[str], float]:
    """
    Lightweight language detector that returns a `(code, confidence)` pair.

    The implementation intentionally mirrors the deterministic heuristics used
    throughout this module so tests can run without heavy NLP dependencies.
    Confidence is a rough heuristic in the 0.0-1.0 range; the goal is to
    provide relative strength (e.g. "definitely Korean" vs. "probably English")
    rather than statistical certainty.
    """
    cleaned = _collapse_whitespace(
        _strip_control_chars(_remove_zero_width(_unicode_normalize(text or "")))
    )
    if not cleaned:
        if language_hint:
            return language_hint, 0.99
        return None, 0.0

    if language_hint:
        return language_hint, 0.99

    # Strong script-based signals take precedence and yield near-certain scores.
    for lang, pattern, confidence in _SCRIPT_PATTERNS:
        if pattern.search(cleaned):
            return lang, confidence

    words = re.findall(r"[A-Za-z\u00C0-\u024F]+", cleaned.lower())
    ascii_chars = sum(1 for ch in cleaned if ord(ch) < 128)
    ascii_prop = ascii_chars / max(1, len(cleaned))
    latin_words = [_strip_accents(w) for w in words]

    best_lang: Optional[str] = None
    best_conf = 0.0
    best_unique_hits = 0

    for lang, keywords in _LANGUAGE_KEYWORDS.items():
        hits = [w for w in latin_words if w in keywords]
        if not hits:
            continue

        coverage = len(hits) / max(1, len(latin_words))
        unique_hits = len(set(hits))
        hit_bonus = min(0.25, len(hits) * 0.1)
        diversity_bonus = min(0.1, unique_hits * 0.05)
        length_bonus = min(0.1, len(cleaned) / 120.0)
        confidence = min(1.0, 0.45 + 0.45 * coverage + hit_bonus + diversity_bonus + length_bonus)

        if (confidence > best_conf) or (confidence == best_conf and unique_hits > best_unique_hits):
            best_lang = lang
            best_conf = confidence
            best_unique_hits = unique_hits

    if best_lang:
        return best_lang, best_conf

    if ascii_prop > 0.85:
        slang_hits = sum(1 for w in latin_words if w in _LANGUAGE_KEYWORDS.get("en", ()))
        length_bonus = min(0.2, len(cleaned) / 200.0)
        base_conf = 0.35 + (ascii_prop - 0.85) * 0.6
        confidence = min(0.85, base_conf + length_bonus + min(0.2, slang_hits * 0.1))
        return "en", max(0.2, confidence)

    # Fall back to the default detector for any remaining scripts.
    fallback = default_language_detector(cleaned)
    if fallback:
        return fallback, 0.2
    return None, 0.0


_default_normalizer = Normalizer()

def normalize(text: str, language_hint: Optional[str] = None) -> NormalizationResult:
    """
    Convenience function used by thin cogs or other modules that don't need a
    custom Normalizer instance.
    """
    return _default_normalizer.normalize(text, language_hint)

# Example: small utility to preserve code blocks (TODO placeholder) ---------
def preserve_code_blocks_before_normalize(text: str) -> Tuple[str, List[Tuple[int, int, str]]]:
    """
    Placeholder helper: extract fenced code blocks and return masked text plus
    metadata about extracted blocks. This prevents normalization from corrupting
    markup like backticks or code that should remain verbatim.

    Current implementation is minimal; a full implementation should handle
    nested fences and language identifiers.
    """
    fence_re = re.compile(r"(```[\s\S]*?```)", flags=re.MULTILINE)
    blocks = []
    def _repl(m):
        idx = len(blocks)
        blocks.append((m.start(), m.end(), m.group(0)))
        return f"__CODE_BLOCK_{idx}__"

    masked = fence_re.sub(_repl, text)
    return masked, blocks

# End of file.
