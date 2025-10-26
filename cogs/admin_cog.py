from __future__ import annotations

from typing import Iterable, Optional, Set

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.engines.admin_ui_engine import AdminUIEngine


class AdminCog(commands.Cog):
    """Slash commands that surface the Admin UI engine capabilities."""

    def __init__(self, bot: commands.Bot, ui_engine: AdminUIEngine, owners: Optional[Set[int]] = None) -> None:
        self.bot = bot
        self.ui = ui_engine
        self.owners: Set[int] = set(owners or [])
        self._denied = "You do not have permission to run this command."

        # Surface the UI on the bot for other components that expect it.
        if not hasattr(bot, "admin_ui"):
            setattr(bot, "admin_ui", ui_engine)

    def _is_owner(self, user_id: int) -> bool:
        return not self.owners or user_id in self.owners

    async def _deny(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(self._denied, ephemeral=True)
        else:
            await interaction.response.send_message(self._denied, ephemeral=True)

    @app_commands.command(name="plugins", description="List registered engines/plugins and their readiness state.")
    async def plugins(self, interaction: discord.Interaction) -> None:
        if not self._is_owner(interaction.user.id):
            await self._deny(interaction)
            return
        await self.ui.handle_plugins_list(interaction=interaction)

    @app_commands.command(name="plugin_enable", description="Enable a plugin by name.")
    @app_commands.describe(name="Plugin name to enable")
    async def plugin_enable(self, interaction: discord.Interaction, name: str) -> None:
        if not self._is_owner(interaction.user.id):
            await self._deny(interaction)
            return
        await self.ui.handle_plugin_enable(interaction=interaction, name=name)

    @app_commands.command(name="plugin_disable", description="Disable a plugin by name.")
    @app_commands.describe(name="Plugin name to disable")
    async def plugin_disable(self, interaction: discord.Interaction, name: str) -> None:
        if not self._is_owner(interaction.user.id):
            await self._deny(interaction)
            return
        await self.ui.handle_plugin_disable(interaction=interaction, name=name)

    @app_commands.command(name="diag", description="Show diagnostics for the engine registry and guardian.")
    async def diag(self, interaction: discord.Interaction) -> None:
        if not self._is_owner(interaction.user.id):
            await self._deny(interaction)
            return
        await self.ui.handle_diag(interaction=interaction)


async def setup_admin_cog(
    bot: commands.Bot,
    ui_engine: AdminUIEngine,
    owners: Optional[Iterable[int]] = None,
) -> None:
    await bot.add_cog(AdminCog(bot, ui_engine, set(owners or [])))
