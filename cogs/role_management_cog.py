from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core import ui_groups
from discord_bot.core.engines.role_manager import (
    AssignmentResult,
    AmbiguousLanguage,
    LanguageNotRecognized,
    RemovalResult,
    RoleLimitExceeded,
    RoleManager,
    RoleManagerError,
    RoleNotAssigned,
    RolePermissionError,
)

logger = logging.getLogger("hippo_bot.role_cog")


class RoleManagementCog(commands.Cog):
    """Modern language role management built on the new RoleManager engine."""

    # Reuse shared language command group to avoid duplicate registration.
    language = ui_groups.language

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

        result: AssignmentResult
        try:
            result = await self.roles.assign_language_role(member, code)
        except AmbiguousLanguage as exc:
            choices = "\n".join(f"- `{opt_code}` ({label})" for opt_code, label in exc.options)
            await interaction.followup.send(
                "That flag or keyword maps to multiple languages. Pick one by running `/language assign <code>`:\n"
                f"{choices}",
                ephemeral=True,
            )
            return
        except LanguageNotRecognized:
            await interaction.followup.send(
                "I couldn't recognise that language. Try short codes like `en`, `es`, or spell it out like `French`.",
                ephemeral=True,
            )
            return
        except RoleLimitExceeded as exc:
            await interaction.followup.send(
                f"You already have {exc.max_roles} language roles. Remove one with `/language remove` before adding another.",
                ephemeral=True,
            )
            return
        except RolePermissionError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            await self._log_error(exc, context="language.assign.permission")
            return
        except RoleManagerError as exc:
            await self._log_error(exc, context="language.assign")
            await interaction.followup.send("Failed to assign the role. Please try again later.", ephemeral=True)
            return

        if result.already_had:
            await interaction.followup.send(
                f"You already had `{result.role.name}`. I refreshed your preference to {result.display_name}.",
                ephemeral=True,
            )
            return

        verb = "Created and assigned" if result.created else "Assigned"
        await interaction.followup.send(
            f"{verb} `{result.role.name}` to {member.mention} (language: {result.display_name}).",
            ephemeral=True,
        )

    @assign.autocomplete("code")
    async def assign_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        if not self.roles:
            return []
        suggestions = self.roles.suggest_languages(current, limit=25)
        return [app_commands.Choice(name=f"{label} ({code})", value=code) for code, label in suggestions]

    @language.command(name="remove", description="Remove one of your language roles.")
    @app_commands.describe(code="Language code or role name to remove.")
    async def remove(self, interaction: discord.Interaction, code: str) -> None:
        member = await self._resolve_member(interaction)
        if not member or not member.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            result: RemovalResult = await self.roles.remove_language_role(member, code)
        except AmbiguousLanguage as exc:
            choices = "\n".join(f"- `{opt_code}` ({label})" for opt_code, label in exc.options)
            await interaction.followup.send(
                "That flag or keyword maps to multiple languages. Tell me which one to remove:\n"
                f"{choices}",
                ephemeral=True,
            )
            return
        except LanguageNotRecognized:
            await interaction.followup.send(
                "I couldn't recognise that language. Try a standard code like `en` or a full name like `Spanish`.",
                ephemeral=True,
            )
            return
        except RoleNotAssigned:
            await interaction.followup.send(
                "You don't currently have that language role. Use `/language list` to see which ones are active.",
                ephemeral=True,
            )
            return
        except RolePermissionError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            await self._log_error(exc, context="language.remove.permission")
            return
        except RoleManagerError as exc:
            await self._log_error(exc, context="language.remove")
            await interaction.followup.send("Failed to remove the role. Please try again later.", ephemeral=True)
            return

        await interaction.followup.send(
            f"Removed `{result.role.name}` (language: {result.display_name}).", ephemeral=True
        )

    @remove.autocomplete("code")
    async def remove_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        if not self.roles or not interaction.guild:
            return []
        member = await self._resolve_member(interaction)
        if not member:
            return []
        user_codes = await self.roles.get_user_languages(member.id, interaction.guild.id)
        suggestions = self.roles.suggest_languages(current, limit=25, restrict_to=user_codes)
        return [app_commands.Choice(name=f"{label} ({code})", value=code) for code, label in suggestions]

    @language.command(name="list", description="List your current language roles.")
    async def list_roles(self, interaction: discord.Interaction) -> None:
        member = await self._resolve_member(interaction)
        if not member or not member.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        entries = []
        if self.roles:
            for role in member.roles:
                code = self.roles.resolve_code(role.name)
                if code:
                    entries.append(f"- {self.roles.friendly_name(code)} (`{role.name}`)")

        if not entries:
            await interaction.response.send_message("You do not have any language roles yet.", ephemeral=True)
            return

        message = "**Your language roles:**\n" + "\n".join(entries)
        await interaction.response.send_message(message, ephemeral=True)

    @language.command(name="sync", description="Sync language roles in this guild with known codes.")
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
            created, recognised = await self.roles.sync_language_roles(interaction.guild)
            if created:
                msg = f"Role sync complete. Created {created} new language roles."
            else:
                msg = f"Role sync complete. Recognised {recognised} existing language roles."
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as exc:
            await self._log_error(exc, context="language.sync")
            await interaction.followup.send("Failed to sync language roles.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RoleManagementCog(bot))
