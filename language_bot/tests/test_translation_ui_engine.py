import types

import pytest

import discord

from language_bot.core.translation_orchestrator import TranslationResult
from language_bot.core.translation_ui_engine import TranslationUIEngine


def test_build_private_embed_contains_translated_text(translation_result: TranslationResult):
    engine = TranslationUIEngine()
    embed = engine.build_private_embed(
        author_name="User#1234",
        message_link="https://discordapp.com/channels/1/2/3",
        original_text="Hello world",
        result=translation_result,
    )
    assert translation_result.translated_text in embed.description
    assert embed.fields[0].name == "Original"
    assert embed.fields[1].name == "Source"
    assert translation_result.provider in embed.footer.text


def _fake_response(status: int) -> types.SimpleNamespace:
    return types.SimpleNamespace(status=status, reason="error", headers={})


class DummyUser:
    def __init__(self, exc=None):
        self.exc = exc
        self.sent = []

    async def send(self, embed):
        if self.exc:
            raise self.exc
        self.sent.append(embed)
        return embed


@pytest.mark.asyncio
async def test_notify_user_success():
    engine = TranslationUIEngine()
    user = DummyUser()
    embed = discord.Embed(description="Test")
    assert await engine.notify_user(member=user, embed=embed) is True
    assert user.sent == [embed]


@pytest.mark.asyncio
async def test_notify_user_handles_forbidden():
    engine = TranslationUIEngine()
    error = discord.Forbidden(response=_fake_response(403), message="Nope")
    user = DummyUser(exc=error)
    assert await engine.notify_user(member=user, embed=discord.Embed()) is False


@pytest.mark.asyncio
async def test_notify_user_handles_generic_http_errors():
    engine = TranslationUIEngine()
    error = discord.HTTPException(response=_fake_response(500), message="fail")
    user = DummyUser(exc=error)
    assert await engine.notify_user(member=user, embed=discord.Embed()) is False


def test_truncate_limits_strings():
    assert TranslationUIEngine._truncate("short") == "short"
    long_text = "x" * 2000
    truncated = TranslationUIEngine._truncate(long_text, limit=100)
    assert truncated.endswith("...")
    assert len(truncated) == 100
