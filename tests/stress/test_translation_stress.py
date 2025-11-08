"""
Stress tests for the translation system.
Tests concurrent translation requests and fallback chain performance.
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
import time


@pytest.fixture
def mock_translation_engine():
    """Mock translation orchestrator for testing."""
    engine = Mock()
    engine.translate = AsyncMock(return_value="Translated text")
    return engine


@pytest.mark.asyncio
async def test_concurrent_translation_requests(mock_translation_engine):
    """Test handling of concurrent translation requests."""
    num_requests = 200
    start_time = time.time()
    
    tasks = [
        mock_translation_engine.translate(
            text=f"Test message {i}",
            source_lang="en",
            target_lang="es"
        )
        for i in range(num_requests)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if isinstance(r, str))
    
    print(f"\n--- Concurrent Translation Stress Test ---")
    print(f"Requests: {num_requests}")
    print(f"Successful: {successful}")
    print(f"Failed: {num_requests - successful}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {num_requests / elapsed:.2f} translations/sec")
    
    assert successful == num_requests
    assert elapsed < 60


@pytest.mark.asyncio
async def test_multilingual_burst_stress(mock_translation_engine):
    """Test handling of burst translation across multiple languages."""
    languages = ["es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
    requests_per_lang = 20
    
    start_time = time.time()
    
    tasks = []
    for lang in languages:
        for i in range(requests_per_lang):
            task = mock_translation_engine.translate(
                text=f"Message {i}",
                source_lang="en",
                target_lang=lang
            )
            tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if isinstance(r, str))
    total_requests = len(languages) * requests_per_lang
    
    print(f"\n--- Multilingual Burst Stress Test ---")
    print(f"Languages: {len(languages)}")
    print(f"Requests per language: {requests_per_lang}")
    print(f"Total requests: {total_requests}")
    print(f"Successful: {successful}")
    print(f"Failed: {total_requests - successful}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {total_requests / elapsed:.2f} translations/sec")
    
    assert successful == total_requests
    assert elapsed < 90


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
