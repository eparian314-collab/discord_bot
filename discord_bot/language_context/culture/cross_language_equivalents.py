"""
Cross-language lexical equivalence helpers.

This module maps short expressions between languages so the system can offer
useful suggestions (e.g., teachable moments or hints for learners).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

# category -> language -> list of equivalents
_EQUIVALENTS: Dict[str, Dict[str, List[str]]] = {
    "greeting": {
        "en": ["hello", "hi"],
        "es": ["hola"],
        "fr": ["bonjour", "salut"],
        "de": ["hallo", "guten tag"],
        "ja": ["こんにちは", "やあ"],
    },
    "gratitude": {
        "en": ["thank you", "thanks"],
        "es": ["gracias", "muchas gracias"],
        "fr": ["merci", "merci beaucoup"],
        "de": ["danke", "vielen dank"],
        "ja": ["ありがとう", "ありがとうございます"],
    },
    "farewell": {
        "en": ["goodbye", "see you"],
        "es": ["adiós", "hasta luego"],
        "fr": ["au revoir", "à bientôt"],
        "de": ["tschüss", "bis bald"],
        "ja": ["さようなら", "またね"],
    },
    "polite_ack": {
        "en": ["you're welcome", "no problem"],
        "es": ["de nada", "no hay problema"],
        "fr": ["de rien", "pas de problème"],
        "de": ["gern geschehen", "kein problem"],
        "ja": ["どういたしまして", "問題ないよ"],
    },
}


def get_equivalents(category: str, language: str) -> List[str]:
    """Return the list of equivalents for a given category/language."""
    lang = (language or "").split("-", 1)[0].lower()
    return list(_EQUIVALENTS.get(category, {}).get(lang, []))


def get_category_pairs(category: str) -> Dict[str, List[str]]:
    """Return raw mapping for a category (copy) to avoid accidental mutation."""
    return {lang: list(words) for lang, words in _EQUIVALENTS.get(category, {}).items()}


def find_equivalent(word: str, *, target_language: str) -> Optional[str]:
    """
    Attempt to match a word in any language and return equivalent in target_language.
    """
    w = (word or "").strip().lower()
    if not w:
        return None
    target = target_language.split("-", 1)[0].lower()
    for category, lang_map in _EQUIVALENTS.items():
        for lang, entries in lang_map.items():
            if w in (entry.lower() for entry in entries):
                candidates = lang_map.get(target, [])
                return candidates[0] if candidates else None
    return None


def categories() -> Iterable[str]:
    """Available equivalence categories."""
    return _EQUIVALENTS.keys()


