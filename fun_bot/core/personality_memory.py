from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .game_storage_engine import GameStorageEngine


PERSONALITY_NAMESPACE = "personality"
RECENT_INTERACTIONS_KEY = "recent_interactions"
MAX_RECENT_INTERACTIONS = 5


@dataclass(slots=True)
class PersonalityEvent:
    """Lightweight record of a notable player interaction.

    These events are used to give FunBot a sense of short-term memory
    for personality and flavour text. They are intentionally small and
    generic so they can be reused across features.
    """

    timestamp: str
    summary: str
    tags: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalityEvent":
        return cls(
            timestamp=str(data.get("timestamp", "")),
            summary=str(data.get("summary", "")),
            tags=list(data.get("tags", []) or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PersonalityMemory:
    """Persist a small rolling window of recent interactions per user."""

    def __init__(self, storage: GameStorageEngine) -> None:
        self._storage = storage

    async def add_event(
        self,
        user_id: int,
        summary: str,
        *,
        tags: Optional[Sequence[str]] = None,
    ) -> PersonalityEvent:
        """Append a new event for the given user, keeping the last few only."""

        await self._storage.initialize()
        raw = await self._storage.get_user_value(
            user_id=user_id,
            namespace=PERSONALITY_NAMESPACE,
            key=RECENT_INTERACTIONS_KEY,
            default=[],
        )
        events: List[PersonalityEvent] = []
        try:
            events = [PersonalityEvent.from_dict(item) for item in raw or []]
        except Exception:
            events = []

        event = PersonalityEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            tags=list(tags or []),
        )
        events.append(event)
        # Keep only the most recent N events.
        if len(events) > MAX_RECENT_INTERACTIONS:
            events = events[-MAX_RECENT_INTERACTIONS:]

        await self._storage.set_user_value(
            user_id=user_id,
            namespace=PERSONALITY_NAMESPACE,
            key=RECENT_INTERACTIONS_KEY,
            value=[e.to_dict() for e in events],
        )
        return event

    async def get_recent_events(self, user_id: int) -> List[PersonalityEvent]:
        """Return the last N events for a user (most recent last)."""

        raw = await self._storage.get_user_value(
            user_id=user_id,
            namespace=PERSONALITY_NAMESPACE,
            key=RECENT_INTERACTIONS_KEY,
            default=[],
        )
        try:
            return [PersonalityEvent.from_dict(item) for item in raw or []]
        except Exception:
            return []

    async def get_last_event_with_tags(
        self,
        user_id: int,
        required_tags: Sequence[str],
    ) -> Optional[PersonalityEvent]:
        """Return the most recent event that includes all of ``required_tags``."""

        events = await self.get_recent_events(user_id)
        if not required_tags:
            return events[-1] if events else None

        required = set(required_tags)
        for event in reversed(events):
            if required.issubset(event.tags):
                return event
        return None


__all__ = ["PersonalityMemory", "PersonalityEvent"]
