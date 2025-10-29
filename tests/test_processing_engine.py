import asyncio
import pytest

from discord_bot.core.engines.processing_engine import ProcessingEngine, TranslationJob
from discord_bot.tests.stubs.providers import SuccessStub, SlowStub, FailingStub


@pytest.mark.asyncio
async def test_single_success_adapter_returns_text():
    engine = ProcessingEngine(cache_manager=None, error_engine=None, default_timeout=1.0)
    engine.add_adapter(SuccessStub("A"), provider_id="stubA", priority=10, timeout=0.5)
    job = TranslationJob(text="hello", src="en", tgt="fr")
    out = await engine.execute_job(job)
    assert out is not None and out.endswith("->fr")


@pytest.mark.asyncio
async def test_priority_first_success_wins():
    engine = ProcessingEngine(cache_manager=None, error_engine=None, default_timeout=1.0)
    engine.add_adapter(FailingStub("X"), provider_id="stubX", priority=5, timeout=0.5)
    engine.add_adapter(SuccessStub("Y"), provider_id="stubY", priority=10, timeout=0.5)
    job = TranslationJob(text="hola", src="es", tgt="en")
    out = await engine.execute_job(job)
    assert out is not None and "[Y]" in out


@pytest.mark.asyncio
async def test_adapter_timeout_fallback_to_next():
    engine = ProcessingEngine(cache_manager=None, error_engine=None, default_timeout=0.3)
    engine.add_adapter(SlowStub(delay=1.0, label="slow1"), provider_id="slow1", priority=5, timeout=0.2)
    engine.add_adapter(SuccessStub("fast"), provider_id="fast", priority=10, timeout=0.5)
    job = TranslationJob(text="ciao", src="it", tgt="en")
    out = await engine.execute_job(job)
    assert out is not None and "[fast]" in out


@pytest.mark.asyncio
async def test_all_fail_returns_none():
    engine = ProcessingEngine(cache_manager=None, error_engine=None, default_timeout=0.2)
    engine.add_adapter(SlowStub(delay=1.0), provider_id="slow", priority=10, timeout=0.1)
    engine.add_adapter(FailingStub(), provider_id="fail", priority=20, timeout=0.1)
    job = TranslationJob(text="hej", src="sv", tgt="en")
    out = await engine.execute_job(job)
    assert out is None
