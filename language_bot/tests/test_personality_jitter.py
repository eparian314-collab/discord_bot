"""Test coverage for the translation cog personality helpers."""

import asyncio
from contextlib import suppress
from unittest.mock import MagicMock

import pytest

from language_bot.cogs.translation_cog import TranslationCog
from language_bot.language_context.localization.personality_phrases import KNOWN_FRIENDS


class DummyChannel:
    async def send(self, msg: str) -> None:
        # Simulate a fire-and-forget channel send
        _ = msg


class DummyBot:
    def __init__(self, loop: asyncio.AbstractEventLoop, channel: DummyChannel):
        self.loop = loop
        self._channel = channel
        self.user = MagicMock(id=999, bot=True)

    async def wait_until_ready(self) -> None:
        return None

    def get_channel(self, _cid: int) -> DummyChannel:
        return self._channel

    def is_closed(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_jitter_and_personality_phrase(sample_config):
    channel = DummyChannel()
    bot = DummyBot(asyncio.get_running_loop(), channel)
    orchestrator = MagicMock()
    ui_engine = MagicMock()
    language_directory = MagicMock()

    cog = TranslationCog(bot, sample_config, orchestrator, ui_engine, language_directory)
    phrase = cog.get_personality_phrase("friendly")
    assert any(friend in phrase for friend in KNOWN_FRIENDS)
    madlib = cog.get_personality_phrase("madlibs")
    assert isinstance(madlib, str) and madlib
    await cog.test_send_personality_phrase(channel, "madlibs")
    await cog.test_send_personality_phrase(channel, "playful")

    cog._jitter_task.cancel()
    with suppress(asyncio.CancelledError):
        await cog._jitter_task
