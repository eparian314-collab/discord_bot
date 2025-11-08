from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from discord_bot.cogs.event_management_cog import EventManagementCog, RecurrenceType
from discord_bot.cogs.kvk_visual_cog import EnhancedKVKRankingCog
from discord_bot.core.engines.event_reminder_engine import EventReminderEngine, EventCategory
from discord_bot.core.engines.kvk_tracker import KVKTracker
from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class InMemoryEventStorage:
    def __init__(self) -> None:
        self._events: dict[str, dict] = {}
        self._sequences: dict[tuple[str, str], int] = {}

    def allocate_event_display_index(self, guild_id: int | str, category: str) -> int:
        key = (str(guild_id), category)
        self._sequences[key] = self._sequences.get(key, 0) + 1
        return self._sequences[key]

    def store_event_reminder(self, event_data: dict) -> bool:
        self._events[event_data["event_id"]] = dict(event_data)
        return True

    def update_event_reminder(self, event_id: str, updates: dict) -> bool:
        if event_id not in self._events:
            return False
        self._events[event_id].update(updates)
        return True

    def delete_event_reminder(self, event_id: str) -> bool:
        self._events.pop(event_id, None)
        return True

    def get_event_reminders(self, guild_id: int | None = None):
        values = list(self._events.values())
        if guild_id is not None:
            values = [evt for evt in values if evt["guild_id"] == guild_id]
        return values


class FakeChannel:
    def __init__(self, channel_id: int, name: str):
        self.id = channel_id
        self.name = name
        self.messages = []

    def permissions_for(self, _):
        return SimpleNamespace(send_messages=True)

    async def send(self, content=None, **payload):
        entry = {"content": content}
        entry.update(payload)
        self.messages.append(entry)


class FakeGuild:
    def __init__(self, guild_id: int, channels: list[FakeChannel]):
        self.id = guild_id
        self.name = "Integration Guild"
        self._channels = {channel.id: channel for channel in channels}
        self.text_channels = channels
        self.default_role = SimpleNamespace()
        self.me = SimpleNamespace()
        self.system_channel = None

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)


class FakeBot:
    def __init__(self, guild: FakeGuild):
        self._guild = guild
        self.event_reminder_engine = None
        self.kvk_tracker = None

    def get_guild(self, guild_id: int):
        if guild_id == self._guild.id:
            return self._guild
        return None

    def get_channel(self, channel_id: int):
        return self._guild.get_channel(channel_id)

    async def fetch_channel(self, channel_id: int):
        return self.get_channel(channel_id)

    def get_user(self, _user_id: int):
        return None


class DummyResponse:
    def __init__(self):
        self.messages = []
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, *, content=None, embed=None, ephemeral: bool):
        self._done = True
        self.messages.append({"content": content, "embed": embed, "ephemeral": ephemeral})

    async def defer(self, *, ephemeral: bool):
        self._done = True


class DummyFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, *, content=None, embed=None, ephemeral: bool):
        self.messages.append({"content": content, "embed": embed, "ephemeral": ephemeral})


class FakeInteraction:
    def __init__(self, guild: FakeGuild, channel: FakeChannel, user_id: int):
        self.guild = guild
        self.guild_id = guild.id
        self.channel = channel
        self.channel_id = channel.id
        self.user = SimpleNamespace(
            id=user_id,
            display_name="Tester",
            guild_permissions=SimpleNamespace(manage_guild=True, administrator=True),
        )
        self.response = DummyResponse()
        self.followup = DummyFollowup()


class FakeAttachment:
    def __init__(self):
        self.content_type = "image/png"
        self.size = 1024
        self.filename = "kvk.png"
        self.url = "https://example.com/kvk.png"

    async def read(self):
        return b"binary"


class FakeVisualManager:
    async def validate_screenshot_requirements(self, _data):
        return {"valid": True}

    async def process_kvk_screenshot(self, **_kwargs):
        return {
            "success": True,
            "parse_result": {
                "stage_type": "prep",
                "prep_day": 1,
                "kingdom_id": 1234,
                "entries_count": 5,
            },
            "self_score": {"rank": 10, "points": 1000, "player_name": "Tester", "guild_tag": "TAG"},
            "comparison": {"user_power": 100, "peer_count": 5, "behind": 1, "top_peer_ahead_by": 50},
            "processing_time_seconds": 0.5,
        }


@pytest.mark.asyncio
async def test_event_create_reminder_to_kvk_submit(monkeypatch, tmp_path):
    bot_channel = FakeChannel(500, "bot-updates")
    rankings_channel = FakeChannel(600, "kvk-rankings")
    guild = FakeGuild(321, [bot_channel, rankings_channel])

    event_storage = InMemoryEventStorage()
    kvk_storage = GameStorageEngine(db_path=str(tmp_path / "kvk.db"))
    kvk_tracker = KVKTracker(kvk_storage)

    bot = FakeBot(guild)
    bot.kvk_tracker = kvk_tracker
    bot.event_reminder_engine = None

    event_engine = EventReminderEngine(event_storage)
    event_engine.bot = bot
    event_engine.kvk_tracker = kvk_tracker
    kvk_tracker.bot = bot
    bot.event_reminder_engine = event_engine

    monkeypatch.setenv("BOT_CHANNEL_ID", str(bot_channel.id))
    monkeypatch.setenv("RANKINGS_CHANNEL_ID", str(rankings_channel.id))
    monkeypatch.setattr("discord_bot.cogs.event_management_cog.is_admin_or_helper", lambda *_: True)
    monkeypatch.setattr("discord_bot.cogs.kvk_visual_cog.is_admin_or_helper", lambda *_: True)

    cog = EventManagementCog(bot, event_engine=event_engine)

    event_time = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    interaction = FakeInteraction(guild, bot_channel, user_id=42)

    await cog.create_event(
        interaction,
        title="KVK Prime Run",
        time_utc=event_time,
        category=EventCategory.RAID.value,
        recurrence=RecurrenceType.ONCE.value,
        remind_minutes="60",
    )

    events = await event_engine.get_events_for_guild(guild.id)
    assert events, "Event should persist to storage"

    reminder_event = events[0]
    reminder_time = reminder_event.event_time_utc - timedelta(minutes=reminder_event.reminder_times[0])
    await event_engine._send_reminder(reminder_event, reminder_event.event_time_utc, reminder_time)

    assert bot_channel.messages, "Reminder should be posted to bot channel"

    cursor = kvk_storage.conn.execute("SELECT COUNT(*) FROM kvk_runs WHERE guild_id = ?", (str(guild.id),))
    assert cursor.fetchone()[0] == 1, "KVK run should be reused rather than duplicated"

    kvk_cog = EnhancedKVKRankingCog(bot)
    kvk_cog.kvk_tracker = kvk_tracker
    kvk_cog.storage = kvk_storage
    kvk_cog.guardian = None
    kvk_cog._rankings_channel_id = rankings_channel.id
    kvk_cog.visual_manager = FakeVisualManager()

    kvk_interaction = FakeInteraction(guild, rankings_channel, user_id=77)
    attachment = FakeAttachment()

    await EnhancedKVKRankingCog.submit_kvk_visual.callback(
        kvk_cog,
        kvk_interaction,
        screenshot=attachment,
    )

    assert kvk_interaction.followup.messages, "KVK submission should respond with a success embed"
