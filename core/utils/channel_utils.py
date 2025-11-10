"""Utility functions for Discord channel management."""

import logging
import os
from typing import List, Optional, Set, Union

import discord


def get_bot_channel_ids() -> List[int]:
    """
    Get bot channel IDs in priority order as configured in environment variables.
    
    Returns:
        Ordered list of channel IDs (first entry treated as primary).
    """
    raw = os.getenv("BOT_CHANNEL_ID", "")
    if not raw:
        return []
    
    channel_ids: List[int] = []
    seen: Set[int] = set()
    for token in raw.replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            channel_id = int(token)
        except ValueError:
            continue
        if channel_id in seen:
            continue
        channel_ids.append(channel_id)
        seen.add(channel_id)
    return channel_ids


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


ChannelLike = Union[int, discord.abc.Snowflake, discord.abc.Messageable]


def is_allowed_channel(channel: ChannelLike) -> bool:
    """
    Check if a channel is in the allowed channels list to use / commands in.
    
    If no allowed channels are configured, returns True (allow all channels).
    
    Args:
        channel: Channel object or ID to check. Threads inherit their parent's allowance.
        
    Returns:
        True if channel is allowed or no restrictions exist, False otherwise
    """
    parent_id: Optional[int] = None
    if isinstance(channel, int):
        channel_id = channel
    else:
        channel_id = getattr(channel, "id", None)
        parent = getattr(channel, "parent", None)
        if parent and hasattr(parent, "id"):
            parent_id = parent.id
        elif hasattr(channel, "parent_id"):
            parent_id = getattr(channel, "parent_id")

    if channel_id is None:
        logging.warning("is_allowed_channel called with channel lacking an id: %s", channel)
        return False

    allowed = get_allowed_channel_ids()
    if not allowed:
        return True  # No restrictions configured
    if channel_id in allowed:
        return True
    if parent_id and parent_id in allowed:
        return True
    return False


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
    candidates: List[str] = []
    for channel_id in channel_ids:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            if can_send(channel):
                return channel
            candidates.append(f"#{channel.name}")
        else:
            candidates.append(str(channel_id))

    # Fallback: search by name
    preferred_names = ("bot", "bots", "bot-commands", "commands")
    for name in preferred_names:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel:
            if can_send(channel):
                return channel
            candidates.append(f"#{channel.name}")
        else:
            candidates.append(name)

    # System channel fallback
    if guild.system_channel:
        if can_send(guild.system_channel):
            return guild.system_channel
        candidates.append(f"#{guild.system_channel.name}")

    # Last resort: first available channel
    for channel in guild.text_channels:
        if can_send(channel):
            return channel
    
    if not candidates:
        logging.warning(
            "find_bot_channel: no candidate channels found in guild %s (%s)",
            guild.id,
            guild.name,
        )
    else:
        logging.warning(
            "find_bot_channel: no send permissions for candidates %s in guild %s (%s)",
            ", ".join(candidates),
            guild.id,
            guild.name,
        )

    return None
