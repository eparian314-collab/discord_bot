"""Environment-backed configuration helpers for LanguageBot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set


def _split_ints(value: str) -> Set[int]:
    ints: Set[int] = set()
    for chunk in (value or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ints.add(int(chunk))
        except ValueError:
            continue
    return ints


def _split_str(value: str, *, default: Optional[Sequence[str]] = None) -> List[str]:
    if not value:
        return list(default or [])
    return [item.strip().lower() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class LanguageBotConfig:
    discord_token: str
    owner_ids: Set[int] = field(default_factory=set)
    test_guild_ids: Set[int] = field(default_factory=set)
    deepl_api_key: Optional[str] = None
    deepl_endpoint: str = "https://api-free.deepl.com/v2/translate"
    my_memory_api_key: Optional[str] = None
    my_memory_email: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    provider_order: List[str] = field(default_factory=lambda: ["deepl", "openai", "mymemory", "google"])
    default_fallback_language: str = "EN"
    language_role_prefix: str = "lang-"
    bot_channel_id: Optional[int] = None  # Added for jitter
    policy_repo: Optional[object] = None  # Optional: PolicyRepository instance

    @classmethod
    def from_env(cls) -> "LanguageBotConfig":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN is required to run the bot")

        channel_value = os.getenv("BOT_CHANNEL_ID", "").strip()
        bot_channel_id = int(channel_value) if channel_value else None

        config = cls(
            discord_token=token,
            owner_ids=_split_ints(os.getenv("OWNER_IDS", "")),
            test_guild_ids=_split_ints(os.getenv("TEST_GUILDS", "")),
            deepl_api_key=os.getenv("DEEPL_API_KEY", "").strip() or None,
            my_memory_api_key=os.getenv("MY_MEMORY_API_KEY", "").strip() or None,
            my_memory_email=os.getenv("MYMEMORY_USER_EMAIL", "").strip() or None,
            openai_api_key=os.getenv("OPEN_AI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini").strip(),
            provider_order=_split_str(
                os.getenv("TRANSLATION_PROVIDERS", "deepl,openai,mymemory"),
                default=["deepl", "openai", "mymemory"],
            ),
            default_fallback_language=os.getenv("TRANSLATION_FALLBACK_LANGUAGE", "en").upper(),
            language_role_prefix=os.getenv("LANGUAGE_ROLE_PREFIX", "lang-").lower(),
            bot_channel_id=bot_channel_id,
        )
        return config


__all__ = ["LanguageBotConfig"]
