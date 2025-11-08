from __future__ import annotations

import asyncio
import os
import time
import psutil
from typing import Any, Dict, Iterable, Optional, Set, TYPE_CHECKING
from datetime import timedelta, datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.utils import is_admin_or_helper
from discord_bot.core.engines.event_engine import EventEngine

if TYPE_CHECKING:
    from discord_bot.core.engines.admin_ui_engine import AdminUIEngine
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine
    from discord_bot.core.engines.cookie_manager import CookieManager


class PermissionError(Exception):
    """Raised when a user lacks permission to run an admin command."""



class AdminCog(commands.Cog):
    """Guild-level admin commands for managing keyword/phrase mappings."""

    keyword = app_commands.Group(
        name="keyword",
        description="🔑 Link and manage custom keywords for this guild",
    )
    
    admin = app_commands.Group(
        name="admin",
        description="🛡️ Moderation and administration tools"
    )
    bot = app_commands.Group(
        name="bot",
        description="HippoBot health and diagnostics",
    )


    def __init__(
        self,
        bot: commands.Bot,
        ui_engine: Optional["AdminUIEngine"] = None,
        owners: Optional[Set[int]] = None,
        storage: Optional["GameStorageEngine"] = None,
        cookie_manager: Optional["CookieManager"] = None,
        event_engine: Optional[EventEngine] = None,
    ) -> None:
        self.bot = bot
        self.ui = ui_engine  # retained for backwards compatibility / help text
        self.owners: Set[int] = set(owners or [])
        self.storage = storage  # For mute functionality
        self.cookie_manager = cookie_manager  # For cookie rewards
        self.event_engine = event_engine
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
        if self.input_engine and hasattr(self.input_engine, "save_sos_mapping"):
            self.input_engine.save_sos_mapping(guild_id, clean)  # type: ignore[attr-defined]

    @bot.command(name="status", description="Summarise reminder, KVK, and OCR health.")
    async def bot_status(self, interaction: discord.Interaction) -> None:
        """Provide a quick operational snapshot for admins."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        reminder_engine = getattr(self.bot, "event_reminder_engine", None)
        kvk_tracker = getattr(self.bot, "kvk_tracker", None)

        pending_reminders = 0
        next_event_label = "No scheduled events"
        if reminder_engine and interaction.guild:
            try:
                events = await reminder_engine.get_events_for_guild(interaction.guild.id)
            except Exception:
                events = []
            now = datetime.now(timezone.utc)
            upcoming: list[tuple[Any, datetime]] = []
            for event in events:
                if not getattr(event, "is_active", True):
                    continue
                next_time = event.get_next_occurrence(now)
                if next_time:
                    pending_reminders += 1
                    upcoming.append((event, next_time))
            upcoming.sort(key=lambda pair: pair[1])
            if upcoming:
                event, when = upcoming[0]
                next_event_label = f"{event.title} @ {when.strftime('%Y-%m-%d %H:%M UTC')}"

        run_summary = "Tracker unavailable"
        if kvk_tracker and interaction.guild:
            run = kvk_tracker.get_active_run(interaction.guild.id, include_tests=True)
            if run:
                label = "Test" if run.is_test else f"Run #{run.run_number}"
                run_summary = f"{label} active until {run.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
            else:
                run_summary = "No active run"

        ocr_enabled = os.getenv("ENABLE_OCR_TRAINING", "false").strip().lower() in {"1", "true", "yes"}

        embed = discord.Embed(
            title="HippoBot Status",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="KVK", value=run_summary, inline=False)
        embed.add_field(name="Pending reminders", value=str(pending_reminders), inline=True)
        embed.add_field(name="Next event", value=next_event_label, inline=True)
        embed.add_field(name="OCR training", value="enabled" if ocr_enabled else "disabled", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

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
    @admin.command(name="mute", description="⏸️ Timeout a user for a specified duration")
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
    
    @admin.command(name="unmute", description="▶️ Remove timeout from a user")
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

    # ------------------------------------------------------------------
    # Admin/Helper Cookie Give Command
    # ------------------------------------------------------------------
    @admin.command(name="give", description="🎁 Share your daily helper cookies with a community member")
    @app_commands.describe(
        member="The member to give cookies to",
        quantity="Number of cookies to give (defaults to 1, max 10)",
        reason="Optional reason for giving the cookies"
    )
    async def admin_give_cookie(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        quantity: app_commands.Range[int, 1, 10] = 1,
        reason: Optional[str] = None
    ) -> None:
        """Allow admins/helpers to share their daily cookie allowance."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return

        # Prevent giving to self
        if member == interaction.user:
            await interaction.response.send_message("❌ You can't give a cookie to yourself!", ephemeral=True)
            return

        if not self.cookie_manager or not self.storage:
            await interaction.response.send_message("❌ Cookie storage not available.", ephemeral=True)
            return

        giver_id = str(interaction.user.id)
        recipient_id = str(member.id)

        remaining = self.cookie_manager.get_admin_gift_remaining(giver_id)
        if remaining <= 0:
            await interaction.response.send_message(
                "🍪 You're out of helper cookies for today. Come back tomorrow!",
                ephemeral=True,
            )
            return

        amount = min(quantity, remaining, self.cookie_manager.ADMIN_DAILY_GIFT_POOL)
        gifted = self.cookie_manager.give_admin_gift(giver_id, recipient_id, amount)
        if gifted <= 0:
            await interaction.response.send_message(
                "🍪 You don't have enough helper cookies left to share that amount.",
                ephemeral=True,
            )
            return

        remaining_after = self.cookie_manager.get_admin_gift_remaining(giver_id)
        reason_text = f" (Reason: {reason})" if reason else ""
        await interaction.response.send_message(
            f"🎉 {member.mention} received {gifted} helper cookie(s)! "
            f"You have {remaining_after} left today.{reason_text}",
            ephemeral=True,
        )

    @admin.command(name="generate_event_report", description="Generate a summary report for KVK and GAR events.")
    async def generate_event_report(self, interaction: discord.Interaction):
        """Generates and sends the event summary report."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return

        await interaction.response.defer(ephemeral=True)
        
        if not self.event_engine:
            await interaction.followup.send("Event engine is not available.", ephemeral=True)
            return

        report_path = self.event_engine.generate_summary_report()
        
        await interaction.followup.send(
            "Generated event summary report.",
            file=discord.File(report_path),
            ephemeral=True
        )

    @admin.command(name="cleanup", description="🧹 Clean up my old messages from this channel")
    @app_commands.describe(limit="Maximum number of messages to check (default: 100)")
    async def cleanup_command(self, interaction: discord.Interaction, limit: int = 100):
        """Manually clean up bot messages in the current channel."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return
        
        # Validate limit
        if limit < 1 or limit > 500:
            await interaction.response.send_message(
                "❌ Limit must be between 1 and 500.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            deleted = 0
            skipped = 0
            errors = 0
            
            # Fetch and delete messages
            async for msg in interaction.channel.history(limit=limit):
                if msg.author.id != self.bot.user.id:
                    continue
                
                # Skip pinned messages
                if msg.pinned:
                    skipped += 1
                    continue
                
                # Skip messages with "DO NOT DELETE" or similar
                if any(keyword in msg.content.upper() for keyword in ["DO NOT DELETE", "SYSTEM NOTICE", "IMPORTANT"]):
                    skipped += 1
                    continue
                
                try:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.5)  # Rate limit protection
                except discord.Forbidden:
                    errors += 1
                except discord.NotFound:
                    pass  # Already deleted
                except Exception:
                    errors += 1
            
            # Build response
            response_parts = [f"✅ Deleted **{deleted}** message(s)."]
            if skipped > 0:
                response_parts.append(f"⏭️ Skipped **{skipped}** (pinned/important).")
            if errors > 0:
                response_parts.append(f"⚠️ **{errors}** error(s) occurred.")
            
            await interaction.followup.send(
                "\n".join(response_parts),
                ephemeral=True
            )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Cleanup failed: {str(e)}",
                ephemeral=True
            )

    @admin.command(name="selfcheck", description="🔍 Check bot health and performance metrics")
    async def selfcheck_command(self, interaction: discord.Interaction):
        """Run diagnostic health check on the bot."""
        try:
            self._ensure_permitted(interaction)
        except PermissionError:
            await self._deny(interaction)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Measure response time
            start_time = time.time()
            
            # Get process information
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Get bot latency
            latency_ms = round(self.bot.latency * 1000, 2)
            
            # Count tasks
            all_tasks = asyncio.all_tasks()
            running_tasks = len([t for t in all_tasks if not t.done()])
            
            # Get uptime (from session manager if available)
            try:
                from discord_bot.core.engines.session_manager import get_session_manager
                session_mgr = get_session_manager()
                session_start = session_mgr.get_current_session_time()
                if session_start:
                    uptime = datetime.now(timezone.utc) - session_start
                    uptime_str = str(uptime).split('.')[0]  # Remove microseconds
                else:
                    uptime_str = "Unknown"
            except:
                uptime_str = "Unknown"
            
            # Calculate response time
            response_time_ms = round((time.time() - start_time) * 1000, 2)
            
            # Build health report embed
            embed = discord.Embed(
                title="🔍 Bot Health Check",
                description="System diagnostics and performance metrics",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Performance metrics
            embed.add_field(
                name="⚡ Performance",
                value=f"**Latency**: {latency_ms}ms\n"
                      f"**Response Time**: {response_time_ms}ms\n"
                      f"**Status**: {'🟢 Healthy' if latency_ms < 500 else '🟡 Slow' if latency_ms < 1000 else '🔴 Degraded'}",
                inline=True
            )
            
            # System resources
            embed.add_field(
                name="💾 Resources",
                value=f"**Memory**: {memory_mb:.1f} MB\n"
                      f"**Tasks**: {running_tasks} active\n"
                      f"**Guilds**: {len(self.bot.guilds)}",
                inline=True
            )
            
            # Runtime info
            embed.add_field(
                name="⏱️ Runtime",
                value=f"**Uptime**: {uptime_str}\n"
                      f"**User**: {self.bot.user.name}\n"
                      f"**ID**: {self.bot.user.id}",
                inline=True
            )
            
            # Event loop health
            loop = asyncio.get_event_loop()
            loop_running = loop.is_running()
            loop_closed = loop.is_closed()
            
            embed.add_field(
                name="🔄 Event Loop",
                value=f"**Status**: {'🟢 Running' if loop_running and not loop_closed else '🔴 Stopped'}\n"
                      f"**Closed**: {'Yes' if loop_closed else 'No'}",
                inline=True
            )
            
            # Cog status
            loaded_cogs = len(self.bot.cogs)
            embed.add_field(
                name="🧩 Cogs",
                value=f"**Loaded**: {loaded_cogs}\n"
                      f"**Commands**: {len(self.bot.tree.get_commands())}",
                inline=True
            )
            
            # Overall status
            overall_health = "🟢 Healthy" if latency_ms < 500 and memory_mb < 500 else "🟡 Monitor" if latency_ms < 1000 else "🔴 Issues Detected"
            embed.add_field(
                name="📊 Overall Status",
                value=overall_health,
                inline=True
            )
            
            embed.set_footer(text="Use /admin cleanup to free up resources if needed")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Selfcheck failed: {str(e)}",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    """Standard setup, called by the bot to load the cog."""
    owners = getattr(bot, "owner_ids", set())
    ui_engine = getattr(bot, "admin_ui", None)
    storage = getattr(bot, "game_storage", None)
    cookie_manager = getattr(bot, "cookie_manager", None)
    event_engine = bot.get_engine("event_engine")
    
    await bot.add_cog(AdminCog(bot, ui_engine, owners, storage, cookie_manager, event_engine))
