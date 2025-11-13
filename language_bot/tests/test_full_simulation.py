import types
import pytest
from unittest.mock import AsyncMock, MagicMock
from language_bot.config import LanguageBotConfig
from language_bot.core.translation_orchestrator import TranslationOrchestrator, TranslationResult, TranslationError
from language_bot.core.personality_engine import PersonalityEngine

class DummyDiscordMessage:
    def __init__(self, content, author_id=1, channel_id=100, mentions=None):
        self.content = content
        self.author = types.SimpleNamespace(id=author_id, bot=False)
        self.channel = types.SimpleNamespace(id=channel_id)
        self.guild = types.SimpleNamespace(id=1)
        self.mentions = mentions or []
        self.id = 123
        self.jump_url = "https://discordapp.com/channels/1/2/3"

@pytest.fixture()
def orchestrator(sample_config):
    sample_config.deepl_api_key = "dummy"
    sample_config.openai_api_key = "dummy"
    return TranslationOrchestrator(sample_config)

@pytest.fixture()
def personality_engine(sample_config):
    return PersonalityEngine(api_key="dummy", model="gpt-4o-mini")

@pytest.mark.asyncio
async def test_full_translation_api_flow(orchestrator):
    # Mock providers
    orchestrator._translate_via_deepl = AsyncMock(return_value=TranslationResult(
        provider="deepl", translated_text="Bonjour", target_language="FR", source_language="EN"
    ))
    orchestrator._translate_via_openai = AsyncMock(return_value=TranslationResult(
        provider="openai", translated_text="Salut", target_language="FR", source_language="EN"
    ))
    # Simulate translation request
    result = await orchestrator.translate(text="Hello", target_language="FR", channel_id=100)
    assert result.translated_text in ("Bonjour", "Salut")
    assert result.provider in ("deepl", "openai")

@pytest.mark.asyncio
async def test_personality_engine_response(personality_engine):
    # Simulate persona prompt
    reply = await personality_engine.get_ai_personality_reply("friendly", "How are you?")
    assert isinstance(reply, str)
    assert reply  # Should not be empty

@pytest.mark.asyncio
async def test_simulated_discord_message_translation(orchestrator):
    # Simulate a Discord message event
    message = DummyDiscordMessage(content="Hello world!", author_id=2, channel_id=101)
    orchestrator._translate_via_deepl = AsyncMock(return_value=TranslationResult(
        provider="deepl", translated_text="Hallo Welt!", target_language="DE", source_language="EN"
    ))
    result = await orchestrator.translate(text=message.content, target_language="DE", channel_id=message.channel.id, user_id=message.author.id)
    assert result.translated_text == "Hallo Welt!"
    assert result.provider == "deepl"

@pytest.mark.asyncio
async def test_simulated_mention_role_context(orchestrator):
    # Simulate mention role context
    message = DummyDiscordMessage(content="Hola", author_id=3, channel_id=102)
    result = await orchestrator.translate(text=message.content, target_language="ES", source_language="ES", mention_roles=["ES", "FR"])
    assert result.provider == "noop"
    assert result.translated_text == "Hola"

@pytest.mark.asyncio
async def test_error_handling_and_fallback(orchestrator):
    orchestrator._translate_via_deepl = AsyncMock(side_effect=RuntimeError("deepl down"))
    orchestrator._translate_via_openai = AsyncMock(return_value=None)
    orchestrator._translate_via_mymemory = AsyncMock(return_value=TranslationResult(
        provider="mymemory", translated_text="Hola", target_language="ES", source_language="EN"
    ))
    result = await orchestrator.translate(text="Hello", target_language="ES", channel_id=103)
    assert result.provider == "mymemory"
    assert result.translated_text == "Hola"

@pytest.mark.asyncio
async def test_short_text_and_emoji_skip(orchestrator):
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="😊", target_language="EN")
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="ok", target_language="EN")
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="hi", target_language="EN")

# Add more simulation scenarios as needed for full coverage
