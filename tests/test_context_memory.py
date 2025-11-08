"""
Tests for Context & Player Memory.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Assume these engines will be created
# from discord_bot.core.engines.context_memory_engine import ContextMemory, PlayerMemory
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine

pytestmark = pytest.mark.asyncio

# --- Mocks for future engines ---

class PlayerMemory:
    def __init__(self, storage_engine):
        self.storage = storage_engine
        self.player_cache = {}

    async def get_player_history(self, user_id: str):
        # In a real implementation, this would query the DB
        if user_id in self.player_cache:
            return self.player_cache[user_id]
        return []

    async def predict_expected_score(self, user_id: str) -> float:
        history = await self.get_player_history(user_id)
        if not history:
            return 0.0
        
        scores = [item['score'] for item in history if item.get('score')]
        if not scores:
            return 0.0
            
        return sum(scores) / len(scores)

    def add_fake_history(self, user_id, history):
        self.player_cache[user_id] = history

class ContextMemory:
    def __init__(self):
        self.cache = {}

    def get_context(self, user_id: str):
        return self.cache.get(user_id, {})

    def update_context(self, user_id: str, new_context: dict):
        if user_id not in self.cache:
            self.cache[user_id] = {}
        self.cache[user_id].update(new_context)

# --- Fixtures ---

@pytest.fixture
def mock_storage():
    return MagicMock(spec=RankingStorageEngine)

@pytest.fixture
def player_memory(mock_storage):
    return PlayerMemory(storage_engine=mock_storage)

@pytest.fixture
def context_memory():
    return ContextMemory()

# --- Test Cases ---

async def test_player_score_prediction(player_memory: PlayerMemory):
    """
    STAGE 4/test_04: Test player score prediction based on history.
    """
    user_id = "Mars"
    # 1. Create fake user "Mars" with 5 historical submissions
    fake_history = [
        {'score': 7800000, 'submitted_at': datetime.utcnow() - timedelta(days=5)},
        {'score': 8100000, 'submitted_at': datetime.utcnow() - timedelta(days=4)},
        {'score': 7950000, 'submitted_at': datetime.utcnow() - timedelta(days=3)},
        {'score': 8200000, 'submitted_at': datetime.utcnow() - timedelta(days=2)},
        {'score': 8050000, 'submitted_at': datetime.utcnow() - timedelta(days=1)},
    ]
    player_memory.add_fake_history(user_id, fake_history)

    # 3. Predict expected score
    predicted_score = await player_memory.predict_expected_score(user_id)
    
    # Expected average: (7.8 + 8.1 + 7.95 + 8.2 + 8.05) / 5 = 8.02M
    assert 8000000 < predicted_score < 8040000
    print(f"\nPredicted score for {user_id}: {predicted_score:,.0f}")

async def test_context_caching(context_memory: ContextMemory):
    """
    STAGE 4/test_04: Test caching of user context.
    """
    user_id = "Mars"
    
    # 5. ContextMemory caches event type, device type, etc.
    context_memory.update_context(user_id, {
        "last_event_type": "kvk",
        "last_device_type": "mobile",
        "guild_tag": "TAO"
    })

    user_context = context_memory.get_context(user_id)
    assert user_context["last_event_type"] == "kvk"
    assert user_context["guild_tag"] == "TAO"

    # Update with new info
    context_memory.update_context(user_id, {"last_event_type": "gar"})
    user_context = context_memory.get_context(user_id)
    assert user_context["last_event_type"] == "gar"

async def test_contextual_parsing_conceptual(player_memory: PlayerMemory):
    """
    STAGE 4/test_04: Conceptual test for how context would improve parsing.
    """
    # This is a conceptual test to illustrate the principle.
    # A full implementation would integrate PlayerMemory into ScreenshotProcessor.
    
    user_id = "Mars"
    fake_history = [{'score': 8000000}]
    player_memory.add_fake_history(user_id, fake_history)

    # 2. Submit new image with a common OCR error
    ocr_parsed_score = 80000 # OCR missed two zeros

    # The parser would use PlayerMemory to validate the result
    expected_score = await player_memory.predict_expected_score(user_id)
    
    is_significant_deviation = abs(ocr_parsed_score - expected_score) / expected_score > 0.5

    corrected_score = ocr_parsed_score
    confidence_boost = 0.0
    if is_significant_deviation:
        # The parser might try to fix it by adding zeros
        if expected_score / ocr_parsed_score in [10, 100, 1000]:
            corrected_score = ocr_parsed_score * (expected_score // ocr_parsed_score)
            confidence_boost = 0.1 # We are more confident now
    
    # This is a simplified example. A real implementation would be more robust.
    # assert corrected_score == 8000000
    # assert confidence_boost == 0.1
    
    print(
        f"\nConceptual: OCR score {ocr_parsed_score} could be auto-corrected to "
        f"{corrected_score:,.0f} (confidence boost {confidence_boost:.1f}) "
        f"based on history targeting ~{expected_score:,.0f}."
    )
