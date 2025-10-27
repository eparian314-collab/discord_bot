import asyncio
import pytest

from discord_bot.core.event_bus import EventBus
from discord_bot.core.event_topics import ENGINE_ERROR
from discord_bot.core.engines.error_engine import GuardianErrorEngine


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = {}

    async def handler(**payload):
        received.update(payload)

    bus.subscribe("custom.event", handler)
    await bus.emit("custom.event", foo=123, bar="baz")

    assert received == {"foo": 123, "bar": "baz"}


@pytest.mark.asyncio
async def test_guardian_error_engine_emits_engine_error_event():
    bus = EventBus()
    seen = {}

    async def on_error(**payload):
        seen.update(payload)

    bus.subscribe(ENGINE_ERROR, on_error)
    guardian = GuardianErrorEngine(event_bus=bus)

    await guardian.log_error(RuntimeError("oops"), context="unit-test", severity="warning", meta=1)

    assert seen.get("message") == "oops"
    assert seen.get("severity") == "warning"
    assert seen.get("context") == "unit-test"

