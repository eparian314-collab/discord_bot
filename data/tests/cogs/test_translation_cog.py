import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from discord_bot.cogs.translation_cog import TranslationCog
from discord_bot.language_context.translation_job import TranslationJob
from discord_bot.language_context.context_models import TranslationResponse


class AliasHelperStub:
    def resolve(self, token: str):
        if token.lower() == "french":
            return "fr"
        return token


class LanguageMapStub(dict):
    def __init__(self):
        super().__init__({"fr": "French"})


class UIStub:
    def __init__(self):
        self.results = []
        self.errors = []

    async def show_result(self, interaction, payload, ephemeral=True):
        self.results.append(payload)

    async def show_error(self, interaction, message, ephemeral=True):
        self.errors.append(message)


class ContextEngineStub:
    def __init__(self, response):
        self.response = response

    async def translate_for_author_via_orchestrator(self, *args, **kwargs):
        return self.response


class OrchestratorStub:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def translate_text_for_user(self, *, text, guild_id, user_id, tgt_lang):
        self.calls += 1
        return self.payload


class InteractionStub:
    def __init__(self):
        self.channel_id = 10


def make_cog():
    cog = TranslationCog.__new__(TranslationCog)
    cog.alias_helper = AliasHelperStub()
    cog.language_map = LanguageMapStub()
    cog.ui = UIStub()
    cog.error_engine = None
    cog.processing = None
    cog.orchestrator = None
    cog.context = None
    return cog


def test_normalize_target_code_accepts_alias():
    cog = make_cog()
    code = cog._normalize_target_code("French")
    assert code == "fr"


@pytest.mark.asyncio
async def test_perform_translation_uses_context_response():
    response = TranslationResponse(text="bonjour", src="en", tgt="fr", provider="stub", confidence=1.0, meta={})
    job = TranslationJob(text="hello", src="en", tgt="fr", guild_id=1, author_id=2)
    cog = make_cog()
    cog.context = ContextEngineStub({"response": response, "job": job})

    await cog._perform_translation(
        InteractionStub(),
        text="hello",
        force_tgt="fr",
        guild_id=1,
        user_id=2,
    )

    assert cog.ui.results
    payload = cog.ui.results[-1]
    assert payload["text"] == "bonjour"
    assert not cog.ui.errors


@pytest.mark.asyncio
async def test_perform_translation_falls_back_to_orchestrator():
    cog = make_cog()
    cog.context = ContextEngineStub({"response": TranslationResponse(text=None, src="en", tgt="fr", provider=None, confidence=0.0, meta={}), "job": None})
    cog.orchestrator = OrchestratorStub(("ciao", "it", "deepl"))

    await cog._perform_translation(
        InteractionStub(),
        text="hello",
        force_tgt="it",
        guild_id=1,
        user_id=2,
    )

    assert cog.orchestrator.calls == 1
    assert cog.ui.results[-1]["text"] == "ciao"


