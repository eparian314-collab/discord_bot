from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from discord_bot.cogs.event_management_cog import EventManagementCog, EventCategory
from discord_bot.core.engines.event_reminder_engine import EventReminder, RecurrenceType


class SequenceEngine:
    def __init__(self, value: int):
        self.value = value

    def allocate_display_index(self, guild_id: int, category: EventCategory) -> int:
        return self.value

    async def get_events_for_guild(self, guild_id: int):
        return []


class FallbackEngine:
    def __init__(self, events):
        self._events = events

    async def get_events_for_guild(self, guild_id: int):
        return list(self._events)


def make_bot(engine):
    return SimpleNamespace(
        event_reminder_engine=engine,
        error_engine=None,
        personality_engine=None,
    )


@pytest.mark.asyncio
async def test_allocate_display_id_prefers_sequence():
    engine = SequenceEngine(3)
    cog = EventManagementCog(make_bot(engine), event_engine=engine)

    display = await cog._allocate_display_id(123, EventCategory.RAID)

    assert display == "2C"


@pytest.mark.asyncio
async def test_allocate_display_id_falls_back_to_scan():
    now = datetime.now(timezone.utc) + timedelta(hours=1)
    events = [
        EventReminder(
            event_id="123:2A",
            guild_id=123,
            title="Raid Alpha",
            description="",
            category=EventCategory.RAID,
            event_time_utc=now,
            recurrence=RecurrenceType.ONCE,
            reminder_times=[60],
        ),
        EventReminder(
            event_id="123:2B",
            guild_id=123,
            title="Raid Beta",
            description="",
            category=EventCategory.RAID,
            event_time_utc=now + timedelta(hours=2),
            recurrence=RecurrenceType.ONCE,
            reminder_times=[60],
        ),
    ]
    engine = FallbackEngine(events)
    cog = EventManagementCog(make_bot(engine), event_engine=engine)

    display = await cog._allocate_display_id(123, EventCategory.RAID)

    assert display == "2C"
