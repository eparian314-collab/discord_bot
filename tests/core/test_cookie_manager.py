"""
Tests for CookieManager engine.
"""

from datetime import datetime, timedelta

import random

import pytest
from discord_bot.games.storage.game_storage_engine import GameStorageEngine
from discord_bot.core.engines.relationship_manager import RelationshipManager
from discord_bot.core.engines.cookie_manager import CookieManager


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


@pytest.fixture
def cookie_manager(storage, relationship_manager):
    """Create a CookieManager with test dependencies."""
    return CookieManager(storage, relationship_manager)


class TestCookieManager:
    """Test suite for CookieManager."""
    
    def test_initialization(self, cookie_manager):
        """Test that CookieManager initializes correctly."""
        assert cookie_manager is not None
        assert cookie_manager.storage is not None
        assert cookie_manager.relationship_manager is not None
    
    def test_try_award_cookies_respects_drop_rates(self, cookie_manager):
        """Test that cookie awards respect drop rates."""
        user_id = "test_user_drops"
        random.seed(0)
        
        # Easter egg has 50% drop rate - test multiple times
        drops = 0
        trials = 100
        
        for _ in range(trials):
            result = cookie_manager.try_award_cookies(user_id, 'easter_egg', 'neutral')
            if result is not None:
                drops += 1
        
        # Should be roughly 50% (allow 30-70% range for randomness)
        drop_rate = drops / trials
        assert 0.3 <= drop_rate <= 0.7
    
    def test_mood_affects_cookie_amounts(self, cookie_manager):
        """Test that bot mood affects cookie amounts."""
        user_id = "test_user_mood"
        
        # Force drops by using high-rate interaction
        happy_cookies = []
        grumpy_cookies = []
        
        for _ in range(50):
            result = cookie_manager.try_award_cookies(user_id, 'rps_win', 'happy')
            if result is not None:
                happy_cookies.append(result)
        
        user_id2 = "test_user_mood2"
        for _ in range(50):
            result = cookie_manager.try_award_cookies(user_id2, 'rps_win', 'grumpy')
            if result is not None:
                grumpy_cookies.append(result)
        
        # Happy mood should generally give more cookies
        if happy_cookies and grumpy_cookies:
            avg_happy = sum(happy_cookies) / len(happy_cookies)
            avg_grumpy = sum(grumpy_cookies) / len(grumpy_cookies)
            assert avg_happy >= avg_grumpy
    
    def test_spend_stamina(self, cookie_manager, storage):
        """Test spending stamina (cookies) for actions."""
        user_id = "test_user_spend"
        
        # Give user some cookies
        storage.add_cookies(user_id, 10)
        
        # Spend cookies for catch (costs 1)
        success, cost = cookie_manager.spend_stamina(user_id, 'catch')
        assert success is True
        assert cost == 1
        
        # Check balance
        _, current = storage.get_user_cookies(user_id)
        assert current == 9
    
    def test_cannot_spend_more_than_balance(self, cookie_manager, storage):
        """Test that users can't spend more cookies than they have."""
        user_id = "test_user_broke"
        
        # Give user only 1 cookie
        storage.add_cookies(user_id, 1)
        
        # Try to spend 3 cookies for explore
        success, cost = cookie_manager.spend_stamina(user_id, 'explore')
        assert success is False
        assert cost == 3
        
        # Balance should remain unchanged
        _, current = storage.get_user_cookies(user_id)
        assert current == 1
    
    def test_can_afford(self, cookie_manager, storage):
        """Test checking if user can afford an action."""
        user_id = "test_user_afford"
        
        # Give user 5 cookies
        storage.add_cookies(user_id, 5)
        
        # Can afford catch (2 cookies)
        assert cookie_manager.can_afford(user_id, 'catch') is True
        
        # Can afford fish (2 cookies)
        assert cookie_manager.can_afford(user_id, 'fish') is True
        
        # Can afford explore (3 cookies)
        assert cookie_manager.can_afford(user_id, 'explore') is True
        
        # Cannot afford evolve (5 cookies) after spending some
        cookie_manager.spend_stamina(user_id, 'explore')
        assert cookie_manager.can_afford(user_id, 'evolve') is False
    
    def test_get_cookie_balance(self, cookie_manager, storage):
        """Test retrieving cookie balance stats."""
        user_id = "test_user_balance"
        
        # Add cookies
        storage.add_cookies(user_id, 10)
        
        # Spend some
        storage.spend_cookies(user_id, 3)
        
        # Check balance
        balance = cookie_manager.get_cookie_balance(user_id)
        assert balance['total_earned'] == 10
        assert balance['current_balance'] == 7
        assert balance['spent'] == 3
    
    def test_game_unlock_eligibility(self, cookie_manager, storage):
        """Test checking game unlock eligibility."""
        user_id = "test_user_unlock"
        
        # Not enough cookies
        assert cookie_manager.check_game_unlock_eligibility(user_id) is False
        
        # Add exactly 5 cookies
        storage.add_cookies(user_id, 5)
        assert cookie_manager.check_game_unlock_eligibility(user_id) is True
        
        # More than 5 is also okay
        storage.add_cookies(user_id, 5)
        assert cookie_manager.check_game_unlock_eligibility(user_id) is True
    
    def test_unlock_game_with_cookies(self, cookie_manager, storage):
        """Test unlocking the game with cookies."""
        user_id = "test_user_game_unlock"
        
        # Give user cookies
        storage.add_cookies(user_id, 10)
        
        # Unlock game
        success = cookie_manager.unlock_game_with_cookies(user_id)
        assert success is True
        
        # Check that game is unlocked
        assert storage.is_game_unlocked(user_id) is True
        
        # Check that 5 cookies were spent
        _, current = storage.get_user_cookies(user_id)
        assert current == 5
    
    def test_cannot_unlock_without_cookies(self, cookie_manager, storage):
        """Test that game cannot be unlocked without enough cookies."""
        user_id = "test_user_no_unlock"
        
        # Give user only 3 cookies
        storage.add_cookies(user_id, 3)
        
        # Try to unlock
        success = cookie_manager.unlock_game_with_cookies(user_id)
        assert success is False
        
        # Game should not be unlocked
        assert storage.is_game_unlocked(user_id) is False
    
    def test_calculate_training_xp(self, cookie_manager, relationship_manager):
        """Test XP calculation for training with cookies."""
        user_id = "test_user_xp"
        
        # Build some relationship for luck
        for _ in range(10):
            relationship_manager.record_interaction(user_id, 'game_action')
        
        # Calculate XP for training with 5 cookies
        xp = cookie_manager.calculate_training_xp(user_id, 5)
        
        # Should yield a reasonable amount of XP (base XP scaled by luck)
        assert xp >= 25
        # Should be influenced by luck (up to 100 base + luck modifier)
        assert xp <= 200
    
    def test_luck_improves_training_xp(self, cookie_manager, relationship_manager):
        """Test that higher luck improves training XP."""
        user1 = "test_user_low_luck"
        user2 = "test_user_high_luck"
        
        # user2 has high relationship
        for _ in range(50):
            relationship_manager.record_interaction(user2, 'game_action')
        
        # Calculate XP for both (average over multiple trials)
        xp1_total = sum(cookie_manager.calculate_training_xp(user1, 5) for _ in range(10))
        xp2_total = sum(cookie_manager.calculate_training_xp(user2, 5) for _ in range(10))
        
        # Higher luck should generally give more XP
        assert xp2_total >= xp1_total

    def test_spam_cooldown_resets_penalties(self, cookie_manager, storage):
        """Ensure repeated requests stop being punished after the cooldown."""
        user_id = "spammy_user"

        # Simulate earning the full daily quota in one shot
        storage.record_easter_egg_attempt(
            user_id,
            cookie_manager.MAX_DAILY_EASTER_EGG_COOKIES,
            is_spam=False,
        )

        # First spam attempt should increase aggravation
        first_attempt = cookie_manager.handle_easter_egg_spam(user_id)
        assert first_attempt["is_spam"] is True
        assert first_attempt["aggravation_level"] >= 1

        # Age the aggravation timestamp beyond the cooldown window
        past_time = (
            datetime.utcnow() - timedelta(minutes=cookie_manager.SPAM_RESET_MINUTES + 5)
        ).isoformat()
        with storage.conn:
            storage.conn.execute(
                """
                UPDATE users
                   SET aggravation_updated_at = ?, aggravation_level = ?
                 WHERE user_id = ?
                """,
                (past_time, first_attempt["aggravation_level"], user_id),
            )

        cooled_attempt = cookie_manager.handle_easter_egg_spam(user_id)
        assert cooled_attempt["is_spam"] is False
        assert cooled_attempt["aggravation_level"] == 0
        assert cooled_attempt["cookie_penalty"] == 0
        assert cooled_attempt["should_mute"] is False
        assert storage.get_aggravation_level(user_id) == 0

    def test_admin_gift_cookies_do_not_affect_totals(self, cookie_manager, storage):
        """Admin/helper gifts should not count toward total cookies."""
        giver = "admin_user"
        recipient = "lucky_member"

        remaining = cookie_manager.get_admin_gift_remaining(giver)
        assert remaining == cookie_manager.ADMIN_DAILY_GIFT_POOL

        gifted = cookie_manager.give_admin_gift(giver, recipient, 6)
        assert gifted == 6

        # Remaining allowance should drop
        assert cookie_manager.get_admin_gift_remaining(giver) == cookie_manager.ADMIN_DAILY_GIFT_POOL - 6

        total, current = storage.get_user_cookies(recipient)
        assert total == 0  # leaderboard unaffected
        assert current == 6

        # Attempt to over-gift should fail and not modify balances
        assert cookie_manager.give_admin_gift(giver, recipient, 10) == 0
        total_after, current_after = storage.get_user_cookies(recipient)
        assert total_after == 0
        assert current_after == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
