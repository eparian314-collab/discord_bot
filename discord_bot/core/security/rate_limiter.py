"""
Rate limiting system for Discord bot security.

Provides comprehensive rate limiting to prevent:
- Spam attacks
- DoS attacks  
- Resource exhaustion
- API abuse
- Command flooding
"""
from __future__ import annotations

import time
import asyncio
from typing import Dict, Optional, Tuple, Union, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: float = 0):
        self.retry_after = retry_after
        super().__init__(message)


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests: int  # Number of requests allowed
    period: float  # Time period in seconds
    burst: Optional[int] = None  # Burst allowance
    
    def __post_init__(self):
        if self.burst is None:
            self.burst = self.requests


@dataclass
class RateLimitState:
    """Tracks rate limit state for a specific key."""
    requests: deque = field(default_factory=deque)
    burst_tokens: int = 0
    last_refill: float = field(default_factory=time.time)
    blocked_until: float = 0
    
    def __post_init__(self):
        # Initialize with current time
        self.requests = deque()


class RateLimiter:
    """
    Advanced rate limiter with multiple strategies.
    
    Supports:
    - Token bucket algorithm
    - Sliding window
    - Per-user, per-guild, and global limits
    - Automatic cleanup of old entries
    - Thread-safe operations
    """
    
    def __init__(self):
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._states: Dict[str, RateLimitState] = {}
        self._limits: Dict[str, RateLimit] = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
        
        # Default rate limits
        self.setup_default_limits()
    
    def setup_default_limits(self):
        """Setup default rate limits for common operations."""
        # Global limits
        self.set_limit("global:commands", RateLimit(100, 60))  # 100 commands per minute globally
        self.set_limit("global:messages", RateLimit(1000, 60))  # 1000 messages per minute globally
        
        # Per-user limits
        self.set_limit("user:commands", RateLimit(30, 60))  # 30 commands per minute per user
        self.set_limit("user:messages", RateLimit(50, 60))  # 50 messages per minute per user
        self.set_limit("user:pokemon_catch", RateLimit(10, 60))  # 10 catches per minute
        self.set_limit("user:translation", RateLimit(20, 60))  # 20 translations per minute
        
        # Per-guild limits
        self.set_limit("guild:commands", RateLimit(200, 60))  # 200 commands per minute per guild
        self.set_limit("guild:messages", RateLimit(500, 60))  # 500 messages per minute per guild
        
        # Burst limits for special operations
        self.set_limit("user:admin", RateLimit(5, 60, burst=10))  # Admin commands
        self.set_limit("user:battle", RateLimit(3, 300))  # Battle creation (longer period)
        self.set_limit("user:role_change", RateLimit(5, 300))  # Role changes
    
    def set_limit(self, limit_type: str, rate_limit: RateLimit):
        """Set a rate limit for a specific type."""
        self._limits[limit_type] = rate_limit
    
    def _get_key(self, limit_type: str, identifier: Union[str, int]) -> str:
        """Generate cache key for rate limit tracking."""
        return f"{limit_type}:{identifier}"
    
    def _cleanup_old_entries(self):
        """Clean up old rate limit entries to prevent memory leaks."""
        current_time = time.time()
        
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        keys_to_remove = []
        for key, state in self._states.items():
            # Remove entries that haven't been accessed in 1 hour
            if current_time - state.last_refill > 3600:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._states[key]
            if key in self._locks:
                del self._locks[key]
        
        self._last_cleanup = current_time
    
    def _refill_tokens(self, state: RateLimitState, rate_limit: RateLimit, current_time: float):
        """Refill tokens for token bucket algorithm."""
        time_passed = current_time - state.last_refill
        tokens_to_add = int(time_passed * rate_limit.requests / rate_limit.period)
        
        if tokens_to_add > 0:
            state.burst_tokens = min(rate_limit.burst, state.burst_tokens + tokens_to_add)
            state.last_refill = current_time
    
    def _clean_old_requests(self, state: RateLimitState, rate_limit: RateLimit, current_time: float):
        """Remove old requests outside the time window."""
        cutoff_time = current_time - rate_limit.period
        while state.requests and state.requests[0] < cutoff_time:
            state.requests.popleft()
    
    async def check_rate_limit(
        self, 
        limit_type: str, 
        identifier: Union[str, int],
        cost: int = 1
    ) -> bool:
        """
        Check if an operation is within rate limits.
        
        Args:
            limit_type: Type of rate limit to check
            identifier: Unique identifier (user ID, guild ID, etc.)
            cost: Cost of the operation (default 1)
            
        Returns:
            True if within limits, False otherwise
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if limit_type not in self._limits:
            return True  # No limit configured
        
        rate_limit = self._limits[limit_type]
        key = self._get_key(limit_type, identifier)
        current_time = time.time()
        
        # Cleanup old entries periodically
        self._cleanup_old_entries()
        
        # Thread-safe access to state
        with self._locks[key]:
            if key not in self._states:
                self._states[key] = RateLimitState()
                self._states[key].burst_tokens = rate_limit.burst
            
            state = self._states[key]
            
            # Check if still blocked
            if current_time < state.blocked_until:
                retry_after = state.blocked_until - current_time
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {limit_type}. Retry after {retry_after:.1f} seconds.",
                    retry_after=retry_after
                )
            
            # Refill tokens (token bucket)
            self._refill_tokens(state, rate_limit, current_time)
            
            # Clean old requests (sliding window)
            self._clean_old_requests(state, rate_limit, current_time)
            
            # Check token bucket limit
            if state.burst_tokens >= cost:
                state.burst_tokens -= cost
                state.requests.append(current_time)
                return True
            
            # Check sliding window limit
            if len(state.requests) + cost <= rate_limit.requests:
                state.requests.append(current_time)
                return True
            
            # Rate limit exceeded - block for a period
            state.blocked_until = current_time + min(rate_limit.period / 4, 60)  # Block for at most 1 minute
            retry_after = state.blocked_until - current_time
            
            raise RateLimitExceeded(
                f"Rate limit exceeded for {limit_type}. Retry after {retry_after:.1f} seconds.",
                retry_after=retry_after
            )
    
    async def check_user_command_limit(self, user_id: int, command_name: str = "generic") -> bool:
        """Check rate limit for user commands."""
        # Check general user command limit
        await self.check_rate_limit("user:commands", user_id)
        
        # Check specific command limits if they exist
        specific_limit = f"user:{command_name}"
        if specific_limit in self._limits:
            await self.check_rate_limit(specific_limit, user_id)
        
        return True
    
    async def check_guild_limit(self, guild_id: int, limit_type: str = "commands") -> bool:
        """Check rate limit for guild operations."""
        return await self.check_rate_limit(f"guild:{limit_type}", guild_id)
    
    async def check_global_limit(self, limit_type: str = "commands") -> bool:
        """Check global rate limits."""
        return await self.check_rate_limit(f"global:{limit_type}", "global")
    
    def get_remaining_requests(self, limit_type: str, identifier: Union[str, int]) -> Optional[int]:
        """Get number of remaining requests for a rate limit."""
        if limit_type not in self._limits:
            return None
        
        rate_limit = self._limits[limit_type]
        key = self._get_key(limit_type, identifier)
        current_time = time.time()
        
        with self._locks[key]:
            if key not in self._states:
                return rate_limit.requests
            
            state = self._states[key]
            
            # Refill tokens
            self._refill_tokens(state, rate_limit, current_time)
            
            # Clean old requests
            self._clean_old_requests(state, rate_limit, current_time)
            
            # Return minimum of token bucket and sliding window
            token_remaining = state.burst_tokens
            window_remaining = rate_limit.requests - len(state.requests)
            
            return min(token_remaining, window_remaining)
    
    def reset_limits(self, identifier: Union[str, int], limit_types: Optional[Set[str]] = None):
        """Reset rate limits for a specific identifier."""
        keys_to_reset = []
        
        for key in self._states.keys():
            if f":{identifier}" in key:
                if limit_types is None or any(key.startswith(f"{lt}:") for lt in limit_types):
                    keys_to_reset.append(key)
        
        for key in keys_to_reset:
            with self._locks[key]:
                if key in self._states:
                    del self._states[key]
    
    def is_rate_limited(self, limit_type: str, identifier: Union[str, int]) -> Tuple[bool, float]:
        """
        Check if an identifier is currently rate limited.
        
        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        if limit_type not in self._limits:
            return False, 0
        
        key = self._get_key(limit_type, identifier)
        current_time = time.time()
        
        with self._locks[key]:
            if key not in self._states:
                return False, 0
            
            state = self._states[key]
            
            if current_time < state.blocked_until:
                return True, state.blocked_until - current_time
            
            return False, 0


# Global rate limiter instance
rate_limiter = RateLimiter()