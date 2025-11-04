"""
RelationshipManager - Tracks user interactions and calculates relationship index.

The relationship system encourages daily engagement and rewards consistent interaction.
Relationship index (0-100) affects cookie drops, luck, and bot personality towards users.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, date
from typing import TYPE_CHECKING, Optional, Set

if TYPE_CHECKING:
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


logger = logging.getLogger("hippo_bot.relationship_manager")


class RelationshipManager:
    """
    Manages user-bot relationship tracking and calculation.
    
    Relationship mechanics:
    - Starts at 0, max 100
    - Increases with each interaction (+1 to +5 based on interaction type)
    - Daily login bonus (+5) and streak bonuses
    - Decays slowly if inactive (-1 per day after 3 days) but drifts back toward a friendly baseline after cooldowns
    - Affects: cookie drop rates, luck values, bot mood towards user
    """
    
    BASELINE_RELATIONSHIP = 55
    RECOVERY_DELAY = timedelta(hours=4)
    RECOVERY_INTERVAL = timedelta(hours=1)
    RECOVERY_STEP = 5

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
        self._best_friend_date: Optional[date] = None
        self._best_friend_user: Optional[str] = None
        self._best_friend_seen: Set[str] = set()
        self._best_friend_unique_count: int = 0
    
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
            return self.BASELINE_RELATIONSHIP
        
        current_relationship = user_data['relationship_index']
        if user_data.get('total_interactions', 0) == 0 and current_relationship < self.BASELINE_RELATIONSHIP:
            current_relationship = self.BASELINE_RELATIONSHIP
        
        # Calculate relationship gain
        base_gain = self.INTERACTION_VALUES.get(interaction_type, 1)
        # Tougher scaling: reduce base gain and keep variance small
        adjusted_base = max(1, base_gain - 2)
        gain = adjusted_base + random.randint(0, 1)

        # Update relationship (cap at 100)
        new_relationship = min(100, current_relationship + gain)
        
        # Check for daily streak bonus
        daily_streak = self._check_daily_streak(user_data)
        
        # Update storage
        self.storage.update_relationship(user_id, new_relationship, daily_streak)
        self.storage.increment_interactions(user_id, interaction_type, cookies_earned)
        self._update_best_friend(user_id)

        return new_relationship
    
    def get_relationship_index(self, user_id: str) -> int:
        """Get current relationship index with decay applied."""
        self.storage.add_user(user_id)
        user_data = self.storage.get_user_data(user_id)
        
        if not user_data:
            return self.BASELINE_RELATIONSHIP

        relationship_value = user_data['relationship_index']

        if user_data.get('total_interactions', 0) == 0 and relationship_value < self.BASELINE_RELATIONSHIP:
            self.storage.update_relationship(
                user_id,
                self.BASELINE_RELATIONSHIP,
                touch_last_interaction=False,
                touch_anchor=True,
            )
            relationship_value = self.BASELINE_RELATIONSHIP
            user_data = self.storage.get_user_data(user_id) or user_data

        anchor_time = self._get_anchor_time(user_data)
        decayed_value = self._apply_decay(anchor_time, relationship_value)
        recovered_value = self._apply_recovery(anchor_time, decayed_value)

        if recovered_value != user_data['relationship_index']:
            self.storage.update_relationship(
                user_id,
                recovered_value,
                touch_last_interaction=False,
                touch_anchor=True,
            )

        return recovered_value
    
    def get_luck_modifier(self, user_id: str) -> float:
        """
        Calculate luck modifier based on relationship (0.5 to 1.5 multiplier).
        Higher relationship = better luck for cookie rewards and XP gains.
        """
        relationship = self.get_relationship_index(user_id)
        # Map 0-100 relationship to a narrower 0.5-1.2 range
        return 0.5 + (relationship / 140.0)
    
    def get_cookie_drop_bonus(self, user_id: str) -> float:
        """
        Get cookie drop rate bonus based on relationship (0% to +50%).
        """
        relationship = self.get_relationship_index(user_id)
        # Map 0-100 relationship to 0-0.4 bonus drop rate
        return relationship / 250.0
    
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
    
    def _apply_decay(self, anchor_time: datetime, current_relationship: int) -> int:
        """Apply relationship decay for inactivity."""
        if current_relationship <= 0:
            return 0
        
        now = datetime.utcnow()
        days_inactive = (now - anchor_time).days
        
        if days_inactive > self.DECAY_START_DAYS:
            # Apply decay
            decay_amount = (days_inactive - self.DECAY_START_DAYS) * self.DECAY_RATE
            return max(0, current_relationship - decay_amount)
        
        return current_relationship

    def _apply_recovery(self, anchor_time: datetime, current_relationship: int) -> int:
        """Recover relationship toward the friendly baseline after cooldown."""
        if current_relationship >= self.BASELINE_RELATIONSHIP:
            return current_relationship

        now = datetime.utcnow()
        elapsed = now - anchor_time

        if elapsed <= self.RECOVERY_DELAY:
            return current_relationship

        extra = elapsed - self.RECOVERY_DELAY
        steps = int(extra / self.RECOVERY_INTERVAL)

        if steps <= 0:
            return current_relationship

        recovered = current_relationship + (steps * self.RECOVERY_STEP)
        return min(self.BASELINE_RELATIONSHIP, recovered)

    def _get_anchor_time(self, user_data: dict) -> datetime:
        """Determine reference timestamp for decay/recovery calculations."""
        anchor_str = user_data.get('relationship_anchor_at') or user_data.get('last_interaction')
        if anchor_str:
            try:
                return datetime.fromisoformat(anchor_str)
            except ValueError:
                pass
        return datetime.utcnow()
    
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
    # ------------------------------------------------------------------
    # Daily best friend tracking
    # ------------------------------------------------------------------
    def _update_best_friend(self, user_id: str) -> None:
        """Reservoir-sample a best friend of the day from active speakers."""
        today = datetime.utcnow().date()

        if self._best_friend_date != today:
            self._best_friend_date = today
            self._best_friend_user = user_id
            self._best_friend_seen = {user_id}
            self._best_friend_unique_count = 1
            logger.debug("Daily best friend reset to %s", user_id)
            return

        if user_id in self._best_friend_seen:
            return

        self._best_friend_seen.add(user_id)
        self._best_friend_unique_count += 1

        if random.randint(1, self._best_friend_unique_count) == 1:
            self._best_friend_user = user_id
            logger.debug("Daily best friend updated to %s", user_id)

    def get_best_friend_of_day(self) -> Optional[str]:
        """Return the current best friend of the day (user_id) if set."""
        today = datetime.utcnow().date()
        if self._best_friend_date != today:
            return None
        return self._best_friend_user

