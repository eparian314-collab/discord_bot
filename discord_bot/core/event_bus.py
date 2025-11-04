"""
Simple asynchronous publish/subscribe event bus used to decouple engines.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import inspect
from typing import Any, Callable, DefaultDict, Dict, Iterable, List, Optional

Handler = Callable[..., Any]


class EventBus:
    """Lightweight async event bus with coroutine handlers."""

    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        handlers = self._handlers.get(event)
        if handlers and handler in handlers:
            handlers.remove(handler)

    async def emit(self, event: str, **payload: Any) -> None:
        handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                result = handler(**payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                if event != "event_bus.error":
                    await self.emit("event_bus.error", original_event=event, handler=handler, exc=exc)

    async def publish(self, event: str, **payload: Any) -> None:
        """Compatibility helper: mirror emit() signature for registry expectations."""
        await self.emit(event, **payload)


