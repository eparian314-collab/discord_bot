"""
Tests for RelationshipManager engine.
"""

import pytest
from datetime import datetime, timedelta
from discord_bot.games.storage.game_storage_engine import GameStorageEngine
from discord_bot.core.engines.relationship_manager import RelationshipManager


@pytest.fixture
def storage():
    """Create a test storage engine with in-memory database."""
    engine = GameStorageEngine(db_path=":memory:")
    yield engine
    engine.conn.close()


@pytest.fixture
def relationship_manager(storage):
    """Create a RelationshipManager with test storage."""
    return RelationshipManager(storage)


class TestRelationshipManager:
    """Test suite for RelationshipManager."""
    
    def test_initialization(self, relationship_manager):
        """Test that RelationshipManager initializes correctly."""
        assert relationship_manager is not None
        assert relationship_manager.storage is not None
    
    def test_record_interaction_increases_relationship(self, relationship_manager):
        """Test that recording interactions increases relationship index."""
        user_id = "test_user_1"
        
        # First interaction
        relationship1 = relationship_manager.record_interaction(user_id, 'translation')
        assert relationship1 >= relationship_manager.BASELINE_RELATIONSHIP
        assert relationship1 <= 100
        
        # Second interaction should increase
        relationship2 = relationship_manager.record_interaction(user_id, 'translation')
        assert relationship2 >= relationship1
        assert relationship2 <= 100
    
    def test_different_interaction_types_have_different_values(self, relationship_manager):
        """Test that different interaction types award different relationship points."""
        user1 = "test_user_1"
        user2 = "test_user_2"
        
        # Easter egg interaction (value: higher than help)
        rel1 = relationship_manager.record_interaction(user1, 'easter_egg')
        
        # Help command (value: 1)
        rel2 = relationship_manager.record_interaction(user2, 'help_command')
        
        # Easter egg should generally give more (accounting for random bonus)
        assert rel1 >= rel2
    
    def test_relationship_index_caps_at_100(self, relationship_manager):
        """Test that relationship index doesn't exceed 100."""
        user_id = "test_user_max"
        
        # Record many interactions
        for _ in range(80):
            rel = relationship_manager.record_interaction(user_id, 'easter_egg')
        
        # Should cap at 100
        assert rel == 100
    
    def test_get_relationship_index(self, relationship_manager):
        """Test retrieving relationship index."""
        user_id = "test_user_get"
        
        # New user should start at the friendly baseline
        rel = relationship_manager.get_relationship_index(user_id)
        assert rel == relationship_manager.BASELINE_RELATIONSHIP
        
        # After interaction
        relationship_manager.record_interaction(user_id, 'translation')
        rel = relationship_manager.get_relationship_index(user_id)
        assert rel >= relationship_manager.BASELINE_RELATIONSHIP
    
    def test_luck_modifier_scales_with_relationship(self, relationship_manager):
        """Test that luck modifier scales correctly with relationship."""
        user_id = "test_user_luck"
        
        # Low relationship = low luck
        luck1 = relationship_manager.get_luck_modifier(user_id)
        expected_baseline = 0.5 + (relationship_manager.BASELINE_RELATIONSHIP / 140.0)
        assert pytest.approx(expected_baseline, rel=0.01) == luck1
        
        # Increase relationship
        for _ in range(30):
            relationship_manager.record_interaction(user_id, 'game_action')
        
        # Higher relationship = higher luck
        luck2 = relationship_manager.get_luck_modifier(user_id)
        assert luck2 > luck1
        assert luck2 <= 1.25  # Adjusted maximum luck multiplier
    
    def test_cookie_drop_bonus_scales_with_relationship(self, relationship_manager):
        """Test that cookie drop bonus scales with relationship."""
        user_id = "test_user_drop"
        
        # Low relationship = low bonus
        bonus1 = relationship_manager.get_cookie_drop_bonus(user_id)
        expected_bonus = relationship_manager.BASELINE_RELATIONSHIP / 250.0
        assert pytest.approx(expected_bonus, rel=0.01) == bonus1
        
        # Increase relationship
        for _ in range(30):
            relationship_manager.record_interaction(user_id, 'game_action')
        
        # Higher relationship = higher bonus
        bonus2 = relationship_manager.get_cookie_drop_bonus(user_id)
        assert bonus2 > bonus1
        assert bonus2 <= 0.4  # Adjusted maximum bonus

    def test_relationship_stays_low_without_cooldown(self, relationship_manager, storage):
        """Relationship should remain lowered immediately after a negative streak."""
        user_id = "test_user_low"
        storage.add_user(user_id)
        now = datetime.utcnow()
        with storage.conn:
            storage.conn.execute(
                """
                UPDATE users
                   SET relationship_index = ?, relationship_anchor_at = ?, last_interaction = ?, total_interactions = ?
                 WHERE user_id = ?
                """,
                (20, now.isoformat(), now.isoformat(), 5, user_id),
            )

        current = relationship_manager.get_relationship_index(user_id)
        assert current == 20

    def test_relationship_recovers_after_cooldown(self, relationship_manager, storage):
        """Relationship should drift back toward baseline when given time."""
        user_id = "test_user_recover"
        storage.add_user(user_id)
        past_time = (datetime.utcnow() - timedelta(hours=8)).isoformat()
        with storage.conn:
            storage.conn.execute(
                """
                UPDATE users
                   SET relationship_index = ?, relationship_anchor_at = ?, last_interaction = ?, total_interactions = ?
                 WHERE user_id = ?
                """,
                (20, past_time, past_time, 10, user_id),
            )

        recovered = relationship_manager.get_relationship_index(user_id)
        assert recovered > 20
        assert recovered < relationship_manager.BASELINE_RELATIONSHIP
    
    def test_relationship_tiers(self, relationship_manager):
        """Test relationship tier names."""
        user_id = "test_user_tiers"
        
        # Baseline should already be friendly
        tier = relationship_manager.get_relationship_tier(user_id)
        assert "Good Friends" in tier or "Close Friends" in tier
        
        # Increase to reach Close Friends (75+)
        for _ in range(30):
            relationship_manager.record_interaction(user_id, 'game_action')
        tier = relationship_manager.get_relationship_tier(user_id)
        assert "Close Friends" in tier or "Best Friends" in tier
        
        # Push to Best Friends (90+)
        for _ in range(60):
            relationship_manager.record_interaction(user_id, 'game_action')
        tier = relationship_manager.get_relationship_tier(user_id)
        assert "Best Friends" in tier


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


