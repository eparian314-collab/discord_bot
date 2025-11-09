import asyncio
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, topic: str, handler: Callable[[Any], None]):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: Any):
        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
