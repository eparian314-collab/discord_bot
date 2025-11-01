import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cogs.event_management_cog import EventManagementCog, RecurrenceType


class DummyResponse:
    def __init__(self):
        self.messages = []
        self._done = False

    async def send_message(self, content=None, embed=None, ephemeral=False):
        self.messages.append({"content": content, "embed": embed, "ephemeral": ephemeral})
        self._done = True

    async def defer(self, *, ephemeral=False):
        self._done = True

    def is_done(self):
        return self._done


@pytest.fixture()
def event_engine():
    engine = AsyncMock()
    engine.create_event = AsyncMock(return_value=True)
    return engine


@pytest.fixture()
def kvk_tracker():
    tracker = AsyncMock()
    run = SimpleNamespace(
        id=1,
        run_number=5,
        is_test=False,
        ends_at=asyncio.get_event_loop().time(),
    )
    tracker.ensure_run = AsyncMock(return_value=(run, True))
    return tracker


@pytest.fixture()
def bot(event_engine, kvk_tracker):
    return SimpleNamespace(
        event_reminder_engine=event_engine,
        kvk_tracker=kvk_tracker,
        error_engine=None,
        personality_engine=None,
    )


def make_interaction(user_id=200, owner_ids=None):
    user = SimpleNamespace(id=user_id, display_name="Tester", name="Tester")
    response = DummyResponse()
    followup = AsyncMock()
    followup.send = AsyncMock()
    interaction = SimpleNamespace(
        guild=SimpleNamespace(id=321),
        guild_id=321,
        channel=SimpleNamespace(id=654),
        channel_id=654,
        user=user,
        response=response,
        followup=followup,
    )
    return interaction


@pytest.mark.asyncio
async def test_create_event_starts_kvk(monkeypatch, bot, event_engine, kvk_tracker):
    monkeypatch.setenv("OWNER_IDS", "999")  # ensure deterministic owner list

    cog = EventManagementCog(bot, event_engine=event_engine)
    interaction = make_interaction(user_id=200)

    await cog.create_event(
        interaction,
        title="Guild KVK Offensive",
        time_utc="2030-01-10 12:00",
        category="raid",
        recurrence=RecurrenceType.ONCE.value,
        remind_minutes="60",
    )

    event_engine.create_event.assert_awaited()
    kvk_tracker.ensure_run.assert_awaited_once()
    args, kwargs = kvk_tracker.ensure_run.call_args
    assert kwargs["guild_id"] == interaction.guild.id
    assert kwargs["title"] == "Guild KVK Offensive"
    assert kwargs["is_test"] is False
    assert kwargs["channel_id"] == interaction.channel_id
    assert interaction.response.messages[0]["embed"] is not None


@pytest.mark.asyncio
async def test_test_kvk_requires_owner(monkeypatch, bot, event_engine, kvk_tracker):
    monkeypatch.setenv("OWNER_IDS", "600")  # different owner id

    cog = EventManagementCog(bot, event_engine=event_engine)
    interaction = make_interaction(user_id=200)

    await cog.create_event(
        interaction,
        title="TEST KVK Trial",
        time_utc="2030-01-10 12:00",
        category="raid",
        recurrence=RecurrenceType.ONCE.value,
        remind_minutes="60",
    )

    # Should short-circuit before attempting to schedule or save.
    assert isinstance(interaction.response.messages[0]["content"], str)
    event_engine.create_event.assert_not_called()
    kvk_tracker.ensure_run.assert_not_called()

