import sys
import time
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from discord_bot.language_context.context.policies import PolicyRepository, TranslationPolicy
from discord_bot.language_context.context.session_memory import SessionMemory
from discord_bot.language_context.context.context_memory import ContextMemory


def test_policy_repository_resolution_order():
    repo = PolicyRepository()

    guild_policy = TranslationPolicy(fallback_language="de")
    channel_policy = TranslationPolicy(fallback_language="fr")
    user_policy = TranslationPolicy(fallback_language="es")

    repo.set_policy(guild_id=123, policy=guild_policy)
    repo.set_policy(guild_id=123, channel_id=5, policy=channel_policy)
    repo.set_policy(guild_id=123, channel_id=5, user_id=77, policy=user_policy)

    resolved = repo.get_policy(guild_id=123, channel_id=5, user_id=77)
    assert resolved.fallback_language == "es"

    resolved_channel = repo.get_policy(guild_id=123, channel_id=5, user_id=None)
    assert resolved_channel.fallback_language == "fr"

    resolved_guild = repo.get_policy(guild_id=123, channel_id=None, user_id=None)
    assert resolved_guild.fallback_language == "de"


@pytest.mark.asyncio
async def test_session_memory_prunes_expired_events(monkeypatch):
    memory = SessionMemory(ttl_seconds=0.1)
    await memory.add_event(1, channel_id=None, user_id=2, text="hello")

    history = await memory.get_history(1, channel_id=None, user_id=2)
    assert len(history) == 1

    original = time.time()
    monkeypatch.setattr("time.time", lambda: original + 1.0)

    history = await memory.get_history(1, channel_id=None, user_id=2)
    assert history == ()


@pytest.mark.asyncio
async def test_context_memory_ttl(monkeypatch):
    memory = ContextMemory(default_ttl=0.1)
    await memory.set("guild:1", "key", {"value": 1})

    value = await memory.get("guild:1", "key")
    assert value == {"value": 1}

    original = time.time()
    monkeypatch.setattr("time.time", lambda: original + 1.0)

    value = await memory.get("guild:1", "key")
    assert value is None


