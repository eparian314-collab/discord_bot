from __future__ import annotations

import asyncio
import logging
from typing import Dict

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.utils import is_admin_or_helper

logger = logging.getLogger("hippo_bot.sos_cog")


class SOSPhraseCog(commands.Cog):
    """Manage SOS keyword -> phrase mappings that the InputEngine will broadcast."""

    sos = app_commands.Group(name="sos", description="Configure SOS keywords for this guild.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.input_engine = getattr(bot, "input_engine", None)
        self.error_engine = getattr(bot, "error_engine", None)
        self._local: Dict[int, Dict[str, str]] = {}

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to manage SOS phrases."""
        return is_admin_or_helper(interaction.user, interaction.guild)

    async def _deny_permission(self, interaction: discord.Interaction) -> None:
        """Send permission denied message."""
        msg = "You do not have permission to manage SOS phrases. This requires admin or helper role."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    def _get_mapping(self, guild_id: int) -> Dict[str, str]:
        if guild_id not in self._local:
            existing: Dict[str, str] = {}
            if self.input_engine and hasattr(self.input_engine, "get_sos_mapping"):
                try:
                    existing = self.input_engine.get_sos_mapping(guild_id)  # type: ignore[attr-defined]
                except Exception:
                    existing = {}
            self._local[guild_id] = {k.lower(): v for k, v in existing.items()}
        return self._local[guild_id]

    def _apply(self, guild_id: int) -> None:
        if self.input_engine and hasattr(self.input_engine, "set_sos_mapping"):
            try:
                self.input_engine.set_sos_mapping(guild_id, self._local[guild_id])  # type: ignore[attr-defined]
            except Exception as exc:
                logger.exception("Failed to apply SOS mapping for guild %s: %s", guild_id, exc)

    async def _log_error(self, exc: Exception, *, context: str) -> None:
        if self.error_engine and hasattr(self.error_engine, "log_error"):
            try:
                maybe = self.error_engine.log_error(exc, context=context)
                if asyncio.iscoroutine(maybe):
                    await maybe
                return
            except Exception:
                pass
        logger.exception("%s failed: %s", context, exc)

    @sos.command(name="add", description="Add or update an SOS keyword for this guild.")
    @app_commands.describe(keyword="Word or phrase to watch for", phrase="Alert text to broadcast")
    async def add(self, interaction: discord.Interaction, keyword: str, phrase: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used inside a guild.", ephemeral=True)
            return

        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return

        mapping = self._get_mapping(interaction.guild.id)
        mapping[keyword.lower()] = phrase
        self._apply(interaction.guild.id)

        await interaction.response.send_message(
            f"Linked keyword `{keyword}` to SOS phrase:\n> {phrase}", ephemeral=True
        )

    @sos.command(name="remove", description="Remove an SOS keyword mapping.")
    @app_commands.describe(keyword="Word or phrase to remove from the SOS mapping")
    async def remove(self, interaction: discord.Interaction, keyword: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used inside a guild.", ephemeral=True)
            return

        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return

        mapping = self._get_mapping(interaction.guild.id)
        lowered = keyword.lower()
        if lowered not in mapping:
            await interaction.response.send_message("That keyword is not currently configured.", ephemeral=True)
            return

        del mapping[lowered]
        self._apply(interaction.guild.id)
        await interaction.response.send_message(f"Removed SOS keyword `{keyword}`.", ephemeral=True)

    @sos.command(name="list", description="List configured SOS keywords for this guild.")
    async def list_keywords(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used inside a guild.", ephemeral=True)
            return

        mapping = self._get_mapping(interaction.guild.id)
        if not mapping:
            await interaction.response.send_message("No custom SOS keywords configured.", ephemeral=True)
            return

        lines = [f"- `{kw}` -> {text}" for kw, text in mapping.items()]
        content = "**Configured SOS keywords:**\n" + "\n".join(lines)
        await interaction.response.send_message(content, ephemeral=True)

    @sos.command(name="clear", description="Remove all SOS keywords for this guild.")
    async def clear(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used inside a guild.", ephemeral=True)
            return

        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return

        self._local.pop(interaction.guild.id, None)
        if self.input_engine and hasattr(self.input_engine, "set_sos_mapping"):
            try:
                self.input_engine.set_sos_mapping(interaction.guild.id, {})  # type: ignore[attr-defined]
            except Exception as exc:
                await self._log_error(exc, context="sos.clear.apply")

        await interaction.response.send_message("Cleared all SOS keywords for this guild.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SOSPhraseCog(bot))
