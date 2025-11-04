import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine
from discord_bot.language_context.translation_job import TranslationJob


class DetectorStub:
    async def detect_language(self, text: str):
        return "es", 0.92


class AdapterStub:
    def __init__(self, output, languages=None):
        self.output = output
        self.languages = languages or []
        self.calls = []

    def supported_languages(self):
        return self.languages

    async def translate(self, text, src, tgt):
        self.calls.append((text, src, tgt))
        return self.output


@pytest.mark.asyncio
async def test_translate_text_prefers_deepl_when_supported():
    deepl = AdapterStub("hola amigo", languages=["en", "fr"])
    mymemory = AdapterStub("bonjour", languages=["en", "fr"])
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=deepl,
        mymemory_adapter=mymemory,
        detection_service=DetectorStub(),
        nlp_processor=None,
    )

    result, src, provider = await orchestrator.translate_text_for_user(
        text="hello", guild_id=1, user_id=2, tgt_lang="fr"
    )

    assert result == "hola amigo"
    assert src == "es"
    assert provider == "deepl"
    assert len(deepl.calls) == 1
    assert len(mymemory.calls) == 0


@pytest.mark.asyncio
async def test_translate_text_falls_back_to_mymemory():
    deepl = AdapterStub(None, languages=["de"])
    mymemory = AdapterStub("salut", languages=["fr"])
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=deepl,
        mymemory_adapter=mymemory,
        detection_service=DetectorStub(),
        nlp_processor=None,
    )

    result, src, provider = await orchestrator.translate_text_for_user(
        text="hello", guild_id=1, user_id=2, tgt_lang="fr"
    )

    assert result == "salut"
    assert provider == "mymemory"
    assert len(mymemory.calls) == 1


class ResultObject:
    def __init__(self, text):
        self.translated_text = text


def test_extract_text_handles_shapes():
    orchestrator = TranslationOrchestratorEngine()
    assert orchestrator._extract_text("plain", "provider") == "plain"
    assert orchestrator._extract_text({"text": "dict"}, "provider") == "dict"
    assert orchestrator._extract_text(ResultObject("attr"), "provider") == "attr"
    assert orchestrator._extract_text(None, "provider") is None


@pytest.mark.asyncio
async def test_translate_job_invokes_text_pipeline():
    adapter = AdapterStub("ciao", languages=["en"])
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=adapter,
        mymemory_adapter=None,
        detection_service=DetectorStub(),
    )

    job = TranslationJob(text="hi", src="en", tgt="en", guild_id=1, author_id=1)
    translated = await orchestrator.translate_job(job)
    assert translated == "ciao"


