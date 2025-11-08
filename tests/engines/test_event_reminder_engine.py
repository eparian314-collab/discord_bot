from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import discord

from discord_bot.core.engines.event_reminder_engine import (
    EventReminderEngine,
    EventReminder,
    EventCategory,
    RecurrenceType,
)


class DummyChannel:
    def __init__(self, channel_id: int, name: str = "bot-updates", allow_send: bool = True, raise_forbidden: bool = False):
        self.id = channel_id
        self.name = name
        self.allow_send = allow_send
        self.raise_forbidden = raise_forbidden
        self.sent = []

    def permissions_for(self, _):
        return SimpleNamespace(send_messages=self.allow_send)

    async def send(self, **payload):
        if self.raise_forbidden:
            response = SimpleNamespace(status=403, reason="forbidden")
            raise discord.Forbidden(response=response, message="no perms")
        self.sent.append(payload)


class DummyGuild:
    def __init__(self, guild_id: int, channel: DummyChannel):
        self.id = guild_id
        self.name = "Guild"
        self._channel = channel
        self.text_channels = [channel]
        self.system_channel = None
        self.default_role = SimpleNamespace()
        self.me = SimpleNamespace()

    def get_channel(self, channel_id: int):
        if channel_id == self._channel.id:
            return self._channel
        return None


class DummyBot:
    def __init__(self, guild: DummyGuild, user=None):
        self._guild = guild
        self._user = user

    def get_guild(self, guild_id: int):
        if guild_id == self._guild.id:
            return self._guild
        return None

    def get_user(self, user_id: int):
        return self._user

    async def fetch_user(self, user_id: int):
        return self._user


def build_event(guild_id: int, *, channel_id: int | None = None, created_by: int = 1) -> EventReminder:
    return EventReminder(
        event_id=f"{guild_id}:2A",
        guild_id=guild_id,
        title="KVK Warmup",
        description="",
        category=EventCategory.RAID,
        event_time_utc=datetime.now(timezone.utc) + timedelta(hours=1),
        recurrence=RecurrenceType.ONCE,
        reminder_times=[60],
        channel_id=channel_id,
        created_by=created_by,
    )


@pytest.mark.asyncio
async def test_send_reminder_uses_find_bot_channel(monkeypatch):
    storage = SimpleNamespace()
    engine = EventReminderEngine(storage)
    fallback_channel = DummyChannel(999)
    guild = DummyGuild(321, fallback_channel)
    engine.bot = DummyBot(guild)

    monkeypatch.setattr(
        "core.engines.event_reminder_engine.find_bot_channel",
        lambda _: fallback_channel,
    )

    event = build_event(guild.id, channel_id=None)
    reminder_time = event.event_time_utc - timedelta(minutes=60)

    await engine._send_reminder(event, event.event_time_utc, reminder_time)

    assert fallback_channel.sent, "Reminder should be dispatched via fallback channel"


@pytest.mark.asyncio
async def test_send_reminder_dm_when_forbidden(monkeypatch):
    storage = SimpleNamespace()
    engine = EventReminderEngine(storage)
    channel = DummyChannel(123, raise_forbidden=True)
    guild = DummyGuild(999, channel)

    class DummyUser:
        def __init__(self):
            self.messages = []

        async def send(self, content):
            self.messages.append(content)

    user = DummyUser()
    engine.bot = DummyBot(guild, user)
    event = build_event(guild.id, channel_id=channel.id, created_by=42)
    reminder_time = event.event_time_utc - timedelta(minutes=60)

    await engine._send_reminder(event, event.event_time_utc, reminder_time)

    assert user.messages, "Creator should be notified when reminders cannot be delivered"
