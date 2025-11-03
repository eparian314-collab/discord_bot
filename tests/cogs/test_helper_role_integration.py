"""
Integration tests for helper role access to admin commands.

Tests that users with the helper role can access admin-only commands
in AdminCog, SOSPhraseCog, and HelpCog.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

import discord
from discord.ext import commands

from cogs.admin_cog import AdminCog
from cogs.sos_phrase_cog import SOSPhraseCog
from cogs.help_cog import HelpCog


# ============================================================================
# Test Fixtures & Mocks
# ============================================================================

class DummyRole:
    """Mock Discord role."""
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name


class DummyPermissions:
    """Mock Discord permissions."""
    def __init__(self, manage_guild: bool = False, administrator: bool = False):
        self.manage_guild = manage_guild
        self.administrator = administrator


class DummyUser:
    """Mock Discord user/member."""
    def __init__(self, user_id: int, permissions: DummyPermissions = None, roles: list = None):
        self.id = user_id
        self.guild_permissions = permissions or DummyPermissions()
        self.roles = roles or []
        self.mention = f"<@{user_id}>"


class DummyGuild:
    """Mock Discord guild."""
    def __init__(self, guild_id: int, owner_id: int):
        self.id = guild_id
        self.owner_id = owner_id


class DummyInteraction:
    """Mock Discord interaction."""
    def __init__(self, user: DummyUser, guild: DummyGuild):
        self.user = user
        self.guild = guild
        self.response = AsyncMock()
        self.response.is_done = Mock(return_value=False)
        self.followup = AsyncMock()


@pytest.fixture
def bot():
    """Create a mock bot."""
    bot = Mock(spec=commands.Bot)
    bot.input_engine = None
    bot.error_engine = None
    bot.get_cog = Mock(return_value=None)  # Mock get_cog to return None
    return bot


@pytest.fixture
def helper_role():
    """Create a helper role."""
    return DummyRole(999999999999999999, "Helper")


@pytest.fixture
def user_with_helper_role(helper_role):
    """Create a user with helper role."""
    user = DummyUser(12345, DummyPermissions(), roles=[helper_role])
    return user


@pytest.fixture
def user_without_helper_role():
    """Create a user without helper role."""
    return DummyUser(67890, DummyPermissions())


@pytest.fixture
def guild():
    """Create a test guild."""
    return DummyGuild(11111, 99999)


# ============================================================================
# AdminCog Tests
# ============================================================================

@pytest.mark.asyncio
async def test_admin_cog_helper_role_has_permission(bot, user_with_helper_role, guild, monkeypatch):
    """Test that helper role grants permission in AdminCog."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = AdminCog(bot, ui_engine=None)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    assert cog._has_permission(interaction) is True


@pytest.mark.asyncio
async def test_admin_cog_without_helper_role_no_permission(bot, user_without_helper_role, guild, monkeypatch):
    """Test that user without helper role lacks permission in AdminCog."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = AdminCog(bot, ui_engine=None)
    interaction = DummyInteraction(user_without_helper_role, guild)
    
    assert cog._has_permission(interaction) is False


@pytest.mark.asyncio
async def test_admin_cog_keyword_set_with_helper_role(bot, user_with_helper_role, guild, monkeypatch):
    """Test that helper role user can set keywords."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = AdminCog(bot, ui_engine=None)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    # Should not raise PermissionError
    await AdminCog.keyword_set.callback(cog, interaction, keyword="test", phrase="Test phrase")
    
    # Should send success message
    assert interaction.response.send_message.called


# ============================================================================
# SOSPhraseCog Tests
# ============================================================================

@pytest.mark.asyncio
async def test_sos_cog_helper_role_has_permission(bot, user_with_helper_role, guild, monkeypatch):
    """Test that helper role grants permission in SOSPhraseCog."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = SOSPhraseCog(bot)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    assert cog._has_permission(interaction) is True


@pytest.mark.asyncio
async def test_sos_cog_without_helper_role_no_permission(bot, user_without_helper_role, guild, monkeypatch):
    """Test that user without helper role lacks permission in SOSPhraseCog."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = SOSPhraseCog(bot)
    interaction = DummyInteraction(user_without_helper_role, guild)
    
    assert cog._has_permission(interaction) is False


@pytest.mark.asyncio
async def test_sos_cog_add_with_helper_role(bot, user_with_helper_role, guild, monkeypatch):
    """Test that helper role user can add SOS keywords."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = SOSPhraseCog(bot)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    await SOSPhraseCog.sos_add.callback(cog, interaction, keyword="help", phrase="Emergency alert!")
    
    # Should send success message
    assert interaction.response.send_message.called


@pytest.mark.asyncio
async def test_sos_cog_add_without_helper_role(bot, user_without_helper_role, guild, monkeypatch):
    """Test that user without helper role cannot add SOS keywords."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = SOSPhraseCog(bot)
    interaction = DummyInteraction(user_without_helper_role, guild)
    
    await SOSPhraseCog.sos_add.callback(cog, interaction, keyword="help", phrase="Emergency alert!")
    
    # Should send permission denied message
    assert interaction.response.send_message.called
    call_args = interaction.response.send_message.call_args
    assert "permission" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_sos_cog_remove_with_helper_role(bot, user_with_helper_role, guild, monkeypatch):
    """Test that helper role user can remove SOS keywords."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = SOSPhraseCog(bot)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    # Add a keyword first
    await SOSPhraseCog.sos_add.callback(cog, interaction, keyword="help", phrase="Emergency alert!")
    
    # Reset mock
    interaction.response.send_message.reset_mock()
    
    # Try to remove it
    await SOSPhraseCog.sos_remove.callback(cog, interaction, keyword="help")
    
    # Should send success message
    assert interaction.response.send_message.called


@pytest.mark.asyncio
async def test_sos_cog_clear_with_helper_role(bot, user_with_helper_role, guild, monkeypatch):
    """Test that helper role user can clear SOS keywords."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    cog = SOSPhraseCog(bot)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    await SOSPhraseCog.sos_clear.callback(cog, interaction)
    
    # Should send success message
    assert interaction.response.send_message.called


# ============================================================================
# HelpCog Tests
# ============================================================================

@pytest.mark.asyncio
async def test_help_cog_helper_role_is_admin(user_with_helper_role, guild, monkeypatch):
    """Test that helper role grants admin status in HelpCog."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    assert HelpCog._is_admin(user_with_helper_role, guild) is True


@pytest.mark.asyncio
async def test_help_cog_without_helper_role_not_admin(user_without_helper_role, guild, monkeypatch):
    """Test that user without helper role is not admin in HelpCog."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    assert HelpCog._is_admin(user_without_helper_role, guild) is False


@pytest.mark.asyncio
async def test_help_cog_server_owner_is_admin(guild, monkeypatch):
    """Test that server owner is always admin."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    # Create server owner user
    owner = DummyUser(guild.owner_id, DummyPermissions())
    
    assert HelpCog._is_admin(owner, guild) is True


@pytest.mark.asyncio
async def test_help_cog_bot_owner_is_admin(guild, monkeypatch):
    """Test that bot owner is always admin."""
    monkeypatch.setenv("OWNER_IDS", "12345")
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    # Create bot owner user
    bot_owner = DummyUser(12345, DummyPermissions())
    
    assert HelpCog._is_admin(bot_owner, guild) is True


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_helper_role_not_configured(bot, user_with_helper_role, guild, monkeypatch):
    """Test that when HELPER_ROLE_ID is not configured, helper role doesn't grant permission."""
    monkeypatch.delenv("HELPER_ROLE_ID", raising=False)
    
    cog = AdminCog(bot, ui_engine=None)
    interaction = DummyInteraction(user_with_helper_role, guild)
    
    # Should not have permission since helper role ID not configured
    assert cog._has_permission(interaction) is False


@pytest.mark.asyncio
async def test_multiple_roles_including_helper(bot, guild, monkeypatch, helper_role):
    """Test that user with multiple roles including helper role has permission."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    other_role = DummyRole(111111111111111111, "Regular")
    user = DummyUser(12345, DummyPermissions(), roles=[other_role, helper_role])
    
    cog = AdminCog(bot, ui_engine=None)
    interaction = DummyInteraction(user, guild)
    
    assert cog._has_permission(interaction) is True


@pytest.mark.asyncio
async def test_discord_admin_permission_still_works(bot, guild, monkeypatch):
    """Test that Discord admin permissions still grant access."""
    monkeypatch.setenv("HELPER_ROLE_ID", "999999999999999999")
    
    # User with Discord admin permission but no helper role
    admin_user = DummyUser(12345, DummyPermissions(administrator=True))
    
    cog = AdminCog(bot, ui_engine=None)
    interaction = DummyInteraction(admin_user, guild)
    
    assert cog._has_permission(interaction) is True
