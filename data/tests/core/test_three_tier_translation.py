"""
Integration test for 3-tier translation pipeline.

This test verifies the complete translation stack:
Tier 1: DeepL (highest quality, ~31 languages)
Tier 2: MyMemory (good quality, broad coverage)
Tier 3: Google Translate (free tier, 100+ languages)

The test validates fallback behavior when earlier tiers don't support a language.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine
from discord_bot.language_context.translators.google_translate_adapter import create_google_translate_adapter


@pytest.mark.asyncio
async def test_three_tier_translation_deepl_success():
    """Test that DeepL is used when available (tier 1)."""
    # Mock DeepL adapter that succeeds
    deepl_mock = MagicMock()
    deepl_mock.translate_async = AsyncMock(return_value="Bonjour le monde")
    deepl_mock.supported_languages.return_value = ["fr", "de", "es", "it"]
    
    # Mock MyMemory (should not be called)
    mymemory_mock = MagicMock()
    mymemory_mock.translate_async = AsyncMock(return_value="MyMemory translation")
    mymemory_mock.supported_languages.return_value = ["fr", "de", "es", "it", "pt", "ru"]
    
    # Real Google adapter (should not be called)
    google_adapter = create_google_translate_adapter()
    
    # Create orchestrator
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=deepl_mock,
        mymemory_adapter=mymemory_mock,
        google_adapter=google_adapter,
        detection_service=None,
        nlp_processor=None,
    )
    
    # Translate
    result, src_lang, provider = await orchestrator.translate_text_for_user(
        text="Hello world",
        tgt_lang="fr",
        guild_id=123,
        user_id=456,
    )
    
    # Should use DeepL
    assert result == "Bonjour le monde"
    assert provider == "deepl"
    deepl_mock.translate_async.assert_called_once()
    mymemory_mock.translate_async.assert_not_called()


@pytest.mark.asyncio
async def test_three_tier_translation_mymemory_fallback():
    """Test that MyMemory is used when DeepL doesn't support the language (tier 2)."""
    # Mock DeepL adapter that doesn't support the target language
    deepl_mock = MagicMock()
    deepl_mock.supported_languages.return_value = ["en", "de", "fr", "es"]  # No Portuguese
    
    # Mock MyMemory that succeeds
    mymemory_mock = MagicMock()
    mymemory_mock.translate_async = AsyncMock(return_value="Olá mundo")
    mymemory_mock.supported_languages.return_value = ["en", "de", "fr", "es", "pt", "ru"]
    
    # Real Google adapter (should not be called)
    google_adapter = create_google_translate_adapter()
    
    # Create orchestrator
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=deepl_mock,
        mymemory_adapter=mymemory_mock,
        google_adapter=google_adapter,
        detection_service=None,
        nlp_processor=None,
    )
    
    # Translate to Portuguese (not in DeepL mock)
    result, src_lang, provider = await orchestrator.translate_text_for_user(
        text="Hello world",
        tgt_lang="pt",
        guild_id=123,
        user_id=456,
    )
    
    # Should use MyMemory
    assert result == "Olá mundo"
    assert provider == "mymemory"
    mymemory_mock.translate_async.assert_called_once()


@pytest.mark.asyncio
async def test_three_tier_translation_google_fallback():
    """Test that Google is used when both DeepL and MyMemory don't support the language (tier 3)."""
    # Mock DeepL adapter that doesn't support the target language
    deepl_mock = MagicMock()
    deepl_mock.supported_languages.return_value = ["en", "de", "fr", "es"]
    
    # Mock MyMemory that doesn't support the target language
    mymemory_mock = MagicMock()
    mymemory_mock.supported_languages.return_value = ["en", "de", "fr", "es", "pt", "ru"]
    
    # Real Google adapter (supports Swahili)
    google_adapter = create_google_translate_adapter()
    
    # Create orchestrator
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=deepl_mock,
        mymemory_adapter=mymemory_mock,
        google_adapter=google_adapter,
        detection_service=None,
        nlp_processor=None,
    )
    
    # Translate to Swahili (not in DeepL or MyMemory mocks)
    result, src_lang, provider = await orchestrator.translate_text_for_user(
        text="Hello, how are you?",
        tgt_lang="sw",
        guild_id=123,
        user_id=456,
    )
    
    # Should use Google Translate
    assert result is not None
    assert len(result) > 0
    assert provider == "google"


@pytest.mark.asyncio
async def test_three_tier_all_fail():
    """Test behavior when all three tiers fail."""
    # Mock all adapters to fail
    deepl_mock = MagicMock()
    deepl_mock.translate_async = AsyncMock(return_value=None)
    deepl_mock.supported_languages.return_value = ["en", "fr"]
    
    mymemory_mock = MagicMock()
    mymemory_mock.translate_async = AsyncMock(return_value=None)
    mymemory_mock.supported_languages.return_value = ["en", "fr", "pt"]
    
    google_mock = MagicMock()
    google_mock.translate_async = AsyncMock(return_value=None)
    google_mock.supported_languages.return_value = ["en", "fr", "pt", "sw"]
    
    # Create orchestrator
    orchestrator = TranslationOrchestratorEngine(
        deepl_adapter=deepl_mock,
        mymemory_adapter=mymemory_mock,
        google_adapter=google_mock,
        detection_service=None,
        nlp_processor=None,
    )
    
    # Translate
    result, src_lang, provider = await orchestrator.translate_text_for_user(
        text="Hello world",
        tgt_lang="fr",
        guild_id=123,
        user_id=456,
    )
    
    # Should return None when all fail (not original text)
    assert result is None
    assert provider is None


@pytest.mark.asyncio
async def test_language_coverage_expansion():
    """Verify that Google Translate expands language coverage significantly."""
    # Create real Google adapter
    google_adapter = create_google_translate_adapter()
    
    # Mock limited adapters
    deepl_mock = MagicMock()
    deepl_mock.supported_languages.return_value = [
        "en", "de", "fr", "es", "it", "nl", "pl", "pt", "ru", "ja", "zh"
    ]  # ~11 languages
    
    mymemory_mock = MagicMock()
    mymemory_mock.supported_languages.return_value = [
        "en", "de", "fr", "es", "it", "nl", "pl", "pt", "ru", "ja", "zh",
        "ar", "hi", "tr", "ko", "vi"
    ]  # ~16 languages
    
    google_langs = google_adapter.supported_languages()
    
    # Google should support significantly more languages
    assert len(google_langs) >= 100
    
    # Verify Google covers rare languages not in DeepL/MyMemory
    rare_langs = ["sw", "hmn", "yi", "sm", "sn", "sd", "si", "ku", "ky", "am"]
    for lang in rare_langs:
        if lang in google_langs:
            # This rare language is only available via Google
            assert lang not in deepl_mock.supported_languages()
            assert lang not in mymemory_mock.supported_languages()
    
    # Should have at least 5 rare languages covered
    covered_rare = [lang for lang in rare_langs if lang in google_langs]
    assert len(covered_rare) >= 5, f"Expected at least 5 rare languages, got {len(covered_rare)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
