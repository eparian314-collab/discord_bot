"""
Shared command groups for organizing UI into logical layers.

This module defines the main command group structure to avoid circular imports
between cogs while maintaining a clean, layered UI organization.
"""
from __future__ import annotations

from discord import app_commands
from discord.ext import commands

# Main top-level groups
language = app_commands.Group(name="language", description="🌍 Language and communication tools")
games = app_commands.Group(name="games", description="🎮 Games and entertainment")
admin = app_commands.Group(name="admin", description="⚙️ Administrative tools")

# Language subgroups
language_translate = app_commands.Group(
    name="translate", 
    description="🔄 Translation services",
    parent=language
)

language_roles = app_commands.Group(
    name="roles", 
    description="🎭 Manage your language roles",
    parent=language
)

language_sos = app_commands.Group(
    name="sos", 
    description="🚨 Configure SOS emergency phrases",
    parent=language
)

# Games subgroups  
games_pokemon = app_commands.Group(
    name="pokemon", 
    description="🎮 Catch, train, and evolve Pokemon!",
    parent=games
)

games_battle = app_commands.Group(
    name="battle", 
    description="⚔️ Pokemon battles and competitions",
    parent=games
)

games_fun = app_commands.Group(
    name="fun", 
    description="🎉 Fun games and entertainment!",
    parent=games
)

games_cookies = app_commands.Group(
    name="cookies",
    description="🍪 Manage your cookies and check stats",
    parent=games
)

games_ranking = app_commands.Group(
    name="ranking",
    description="📊 Top Heroes event rankings and leaderboards",
    parent=games
)


def register_command_groups(bot: commands.Bot) -> None:
    """
    Register all top-level command groups with the bot's command tree.
    
    This MUST be called before any cogs that use these groups are loaded,
    otherwise the subcommands won't appear in Discord.
    
    Args:
        bot: The Discord bot instance
    """
    # Add only the TOP-LEVEL groups - subgroups are automatically included
    # Use override=True to avoid CommandAlreadyRegistered errors
    bot.tree.add_command(language, override=True)
    bot.tree.add_command(games, override=True)
    bot.tree.add_command(admin, override=True)
