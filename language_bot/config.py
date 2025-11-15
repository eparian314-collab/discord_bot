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
    # Default to lowest-cost providers first; OpenAI is *not* used as a
    # translation provider by default (reserved for personality only).
    provider_order: List[str] = field(default_factory=lambda: ["mymemory", "google", "deepl"])
    default_fallback_language: str = "EN"
    language_role_prefix: str = "lang-"
    bot_channel_id: Optional[int] = None  # Added for jitter
    policy_repo: Optional[object] = None  # Optional: PolicyRepository instance
    # New config fields
    server_default_language: str = "en"
    auto_translate_enabled: bool = False
    auto_translate_confidence_threshold: float = 0.7
    auto_translate_min_length: int = 15
    timezone: str = "UTC"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "LanguageBotConfig":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN is required to run the bot")

        channel_value = os.getenv("BOT_CHANNEL_ID", "").strip()
        # Accept a single ID or a comma/semicolon-separated list and use
        # the first valid integer as the configured bot channel.
        bot_channel_ids = _split_ints(channel_value)
        bot_channel_id = next(iter(bot_channel_ids)) if bot_channel_ids else None

        # New config fields
        server_default_language = os.getenv("SERVER_DEFAULT_LANGUAGE", "en")
        auto_translate_enabled = os.getenv("AUTO_TRANSLATE_ENABLED", "false").lower() == "true"
        try:
            auto_translate_confidence_threshold = float(os.getenv("AUTO_TRANSLATE_CONFIDENCE_THRESHOLD", "0.7"))
        except ValueError:
            auto_translate_confidence_threshold = 0.7
        try:
            auto_translate_min_length = int(os.getenv("AUTO_TRANSLATE_MIN_LENGTH", "15"))
        except ValueError:
            auto_translate_min_length = 15
        timezone = os.getenv("TIMEZONE", "UTC")
        log_level = os.getenv("LOG_LEVEL", "INFO")

        config = cls(
            discord_token=token,
            owner_ids=_split_ints(os.getenv("OWNER_IDS", "")),
            test_guild_ids=_split_ints(os.getenv("TEST_GUILDS", "")),
            deepl_api_key=os.getenv("DEEPL_API_KEY", "").strip() or None,
            deepl_endpoint=os.getenv("DEEPL_ENDPOINT", "https://api-free.deepl.com/v2/translate").strip()
            or "https://api-free.deepl.com/v2/translate",
            my_memory_api_key=os.getenv("MY_MEMORY_API_KEY", "").strip() or None,
            my_memory_email=os.getenv("MYMEMORY_USER_EMAIL", "").strip() or None,
            # Support both OPENAI_API_KEY and legacy OPEN_AI_API_KEY
            openai_api_key=(
                os.getenv("OPENAI_API_KEY", "").strip()
                or os.getenv("OPEN_AI_API_KEY", "").strip()
                or None
            ),
            openai_model=os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini").strip(),
            provider_order=_split_str(
                os.getenv("TRANSLATION_PROVIDERS", "deepl,mymemory,google"),
                default=["deepl", "mymemory", "google"],
            ),
            default_fallback_language=os.getenv("TRANSLATION_FALLBACK_LANGUAGE", "en").upper(),
            language_role_prefix=os.getenv("LANGUAGE_ROLE_PREFIX", "lang-").lower(),
            bot_channel_id=bot_channel_id,
            # New config fields
            server_default_language=server_default_language,
            auto_translate_enabled=auto_translate_enabled,
            auto_translate_confidence_threshold=auto_translate_confidence_threshold,
            auto_translate_min_length=auto_translate_min_length,
            timezone=timezone,
            log_level=log_level,
        )
        return config


__all__ = ["LanguageBotConfig"]
