"""
Simple asynchronous publish/subscribe event bus used to decouple engines.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable, DefaultDict, Dict, Iterable, List, Optional

Handler = Callable[..., Awaitable[None]]


class EventBus:
    """Lightweight async event bus with coroutine handlers."""

    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event: str, handler: Handler) -> None:
        async with self._lock:
            self._handlers[event].append(handler)

    async def unsubscribe(self, event: str, handler: Handler) -> None:
        async with self._lock:
            if handler in self._handlers.get(event, []):
                self._handlers[event].remove(handler)

    async def emit(self, event: str, **payload: Any) -> None:
        handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                await handler(**payload)
            except Exception as exc:
                if event != "event_bus.error":
                    await self.emit("event_bus.error", event=event, handler=handler, exc=exc)

    async def publish(self, event: str, **payload: Any) -> None:
        """Compatibility helper: mirror emit() signature for registry expectations."""
        await self.emit(event, **payload)
