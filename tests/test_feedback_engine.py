"""
Tests for the Feedback Engine and Correction Memory.
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor, OCRParseResult, RankingData, StageType, RankingCategory
from discord_bot.core.engines.openai_engine import OpenAIEngine
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
# Assume the existence of these future engines for testing purposes
# from discord_bot.core.engines.ocr_feedback_engine import OCRFeedbackEngine, CorrectionData
# from discord_bot.core.engines.adaptive_rules_engine import AdaptiveRulesEngine

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

# --- Fixtures ---

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_image_dir():
    """Path to test image directory."""
    return Path(__file__).parent / "data"

@pytest.fixture
def mock_storage_engine():
    """In-memory SQLite database for testing storage."""
    engine = RankingStorageEngine(db_path=":memory:")
    # The _ensure_tables() is called in __init__, so tables should exist
    return engine

@pytest.fixture
def mock_openai_engine():
    """Mocked OpenAI engine that returns predictable results."""
    engine = MagicMock(spec=OpenAIEngine)
    engine.analyze_screenshot_with_vision = AsyncMock(return_value={
        "rank": 101,
        "score": 1234567,
        "player_name": "AIVision",
        "guild_tag": "AI"
    })
    engine.analyze_correction = AsyncMock(return_value={
        "failure_category": "layout_shift",
        "confidence": 0.9,
        "suggestion": "The player name and score were swapped."
    })
    return engine

# --- Test Cases ---

async def test_vision_model_fallback(mock_openai_engine, test_image_dir):
    """
    STAGE 2/test_02: Validate OpenAIEngine image correction.
    """
    # 1. Feed an intentionally low-quality screenshot (or simulate a failed OCR)
    image_path = test_image_dir / "low_contrast.png"
    if not image_path.exists():
        pytest.skip("Test image not found.")
    image_data = image_path.read_bytes()
    image_url = "http://example.com/low_contrast.png"

    processor = ScreenshotProcessor(openai_engine=mock_openai_engine)

    # 2. Simulate pytesseract returning an empty string
    original_func = processor.process_screenshot_v2
    async def mock_process_v2(*args, **kwargs):
        from datetime import datetime
        # Create a partial ranking data object for the AI to fill
        partial_ranking = RankingData(
            user_id=args[1],
            username=args[2],
            guild_tag=None,
            event_week="2025-45",
            stage_type=StageType.PREP,
            day_number=1,
            category=RankingCategory.CONSTRUCTION,
            rank=0,
            score=0,
            player_name=None,
            submitted_at=datetime.utcnow(),
            guild_id=args[3] if len(args) > 3 else None
        )
        res = OCRParseResult(
            ranking_data=partial_ranking,
            error_message="Could not read any text from the image.",
            confidence=0.0,
            fields_found=[],
            fields_missing=["rank", "score"],
            raw_ocr_text=""
        )
        return res
    
    processor.process_screenshot_v2 = mock_process_v2

    # 3. Ensure process_screenshot_with_ai() triggers vision fallback
    result = await processor.process_screenshot_with_ai(
        image_data, "user1", "username1", "guild1", image_url
    )

    # 4. Verify AI result fills the fields
    mock_openai_engine.analyze_screenshot_with_vision.assert_called_once()
    assert result.ranking_data.rank == 101
    assert result.ranking_data.score == 1234567
    assert result.ranking_data.player_name == "AIVision"
    assert not result.fields_missing, "Fields should be filled by AI"
    assert result.confidence == 0.8, "Confidence should be marked as AI-assisted"

async def test_feedback_engine_round_trip_placeholder(mock_storage_engine, mock_openai_engine):
    """
    STAGE 3/test_03: Ensure user corrections are logged and analyzed.
    This is a placeholder for the full feedback engine.
    """
    from datetime import datetime
    # 1. Simulate a missing field scenario
    initial_data = RankingData(
        user_id="user2", username="UserTwo", guild_tag="ABC",
        event_week="2025-45", stage_type=StageType.WAR, day_number=3,
        category=RankingCategory.HERO, rank=50, score=0, # Score is missing
        player_name="UserTwo", submitted_at=datetime.utcnow()
    )
    
    # 2. Mock user answers
    corrected_score = 7948885
    reason = "OCR missed commas"

    # 3. Save to database (simulating what the feedback engine would do)
    ranking_id = mock_storage_engine.save_ranking(initial_data)
    
    # Simulate AI analysis of the correction
    analysis = await mock_openai_engine.analyze_correction(
        image_url="http://example.com/img.png",
        original_text="Rank 50 Score O",
        user_correction=f"Score: {corrected_score}",
        fields_missing=["score"]
    )

    mock_storage_engine.save_ocr_correction(
        ranking_id=ranking_id,
        user_id="user2",
        image_url="http://example.com/img.png",
        initial_text="Rank 50 Score O",
        failure_category=analysis["failure_category"],
        initial_rank=50,
        initial_score=0,
        corrected_rank=50,
        corrected_score=corrected_score,
        ai_analysis=analysis["suggestion"]
    )

    # 4. Confirm data was saved
    corrections = mock_storage_engine.get_ocr_correction_stats()
    assert corrections['total_corrections'] == 1
    assert corrections['failure_categories']['layout_shift'] == 1

    # 5. AdaptiveRules check (conceptual)
    # In a full implementation, we would now check if AdaptiveRulesEngine
    # suggests a new regex based on this failure.
    # adaptive_rules_engine.update_from_feedback(corrections)
    # assert r'(\d{1,3}(?:[.,]\d{3})+)' in adaptive_rules_engine.get_patterns('score')
    
    print("\n(Conceptual) AdaptiveRules would now learn from the 'layout_shift' failure.")

# This file would be expanded with more tests for the actual
# OCRFeedbackEngine and AdaptiveRulesEngine once they are built.
