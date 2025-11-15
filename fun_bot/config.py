"""Minimal configuration for FunBot (env-backed)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Set


def _split_ints(value: str) -> Set[int]:
    ids: Set[int] = set()
    for chunk in (value or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError:
            continue
    return ids


@dataclass(slots=True)
class FunBotConfig:
    discord_token: str
    owner_ids: Set[int] = field(default_factory=set)
    command_prefix: str = "!"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    db_path: str = "data/funbot.sqlite3"
    bot_channel_ids: Set[int] = field(default_factory=set)

    @classmethod
    def from_env(cls) -> "FunBotConfig":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN is required to run the bot")
        return cls(
            discord_token=token,
            owner_ids=_split_ints(os.getenv("OWNER_IDS", "")),
            command_prefix=os.getenv("BOT_PREFIX", "!").strip() or "!",
            openai_api_key=(
                os.getenv("OPENAI_API_KEY", "").strip()
                or os.getenv("OPEN_AI_API_KEY", "").strip()
                or None
            ),
            openai_model=os.getenv("OPENAI_PERSONALITY_MODEL", "gpt-4o-mini").strip(),
            db_path=os.getenv("FUNBOT_DB_PATH", "data/funbot.sqlite3").strip() or "data/funbot.sqlite3",
            bot_channel_ids=_split_ints(os.getenv("BOT_CHANNEL_ID", "")),
        )


__all__ = ["FunBotConfig"]
