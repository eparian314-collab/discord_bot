import asyncio
from contextlib import suppress
import types

import pytest

from language_bot.cogs.translation_cog import TranslationCog
from language_bot.core.translation_orchestrator import TranslationResult
from language_bot.core.translation_ui_engine import TranslationUIEngine
from language_bot.language_context.flag_map import LanguageDirectory
from language_bot.tests.conftest import DummyMember, DummyRole


class DummyBot:
    def __init__(self, loop):
        self.user = types.SimpleNamespace(id=999, bot=True)
        self.loop = loop

    async def wait_until_ready(self):
        return None

    def get_channel(self, _cid):
        return None

    def is_closed(self):
        return True


class StubOrchestrator:
    def __init__(self):
        self.detect_language_calls = []
        self.translate_calls = []

    def detect_language(self, text: str):
        self.detect_language_calls.append(text)
        return "es"

    async def translate(self, **kwargs):
        self.translate_calls.append(kwargs)
        return TranslationResult(
            provider="deepl",
            translated_text="Hello there",
            target_language=kwargs["target_language"],
            source_language=kwargs["source_language"],
        )


@pytest.mark.asyncio
async def test_translation_flow_sends_dm(sample_config):
    bot = DummyBot(asyncio.get_running_loop())
    orchestrator = StubOrchestrator()
    ui_engine = TranslationUIEngine()
    language_directory = LanguageDirectory.default()
    cog = TranslationCog(
        bot=bot,
        config=sample_config,
        orchestrator=orchestrator,
        ui_engine=ui_engine,
        language_directory=language_directory,
    )

    author = DummyMember(id=10, roles=[])
    mention = DummyMember(id=11, roles=[DummyRole("lang-english")])
    message = types.SimpleNamespace(
        guild=object(),
        content="Hola amigos",
        author=author,
        mentions=[mention],
        id=123,
        jump_url="https://discordapp.com/channels/1/2/3",
    )

    await cog.on_message(message)
    cog._jitter_task.cancel()
    with suppress(asyncio.CancelledError):
        await cog._jitter_task

    assert mention.last_embed is not None
    assert mention.last_embed.description == "Hello there"
    assert orchestrator.detect_language_calls == ["Hola amigos"]
    assert orchestrator.translate_calls
