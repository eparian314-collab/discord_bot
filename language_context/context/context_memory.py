"""
Lightweight in-memory storage used by the language context stack.

The goal is to provide a small, asyncio-friendly cache for contextual metadata
such as per-user preferences, conversation hints, or last translation results.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional


@dataclass
class MemoryRecord:
    """Represents a single cached value with optional expiration metadata."""

    value: Any
    created_at: float = field(default_factory=lambda: time.time())
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, *, now: Optional[float] = None) -> bool:
        """Return True when the record is past its expiration time."""
        if self.expires_at is None:
            return False
        return (now or time.time()) >= self.expires_at


class ContextMemory:
    async def record_interaction(
        self,
        user_id: str,
        interaction_type: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Record a user interaction (message, thread, game, etc.) in memory.

        Args:
            user_id: Discord user ID (str)
            interaction_type: Type of interaction (e.g., 'message', 'thread', 'game', 'command')
            context: Optional dict with extra details (e.g., channel, thread_id, game_name)
            timestamp: Optional float (epoch seconds); defaults to now

        Stores a set of interaction types and a list of detailed events in metadata.
        """
        ns = f"user:{user_id}"
        key = "interactions"
        record = await self.get_record(ns, key)
        interactions = set(record.value) if record else set()
        interactions.add(interaction_type)

        # Build event metadata
        event = {
            "type": interaction_type,
            "timestamp": timestamp or time.time(),
            "context": context or {},
        }
        metadata = record.metadata if record else {"events": []}
        metadata.setdefault("events", []).append(event)

        await self.set(ns, key, list(interactions), metadata=metadata)

    async def has_interacted(
        self,
        user_id: str,
        interaction_type: Optional[str] = None,
    ) -> bool:
        """
        Check if a user has interacted before (optionally by type).

        Args:
            user_id: Discord user ID (str)
            interaction_type: Optional type to check (e.g., 'game')

        Returns True if any interaction exists, or if the specific type is present.
        """
        ns = f"user:{user_id}"
        key = "interactions"
        interactions = await self.get(ns, key, default=[])
        if interaction_type:
            return interaction_type in interactions
        return bool(interactions)

    async def get_interaction_history(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list:
        """
        Get detailed interaction history for a user (most recent first).

        Args:
            user_id: Discord user ID (str)
            limit: Max number of events to return

        Returns a list of event dicts: {type, timestamp, context}
        """
        ns = f"user:{user_id}"
        key = "interactions"
        record = await self.get_record(ns, key)
        if not record or "events" not in record.metadata:
            return []
        return list(reversed(record.metadata["events"][-limit:]))
    """
    Simple namespace-aware memory with TTL support.

    Usage:
        memory = ContextMemory(default_ttl=600)
        await memory.set("guild:123", "preferred_lang:456", "es")
        lang = await memory.get("guild:123", "preferred_lang:456")
    """

    def __init__(
        self,
        *,
        default_ttl: Optional[float] = 900.0,
        max_records_per_namespace: int = 1024,
    ) -> None:
        self.default_ttl = default_ttl
        self.max_records = max(1, int(max_records_per_namespace))
        self._store: Dict[str, Dict[str, MemoryRecord]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a value with optional TTL and metadata."""
        expires_at = None
        effective_ttl = ttl if ttl is not None else self.default_ttl
        if effective_ttl:
            expires_at = time.time() + float(effective_ttl)

        async with self._lock:
            bucket = self._store[namespace]
            bucket[key] = MemoryRecord(value=value, expires_at=expires_at, metadata=metadata or {})
            if len(bucket) > self.max_records:
                self._evict_oldest(bucket)

    async def get(self, namespace: str, key: str, *, default: Any = None) -> Any:
        """Return the stored value or default if missing/expired."""
        async with self._lock:
            bucket = self._store.get(namespace)
            if not bucket:
                return default
            record = bucket.get(key)
            if not record:
                return default
            if record.is_expired():
                bucket.pop(key, None)
                return default
            return record.value

    async def get_record(self, namespace: str, key: str) -> Optional[MemoryRecord]:
        """Return the full record, removing it if expired."""
        async with self._lock:
            bucket = self._store.get(namespace)
            if not bucket:
                return None
            record = bucket.get(key)
            if not record or record.is_expired():
                bucket.pop(key, None)
                return None
            return record

    async def delete(self, namespace: str, key: str) -> None:
        """Remove a value if present."""
        async with self._lock:
            bucket = self._store.get(namespace)
            if bucket:
                bucket.pop(key, None)

    async def clear_namespace(self, namespace: str) -> None:
        """Remove all records for a namespace."""
        async with self._lock:
            self._store.pop(namespace, None)

    async def purge_expired(self, namespaces: Optional[Iterable[str]] = None) -> int:
        """
        Remove expired entries. Returns number of records purged.
        When namespaces is None, all namespaces are inspected.
        """
        now = time.time()
        purged = 0
        async with self._lock:
            targets = namespaces or list(self._store.keys())
            for ns in targets:
                bucket = self._store.get(ns)
                if not bucket:
                    continue
                expired_keys = [k for k, rec in bucket.items() if rec.is_expired(now=now)]
                for k in expired_keys:
                    bucket.pop(k, None)
                    purged += 1
                if not bucket:
                    self._store.pop(ns, None)
        return purged

    async def snapshot(self) -> Dict[str, Dict[str, MemoryRecord]]:
        """Return a shallow snapshot of non-expired records (for diagnostics)."""
        await self.purge_expired()
        async with self._lock:
            return {
                namespace: dict(records)
                for namespace, records in self._store.items()
            }

    def _evict_oldest(self, bucket: Dict[str, MemoryRecord]) -> None:
        """Remove the oldest record from a namespace."""
        oldest_key = None
        oldest_time = float("inf")
        for key, record in bucket.items():
            if record.created_at < oldest_time:
                oldest_time = record.created_at
                oldest_key = key
        if oldest_key is not None:
            bucket.pop(oldest_key, None)
