"""Personality helpers that optionally integrate with OpenAI."""

from __future__ import annotations

from typing import Optional

try:  # pragma: no cover - optional dependency
    from language_bot.core.openai_engine import OpenAIEngine  # type: ignore
except Exception:  # pragma: no cover
    OpenAIEngine = None  # type: ignore


class PersonalityEngine:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._openai: Optional[OpenAIEngine] = None  # type: ignore[assignment]
        if OpenAIEngine is not None and api_key:
            self._openai = OpenAIEngine(api_key=api_key, model=model)

    def get_personality_prompt(self, persona: str) -> str:
        """Return a prompt string for the given persona."""
        return f"[Personality: {persona}]"

    async def get_ai_personality_reply(self, persona, user_message):
        """Generate a personality-driven reply using OpenAI."""
        if not self._openai:
            raise RuntimeError("OpenAIEngine is not configured")
        return await self._openai.personality_response(persona, user_message)
