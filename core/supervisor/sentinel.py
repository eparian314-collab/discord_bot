import asyncio
from .scorecard import Scorecard
from .event_bus import EventBus

class GuardianSentinel:
    def __init__(self):
        self.safe_mode = False
        self.scorecard = Scorecard()
        self.event_bus = EventBus()
        self.last_trigger_reason = None

    async def monitor(self):
        while True:
            score = self.scorecard.score()
            if score < 0.4 and not self.safe_mode:
                self.safe_mode = True
                self.last_trigger_reason = f"Score dropped to {score:.2f}"
                print("⚠️ Stability threshold breached - defensive posture activated.")
                await self.event_bus.publish("system_safe_mode_enabled", self.last_trigger_reason)
            elif score > 0.8 and self.safe_mode:
                self.safe_mode = False
                self.last_trigger_reason = f"Score rose to {score:.2f}"
                print("✅ System stability restored - returning to standard operation.")
                await self.event_bus.publish("system_safe_mode_disabled", self.last_trigger_reason)
            await asyncio.sleep(5)

    def wrap(self, coro):
        async def wrapped(*args, **kwargs):
            try:
                return await coro(*args, **kwargs)
            except Exception as e:
                self.scorecard.record_error()
                raise
        return wrapped
