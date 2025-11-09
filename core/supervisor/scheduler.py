from datetime import datetime, timedelta
import asyncio

class DailyScheduler:
    def __init__(self, task):
        self.task = task   # async function to run daily

    async def start(self):
        while True:
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            delay = (tomorrow - now).total_seconds()
            await asyncio.sleep(delay)
            await self.task()

scheduler = DailyScheduler
