"""Async OpenAI helper using the v1 SDK.

This implementation prefers the low-cost model by default and reads the
standard `OPENAI_API_KEY` (with legacy fallback) from the environment when
not provided explicitly.
"""

from __future__ import annotations

import os
from typing import Any, List

try:  # pragma: no cover - import guard for environments without openai installed
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore


class OpenAIEngine:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        raw_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
        self.api_key = raw_key or ""
        self.model = (model or os.getenv("OPENAI_TRANSLATION_MODEL") or "gpt-4o-mini").strip()
        self._client = AsyncOpenAI(api_key=self.api_key) if (AsyncOpenAI and self.api_key) else None

    async def chat_completion(self, messages: List[dict[str, Any]], temperature: float = 0.7) -> str:
        if not self._client:
            raise RuntimeError("OpenAI client is not configured")
        completion = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        choice = completion.choices[0]
        content = getattr(choice.message, "content", "") or ""
        return content.strip()

    async def personality_response(self, persona: str, user_message: str) -> str:
        system_prompt = (
            f"You are a Discord bot with a {persona} personality. "
            f"Respond concisely and in character."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return await self.chat_completion(messages)
