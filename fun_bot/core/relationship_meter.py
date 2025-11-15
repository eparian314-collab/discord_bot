from __future__ import annotations

from typing import Optional
from fun_bot.core.game_storage_engine import GameStorageEngine

RELATIONSHIP_NAMESPACE = "relationship"
RELATIONSHIP_KEY = "meter"

class RelationshipMeter:
    def __init__(self, storage: GameStorageEngine):
        self._storage = storage

    async def get_meter(self, user_id: int) -> int:
        import time
        raw = await self._storage.get_user_value(
            user_id=user_id,
            namespace=RELATIONSHIP_NAMESPACE,
            key=RELATIONSHIP_KEY,
            default={"value": 0, "last_update": time.time()},
        )
        try:
            value = int(raw.get("value", 0))
        except Exception:
            value = 0
        # Forgiveness logic: meter trends toward 0 over time (1/hr)
        last_update = raw.get("last_update", time.time())
        now = time.time()
        hours_passed = (now - last_update) / 3600
        if abs(value) > 0 and hours_passed >= 1:
            # Move toward zero by 1 per hour
            forgiven = int(hours_passed)
            if value > 0:
                value = max(0, value - forgiven)
            else:
                value = min(0, value + forgiven)
            await self.set_meter(user_id, value)
        return value

    async def set_meter(self, user_id: int, value: int) -> int:
        import time
        value = max(min(int(value), 10), -10)  # Clamp between -10 and 10
        payload = {"value": value, "last_update": time.time()}
        await self._storage.set_user_value(
            user_id=user_id,
            namespace=RELATIONSHIP_NAMESPACE,
            key=RELATIONSHIP_KEY,
            value=payload,
        )
        return value

    async def adjust_meter(self, user_id: int, delta: int) -> int:
        current = await self.get_meter(user_id)
        new_value = max(min(current + int(delta), 10), -10)
        return await self.set_meter(user_id, new_value)

__all__ = ["RelationshipMeter"]
