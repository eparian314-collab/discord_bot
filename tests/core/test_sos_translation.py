"""
Tests for SOS phrase translation and DM functionality.
"""

import pytest
from unittest.mock import AsyncMock, Mock
import discord
from discord_bot.core.engines.input_engine import InputEngine


@pytest.fixture
def mock_bot():
    """Create a mock bot instance."""
    bot = Mock(spec=discord.Client)
    return bot


@pytest.fixture
def mock_context_engine():
    """Create a mock context engine."""
    return Mock()


@pytest.fixture
def mock_processing_engine():
    """Create a mock processing engine with orchestrator."""
    processing = Mock()
    orchestrator = Mock()
    orchestrator.translate_text_for_user = AsyncMock(return_value=("Translated text", "en", "deepl"))
    processing.orchestrator = orchestrator
    return processing


@pytest.fixture
def mock_output_engine():
    """Create a mock output engine."""
    return Mock()


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager."""
    return Mock()


@pytest.fixture
def mock_role_manager():
    """Create a mock role manager."""
    role_manager = Mock()
    role_manager.get_user_languages = AsyncMock(return_value=["es"])
    return role_manager


@pytest.fixture
def input_engine(
    mock_bot,
    mock_context_engine,
    mock_processing_engine,
    mock_output_engine,
    mock_cache_manager,
    mock_role_manager
):
    """Create an InputEngine with mocked dependencies."""
    return InputEngine(
        mock_bot,
        context_engine=mock_context_engine,
        processing_engine=mock_processing_engine,
        output_engine=mock_output_engine,
        cache_manager=mock_cache_manager,
        role_manager=mock_role_manager,
    )


@pytest.mark.asyncio
async def test_trigger_sos_sends_channel_alert(input_engine):
    """Test that SOS trigger sends alert in the channel."""
    # Create mock message
    message = Mock(spec=discord.Message)
    message.channel = Mock()
    message.channel.send = AsyncMock(return_value=Mock())
    message.guild = None  # No guild to skip DM sending
    message.author = Mock(spec=discord.User)

    # Trigger SOS
    await input_engine._trigger_sos(message, "Emergency alert!")

    # Verify channel message was sent
    message.channel.send.assert_called_once()
    call_args = message.channel.send.call_args[0][0]
    assert "SOS Triggered" in call_args
    assert "Emergency alert!" in call_args


@pytest.mark.asyncio
async def test_send_sos_dms_to_users_with_language_roles(input_engine, mock_role_manager):
    """Test that SOS DMs are sent to users with language roles."""
    # Create mock guild and members
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    # Create mock members
    sender = Mock(spec=discord.User)
    sender.id = 1
    sender.mention = "@sender"
    
    member1 = Mock(spec=discord.Member)
    member1.id = 2
    member1.bot = False
    member1.name = "User1"
    member1.send = AsyncMock()
    
    member2 = Mock(spec=discord.Member)
    member2.id = 3
    member2.bot = False
    member2.name = "User2"
    member2.send = AsyncMock()
    
    bot_member = Mock(spec=discord.Member)
    bot_member.id = 4
    bot_member.bot = True
    
    guild.members = [sender, member1, member2, bot_member]
    
    # Setup role manager to return different languages
    async def get_user_languages_side_effect(user_id, guild_id):
        if user_id == 2:
            return ["es"]  # Spanish for member1
        elif user_id == 3:
            return ["fr"]  # French for member2
        return []
    
    mock_role_manager.get_user_languages = AsyncMock(side_effect=get_user_languages_side_effect)
    
    # Send SOS DMs
    await input_engine._send_sos_dms(guild, "Emergency!", sender)
    
    # Verify DMs were sent to members with language roles (not sender or bots)
    assert member1.send.call_count == 1
    assert member2.send.call_count == 1
    
    # Verify message content
    dm_content_1 = member1.send.call_args[0][0]
    assert "SOS ALERT" in dm_content_1
    assert "Test Guild" in dm_content_1


@pytest.mark.asyncio
async def test_send_sos_dms_translates_to_target_language(input_engine, mock_role_manager):
    """Test that SOS messages are translated to user's language."""
    # Create mock guild and member
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    sender = Mock(spec=discord.User)
    sender.id = 1
    sender.mention = "@sender"
    
    member = Mock(spec=discord.Member)
    member.id = 2
    member.bot = False
    member.name = "Spanish User"
    member.send = AsyncMock()
    
    guild.members = [sender, member]
    
    # Setup role manager to return Spanish
    mock_role_manager.get_user_languages = AsyncMock(return_value=["es"])
    
    # Setup orchestrator to return translated text
    orchestrator = input_engine.processing.orchestrator
    orchestrator.translate_text_for_user = AsyncMock(
        return_value=("¡Emergencia!", "en", "deepl")
    )
    
    # Send SOS DMs
    await input_engine._send_sos_dms(guild, "Emergency!", sender)
    
    # Verify translation was requested
    orchestrator.translate_text_for_user.assert_called_once_with(
        text="Emergency!",
        guild_id=guild.id,
        user_id=member.id,
        tgt_lang="es"
    )
    
    # Verify DM was sent
    assert member.send.call_count == 1
    dm_content = member.send.call_args[0][0]
    assert "¡Emergencia!" in dm_content


@pytest.mark.asyncio
async def test_send_sos_dms_skips_english_speakers(input_engine, mock_role_manager):
    """Test that English SOS messages are sent without translation to English users."""
    # Create mock guild and member
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    sender = Mock(spec=discord.User)
    sender.id = 1
    sender.mention = "@sender"
    
    member = Mock(spec=discord.Member)
    member.id = 2
    member.bot = False
    member.name = "English User"
    member.send = AsyncMock()
    
    guild.members = [sender, member]
    
    # Setup role manager to return English
    mock_role_manager.get_user_languages = AsyncMock(return_value=["en"])
    
    # Setup orchestrator
    orchestrator = input_engine.processing.orchestrator
    orchestrator.translate_text_for_user = AsyncMock(
        return_value=("Emergency!", "en", "deepl")
    )
    
    # Send SOS DMs
    await input_engine._send_sos_dms(guild, "Emergency!", sender)
    
    # Verify translation was NOT requested (English to English)
    orchestrator.translate_text_for_user.assert_not_called()
    
    # Verify DM was sent with original message
    assert member.send.call_count == 1
    dm_content = member.send.call_args[0][0]
    assert "Emergency!" in dm_content


@pytest.mark.asyncio
async def test_send_sos_dms_handles_dm_disabled(input_engine, mock_role_manager):
    """Test that SOS DMs handle users with DMs disabled gracefully."""
    # Create mock guild and member
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    sender = Mock(spec=discord.User)
    sender.id = 1
    sender.mention = "@sender"
    
    member = Mock(spec=discord.Member)
    member.id = 2
    member.bot = False
    member.name = "DMs Disabled User"
    member.send = AsyncMock(side_effect=discord.Forbidden(Mock(), "Cannot send messages"))
    
    guild.members = [sender, member]
    
    # Setup role manager to return a language
    mock_role_manager.get_user_languages = AsyncMock(return_value=["es"])
    
    # Send SOS DMs - should not raise exception
    await input_engine._send_sos_dms(guild, "Emergency!", sender)
    
    # Verify attempt was made
    assert member.send.call_count == 1


@pytest.mark.asyncio
async def test_send_sos_dms_skips_users_without_language_roles(input_engine, mock_role_manager):
    """Test that SOS DMs are not sent to users without language roles."""
    # Create mock guild and member
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    sender = Mock(spec=discord.User)
    sender.id = 1
    sender.mention = "@sender"
    
    member = Mock(spec=discord.Member)
    member.id = 2
    member.bot = False
    member.name = "No Role User"
    member.send = AsyncMock()
    
    guild.members = [sender, member]
    
    # Setup role manager to return no languages
    mock_role_manager.get_user_languages = AsyncMock(return_value=[])
    
    # Send SOS DMs
    await input_engine._send_sos_dms(guild, "Emergency!", sender)
    
    # Verify NO DM was sent (user has no language role)
    member.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_sos_dms_uses_fallback_on_translation_failure(input_engine, mock_role_manager):
    """Test that original message is sent if translation fails."""
    # Create mock guild and member
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    sender = Mock(spec=discord.User)
    sender.id = 1
    sender.mention = "@sender"
    
    member = Mock(spec=discord.Member)
    member.id = 2
    member.bot = False
    member.name = "Spanish User"
    member.send = AsyncMock()
    
    guild.members = [sender, member]
    
    # Setup role manager to return Spanish
    mock_role_manager.get_user_languages = AsyncMock(return_value=["es"])
    
    # Setup orchestrator to fail translation
    orchestrator = input_engine.processing.orchestrator
    orchestrator.translate_text_for_user = AsyncMock(return_value=(None, "en", None))
    
    # Send SOS DMs
    await input_engine._send_sos_dms(guild, "Emergency!", sender)
    
    # Verify DM was sent with original English message
    assert member.send.call_count == 1
    dm_content = member.send.call_args[0][0]
    assert "Emergency!" in dm_content
