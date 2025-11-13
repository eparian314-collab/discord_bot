import types
from unittest.mock import AsyncMock

import pytest
import discord

from language_bot.cogs.role_management_cog import LanguageRoleManager
from language_bot.language_context.flag_map import LanguageDirectory, LanguageSpec


class StubGuild:
    def __init__(self, roles=None):
        self.roles = roles or []
        self.id = 123
        self.created = []
        self.members = {}

    def get_member(self, user_id):
        return self.members.get(user_id)

    async def fetch_member(self, user_id):
        return self.members.get(user_id)

    async def create_role(self, *, name, mentionable, reason):
        role = types.SimpleNamespace(name=name)
        self.created.append((name, mentionable, reason))
        self.roles.append(role)
        return role


class StubMember:
    def __init__(self, guild):
        self.guild = guild
        self.bot = False
        self.roles = []
        self.add_roles = AsyncMock()


@pytest.fixture()
def manager(sample_config):
    bot = types.SimpleNamespace(user=types.SimpleNamespace(id=999))
    bot.get_guild = lambda _gid: None
    bot.fetch_guild = AsyncMock(return_value=StubGuild())
    directory = LanguageDirectory.default()
    return LanguageRoleManager(bot, sample_config, directory)


def _spec(code: str) -> LanguageSpec:
    return LanguageSpec(
        name="Test",
        iso_code=code,
        default_role_slug=code,
        aliases=(code,),
        flag_emojis=("🏳️",),
    )


@pytest.mark.asyncio
async def test_assign_roles_adds_new_roles(manager: LanguageRoleManager):
    guild = StubGuild()
    member = StubMember(guild)
    spec = _spec("es")
    role = types.SimpleNamespace(name="lang-es")
    manager._ensure_role = AsyncMock(return_value=role)  # type: ignore[assignment]

    await manager._assign_roles(member, [spec])

    member.add_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_roles_ignores_bots(manager: LanguageRoleManager):
    guild = StubGuild()
    member = StubMember(guild)
    member.bot = True
    spec = _spec("es")
    await manager._assign_roles(member, [spec])
    member.add_roles.assert_not_called()


@pytest.mark.asyncio
async def test_assign_roles_handles_permission_errors(manager: LanguageRoleManager):
    guild = StubGuild()
    member = StubMember(guild)
    spec = _spec("es")
    manager._ensure_role = AsyncMock(return_value=types.SimpleNamespace(name="lang-es"))  # type: ignore[assignment]

    response = types.SimpleNamespace(status=403, reason="Forbidden", headers={})
    member.add_roles.side_effect = discord.Forbidden(response=response, message="nope")

    await manager._assign_roles(member, [spec])
    member.add_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_roles_handles_http_errors(manager: LanguageRoleManager):
    guild = StubGuild()
    member = StubMember(guild)
    spec = _spec("es")
    manager._ensure_role = AsyncMock(return_value=types.SimpleNamespace(name="lang-es"))  # type: ignore[assignment]
    response = types.SimpleNamespace(status=500, reason="boom", headers={})
    member.add_roles.side_effect = discord.HTTPException(response=response, message="fail")

    await manager._assign_roles(member, [spec])
    member.add_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_role_returns_existing(manager: LanguageRoleManager):
    role = types.SimpleNamespace(name="lang-es")
    guild = StubGuild(roles=[role])
    spec = _spec("es")
    result = await manager._ensure_role(guild, spec)
    assert result is role


@pytest.mark.asyncio
async def test_ensure_role_creates_when_missing(manager: LanguageRoleManager):
    guild = StubGuild()
    spec = _spec("es")
    role = await manager._ensure_role(guild, spec)
    assert role is not None
    assert guild.created


@pytest.mark.asyncio
async def test_ensure_role_handles_forbidden(manager: LanguageRoleManager):
    guild = StubGuild()
    spec = _spec("es")

    response = types.SimpleNamespace(status=403, reason="Forbidden", headers={})

    async def failing_create_role(**_kwargs):
        raise discord.Forbidden(response=response, message="nope")

    guild.create_role = failing_create_role  # type: ignore[assignment]
    assert await manager._ensure_role(guild, spec) is None


@pytest.mark.asyncio
async def test_ensure_role_handles_http_error(manager: LanguageRoleManager):
    guild = StubGuild()
    spec = _spec("es")
    response = types.SimpleNamespace(status=500, reason="boom", headers={})

    async def failing_create_role(**_kwargs):
        raise discord.HTTPException(response=response, message="fail")

    guild.create_role = failing_create_role  # type: ignore[assignment]
    assert await manager._ensure_role(guild, spec) is None


@pytest.mark.asyncio
async def test_on_message_triggers_assignment(manager: LanguageRoleManager):
    member = StubMember(StubGuild())
    message = types.SimpleNamespace(
        guild=member.guild,
        author=member,
        content="Hola 🇲🇽",
    )
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]
    await manager.on_message(message)
    manager._assign_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_message_skips_bot(manager: LanguageRoleManager):
    member = StubMember(StubGuild())
    member.bot = True
    message = types.SimpleNamespace(guild=member.guild, author=member, content="Hola 🇲🇽")
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]
    await manager.on_message(message)
    manager._assign_roles.assert_not_called()


@pytest.mark.asyncio
async def test_on_raw_reaction_add_fetches_member(manager: LanguageRoleManager):
    guild = StubGuild()
    member = StubMember(guild)
    guild.members[5] = member
    manager.bot.get_guild = lambda _gid: guild  # type: ignore[attr-defined]
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]
    payload = types.SimpleNamespace(guild_id=1, user_id=5, emoji="🇲🇽", member=None)

    await manager.on_raw_reaction_add(payload)
    manager._assign_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_raw_reaction_add_ignores_unknown_flag(manager: LanguageRoleManager):
    payload = types.SimpleNamespace(guild_id=1, user_id=5, emoji="❓", member=None)
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]
    await manager.on_raw_reaction_add(payload)
    manager._assign_roles.assert_not_called()


@pytest.mark.asyncio
async def test_on_raw_reaction_add_fetches_guild_when_missing(manager: LanguageRoleManager):
    fetched_guild = StubGuild()
    member = StubMember(fetched_guild)
    fetched_guild.members[7] = member
    manager.bot.get_guild = lambda _gid: None  # type: ignore[attr-defined]
    manager.bot.fetch_guild = AsyncMock(return_value=fetched_guild)  # type: ignore[attr-defined]
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]

    payload = types.SimpleNamespace(guild_id=1, user_id=7, emoji="🇲🇽", member=None)
    await manager.on_raw_reaction_add(payload)
    manager._assign_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_raw_reaction_add_handles_member_fetch_failure(manager: LanguageRoleManager):
    guild = StubGuild()

    async def failing_fetch_member(_user_id):
        response = types.SimpleNamespace(status=404, reason="missing", headers={})
        raise discord.HTTPException(response=response, message="fail")

    guild.fetch_member = failing_fetch_member  # type: ignore[assignment]
    manager.bot.get_guild = lambda _gid: guild  # type: ignore[attr-defined]
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]
    payload = types.SimpleNamespace(guild_id=1, user_id=8, emoji="🇲🇽", member=None)
    await manager.on_raw_reaction_add(payload)
    manager._assign_roles.assert_not_called()


@pytest.mark.asyncio
async def test_on_raw_reaction_add_ignores_bot_user(manager: LanguageRoleManager):
    payload = types.SimpleNamespace(guild_id=1, user_id=manager.bot.user.id, emoji="🇲🇽", member=None)
    manager._assign_roles = AsyncMock()  # type: ignore[assignment]
    await manager.on_raw_reaction_add(payload)
    manager._assign_roles.assert_not_called()
