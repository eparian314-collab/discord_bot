"""
Contextual phrase library used for friendly system responses.

These phrases can be surfaced by routers or UI engines to provide lightweight
localized hints (e.g., when asking users to clarify a request).
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

_PHRASES: Dict[str, Dict[str, List[str]]] = {
    "en": {
        "greeting": ["Hello!", "Hey there!", "Hi, how can I help?"],
        "clarify": [
            "Could you tell me a bit more?",
            "Mind clarifying what you'd like translated?",
            "I'm here-just need a touch more detail.",
        ],
        "thanks": ["Thanks!", "Much appreciated!", "Thank you for the info!"],
    },
    "es": {
        "greeting": ["¡Hola!", "¡Buenas!", "¿En qué puedo ayudarte?"],
        "clarify": [
            "¿Podrías contarme un poco más?",
            "Necesito un poco más de contexto para ayudarte.",
        ],
        "thanks": ["¡Gracias!", "¡Muchas gracias!"],
    },
    "fr": {
        "greeting": ["Bonjour !", "Salut !", "Comment puis-je vous aider ?"],
        "clarify": [
            "Pouvez-vous préciser votre demande ?",
            "J'ai besoin d'un peu plus de contexte.",
        ],
        "thanks": ["Merci !", "Merci beaucoup !"],
    },
    "de": {
        "greeting": ["Hallo!", "Guten Tag!", "Wie kann ich helfen?"],
        "clarify": [
            "Kannst du das etwas genauer erklären?",
            "Ich brauche ein wenig mehr Kontext.",
        ],
        "thanks": ["Danke!", "Vielen Dank!"],
    },
    "ja": {
        "greeting": ["こんにちは！", "やあ！", "お手伝いしましょうか？"],
        "clarify": ["もう少し詳しく教えてください。", "もう少し情報をいただけますか？"],
        "thanks": ["ありがとうございます！", "助かりました！"],
    },
}


def get_phrases(language: str, category: str) -> List[str]:
    """Return all phrases for the given language/category or an empty list."""
    lang = (language or "").split("-", 1)[0].lower()
    return list(_PHRASES.get(lang, {}).get(category, []))


def get_random_phrase(language: str, category: str, *, fallback_language: str = "en") -> Optional[str]:
    """
    Return a random phrase for the language/category. Falls back to the provided
    fallback language if no phrase exists for the requested locale.
    """
    options = get_phrases(language, category)
    if not options and fallback_language:
        options = get_phrases(fallback_language, category)
    if not options:
        return None
    return random.choice(options)


def available_languages() -> List[str]:
    """Languages for which phrases are available."""
    return sorted(_PHRASES.keys())


