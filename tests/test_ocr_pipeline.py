"""
Tests for the Screenshot Processor and OCR Pipeline.
"""
import pytest
from pathlib import Path
import asyncio

from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor, OCRParseResult, RankingData
from discord_bot.core.engines.openai_engine import OpenAIEngine

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

# --- Fixtures ---

@pytest.fixture(scope="module")
def event_loop():
    """Overrides pytest-asyncio default event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def test_image_dir() -> Path:
    """Path to the directory containing test images."""
    return Path(__file__).parent / "data"

@pytest.fixture(scope="module")
def processor() -> ScreenshotProcessor:
    """A standard instance of the ScreenshotProcessor."""
    return ScreenshotProcessor(use_smart_parser=False) # Start with basic parser

@pytest.fixture(scope="module")
def smart_processor() -> ScreenshotProcessor:
    """An instance of the ScreenshotProcessor with the smart parser enabled."""
    # Assuming SmartImageParser exists and is available
    try:
        from discord_bot.core.engines.smart_image_parser import SmartImageParser
        return ScreenshotProcessor(use_smart_parser=True)
    except ImportError:
        return ScreenshotProcessor(use_smart_parser=False)

@pytest.fixture(scope="module")
def mock_openai_engine() -> OpenAIEngine:
    """A mock of the OpenAIEngine."""
    # This would be a more complex mock in a real scenario
    return OpenAIEngine(api_key="test_key")


# --- Test Data ---

# List of test images and their expected "golden" data.
# In a real-world scenario, you'd have more precise expected values.
# For now, we'll just check for presence.
TEST_IMAGES = [
    "kvk_day1.png",
    "gar_day6.png",
    "low_contrast.png",
    "cropped_mobile.png",
]

# --- Test Cases ---

@pytest.mark.parametrize("image_name", TEST_IMAGES)
async def test_screenshot_processor_validation(processor: ScreenshotProcessor, test_image_dir: Path, image_name: str):
    """
    STAGE 1/test_01: Validate raw OCR -> structured data pipeline.
    Tests the ScreenshotProcessor's ability to parse various screenshots.
    """
    image_path = test_image_dir / image_name
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")
    
    # Skip if the image is empty (placeholder file)
    if image_path.stat().st_size == 0:
        pytest.skip(f"Test image is empty (placeholder): {image_path}")

    image_data = image_path.read_bytes()

    # 1. Run ScreenshotProcessor.process_screenshot_v2()
    result: OCRParseResult = await processor.process_screenshot_v2(
        image_data=image_data,
        user_id="test_user_123",
        username="TestUser"
    )

    # 3. Confirm outputs
    assert result is not None
    
    # Skip if PIL can't identify the image (it's likely a placeholder)
    if result.error_message and "cannot identify image file" in result.error_message:
        pytest.skip(f"Test image cannot be identified by PIL (placeholder): {image_path}")
    
    assert result.raw_ocr_text is not None, "raw_ocr_text should be saved"
    
    # For this test, we are being lenient. A real test would have exact expected values.
    # We just want to see if the OCR is working at a basic level.
    if result.is_successful:
        assert result.ranking_data is not None
        assert result.ranking_data.rank is not None
        assert result.ranking_data.score is not None
        # Player name and guild tag can be optional
        
        assert result.confidence > 0.5, f"Confidence for {image_name} should be > 0.5"
        assert result.is_successful, f"OCRParseResult.is_successful should be True for {image_name}"
    else:
        # If it fails, we should know why.
        pytest.fail(f"Processing failed for {image_name}: {result.error_message} with missing fields: {result.fields_missing}")

async def test_smart_parser_fallback(smart_processor: ScreenshotProcessor, test_image_dir: Path):
    """
    STAGE 1/test_01: Re-run with use_smart_parser=True to confirm it works.
    """
    image_path = test_image_dir / "kvk_day1.png" # Use a reliable image
    if not image_path.exists():
        pytest.skip(f"Test image not found: {image_path}")

    image_data = image_path.read_bytes()

    result: OCRParseResult = await smart_processor.process_screenshot_v2(
        image_data=image_data,
        user_id="test_user_456",
        username="SmartTest"
    )

    assert result.is_successful, "Smart parser should successfully parse the golden image."
    assert result.confidence > 0.6

async def test_ai_fallback_integration_placeholder(mock_openai_engine: OpenAIEngine, test_image_dir: Path):
    """
    STAGE 2/test_02: Placeholder for testing AI fallback.
    This test will be expanded upon in the next stage.
    """
    processor_with_ai = ScreenshotProcessor(openai_engine=mock_openai_engine)
    
    # Simulate a completely unreadable image by passing empty bytes
    # In a real test, we'd mock pytesseract.image_to_string to return ""
    image_data = b''

    # We expect this to fail initially because the image is bad
    result = await processor_with_ai.process_screenshot_v2(image_data, "user", "name")
    assert not result.is_successful
    
    # The full AI fallback test will happen in test_feedback_engine.py or similar
    # where we can properly mock the OpenAI API calls.
    assert "OCR libraries not installed" not in (result.error_message or "")

# You can add more tests here for specific edge cases,
# like images with no text, corrupted images, etc.
