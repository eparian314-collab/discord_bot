"""
Shared command groups for organizing UI into logical layers.

This module defines the main command group structure to avoid circular imports
between cogs while maintaining a clean, layered UI organization.
"""
from __future__ import annotations

from discord import app_commands
from discord.ext import commands

# Main top-level groups
language = app_commands.Group(name="language", description="Language and communication tools")
games = app_commands.Group(name="games", description="Games and entertainment")
kvk = app_commands.Group(name="kvk", description="Top Heroes / KVK tools")
admin = app_commands.Group(name="admin", description="Administrative tools")

# Additional metadata for common subgroup names
LANGUAGE_SOS_NAME = "sos"
LANGUAGE_SOS_DESCRIPTION = "Configure SOS emergency phrases"

GAMES_POKEMON_NAME = "pokemon"
GAMES_POKEMON_DESCRIPTION = "Catch, train, and evolve Pokemon"

GAMES_BATTLE_NAME = "battle"
GAMES_BATTLE_DESCRIPTION = "Pokemon battles and competitions"

GAMES_FUN_NAME = "fun"
GAMES_FUN_DESCRIPTION = "Fun games and entertainment"

GAMES_COOKIES_NAME = "cookies"
GAMES_COOKIES_DESCRIPTION = "Manage your cookies and check stats"

KVK_RANKING_NAME = "ranking"
KVK_RANKING_DESCRIPTION = "Top Heroes event rankings and leaderboards"


def register_command_groups(bot: commands.Bot) -> None:
    """
    Register all top-level command groups with the bot's command tree.
    
    This MUST be called before any cogs that use these groups are loaded,
    otherwise the subcommands won't appear in Discord.
    
    Args:
        bot: The Discord bot instance
    """
    # Guard against double registration
    if hasattr(bot, '_ui_groups_registered'):
        import logging
        logging.getLogger("ui_groups").warning(
            "Command groups already registered - skipping duplicate registration"
        )
        return
    
    # Add only the TOP-LEVEL groups - subgroups are automatically included
    # Use override=True to avoid CommandAlreadyRegistered errors
    bot.tree.add_command(language, override=True)
    bot.tree.add_command(games, override=True)
    bot.tree.add_command(kvk, override=True)
    # Admin group is registered when the admin cog mounts to avoid double registration.
    
    # Mark as registered
    bot._ui_groups_registered = True
