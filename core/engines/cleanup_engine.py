"""
Message Cleanup Engine for HippoBot.

Safely deletes old bot messages from previous sessions while respecting
pinned messages, rate limits, and important content.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set

import discord

from discord_bot.core.engines.base.logging_utils import get_logger

logger = get_logger("cleanup_engine")

# Default cleanup configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "skip_recent_minutes": 30,
    "skip_channels": ["bot-logs", "announcements", "mod-log"],
    "delete_limit_per_channel": 200,
    "rate_limit_delay": 0.5,  # seconds between deletions
    "preserve_keywords": ["DO NOT DELETE", "SYSTEM NOTICE", "IMPORTANT"],
}


class CleanupEngine:
    """Engine for cleaning up old bot messages."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize cleanup engine.
        
        Args:
            config: Configuration dictionary (uses defaults if None)
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.stats = {
            "messages_deleted": 0,
            "channels_cleaned": 0,
            "channels_skipped": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    def _should_preserve_message(self, message: discord.Message) -> tuple[bool, str]:
        """Check if a message should be preserved.
        
        Args:
            message: Discord message to check
            
        Returns:
            tuple: (should_preserve: bool, reason: str)
        """
        # Preserve pinned messages
        if message.pinned:
            return True, "pinned"
        
        # Preserve messages with preserve keywords
        for keyword in self.config["preserve_keywords"]:
            if keyword.lower() in message.content.lower():
                return True, f"keyword:{keyword}"
        
        # Preserve messages with reactions (likely important)
        if message.reactions:
            return True, "has_reactions"
        
        # Preserve recent messages
        skip_recent_minutes = self.config.get("skip_recent_minutes", 30)
        if skip_recent_minutes > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=skip_recent_minutes)
            if message.created_at > cutoff:
                return True, "too_recent"
        
        return False, ""

    def _should_skip_channel(self, channel: discord.TextChannel) -> tuple[bool, str]:
        """Check if a channel should be skipped.
        
        Args:
            channel: Discord text channel
            
        Returns:
            tuple: (should_skip: bool, reason: str)
        """
        # Skip channels in blocklist
        skip_channels = self.config.get("skip_channels", [])
        channel_name_lower = channel.name.lower()
        
        for skip_pattern in skip_channels:
            if skip_pattern.lower() in channel_name_lower:
                return True, f"blocklist:{skip_pattern}"
        
        # Skip if bot lacks permissions
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.read_message_history:
            return True, "no_read_history_permission"
        if not permissions.manage_messages:
            return True, "no_manage_messages_permission"
        
        return False, ""

    async def cleanup_channel(
        self,
        channel: discord.TextChannel,
        bot_user: discord.User,
        since: Optional[datetime] = None,
    ) -> int:
        """Clean up bot messages in a specific channel.
        
        Args:
            channel: Channel to clean
            bot_user: Bot's user object
            since: Only delete messages after this timestamp (None = all)
            
        Returns:
            int: Number of messages deleted
        """
        deleted_count = 0
        limit = self.config.get("delete_limit_per_channel", 200)
        rate_delay = self.config.get("rate_limit_delay", 0.5)
        
        try:
            async for message in channel.history(limit=limit, after=since):
                # Only process bot's own messages
                if message.author.id != bot_user.id:
                    continue
                
                # Check if message should be preserved
                should_preserve, reason = self._should_preserve_message(message)
                if should_preserve:
                    logger.debug(
                        "Preserving message %s in %s: %s",
                        message.id,
                        channel.name,
                        reason
                    )
                    continue
                
                # Delete message
                try:
                    await message.delete()
                    deleted_count += 1
                    logger.debug("Deleted message %s from %s", message.id, channel.name)
                    
                    # Respect rate limits
                    if rate_delay > 0:
                        await asyncio.sleep(rate_delay)
                
                except discord.Forbidden:
                    logger.warning("Missing permissions to delete message %s", message.id)
                    self.stats["errors"] += 1
                
                except discord.NotFound:
                    logger.debug("Message %s already deleted", message.id)
                
                except Exception as e:
                    logger.error("Error deleting message %s: %s", message.id, e)
                    self.stats["errors"] += 1
        
        except discord.Forbidden:
            logger.warning("Missing permissions to read history in %s", channel.name)
            self.stats["errors"] += 1
        
        except Exception as e:
            logger.error("Error processing channel %s: %s", channel.name, e)
            self.stats["errors"] += 1
        
        return deleted_count

    async def cleanup_guild(
        self,
        guild: discord.Guild,
        bot_user: discord.User,
        since: Optional[datetime] = None,
        channel_filter: Optional[Set[int]] = None,
    ) -> dict:
        """Clean up bot messages in a guild.
        
        Args:
            guild: Guild to clean
            bot_user: Bot's user object
            since: Only delete messages after this timestamp
            channel_filter: Set of channel IDs to clean (None = all)
            
        Returns:
            dict: Cleanup statistics
        """
        guild_stats = {
            "guild_id": guild.id,
            "guild_name": guild.name,
            "channels_cleaned": 0,
            "channels_skipped": 0,
            "messages_deleted": 0,
        }
        
        logger.info("Starting cleanup in guild: %s", guild.name)
        
        for channel in guild.text_channels:
            # Apply channel filter if provided
            if channel_filter and channel.id not in channel_filter:
                continue
            
            # Check if channel should be skipped
            should_skip, reason = self._should_skip_channel(channel)
            if should_skip:
                logger.debug("Skipping channel %s: %s", channel.name, reason)
                guild_stats["channels_skipped"] += 1
                self.stats["channels_skipped"] += 1
                continue
            
            # Clean the channel
            deleted = await self.cleanup_channel(channel, bot_user, since)
            
            if deleted > 0:
                logger.info("Deleted %d messages from %s", deleted, channel.name)
                guild_stats["messages_deleted"] += deleted
                guild_stats["channels_cleaned"] += 1
                self.stats["messages_deleted"] += deleted
                self.stats["channels_cleaned"] += 1
        
        return guild_stats

    async def cleanup_old_messages(
        self,
        bot: discord.Client,
        guild_ids: Optional[List[int]] = None,
        since: Optional[datetime] = None,
    ) -> dict:
        """Clean up old bot messages across guilds.
        
        Args:
            bot: Discord bot client
            guild_ids: List of guild IDs to clean (None = all)
            since: Only delete messages after this timestamp
            
        Returns:
            dict: Overall cleanup statistics
        """
        if not self.config.get("enabled", True):
            logger.info("Cleanup is disabled in configuration")
            return self.stats
        
        self.stats["start_time"] = datetime.now(timezone.utc)
        
        # Determine which guilds to clean
        guilds_to_clean = []
        if guild_ids:
            for guild_id in guild_ids:
                guild = bot.get_guild(guild_id)
                if guild:
                    guilds_to_clean.append(guild)
                else:
                    logger.warning("Guild %d not found", guild_id)
        else:
            guilds_to_clean = bot.guilds
        
        logger.info(
            "Starting cleanup across %d guilds (since: %s)",
            len(guilds_to_clean),
            since or "beginning"
        )
        
        # Clean each guild
        guild_results = []
        for guild in guilds_to_clean:
            result = await self.cleanup_guild(guild, bot.user, since)
            guild_results.append(result)
        
        self.stats["end_time"] = datetime.now(timezone.utc)
        self.stats["duration_seconds"] = (
            self.stats["end_time"] - self.stats["start_time"]
        ).total_seconds()
        self.stats["guild_results"] = guild_results
        
        logger.info(
            "Cleanup complete: deleted %d messages across %d channels in %.2fs",
            self.stats["messages_deleted"],
            self.stats["channels_cleaned"],
            self.stats["duration_seconds"]
        )
        
        return self.stats

    def get_stats(self) -> dict:
        """Get cleanup statistics.
        
        Returns:
            dict: Current statistics
        """
        return self.stats.copy()


# Module-level helper functions
async def cleanup_old_messages(
    bot: discord.Client,
    guild_ids: Optional[List[int]] = None,
    since: Optional[datetime] = None,
    config: Optional[dict] = None,
) -> dict:
    """Clean up old bot messages (convenience function).
    
    Args:
        bot: Discord bot client
        guild_ids: List of guild IDs to clean (None = all)
        since: Only delete messages after this timestamp
        config: Cleanup configuration
        
    Returns:
        dict: Cleanup statistics
    """
    engine = CleanupEngine(config)
    return await engine.cleanup_old_messages(bot, guild_ids, since)
