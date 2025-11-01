"""
Tests for SOS keyword matching in InputEngine.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from discord_bot.core.engines.input_engine import InputEngine


@pytest.fixture
def input_engine():
    """Create an InputEngine with minimal dependencies for SOS tests."""
    bot = MagicMock()
    context = MagicMock()
    processing = MagicMock()
    output = MagicMock()
    cache = MagicMock()
    roles = MagicMock()

    return InputEngine(
        bot,
        context_engine=context,
        processing_engine=processing,
        output_engine=output,
        cache_manager=cache,
        role_manager=roles,
    )


class TestSOSKeywordMatching:
    """Ensure SOS keyword detection only fires on whole-word matches."""

    def test_whole_word_match_triggers(self, input_engine: InputEngine):
        input_engine.set_sos_mapping(42, {"help": "Alert!"})
        assert input_engine._match_emergency_keyword("we need help!", 42) == "Alert!"

    def test_partial_word_does_not_trigger(self, input_engine: InputEngine):
        input_engine.set_sos_mapping(43, {"help": "Alert!"})
        assert input_engine._match_emergency_keyword("she is very helpful", 43) is None

    def test_multi_word_phrase_requires_exact_boundary(self, input_engine: InputEngine):
        input_engine.set_sos_mapping(44, {"fire drill": "Drill time"})
        assert input_engine._match_emergency_keyword("the fire drill starts now", 44) == "Drill time"
        assert input_engine._match_emergency_keyword("fire drilling practice", 44) is None
