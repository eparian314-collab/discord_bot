from __future__ import annotations

import random
from typing import Dict, Iterable, List

from .personality_prompts import PERSONALITY_PROMPTS


class PersonalityEngine:
    """Local, non-AI personality helper for FunBot.

    The engine exposes a small API for formatting named messages with a
    consistent tone. It chooses from a set of predefined templates for
    the active persona, falling back to the "classic" persona when
    needed.
    """

    def __init__(self, persona: str = "classic") -> None:
        self.persona = persona if persona in PERSONALITY_PROMPTS else "classic"

    def _get_templates(self, message_key: str) -> List[str]:
        data: Dict[str, Dict[str, List[str]]] = PERSONALITY_PROMPTS
        # Prefer the active persona, then fall back to classic.
        if self.persona in data and message_key in data[self.persona]:
            return data[self.persona][message_key]
        if "classic" in data and message_key in data["classic"]:
            return data["classic"][message_key]
        # As a last resort, return a generic template.
        return [message_key]

    def format(self, message_key: str, **kwargs: object) -> str:
        """Format a message for a given key and parameters."""

        templates = self._get_templates(message_key)
        template = random.choice(templates)
        try:
            return template.format(**kwargs)
        except Exception:
            # Avoid crashing on formatting mistakes; fall back to the raw template.
            return template


__all__ = ["PersonalityEngine"]
