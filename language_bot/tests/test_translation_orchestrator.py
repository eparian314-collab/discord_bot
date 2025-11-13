import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from language_bot.config import LanguageBotConfig
from language_bot.core.translation_orchestrator import (
    TranslationError,
    TranslationOrchestrator,
    TranslationResult,
)


@pytest.fixture()
def orchestrator(sample_config: LanguageBotConfig) -> TranslationOrchestrator:
    return TranslationOrchestrator(sample_config)


@pytest.fixture()
def orchestrator_with_policy(sample_config: LanguageBotConfig):
    class DummyPolicyRepo:
        def get_provider_order_for_channel(self, channel_id):
            if channel_id == 42:
                return ["openai", "deepl"]
            return None
    sample_config.policy_repo = DummyPolicyRepo()
    return TranslationOrchestrator(sample_config)


def test_detect_language_handles_empty(orchestrator: TranslationOrchestrator):
    assert orchestrator.detect_language("") is None


def test_detect_language_handles_exception(monkeypatch, orchestrator: TranslationOrchestrator):
    def fake_detect(_text: str):
        from langdetect import LangDetectException

        raise LangDetectException(0, "bad data")

    monkeypatch.setattr("language_bot.core.translation_orchestrator.detect", fake_detect)
    assert orchestrator.detect_language("???") is None


@pytest.mark.asyncio
async def test_translate_short_circuits_matching_languages(orchestrator: TranslationOrchestrator):
    result = await orchestrator.translate(text="Hello", target_language="en", source_language="en")
    assert result.provider == "noop"
    assert result.translated_text == "Hello"


@pytest.mark.asyncio
async def test_translate_raises_on_empty_text(orchestrator: TranslationOrchestrator):
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="   ", target_language="es")


@pytest.mark.asyncio
async def test_translate_attempts_providers_until_success(orchestrator: TranslationOrchestrator):
    orchestrator._provider_order = ["deepl", "mymemory"]

    async def failing_provider(*_args, **_kwargs):
        raise RuntimeError("deepl down")

    async def succeeding_provider(*_args, **_kwargs):
        return TranslationResult(
            provider="mymemory",
            translated_text="Hola",
            target_language="ES",
            source_language="EN",
        )

    orchestrator._translate_via_deepl = failing_provider  # type: ignore[assignment]
    orchestrator._translate_via_mymemory = succeeding_provider  # type: ignore[assignment]

    result = await orchestrator.translate(text="Hello", target_language="ES", source_language="EN")
    assert result.provider == "mymemory"


@pytest.mark.asyncio
async def test_translate_raises_when_all_providers_fail(orchestrator: TranslationOrchestrator):
    orchestrator._provider_order = ["deepl"]

    async def failing_provider(*_args, **_kwargs):
        raise RuntimeError("offline")

    orchestrator._translate_via_deepl = failing_provider  # type: ignore[assignment]

    with pytest.raises(TranslationError) as excinfo:
        await orchestrator.translate(text="Hello", target_language="ES", source_language="EN")
    assert "deepl" in str(excinfo.value)


@pytest.mark.asyncio
async def test_translate_via_deepl(monkeypatch, sample_config: LanguageBotConfig):
    sample_config.deepl_api_key = "deepl"
    orchestrator = TranslationOrchestrator(sample_config)

    class DummyResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

        def raise_for_status(self):
            return None

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            payload = {
                "translations": [
                    {"text": "Hola", "detected_source_language": "EN", "confidence": 0.8}
                ]
            }
            return DummyResponse(payload)

    monkeypatch.setattr(
        "language_bot.core.translation_orchestrator.httpx.AsyncClient",
        lambda timeout=15: DummyClient(),
    )
    result = await orchestrator._translate_via_deepl("Hello", "EN", "ES")
    assert result and result.provider == "deepl" and result.translated_text == "Hola"


@pytest.mark.asyncio
async def test_translate_via_deepl_without_translations(monkeypatch, sample_config: LanguageBotConfig):
    sample_config.deepl_api_key = "deepl"
    orchestrator = TranslationOrchestrator(sample_config)

    class DummyResponse:
        def json(self):
            return {"translations": []}

        def raise_for_status(self):
            return None

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            return DummyResponse()

    monkeypatch.setattr(
        "language_bot.core.translation_orchestrator.httpx.AsyncClient",
        lambda timeout=15: DummyClient(),
    )
    with pytest.raises(TranslationError):
        await orchestrator._translate_via_deepl("Hello", "EN", "ES")


@pytest.mark.asyncio
async def test_translate_via_mymemory(monkeypatch, orchestrator: TranslationOrchestrator):
    class DummyResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            return DummyResponse({"matches": [{"translation": "Hola", "match": 0.9}]})

    monkeypatch.setattr(
        "language_bot.core.translation_orchestrator.httpx.AsyncClient",
        lambda timeout=15: DummyClient(),
    )

    result = await orchestrator._translate_via_mymemory("Hello", "EN", "ES")
    assert result and result.translated_text == "Hola" and result.provider == "mymemory"


@pytest.mark.asyncio
async def test_translate_via_mymemory_uses_response_data(monkeypatch, orchestrator: TranslationOrchestrator):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"matches": [], "responseData": {"translatedText": "Hola", "match": 0.7}}

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            return DummyResponse()

    monkeypatch.setattr(
        "language_bot.core.translation_orchestrator.httpx.AsyncClient",
        lambda timeout=15: DummyClient(),
    )

    result = await orchestrator._translate_via_mymemory("Hello", "EN", "ES")
    assert result and result.confidence == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_translate_via_openai(monkeypatch, sample_config: LanguageBotConfig):
    sample_config.openai_api_key = "key"

    class DummyCompletion:
        def __init__(self):
            choice = types.SimpleNamespace(message=types.SimpleNamespace(content="Salut"))
            self.choices = [choice]

    class DummyChat:
        def __init__(self):
            self.completions = AsyncMock()
            self.completions.create = AsyncMock(return_value=DummyCompletion())

    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = DummyChat()

    monkeypatch.setattr("language_bot.core.translation_orchestrator.AsyncOpenAI", DummyOpenAI)
    orchestrator = TranslationOrchestrator(sample_config)
    result = await orchestrator._translate_via_openai("Hello", "EN", "FR")
    assert result and result.provider == "openai" and result.translated_text == "Salut"


@pytest.mark.asyncio
async def test_conversation_language_cache_bias(orchestrator):
    # Simulate recent language detections in channel 99
    orchestrator._recent_language_cache[99].extend([
        (1, "fr"), (2, "fr"), (3, "fr"), (4, "en"), (5, "fr")
    ])
    # Should bias to 'fr' as most common
    lang = orchestrator._resolve_source_language("", None, channel_id=99, user_id=6)
    assert lang == "fr"


@pytest.mark.asyncio
async def test_policy_repo_provider_override(orchestrator_with_policy):
    orchestrator = orchestrator_with_policy
    orchestrator._translate_via_openai = AsyncMock(return_value=TranslationResult(
        provider="openai", translated_text="Bonjour", target_language="FR", source_language="EN"
    ))
    orchestrator._translate_via_deepl = AsyncMock(return_value=TranslationResult(
        provider="deepl", translated_text="Salut", target_language="FR", source_language="EN"
    ))
    # Should use openai first due to policy
    result = await orchestrator.translate(text="Hello", target_language="FR", channel_id=42)
    assert result.provider == "openai"


@pytest.mark.asyncio
async def test_mention_roles_smart_context(orchestrator):
    # If mention_roles includes detected language, should short-circuit
    result = await orchestrator.translate(text="Hola", target_language="ES", source_language="ES", mention_roles=["ES", "FR"])
    assert result.provider == "noop"
    assert result.translated_text == "Hola"


@pytest.mark.asyncio
async def test_translate_skips_short_or_emoji(orchestrator):
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="😊", target_language="EN")
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="ok", target_language="EN")
    with pytest.raises(TranslationError):
        await orchestrator.translate(text="hi", target_language="EN")


def test_extract_confidence_handles_invalid(orchestrator: TranslationOrchestrator):
    assert orchestrator._extract_confidence({"match": "0.5"}) == 0.5
    assert orchestrator._extract_confidence({"confidence": float("nan")}) is None
    assert orchestrator._extract_confidence({}) is None
