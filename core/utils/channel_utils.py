"""Utility functions for Discord channel management."""

import os
from typing import Optional, Set
import discord


def get_bot_channel_ids() -> Set[int]:
    """
    Get the configured bot channel IDs from environment variables.
    
    Returns:
        A set of channel IDs if configured, an empty set otherwise.
    """
    raw = os.getenv("BOT_CHANNEL_ID", "")
    if not raw:
        return set()
    
    channel_ids = set()
    for token in raw.split(","):
        token = token.strip()
        if token:
            try:
                channel_ids.add(int(token))
            except ValueError:
                pass  # Ignore invalid entries
    return channel_ids


def get_sos_channel_id() -> Optional[int]:
    """
    Get the configured SOS alert channel ID from environment variables.
    Returns the first configured SOS channel if multiple are listed.
    
    Returns:
        Channel ID if configured, None otherwise
    """
    raw = os.getenv("SOS_CHANNEL_ID", "")
    if not raw:
        return None
    
    # Handle comma-separated values, take the first one
    first_channel = raw.split(",")[0].strip()
    if not first_channel:
        return None
    
    try:
        return int(first_channel)
    except ValueError:
        return None


def get_allowed_channel_ids() -> Set[int]:
    """
    Get all allowed interaction channel IDs from environment.
    
    Reads from ALLOWED_CHANNELS (comma/semicolon separated).
    Falls back to GENERAL_CHANNEL_ID and MEMBERSHIP_CHANNEL_ID for backwards compatibility.
    
    Example .env:
        ALLOWED_CHANNELS=1423024480799817881,1426291734996062440,1234567890123456789
    
    Returns:
        Set of channel IDs where bot can respond to commands
    """
    allowed_ids: Set[int] = set()
    
    # Try new format first (comma or semicolon separated)
    raw = os.getenv("ALLOWED_CHANNELS", "")
    if raw:
        for chunk in raw.replace(";", ",").split(","):
            token = chunk.strip()
            if token:
                try:
                    allowed_ids.add(int(token))
                except ValueError:
                    pass
        return allowed_ids
    
    # New fallback: check for specific channel names
    guild = discord.utils.get(discord.Client().guilds)  # Get the first guild (adjust as needed)
    if guild:
        for name in ["bot-channel", "fun-games-with-our-bot-friend"]:
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel:
                allowed_ids.add(channel.id)

    return allowed_ids


def is_allowed_channel(channel_id: int) -> bool:
    """
    Check if a channel is in the allowed channels list to use / commands in.
    
    If no allowed channels are configured, returns True (allow all channels).
    
    Args:
        channel_id: Discord channel ID to check
        
    Returns:
        True if channel is allowed or no restrictions exist, False otherwise
    """
    allowed = get_allowed_channel_ids()
    if not allowed:
        return True  # No restrictions configured
    return channel_id in allowed


def find_bot_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """
    Find the bot announcement channel in a guild.
    
    Tries in order:
    1. Configured BOT_CHANNEL_ID(s) from environment
    2. Channel named "bot", "bots", "bot-commands", or "commands"
    3. System channel
    4. First available text channel with send permissions
    
    Args:
        guild: Discord guild to search in
        
    Returns:
        TextChannel if found, None otherwise
    """
    me = guild.me

    def can_send(channel: discord.TextChannel) -> bool:
        perms = channel.permissions_for(me or guild.default_role)
        return perms.send_messages

    # First try configured BOT_CHANNEL_ID(s)
    channel_ids = get_bot_channel_ids()
    for channel_id in channel_ids:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel) and can_send(channel):
            return channel

    # Fallback: search by name
    preferred_names = ("bot", "bots", "bot-commands", "commands")
    for name in preferred_names:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel and can_send(channel):
            return channel

    # System channel fallback
    if guild.system_channel and can_send(guild.system_channel):
        return guild.system_channel

    # Last resort: first available channel
    for channel in guild.text_channels:
        if can_send(channel):
            return channel
    
    return None

def find_sos_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """
    Temporarily route SOS alerts to the bot channel for testing.
    """
    return find_bot_channel(guild)    
    

    