"""
CookieManager - Handles cookie economy with luck-based rewards and stamina costs.

Manages cookie earning, spending, and reward calculations based on:
- User relationship index (affects drop rates and amounts)
- Bot mood (affects generosity)
- Action type (different drop rates for different activities)
"""

from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING, Optional, Dict, Set

if TYPE_CHECKING:
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine
    from discord_bot.core.engines.relationship_manager import RelationshipManager


class CookieManager:
    """
    Manages the cookie economy system.
    
    Cookie mechanics:
    - Random drops based on interaction type and drop rates
    - Amount influenced by relationship and bot mood
    - Stamina costs for game actions
    - Rewards for successful interactions
    - Daily easter egg limits (max 15 cookies per day)
    - Progressive spam penalties
    """
    
    # Base drop rates by interaction type (probability 0.0-1.0)
    DROP_RATES = {
        'translation': 0.08,        # Core function - lower rate
        'role_assign': 0.10,        # Core function - lower rate
        'easter_egg': 0.50,         # Fun interactions - high rate
        'game_action': 0.30,        # Game actions - medium rate
        'help_command': 0.15,       # Info commands - medium-low rate
        'mention': 0.40,            # Direct interaction - high rate
        'rps_win': 0.70,            # Game win - very high rate
        'trivia_correct': 0.65,     # Correct answer - high rate
        'riddle_correct': 0.65,     # Correct answer - high rate
    }
    
    # Stamina costs for actions (in cookies)
    STAMINA_COSTS = {
        'catch': 1,         # Catching Pokemon - basic action
        'fish': 1,          # Fishing for Pokemon - basic action
        'explore': 3,       # Exploring for rare Pokemon - expensive
        'train': 2,         # Training Pokemon - medium cost
        'battle': 2,        # Pokemon battles - expensive (future)
        'evolve': 5,        # Evolution - most expensive
    }
    
    # Mood multipliers for cookie amounts
    MOOD_MULTIPLIERS = {
        'happy': (2, 4),      # Give 2-4 cookies when happy
        'neutral': (1, 2),    # Give 1-2 cookies when neutral
        'grumpy': (0, 1),     # Give 0-1 cookies when grumpy (can give nothing)
    }
    
    # Easter egg limits
    MAX_DAILY_EASTER_EGG_COOKIES = 15
    ADMIN_DAILY_GIFT_POOL = 10
    SPAM_PENALTY_COOKIE_AMOUNT = 1
    BASE_MUTE_CHANCE = 0.01  # 1%
    MUTE_CHANCE_INCREMENT = 0.10  # 10% per spam attempt
    MUTE_DURATION_MINUTES = 30
    
    def __init__(self, storage: GameStorageEngine, relationship_manager: RelationshipManager, owner_ids: Optional[Set[int]] = None):
        self.storage = storage
        self.relationship_manager = relationship_manager
        # Owner bypass for testing - unlimited cookies!
        self.owner_ids: Set[int] = owner_ids or self._load_owner_ids()
    
    def _load_owner_ids(self) -> Set[int]:
        """Load owner IDs from environment variable."""
        owner_ids_str = os.getenv("OWNER_IDS", "")
        if not owner_ids_str:
            return set()
        try:
            return {int(id.strip()) for id in owner_ids_str.split(",") if id.strip()}
        except ValueError:
            return set()
    
    def _is_owner(self, user_id: str) -> bool:
        """Check if user is an owner (has unlimited cookies for testing)."""
        try:
            return int(user_id) in self.owner_ids
        except ValueError:
            return False
    
    def try_award_cookies(self, user_id: str, interaction_type: str, 
                         bot_mood: str = 'neutral') -> Optional[int]:
        """
        Attempt to award cookies based on drop rates and luck.
        Returns number of cookies awarded, or None if no drop.
        """
        # Get base drop rate
        base_rate = self.DROP_RATES.get(interaction_type, 0.10)
        
        # Apply relationship bonus to drop rate
        relationship_bonus = self.relationship_manager.get_cookie_drop_bonus(user_id)
        final_rate = min(1.0, base_rate + relationship_bonus)
        
        # Roll for cookie drop
        if random.random() > final_rate:
            return None
        
        # Calculate cookie amount based on mood and luck
        luck_modifier = self.relationship_manager.get_luck_modifier(user_id)
        min_cookies, max_cookies = self.MOOD_MULTIPLIERS.get(bot_mood, (1, 2))
        
        # Apply luck modifier
        base_amount = random.randint(min_cookies, max_cookies)
        luck_bonus = int(base_amount * (luck_modifier - 1.0))  # Extra cookies from luck
        
        total_cookies = max(0, base_amount + luck_bonus)
        
        # Award cookies
        if total_cookies > 0:
            self.storage.add_cookies(user_id, total_cookies)
            return total_cookies
        
        return None
    
    def spend_stamina(self, user_id: str, action: str) -> tuple[bool, int]:
        """
        Spend stamina (cookies) for an action.
        Returns (success, cost).
        
        Owners have unlimited cookies for testing!
        """
        cost = self.STAMINA_COSTS.get(action, 1)
        
        # Owner bypass - always succeed without actually spending
        if self._is_owner(user_id):
            return (True, cost)
        
        success = self.storage.spend_cookies(user_id, cost)
        return (success, cost)
    
    def can_afford(self, user_id: str, action: str) -> bool:
        """
        Check if user can afford an action.
        
        Owners always have unlimited cookies for testing!
        """
        # Owner bypass - always can afford
        if self._is_owner(user_id):
            return True
        
        cost = self.STAMINA_COSTS.get(action, 1)
        _, current = self.storage.get_user_cookies(user_id)
        return current >= cost
    
    def get_cookie_balance(self, user_id: str) -> Dict[str, int]:
        """Get user's cookie statistics."""
        total, current = self.storage.get_user_cookies(user_id)
        return {
            'total_earned': total,
            'current_balance': current,
            'spent': total - current
        }
    
    def check_game_unlock_eligibility(self, user_id: str) -> bool:
        """Check if user has enough cookies to unlock the game (5 cookies)."""
        _, current = self.storage.get_user_cookies(user_id)
        return current >= 5
    
    def unlock_game_with_cookies(self, user_id: str) -> bool:
        """
        Unlock game by feeding 5 cookies to the hippo.
        Returns True if successful, False if not enough cookies.
        """
        if not self.check_game_unlock_eligibility(user_id):
            return False
        
        # Spend 5 cookies
        if self.storage.spend_cookies(user_id, 5):
            self.storage.unlock_game(user_id)
            return True
        
        return False
    
    def calculate_training_xp(self, user_id: str, cookies_spent: int) -> int:
        """
        Calculate XP gained from training with cookies.
        XP is based on cookies spent, modified by luck.
        """
        luck_modifier = self.relationship_manager.get_luck_modifier(user_id)
        
        # Base: 10-20 XP per cookie
        base_xp_per_cookie = random.randint(10, 20)
        total_base_xp = base_xp_per_cookie * cookies_spent
        
        # Apply luck modifier
        final_xp = int(total_base_xp * luck_modifier)
        
        return final_xp
    
    def get_stamina_costs_display(self) -> str:
        """Get formatted string of all stamina costs for display."""
        lines = ["**Cookie Costs (Stamina):**"]
        for action, cost in sorted(self.STAMINA_COSTS.items()):
            lines.append(f"• `/{action}`: {cost} 🍪")
        return "\n".join(lines)

    # Admin/helper gift utilities
    def get_admin_gift_remaining(self, user_id: str) -> int:
        """Return remaining gift cookies the admin/helper can distribute today."""
        return self.storage.get_admin_gift_remaining(user_id, self.ADMIN_DAILY_GIFT_POOL)

    def give_admin_gift(self, giver_id: str, recipient_id: str, amount: int) -> int:
        """
        Distribute gift cookies from an admin/helper allowance.
        Returns number of cookies actually gifted (0 if allowance exceeded).
        """
        if amount <= 0:
            return 0

        if not self.storage.consume_admin_gift_allowance(giver_id, amount, self.ADMIN_DAILY_GIFT_POOL):
            return 0

        self.storage.add_gift_cookies(recipient_id, amount)
        return amount

    # Easter Egg Daily Limit System
    def check_easter_egg_limit(self, user_id: str) -> tuple[bool, int]:
        """
        Check if user has reached daily easter egg cookie limit.
        Returns (can_earn, cookies_earned_today).
        """
        stats = self.storage.get_daily_easter_egg_stats(user_id)
        cookies_earned = stats['cookies_earned']
        can_earn = cookies_earned < self.MAX_DAILY_EASTER_EGG_COOKIES
        return (can_earn, cookies_earned)
    
    def try_award_easter_egg_cookies(self, user_id: str, bot_mood: str = 'neutral') -> Optional[int]:
        """
        Try to award cookies for easter egg interaction.
        Returns cookies awarded or None if limit reached or no drop.
        """
        # Check daily limit first
        can_earn, cookies_today = self.check_easter_egg_limit(user_id)
        
        if not can_earn:
            # Record spam attempt
            self.storage.record_easter_egg_attempt(user_id, 0, is_spam=True)
            return None
        
        # Normal cookie drop logic
        cookies = self.try_award_cookies(user_id, 'easter_egg', bot_mood)
        
        if cookies and cookies > 0:
            # Ensure we don't exceed daily limit
            remaining = self.MAX_DAILY_EASTER_EGG_COOKIES - cookies_today
            cookies = min(cookies, remaining)
            
            # Record legitimate attempt
            self.storage.record_easter_egg_attempt(user_id, cookies, is_spam=False)
            return cookies
        
        # No cookies dropped, but still a legitimate attempt
        self.storage.record_easter_egg_attempt(user_id, 0, is_spam=False)
        return None
    
    def handle_easter_egg_spam(self, user_id: str) -> dict:
        """
        Handle spam detection for easter eggs.
        Returns dict with: {
            'is_spam': bool,
            'aggravation_level': int,
            'cookie_penalty': int,
            'mute_chance': float,
            'should_mute': bool
        }
        """
        stats = self.storage.get_daily_easter_egg_stats(user_id)
        
        # Check if this is spam (limit reached)
        if stats['cookies_earned'] < self.MAX_DAILY_EASTER_EGG_COOKIES:
            return {
                'is_spam': False,
                'aggravation_level': 0,
                'cookie_penalty': 0,
                'mute_chance': 0.0,
                'should_mute': False
            }
        
        # This is spam - increase aggravation
        aggravation_level = self.storage.increase_aggravation(user_id, 1)
        
        # Calculate mute chance based on aggravation
        mute_chance = min(1.0, self.BASE_MUTE_CHANCE + (self.MUTE_CHANCE_INCREMENT * (aggravation_level - 1)))
        
        # Roll for mute
        should_mute = random.random() < mute_chance
        
        # Apply cookie penalty (1% chance to take cookie on first spam, increases with aggravation)
        cookie_penalty = 0
        penalty_chance = self.BASE_MUTE_CHANCE + (self.MUTE_CHANCE_INCREMENT * (aggravation_level - 1))
        if random.random() < penalty_chance:
            if self.storage.spend_cookies(user_id, self.SPAM_PENALTY_COOKIE_AMOUNT):
                cookie_penalty = self.SPAM_PENALTY_COOKIE_AMOUNT
        
        return {
            'is_spam': True,
            'aggravation_level': aggravation_level,
            'cookie_penalty': cookie_penalty,
            'mute_chance': mute_chance * 100,  # Convert to percentage
            'should_mute': should_mute
        }
    
    def get_easter_egg_stats(self, user_id: str) -> dict:
        """Get formatted easter egg stats for user."""
        stats = self.storage.get_daily_easter_egg_stats(user_id)
        aggravation = self.storage.get_aggravation_level(user_id)
        
        return {
            'cookies_today': stats['cookies_earned'],
            'max_cookies': self.MAX_DAILY_EASTER_EGG_COOKIES,
            'remaining': self.MAX_DAILY_EASTER_EGG_COOKIES - stats['cookies_earned'],
            'attempts': stats['attempts'],
            'spam_count': stats['spam_count'],
            'aggravation_level': aggravation
        }
