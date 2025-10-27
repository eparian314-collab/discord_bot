from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, TYPE_CHECKING
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.utils import is_admin_or_helper

if TYPE_CHECKING:
    from discord_bot.core.engines.admin_ui_engine import AdminUIEngine
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class PermissionError(Exception):
    """Raised when a user lacks permission to run an admin command."""



class AdminCog(commands.Cog):
    """Guild-level admin commands for managing keyword/phrase mappings."""

    keyword = app_commands.Group(
        name="keyword",
        description="Link and manage custom keywords for this guild.",
    )

    def __init__(
        self,
        bot: commands.Bot,
        ui_engine: Optional["AdminUIEngine"] = None,
        owners: Optional[Set[int]] = None,
        storage: Optional["GameStorageEngine"] = None,
    ) -> None:
        self.bot = bot
        self.ui = ui_engine  # retained for backwards compatibility / help text
        self.owners: Set[int] = set(owners or [])
        self.storage = storage  # For mute functionality
        self._cache: Dict[int, Dict[str, str]] = {}
        self._denied = "You do not have permission to run this command."
        self.input_engine = getattr(bot, "input_engine", None)

        if ui_engine and not hasattr(bot, "admin_ui"):
            setattr(bot, "admin_ui", ui_engine)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _has_permission(self, interaction: discord.Interaction) -> bool:
        # Check if user is admin or has helper role
        if is_admin_or_helper(interaction.user, interaction.guild):
            return True
        
        # Fallback: check legacy owner list
        if interaction.user.id in self.owners:
            return True
        
        # Check Discord permissions
        if not interaction.guild:
            return False
        perms = interaction.user.guild_permissions
        return perms.manage_guild or perms.administrator

    async def _deny(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(self._denied, ephemeral=True)
        else:
            await interaction.response.send_message(self._denied, ephemeral=True)

    def _ensure_permitted(self, interaction: discord.Interaction) -> None:
        if not self._has_permission(interaction):
            raise PermissionError()

    def _get_mapping(self, guild_id: int) -> Dict[str, str]:
        if guild_id in self._cache:
            return self._cache[guild_id]

        mapping: Dict[str, str] = {}
        if self.input_engine and hasattr(self.input_engine, "get_sos_mapping"):
            try:
                mapping = self.input_engine.get_sos_mapping(guild_id)  # type: ignore[attr-defined]
            except Exception:
                mapping = {}

        clean = {k.lower(): v for k, v in mapping.items()}
        self._cache[guild_id] = clean
        return clean

    def _save_mapping(self, guild_id: int, mapping: Dict[str, str]) -> None:
        clean = {k.lower(): v for k, v in mapping.items()}
        self._cache[guild_id] = clean

        if self.input_engine and hasattr(self.input_engine, "set_sos_mapping"):
            try:
                self.input_engine.set_sos_mapping(guild_id, clean)  # type: ignore[attr-defined]
            except Exception:
                pass

        # Keep SOSPhraseCog cache in sync if it's loaded.
        sos_cog = self.bot.get_cog("SOSPhraseCog")
        if sos_cog and hasattr(sos_cog, "_local"):
            sos_cog._local[guild_id] = dict(clean)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Keyword commands
    # ------------------------------------------------------------------
    @keyword.command(name="set", description="Link or update a keyword with a phrase for this guild.")
    @app_commands.describe(keyword="Word or phrase to watch for", phrase="Message to broadcast when triggered")
    async def keyword_set(self, interaction: discord.Interaction, keyword: str, phrase: str) -> None:
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        mapping = dict(self._get_mapping(interaction.guild.id))
        mapping[keyword.lower()] = phrase
        self._save_mapping(interaction.guild.id, mapping)

        await interaction.response.send_message(
            f"Linked keyword `{keyword}` to:\n> {phrase}",
            ephemeral=True,
        )

    @keyword.command(name="link", description="Assign an existing keyword's phrase to a new keyword.")
    @app_commands.describe(
        new_keyword="Keyword that should reuse the phrase.",
        existing_keyword="Existing keyword whose phrase will be reused.",
    )
    async def keyword_link(
        self,
        interaction: discord.Interaction,
        new_keyword: str,
        existing_keyword: str,
    ) -> None:
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        mapping = dict(self._get_mapping(interaction.guild.id))
        source = mapping.get(existing_keyword.lower())
        if not source:
            await interaction.response.send_message(
                f"`{existing_keyword}` is not linked to any phrase.",
                ephemeral=True,
            )
            return

        mapping[new_keyword.lower()] = source
        self._save_mapping(interaction.guild.id, mapping)

        await interaction.response.send_message(
            f"Linked keyword `{new_keyword}` to the existing phrase for `{existing_keyword}`.",
            ephemeral=True,
        )

    @keyword.command(name="remove", description="Remove a keyword mapping from this guild.")
    @app_commands.describe(keyword="Keyword to remove")
    async def keyword_remove(self, interaction: discord.Interaction, keyword: str) -> None:
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        mapping = dict(self._get_mapping(interaction.guild.id))
        lowered = keyword.lower()
        if lowered not in mapping:
            await interaction.response.send_message(
                f"`{keyword}` is not currently linked to a phrase.",
                ephemeral=True,
            )
            return

        del mapping[lowered]
        self._save_mapping(interaction.guild.id, mapping)

        await interaction.response.send_message(f"Removed keyword `{keyword}`.", ephemeral=True)

    @keyword.command(name="list", description="List the configured keywords for this guild.")
    async def keyword_list(self, interaction: discord.Interaction) -> None:
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        mapping = self._get_mapping(interaction.guild.id)
        if not mapping:
            await interaction.response.send_message("No keywords are currently configured.", ephemeral=True)
            return

        lines = [f"- `{kw}` -> {phrase}" for kw, phrase in mapping.items()]
        content = "**Configured keywords:**\n" + "\n".join(lines)
        await interaction.response.send_message(content, ephemeral=True)

    @keyword.command(name="clear", description="Remove every keyword mapping for this guild.")
    async def keyword_clear(self, interaction: discord.Interaction) -> None:
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        self._cache.pop(interaction.guild.id, None)
        self._save_mapping(interaction.guild.id, {})
        await interaction.response.send_message("Cleared all keywords for this guild.", ephemeral=True)
    
    # ------------------------------------------------------------------
    # Moderation commands (mute/unmute)
    # ------------------------------------------------------------------
    @app_commands.command(name="mute", description="Timeout a user for a specified duration")
    @app_commands.describe(
        member="The member to mute",
        duration="Duration in minutes (default: 5)",
        reason="Reason for the mute"
    )
    async def mute_user(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member,
        duration: int = 5,
        reason: Optional[str] = None
    ) -> None:
        """Mute (timeout) a user."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return
        
        # Check if bot has permission
        if not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ I don't have permission to timeout members!", ephemeral=True)
            return
        
        # Can't mute self or someone with higher role
        if member == interaction.user:
            await interaction.response.send_message("❌ You can't mute yourself!", ephemeral=True)
            return
        
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ You can't mute someone with equal or higher role!", ephemeral=True)
            return
        
        # Apply timeout
        try:
            timeout_duration = timedelta(minutes=duration)
            await member.timeout(timeout_duration, reason=reason or "Muted by moderator")
            
            # Track in database if storage available
            if self.storage:
                from datetime import datetime
                mute_until = datetime.utcnow() + timeout_duration
                self.storage.set_mute_until(str(member.id), mute_until)
                # Reset aggravation when manually muted
                self.storage.reset_aggravation(str(member.id))
            
            reason_text = f" (Reason: {reason})" if reason else ""
            await interaction.response.send_message(
                f"✅ {member.mention} has been muted for {duration} minutes{reason_text}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this user!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to mute user: {e}", ephemeral=True)
    
    @app_commands.command(name="unmute", description="Remove timeout from a user")
    @app_commands.describe(member="The member to unmute")
    async def unmute_user(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Unmute (remove timeout from) a user."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return
        
        # Check if bot has permission
        if not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ I don't have permission to manage timeouts!", ephemeral=True)
            return
        
        try:
            await member.timeout(None, reason="Unmuted by moderator")
            
            # Clear from database if storage available
            if self.storage:
                self.storage.clear_mute(str(member.id))
                self.storage.reset_aggravation(str(member.id))
            
            await interaction.response.send_message(
                f"✅ {member.mention} has been unmuted",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this user!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to unmute user: {e}", ephemeral=True)


async def setup_admin_cog(
    bot: commands.Bot,
    ui_engine: Optional["AdminUIEngine"] = None,
    owners: Optional[Iterable[int]] = None,
    storage: Optional["GameStorageEngine"] = None,
) -> None:
    await bot.add_cog(AdminCog(bot, ui_engine, set(owners or []), storage))
