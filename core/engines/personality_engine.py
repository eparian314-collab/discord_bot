from __future__ import annotations

from typing import Optional


class PersonalityEngine:
    """
    Provides personality strings and micro-prompts for bot responses.
    Can be extended with localization or style profiles.
    """

    def __init__(self, *, cache_manager) -> None:
        self.cache = cache_manager

    def greeting(self, user_name: str) -> str:
        return f"Hello {user_name}! 😊"

    def confirmation(self, text: str) -> str:
        return f"✅ {text}"

    def error(self) -> str:
        return "⚠️ Oops, something went wrong. Please try again."
