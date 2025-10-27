"""
RelationshipManager - Tracks user interactions and calculates relationship index.

The relationship system encourages daily engagement and rewards consistent interaction.
Relationship index (0-100) affects cookie drops, luck, and bot personality towards users.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class RelationshipManager:
    """
    Manages user-bot relationship tracking and calculation.
    
    Relationship mechanics:
    - Starts at 0, max 100
    - Increases with each interaction (+1 to +5 based on interaction type)
    - Daily login bonus (+5) and streak bonuses
    - Decays slowly if inactive (-1 per day after 3 days)
    - Affects: cookie drop rates, luck values, bot mood towards user
    """
    
    # Interaction type values
    INTERACTION_VALUES = {
        'translation': 2,
        'role_assign': 3,
        'easter_egg': 4,
        'game_action': 3,
        'help_command': 1,
        'mention': 2,
        'daily_login': 5,
    }
    
    # Relationship decay settings
    DECAY_START_DAYS = 3
    DECAY_RATE = 1
    
    def __init__(self, storage: GameStorageEngine):
        self.storage = storage
    
    def record_interaction(self, user_id: str, interaction_type: str, 
                          cookies_earned: int = 0) -> int:
        """
        Record an interaction and update relationship index.
        Returns the new relationship index.
        """
        # Ensure user exists
        self.storage.add_user(user_id)
        
        # Get current user data
        user_data = self.storage.get_user_data(user_id)
        if not user_data:
            return 0
        
        current_relationship = user_data['relationship_index']
        
        # Calculate relationship gain
        base_gain = self.INTERACTION_VALUES.get(interaction_type, 1)
        # Add small random bonus (0-2)
        gain = base_gain + random.randint(0, 2)
        
        # Update relationship (cap at 100)
        new_relationship = min(100, current_relationship + gain)
        
        # Check for daily streak bonus
        daily_streak = self._check_daily_streak(user_data)
        
        # Update storage
        self.storage.update_relationship(user_id, new_relationship, daily_streak)
        self.storage.increment_interactions(user_id, interaction_type, cookies_earned)
        
        return new_relationship
    
    def get_relationship_index(self, user_id: str) -> int:
        """Get current relationship index with decay applied."""
        self.storage.add_user(user_id)
        user_data = self.storage.get_user_data(user_id)
        
        if not user_data:
            return 0
        
        # Apply decay if needed
        decayed_value = self._apply_decay(user_data)
        
        if decayed_value != user_data['relationship_index']:
            self.storage.update_relationship(user_id, decayed_value)
        
        return decayed_value
    
    def get_luck_modifier(self, user_id: str) -> float:
        """
        Calculate luck modifier based on relationship (0.5 to 1.5 multiplier).
        Higher relationship = better luck for cookie rewards and XP gains.
        """
        relationship = self.get_relationship_index(user_id)
        # Map 0-100 relationship to 0.5-1.5 luck multiplier
        return 0.5 + (relationship / 100.0)
    
    def get_cookie_drop_bonus(self, user_id: str) -> float:
        """
        Get cookie drop rate bonus based on relationship (0% to +50%).
        """
        relationship = self.get_relationship_index(user_id)
        # Map 0-100 relationship to 0-0.5 bonus drop rate
        return relationship / 200.0
    
    def _check_daily_streak(self, user_data: dict) -> int:
        """Check and update daily login streak."""
        last_check_str = user_data.get('last_daily_check')
        current_streak = user_data.get('daily_streak', 0)
        
        if not last_check_str:
            # First time checking
            self.storage.update_daily_check(user_data['user_id'])
            return 1
        
        last_check = datetime.fromisoformat(last_check_str)
        now = datetime.utcnow()
        days_diff = (now - last_check).days
        
        if days_diff >= 1:
            # Update daily check
            self.storage.update_daily_check(user_data['user_id'])
            
            if days_diff == 1:
                # Consecutive day - increment streak
                return current_streak + 1
            else:
                # Streak broken - reset to 1
                return 1
        
        # Same day - return current streak
        return current_streak
    
    def _apply_decay(self, user_data: dict) -> int:
        """Apply relationship decay for inactivity."""
        last_interaction_str = user_data.get('last_interaction')
        current_relationship = user_data['relationship_index']
        
        if not last_interaction_str or current_relationship <= 0:
            return current_relationship
        
        last_interaction = datetime.fromisoformat(last_interaction_str)
        now = datetime.utcnow()
        days_inactive = (now - last_interaction).days
        
        if days_inactive > self.DECAY_START_DAYS:
            # Apply decay
            decay_amount = (days_inactive - self.DECAY_START_DAYS) * self.DECAY_RATE
            return max(0, current_relationship - decay_amount)
        
        return current_relationship
    
    def get_relationship_tier(self, user_id: str) -> str:
        """Get relationship tier name for display."""
        relationship = self.get_relationship_index(user_id)
        
        if relationship >= 90:
            return "Best Friends 💖"
        elif relationship >= 75:
            return "Close Friends 💙"
        elif relationship >= 50:
            return "Good Friends 💚"
        elif relationship >= 25:
            return "Friends 🙂"
        elif relationship >= 10:
            return "Acquaintances 👋"
        else:
            return "Strangers 🤝"
