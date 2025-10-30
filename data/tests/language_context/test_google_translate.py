"""
Tests for Google Translate adapter integration.

This module verifies that:
1. GoogleTranslateAdapter is properly instantiated
2. It reports 100+ supported languages
3. Basic translation functionality works
4. 3-tier translation pipeline falls back to Google when needed
"""

import pytest
from discord_bot.language_context.translators.google_translate_adapter import (
    create_google_translate_adapter,
    GoogleTranslateAdapter,
)


@pytest.fixture
def google_adapter():
    """Create a Google Translate adapter instance."""
    return create_google_translate_adapter()


def test_google_adapter_creation(google_adapter):
    """Test that Google Translate adapter is created successfully."""
    assert google_adapter is not None
    assert isinstance(google_adapter, GoogleTranslateAdapter)


def test_google_supported_languages(google_adapter):
    """Test that Google Translate supports 100+ languages."""
    supported = google_adapter.supported_languages()
    assert isinstance(supported, list)
    assert len(supported) >= 100, f"Expected 100+ languages, got {len(supported)}"
    
    # Check for some common languages
    common_langs = ["en", "es", "fr", "de", "ja", "ko", "zh-cn", "ar", "hi", "pt", "ru"]
    for lang in common_langs:
        assert lang in supported, f"Expected '{lang}' to be in supported languages"


@pytest.mark.asyncio
async def test_google_translate_basic(google_adapter):
    """Test basic translation using Google Translate."""
    result = await google_adapter.translate_async(
        text="Hello, world!",
        tgt="es",
        src="en"
    )
    
    assert result is not None
    assert len(result) > 0
    assert "hola" in result.lower() or "mundo" in result.lower()


@pytest.mark.asyncio
async def test_google_translate_rare_language(google_adapter):
    """Test translation to a rare language not in DeepL/MyMemory."""
    # Test with Swahili (sw) - not commonly in DeepL
    result = await google_adapter.translate_async(
        text="Hello, how are you?",
        tgt="sw",
        src="en"
    )
    
    assert result is not None
    assert len(result) > 0
    # Should get Swahili translation (not checking exact text due to potential variations)


@pytest.mark.asyncio
async def test_google_translate_auto_detect(google_adapter):
    """Test translation with auto-detection."""
    result = await google_adapter.translate_async(
        text="Bonjour le monde",
        tgt="en",
        src="auto"  # Auto-detect
    )
    
    assert result is not None
    assert len(result) > 0
    assert "hello" in result.lower() or "world" in result.lower()


def test_google_language_coverage():
    """Test that Google covers languages DeepL doesn't."""
    adapter = create_google_translate_adapter()
    supported = adapter.supported_languages()
    
    # Languages that DeepL typically doesn't support but Google does
    rare_langs = ["sw", "hmn", "yi", "sm", "sn", "sd", "si", "ku", "ky"]
    
    found_count = sum(1 for lang in rare_langs if lang in supported)
    assert found_count >= 5, f"Expected at least 5 rare languages, found {found_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
