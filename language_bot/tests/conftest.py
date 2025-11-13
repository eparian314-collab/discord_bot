import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from language_bot.config import LanguageBotConfig  # noqa: E402
from language_bot.core.translation_orchestrator import TranslationResult  # noqa: E402


@pytest.fixture()
def sample_config() -> LanguageBotConfig:
    return LanguageBotConfig(
        discord_token="testing-token",
        owner_ids={1},
        test_guild_ids={2},
        deepl_api_key="deepl-key",
        my_memory_api_key="mm-key",
        my_memory_email="dev@example.com",
        openai_api_key="sk-test",
        provider_order=["deepl", "mymemory", "openai"],
        default_fallback_language="EN",
        language_role_prefix="lang-",
    )


@pytest.fixture()
def translation_result() -> TranslationResult:
    return TranslationResult(
        provider="noop",
        translated_text="Bonjour",
        target_language="FR",
        source_language="EN",
        confidence=0.9,
    )


@pytest.fixture()
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@dataclass
class DummyRole:
    name: str


@dataclass(eq=False)
class DummyMember:
    id: int
    roles: List[DummyRole]
    display_name: str = "TestUser"
    last_embed = None

    @property
    def bot(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.display_name

    async def send(self, embed):
        self.last_embed = embed
        return embed

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, DummyMember):
            return NotImplemented
        return self.id == other.id


__all__ = [
    "sample_config",
    "translation_result",
    "DummyRole",
    "DummyMember",
]
