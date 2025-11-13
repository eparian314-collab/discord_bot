import asyncio
import types
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock

import pytest

from language_bot.cogs.translation_cog import TranslationCog
from language_bot.core.translation_orchestrator import TranslationError, TranslationResult
from language_bot.language_context.flag_map import LanguageDirectory
from language_bot.tests.conftest import DummyMember, DummyRole


def _build_message(content: str, author, mentions):
    class Message:
        def __init__(self):
            self.guild = object()
            self.content = content
            self.author = author
            self.mentions = mentions
            self.id = 123
            self.jump_url = "https://discordapp.com/channels/1/2/3"

    return Message()


@pytest.fixture()
def translation_cog(sample_config, event_loop):
    class DummyBot:
        def __init__(self, loop):
            self.user = types.SimpleNamespace(id=999, bot=True)
            self.loop = loop

        async def wait_until_ready(self):
            return None

    bot = DummyBot(event_loop)
    orchestrator = MagicMock()
    orchestrator.detect_language.return_value = "en"
    orchestrator.translate = AsyncMock(
        return_value=TranslationResult(
            provider="deepl",
            translated_text="Hola",
            target_language="ES",
            source_language="EN",
        )
    )

    ui_engine = MagicMock()
    ui_engine.build_private_embed.return_value = object()
    ui_engine.notify_user = AsyncMock(return_value=True)

    language_directory = LanguageDirectory.default()

    cog = TranslationCog(
        bot=bot,
        config=sample_config,
        orchestrator=orchestrator,
        ui_engine=ui_engine,
        language_directory=language_directory,
    )
    yield cog, orchestrator, ui_engine
    cog._jitter_task.cancel()
    with suppress(asyncio.CancelledError):
        event_loop.run_until_complete(cog._jitter_task)


def test_extract_languages_filters_roles(translation_cog):
    cog, *_ = translation_cog
    roles = [
        DummyRole("lang-spanish"),
        DummyRole("other-role"),
        DummyRole("lang-japanese fan"),
    ]
    languages = cog._extract_languages(roles)
    assert languages == ["ES", "JA"]


def test_language_supported_matches_variants():
    assert TranslationCog._language_supported("en-US", ["es", "en"])
    assert not TranslationCog._language_supported("de", ["es", "fr"])


@pytest.mark.asyncio
async def test_fan_out_translations_creates_tasks(translation_cog):
    cog, *_ = translation_cog
    member_a = DummyMember(id=1, roles=[DummyRole("lang-es")])
    member_b = DummyMember(id=2, roles=[DummyRole("lang-en")])
    cog._translate_for_member = AsyncMock(return_value=None)  # type: ignore[assignment]
    message = types.SimpleNamespace(content="Hello")

    await cog._fan_out_translations(
        message=message,
        detected_language="en",
        targets={member_a: ["es"], member_b: ["en"]},
    )

    cog._translate_for_member.assert_awaited_once()
    kwargs = cog._translate_for_member.call_args.kwargs
    assert kwargs["member"] == member_a
    assert kwargs["target_language"] == "es"


@pytest.mark.asyncio
async def test_translate_for_member_builds_embed(translation_cog):
    cog, orchestrator, ui_engine = translation_cog
    member = DummyMember(id=7, roles=[])

    class Author:
        def __str__(self):
            return "Author#1234"

    message = types.SimpleNamespace(content="Hello", author=Author(), jump_url="url", id=55)
    await cog._translate_for_member(
        member=member,
        message=message,
        source_language="EN",
        target_language="ES",
    )

    orchestrator.translate.assert_awaited_once()
    ui_engine.build_private_embed.assert_called_once()
    ui_engine.notify_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_translate_for_member_handles_errors(translation_cog):
    cog, orchestrator, ui_engine = translation_cog
    orchestrator.translate = AsyncMock(side_effect=TranslationError("boom"))
    member = DummyMember(id=8, roles=[])
    message = types.SimpleNamespace(content="Hi", author=member, jump_url="url", id=99)
    await cog._translate_for_member(member=member, message=message, source_language="EN", target_language="FR")
    ui_engine.build_private_embed.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_triggers_fan_out(translation_cog):
    cog, orchestrator, _ = translation_cog
    author = DummyMember(id=10, roles=[])
    mention = DummyMember(id=11, roles=[DummyRole("lang-spanish")])
    message = _build_message("Hola amigos", author, [mention])
    cog._fan_out_translations = AsyncMock(return_value=None)  # type: ignore[assignment]

    await cog.on_message(message)

    cog._fan_out_translations.assert_awaited_once()
    args = cog._fan_out_translations.call_args.kwargs
    assert mention in args["targets"]


@pytest.mark.asyncio
async def test_on_message_skips_when_detection_fails(translation_cog):
    cog, orchestrator, _ = translation_cog
    orchestrator.detect_language.return_value = None
    author = DummyMember(id=10, roles=[])
    mention = DummyMember(id=11, roles=[DummyRole("lang-spanish")])
    message = _build_message("Hola amigos", author, [mention])
    cog._fan_out_translations = AsyncMock(return_value=None)  # type: ignore[assignment]

    await cog.on_message(message)

    cog._fan_out_translations.assert_not_called()
