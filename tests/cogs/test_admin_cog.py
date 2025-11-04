from typing import Dict

import pytest

from discord_bot.cogs.admin_cog import AdminCog


class FakeInputEngine:
    def __init__(self):
        self._store: Dict[int, Dict[str, str]] = {}

    def get_sos_mapping(self, guild_id: int) -> Dict[str, str]:
        return dict(self._store.get(guild_id, {}))

    def set_sos_mapping(self, guild_id: int, mapping: Dict[str, str]) -> None:
        self._store[guild_id] = dict(mapping)


class DummyPermissions:
    def __init__(self, manage_guild: bool = False, administrator: bool = False):
        self.manage_guild = manage_guild
        self.administrator = administrator


class DummyGuild:
    def __init__(self, guild_id: int, owner_id: int):
        self.id = guild_id
        self.owner_id = owner_id


class DummyUser:
    def __init__(self, user_id: int, permissions: DummyPermissions):
        self.id = user_id
        self.guild_permissions = permissions


class DummyResponse:
    def __init__(self):
        self._done = False
        self.messages = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: str, *, ephemeral: bool) -> None:
        self._done = True
        self.messages.append((content, ephemeral))


class DummyFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content: str, *, ephemeral: bool) -> None:
        self.messages.append((content, ephemeral))


class DummyInteraction:
    def __init__(self, *, guild: DummyGuild, user: DummyUser):
        self.guild = guild
        self.user = user
        self.response = DummyResponse()
        self.followup = DummyFollowup()


class FakeBot:
    def __init__(self, input_engine: FakeInputEngine):
        self.input_engine = input_engine
        self._cogs = {}

    def get_cog(self, name: str):
        return self._cogs.get(name)


@pytest.mark.asyncio
async def test_keyword_set_updates_mapping():
    engine = FakeInputEngine()
    bot = FakeBot(engine)
    cog = AdminCog(bot, ui_engine=None)

    interaction = DummyInteraction(
        guild=DummyGuild(1, owner_id=99),
        user=DummyUser(42, DummyPermissions(manage_guild=True)),
    )

    await AdminCog.keyword_set.callback(cog, interaction, keyword="Alert", phrase="Test phrase")

    assert engine.get_sos_mapping(1)["alert"] == "Test phrase"
    assert interaction.response.messages


@pytest.mark.asyncio
async def test_keyword_link_reuses_existing_phrase():
    engine = FakeInputEngine()
    engine.set_sos_mapping(1, {"alert": "Test phrase"})
    bot = FakeBot(engine)
    cog = AdminCog(bot, ui_engine=None)

    interaction = DummyInteraction(
        guild=DummyGuild(1, owner_id=99),
        user=DummyUser(42, DummyPermissions(manage_guild=True)),
    )

    await AdminCog.keyword_link.callback(
        cog,
        interaction,
        new_keyword="panic",
        existing_keyword="alert",
    )

    mapping = engine.get_sos_mapping(1)
    assert mapping["panic"] == "Test phrase"


@pytest.mark.asyncio
async def test_keyword_remove_requires_existing_mapping():
    engine = FakeInputEngine()
    engine.set_sos_mapping(1, {"alert": "Test"})
    bot = FakeBot(engine)
    cog = AdminCog(bot, ui_engine=None)

    interaction = DummyInteraction(
        guild=DummyGuild(1, owner_id=99),
        user=DummyUser(42, DummyPermissions(manage_guild=True)),
    )

    await AdminCog.keyword_remove.callback(cog, interaction, keyword="alert")

    assert "alert" not in engine.get_sos_mapping(1)
    assert interaction.response.messages[0][0].startswith("Removed keyword")
