import asyncio
from contextlib import suppress
import types

import pytest

from language_bot.cogs.translation_cog import TranslationCog
from language_bot.core.translation_orchestrator import TranslationOrchestrator
from language_bot.core.translation_ui_engine import TranslationUIEngine
from language_bot.language_context.flag_map import LanguageDirectory
from language_bot.tests.conftest import DummyMember, DummyRole


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class DummyHttpClient:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *_args, **_kwargs):
        return DummyResponse(self.payload)

    async def get(self, *_args, **_kwargs):
        return DummyResponse(self.payload)


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


@pytest.mark.asyncio
async def test_end_to_end_translation_flow(monkeypatch, sample_config):
    sample_config.deepl_api_key = "deepl"
    payload = {"translations": [{"text": "Hello friends", "detected_source_language": "ES", "confidence": 0.99}]}
    monkeypatch.setattr(
        "language_bot.core.translation_orchestrator.httpx.AsyncClient",
        lambda timeout=15: DummyHttpClient(payload),
    )
    bot = DummyBot(asyncio.get_running_loop())
    orchestrator = TranslationOrchestrator(sample_config)
    ui_engine = TranslationUIEngine()
    language_directory = LanguageDirectory.default()
    cog = TranslationCog(bot, sample_config, orchestrator, ui_engine, language_directory)

    author = DummyMember(id=20, roles=[])
    mention = DummyMember(id=21, roles=[DummyRole("lang-english")])
    message = types.SimpleNamespace(
        guild=object(),
        content="Hola amigos",
        author=author,
        mentions=[mention],
        id=321,
        jump_url="https://discordapp.com/channels/1/2/3",
    )

    # Force deterministic language detection.
    orchestrator.detect_language = lambda _text: "es"  # type: ignore[assignment]

    await cog.on_message(message)
    cog._jitter_task.cancel()
    with suppress(asyncio.CancelledError):
        await cog._jitter_task

    assert mention.last_embed is not None
    assert "Hello friends" in mention.last_embed.description
