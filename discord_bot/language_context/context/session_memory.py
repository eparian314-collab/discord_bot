"""
Session-level memory utilities for short-lived conversational context.

This module keeps lightweight recent history per (guild, channel, user) tuple,
which helps translation heuristics reason about prior utterances without
requiring a full persistence layer.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, Optional, Tuple


HistoryKey = Tuple[int, Optional[int], Optional[int]]


@dataclass
class SessionEvent:
    """Represents a single conversational event captured in memory."""

    text: str
    author_id: Optional[int]
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionMemory:
    """
    Manage small, in-memory conversation histories.

    - Events are grouped by (guild_id, channel_id, user_id) tuples.
    - Each history is capped in length and optionally TTL-pruned.
    """

    def __init__(
        self,
        *,
        max_events_per_session: int = 10,
        ttl_seconds: Optional[float] = 900.0,
    ) -> None:
        self.max_events = max(1, int(max_events_per_session))
        self.ttl = ttl_seconds
        self._store: Dict[HistoryKey, Deque[SessionEvent]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def add_event(
        self,
        guild_id: int,
        *,
        channel_id: Optional[int],
        user_id: Optional[int],
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an event to the session history."""
        key = (guild_id, channel_id, user_id)
        event = SessionEvent(text=text, author_id=user_id, metadata=metadata or {})
        async with self._lock:
            history = self._store[key]
            history.append(event)
            while len(history) > self.max_events:
                history.popleft()
            if self.ttl is not None:
                self._prune_history(history)

    async def get_history(
        self,
        guild_id: int,
        *,
        channel_id: Optional[int],
        user_id: Optional[int],
        limit: Optional[int] = None,
    ) -> Iterable[SessionEvent]:
        """
        Return most recent events for a session.
        Limit defaults to full session length.
        """
        key = (guild_id, channel_id, user_id)
        async with self._lock:
            history = self._store.get(key)
            if not history:
                return tuple()
            if self.ttl is not None:
                self._prune_history(history)
                if not history:
                    self._store.pop(key, None)
                    return tuple()
            if limit is None or limit >= len(history):
                return tuple(history)
            return tuple(list(history)[-limit:])

    async def clear_session(
        self,
        guild_id: int,
        *,
        channel_id: Optional[int],
        user_id: Optional[int],
    ) -> None:
        """Remove all events for the session key."""
        key = (guild_id, channel_id, user_id)
        async with self._lock:
            self._store.pop(key, None)

    async def prune_all(self) -> int:
        """Remove expired events across all sessions. Returns number deleted."""
        if self.ttl is None:
            return 0
        now = time.time()
        removed = 0
        async with self._lock:
            for key in list(self._store.keys()):
                history = self._store[key]
                original_len = len(history)
                self._prune_history(history, now=now)
                removed += original_len - len(history)
                if not history:
                    self._store.pop(key, None)
        return removed

    def _prune_history(self, history: Deque[SessionEvent], *, now: Optional[float] = None) -> None:
        """Internal helper to remove expired events in-place."""
        if self.ttl is None:
            return
        cutoff = (now or time.time()) - self.ttl
        while history and history[0].timestamp < cutoff:
            history.popleft()


