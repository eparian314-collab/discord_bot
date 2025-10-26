from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.engines.role_manager import RoleManager

logger = logging.getLogger("hippo_bot.role_cog")


class RoleManagementCog(commands.Cog):
    """Modern language role management built on the new RoleManager engine."""

    language = app_commands.Group(name="language", description="Manage language roles for yourself or the server.")

    def __init__(self, bot: commands.Bot, role_manager: Optional[RoleManager] = None) -> None:
        self.bot = bot
        self.roles = role_manager or getattr(bot, "role_manager", None)
        self.error_engine = getattr(bot, "error_engine", None)

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

    async def _resolve_member(self, interaction: discord.Interaction) -> Optional[discord.Member]:
        user = interaction.user
        if isinstance(user, discord.Member):
            return user
        if interaction.guild:
            try:
                return await interaction.guild.fetch_member(user.id)
            except discord.HTTPException:
                return None
        return None

    def _find_role(self, guild: discord.Guild, code: str) -> Optional[discord.Role]:
        if not self.roles:
            return None
        target = self.roles.resolve_code(code)
        if not target:
            return None
        for role in guild.roles:
            if self.roles.resolve_code(role.name) == target:
                return role
        return None

    @language.command(name="assign", description="Assign a language role to yourself.")
    @app_commands.describe(code="Language code or role name. Example: en, es, fr")
    async def assign(self, interaction: discord.Interaction, code: str) -> None:
        if not self.roles:
            await interaction.response.send_message("Role manager not configured.", ephemeral=True)
            return

        member = await self._resolve_member(interaction)
        if not member or not member.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            role = await self.roles.assign_language_role(member, code)
            if role:
                await interaction.followup.send(
                    f"Assigned `{role.name}` to {member.mention}.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Could not find a matching language role. Ask an admin to create it or use /language sync.",
                    ephemeral=True,
                )
        except Exception as exc:
            await self._log_error(exc, context="language.assign")
            await interaction.followup.send("Failed to assign the role. Please try again later.", ephemeral=True)

    @language.command(name="remove", description="Remove one of your language roles.")
    @app_commands.describe(code="Language code or role name to remove.")
    async def remove(self, interaction: discord.Interaction, code: str) -> None:
        member = await self._resolve_member(interaction)
        if not member or not member.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        role = self._find_role(member.guild, code)
        if not role or role not in member.roles:
            await interaction.followup.send(
                "You do not currently have that language role. Use `/language list` to see your roles.",
                ephemeral=True,
            )
            return

        try:
            await member.remove_roles(role, reason="Language role removal via command")
            await interaction.followup.send(f"Removed `{role.name}` from {member.mention}.", ephemeral=True)
        except Exception as exc:
            await self._log_error(exc, context="language.remove")
            await interaction.followup.send("Failed to remove the role. Please try again later.", ephemeral=True)

    @language.command(name="list", description="List your current language roles.")
    async def list_roles(self, interaction: discord.Interaction) -> None:
        member = await self._resolve_member(interaction)
        if not member or not member.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        entries = []
        resolver = self.roles.resolve_code if self.roles else (lambda name: name.lower())
        for role in member.roles:
            code = resolver(role.name)
            if code:
                entries.append(f"- {role.name} (`{code}`)")

        if not entries:
            await interaction.response.send_message("You do not have any language roles yet.", ephemeral=True)
            return

        message = "**Your language roles:**\n" + "\n".join(entries)
        await interaction.response.send_message(message, ephemeral=True)

    @language.command(name="sync", description="Sync language roles in this guild with known codes.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync(self, interaction: discord.Interaction) -> None:
        if not self.roles:
            await interaction.response.send_message("Role manager not configured.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("This command must be used inside a guild.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            created, _ = await self.roles.sync_language_roles(interaction.guild)
            await interaction.followup.send(
                f"Role sync complete. Created {created} new roles (if any).", ephemeral=True
            )
        except Exception as exc:
            await self._log_error(exc, context="language.sync")
            await interaction.followup.send("Failed to sync language roles.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RoleManagementCog(bot))
