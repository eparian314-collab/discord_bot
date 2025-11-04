"""
Minimal profanity lexicon and helper utilities.

The data set is intentionally small and safe-extend or replace it in production
with more comprehensive resources as needed.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Set

_PROFANITY: Dict[str, Set[str]] = {
    "en": {"damn", "shit", "fuck"},
    "es": {"mierda", "coño", "joder"},
    "fr": {"merde", "putain"},
    "de": {"scheiße", "arsch"},
    "ja": {"くそ", "ばか"},
}

_WORD_RE = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)


def get_terms(language: str) -> Set[str]:
    """Return profanity terms for the language (lowercase)."""
    lang = (language or "").split("-", 1)[0].lower()
    return set(_PROFANITY.get(lang, ()))


def contains_profanity(text: str, *, language: Optional[str] = None) -> bool:
    """
    Basic profanity detection. If language not supplied, checks across all sets.
    """
    words = {match.group(0).lower() for match in _WORD_RE.finditer(text or "")}
    if not words:
        return False
    if language:
        profane = get_terms(language)
        return any(word in profane for word in words)
    for profane in _PROFANITY.values():
        if any(word in profane for word in words):
            return True
    return False


def add_terms(language: str, terms: Iterable[str]) -> None:
    """Extend the word list for a language at runtime."""
    lang = (language or "").split("-", 1)[0].lower()
    if lang not in _PROFANITY:
        _PROFANITY[lang] = set()
    _PROFANITY[lang].update(term.lower() for term in terms if term)


