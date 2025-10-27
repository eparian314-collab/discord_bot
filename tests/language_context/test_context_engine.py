import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import discord_bot.language_context.context_engine as context_engine_module
from discord_bot.language_context.context_engine import ContextEngine
from discord_bot.language_context.translation_job import TranslationJob
from discord_bot.language_context.context.policies import PolicyRepository, TranslationPolicy
from discord_bot.language_context.context.context_memory import ContextMemory
from discord_bot.language_context.context.session_memory import SessionMemory


class FakeNormalizerResult:
    def __init__(self, normalized: str) -> None:
        self.normalized = normalized


@pytest.fixture(autouse=True)
def patch_normalizer(monkeypatch):
    def fake_normalize(text: str, *, language_hint=None):
        return FakeNormalizerResult(text.upper())

    monkeypatch.setattr(context_engine_module, "normalize_text", fake_normalize)
    yield
    monkeypatch.delattr(context_engine_module, "normalize_text", raising=False)


class DetectorStub:
    def __init__(self, detected: str):
        self.detected = detected

    async def detect_language(self, text: str):
        return self.detected, 0.99


class CacheStub:
    def __init__(self, user_lang: str):
        self.user_lang = user_lang

    def get_user_lang(self, guild_id: int, user_id: int):
        return self.user_lang


@pytest.mark.asyncio
async def test_plan_for_author_includes_normalized_metadata():
    guild_id = 1
    user_id = 42
    session_memory = SessionMemory()
    await session_memory.add_event(guild_id, channel_id=None, user_id=user_id, text="Previous message", metadata={})

    policy_repo = PolicyRepository()
    policy_repo.set_policy(
        guild_id=guild_id,
        user_id=user_id,
        policy=TranslationPolicy(fallback_language="en", preferred_providers=("alpha", "beta")),
    )

    engine = ContextEngine(
        role_manager=None,
        cache_manager=CacheStub("fr"),
        policy_repository=policy_repo,
        detection_service=DetectorStub("es"),
        session_memory=session_memory,
        context_memory=None,
    )

    result = await engine.plan_for_author(guild_id, user_id, text="hello world", channel_id=None)

    job = result["job"]
    context = result["context"]

    assert job is not None
    assert job.text == "hello world"
    assert job.src_lang == "es"
    assert job.tgt_lang == "fr"
    assert context == {"src": "es", "tgt": "fr"}

    metadata = job.metadata
    assert metadata["preferred_providers"] == ["alpha", "beta"]
    assert metadata["normalized_text"] == "HELLO WORLD"
    assert metadata["recent_history"] == ["Previous message"]
    assert metadata["policy"]["fallback_language"] == "en"


@pytest.mark.asyncio
async def test_plan_for_author_skips_when_languages_match():
    policy_repo = PolicyRepository()
    policy_repo.set_policy(guild_id=99, user_id=5, policy=TranslationPolicy(fallback_language="en"))

    engine = ContextEngine(
        role_manager=None,
        cache_manager=CacheStub("es"),
        policy_repository=policy_repo,
        detection_service=DetectorStub("es"),
    )

    result = await engine.plan_for_author(99, 5, text="hola", channel_id=None)

    assert result["job"] is None
    assert result["context"] == {"src": "es", "tgt": "es"}


class OrchestratorStub:
    def __init__(self):
        self.calls = []

    async def translate_job(self, job):
        self.calls.append(job)
        return {
            "text": job.text.upper(),
            "src": job.src_lang,
            "tgt": job.tgt_lang,
            "provider": "stub",
            "confidence": 0.88,
        }


@pytest.mark.asyncio
async def test_translate_for_author_records_session_and_context():
    guild_id = 7
    user_id = 77
    session_memory = SessionMemory()
    context_memory = ContextMemory()
    policy_repo = PolicyRepository()
    policy_repo.set_policy(guild_id=guild_id, user_id=user_id, policy=TranslationPolicy(fallback_language="en"))

    engine = ContextEngine(
        role_manager=None,
        cache_manager=CacheStub("fr"),
        policy_repository=policy_repo,
        detection_service=DetectorStub("en"),
        session_memory=session_memory,
        context_memory=context_memory,
    )

    orchestrator = OrchestratorStub()

    result = await engine.translate_for_author_via_orchestrator(
        guild_id, user_id, orchestrator, text="bonjour", force_tgt=None, timeout=None, channel_id=11
    )

    job = result["job"]
    response = result["response"]

    assert job is not None
    assert response.text == "BONJOUR"
    assert response.provider == "stub"
    assert response.tgt == "fr"

    history = await session_memory.get_history(guild_id, channel_id=11, user_id=user_id)
    assert history
    assert history[-1].metadata["provider"] == "stub"

    record = await context_memory.get_record(f"guild:{guild_id}", f"user:{user_id}:last_translation")
    assert record is not None
    assert record.value["provider"] == "stub"
    assert record.value["tgt"] == "fr"


class AliasHelperStub:
    def resolve(self, token: str) -> str:
        return "fr-FR" if token.lower() == "french" else token


class RoleManagerStub:
    def resolve_code(self, token: str) -> str:
        return "fr" if token.lower() == "fr-fr" else token


class AmbiguityResolverStub:
    def resolve(self, code: str, context):
        return "pt-BR"


class DetectorSyncStub:
    def __init__(self, result):
        self.result = result

    def detect_language(self, text: str):
        return self.result


def test_normalize_code_prefers_alias_and_role_resolution():
    engine = ContextEngine(
        role_manager=RoleManagerStub(),
        cache_manager=None,
        alias_helper=AliasHelperStub(),
        ambiguity_resolver=None,
    )

    normalized = engine._normalize_code("French")
    assert normalized == "fr"


def test_resolve_ambiguity_normalizes_result():
    engine = ContextEngine(
        role_manager=None,
        cache_manager=None,
        alias_helper=None,
        ambiguity_resolver=AmbiguityResolverStub(),
    )

    resolved = engine._resolve_ambiguity("pt", {"guild_id": 1})
    assert resolved == "pt"


@pytest.mark.asyncio
async def test_detect_source_uses_injected_detector_tuple_response():
    engine = ContextEngine(
        role_manager=None,
        cache_manager=None,
        detection_service=DetectorSyncStub(("de", 0.87)),
    )

    detected = await engine._detect_source_code("Guten Tag")
    assert detected == "de"


@pytest.mark.asyncio
async def test_detect_source_heuristics_for_unicode_ranges():
    engine = ContextEngine(role_manager=None, cache_manager=None)
    detected = await engine._detect_source_code("これはテストです")
    assert detected == "ja"


@pytest.mark.asyncio
async def test_normalize_orchestrator_result_handles_dict_and_string():
    engine = ContextEngine(role_manager=None, cache_manager=None)
    job = TranslationJob(text="ciao", src="it", tgt="en")

    dict_resp = engine._normalize_orchestrator_result(
        {"text": "hello", "src": "it", "tgt": "en", "provider": "mock", "confidence": 0.5},
        job,
    )
    assert dict_resp.text == "hello"
    assert dict_resp.provider == "mock"

    str_resp = engine._normalize_orchestrator_result("hola", job)
    assert str_resp.text == "hola"
