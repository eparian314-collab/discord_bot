"""
Event Ranking Cog - Submit and view Top Heroes event rankings.

Commands:
- /kvk ranking submit - Submit a screenshot of your event ranking (RANKINGS CHANNEL ONLY!)
- /kvk ranking view - View your ranking history
- /kvk ranking leaderboard - View guild leaderboard
- /kvk ranking stats - View submission statistics
"""

from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, TYPE_CHECKING, List, Dict, Any
import aiohttp
import os

from discord_bot.core.engines.screenshot_processor import StageType
from discord_bot.core.utils import find_bot_channel, is_admin_or_helper
from discord_bot.core import ui_groups

if TYPE_CHECKING:
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor, StageType
    from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
    from discord_bot.core.engines.kvk_tracker import KVKRun


class RankingCog(commands.Cog):
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only act in rankings channel, ignore bot and command messages
        if (
            message.channel and
            self._rankings_channel_id and
            message.channel.id == self._rankings_channel_id and
            not message.author.bot and
            not message.content.startswith("/")
        ):
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.author.send(
                    "This channel is reserved for ranking submissions and commands only. "
                    "Please use the available slash commands: /kvk ranking submit, /kvk ranking view, /kvk ranking leaderboard, /ranking_compare_me, /ranking_compare_others."
                )
            except Exception:
                pass
    """Top Heroes event ranking commands."""
    
    # Use ranking group from ui_groups
    ranking = ui_groups.kvk_ranking
    
    def __init__(
        self,
        bot: commands.Bot,
        processor: ScreenshotProcessor,
        storage: RankingStorageEngine,
        kvk_tracker=None
    ):
        self.bot = bot
        self.processor = processor
        self.storage = storage
        self._rankings_channel_id = self._get_rankings_channel_id()
        self.kvk_tracker = kvk_tracker or getattr(bot, "kvk_tracker", None)
        self.bot.loop.create_task(self._post_guidance_message())

    async def _post_guidance_message(self):
        await self.bot.wait_until_ready()
        channel_id = self._rankings_channel_id
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        guidance = (
            "📢 **Rankings Channel Guidance**\n"
            "This channel is reserved for Top Heroes event ranking submissions and commands only.\n\n"
            "**Allowed actions:**\n"
            "• Submit your event ranking screenshot using `/kvk ranking submit`\n"
            "• View your ranking history with `/kvk ranking view`\n"
            "• See the leaderboard with `/kvk ranking leaderboard`\n"
            "• Compare your results with `/ranking_compare_me` and `/ranking_compare_others`\n\n"
            "Please do not chat or post unrelated messages here. Use the available slash commands for all ranking-related actions."
        )
        # Try to find an existing guidance message
        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user and "Rankings Channel Guidance" in msg.content:
                return  # Already posted
        await channel.send(guidance)

    def __getattribute__(self, name: str):
        value = object.__getattribute__(self, name)
        if isinstance(value, app_commands.Command):
            return value.callback.__get__(self, type(self))
        return value
    
    def _get_rankings_channel_id(self) -> Optional[int]:
        """Get the dedicated rankings channel ID from environment."""
        raw = os.getenv("RANKINGS_CHANNEL_ID", "")
        if not raw:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None
    
    def _get_modlog_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Find the modlog channel in guild."""
        # Look for channel named "modlog" or "mod-log"
        for channel in guild.text_channels:
            if channel.name.lower() in ['modlog', 'mod-log', 'mod_log']:
                return channel
        return None
    
    async def _send_to_modlog(self, guild: discord.Guild, embed: discord.Embed):
        """Send a message to modlog channel."""
        modlog = self._get_modlog_channel(guild)
        if modlog:
            try:
                await modlog.send(embed=embed)
            except:
                pass  # Silently fail if can't post

    def _resolve_kvk_run(self, interaction: discord.Interaction) -> tuple[Optional["KVKRun"], bool]:
        if not interaction.guild or not self.kvk_tracker:
            return None, False
        run = self.kvk_tracker.get_active_run(interaction.guild.id, include_tests=True)
        if run:
            return run, run.is_active
        runs = self.kvk_tracker.list_runs(interaction.guild.id, include_tests=True)
        if runs:
            return runs[0], False
        return None, False

    def _format_event_week_label(self, kvk_run: Optional["KVKRun"]) -> str:
        if not kvk_run:
            return self.storage.get_current_event_week()
        if getattr(kvk_run, "is_test", False):
            return f"KVK-TEST-{kvk_run.id}"
        if getattr(kvk_run, "run_number", None):
            return f"KVK-{int(kvk_run.run_number):02d}"
        return f"KVK-{kvk_run.id}"

    def _normalize_day(self, stage_type: "StageType", day: int) -> int:
        if stage_type == StageType.WAR:
            return 6
        return day

    def _format_day_label(self, day: int, stage_type: "StageType") -> str:
        if day == 6:
            return "War Stage"
        if day == -1:
            return "Prep Stage Total"
        if stage_type == StageType.PREP:
            mapping = {
                1: "Construction Day",
                2: "Research Day",
                3: "Resource & Mob Day",
                4: "Hero Day",
                5: "Troop Training Day",
            }
            return mapping.get(day, f"Day {day}")
        return f"Day {day}"

    def _aggregate_entries(self, entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not entries:
            return None
        scores = [row.get("score", 0) for row in entries]
        ranks = [row.get("rank") for row in entries if row.get("rank") is not None]
        return {
            "score": sum(scores),
            "rank": min(ranks) if ranks else None,
            "samples": len(entries),
        }

    def _format_run_header(self, kvk_run: "KVKRun") -> str:
        run_label = "Test run" if kvk_run.is_test else f"Run #{kvk_run.run_number}"
        window = f"{kvk_run.started_at.strftime('%Y-%m-%d %H:%M UTC')} - {kvk_run.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
        status = "active" if kvk_run.is_active else "closed"
        return f"{run_label} | {window} | {status}"

    def _validate_day_argument(self, day: Optional[int]) -> Optional[int]:
        if day is None:
            return None
        if day < 1 or day > 6:
            raise ValueError("Day must be between 1 and 6")
        return day

    def _fetch_user_stat(self, run_id: int, user_id: int, day: Optional[int]) -> Optional[Dict[str, Any]]:
        if not self.kvk_tracker:
            return None
        if day is not None:
            entries = self.kvk_tracker.fetch_user_entries(
                run_id=run_id,
                user_id=user_id,
                day_number=day,
            )
            if not entries:
                return None
            entry = dict(entries[0])
            entry.setdefault("kvk_day", day)
            return entry
        entries = self.kvk_tracker.fetch_user_entries(
            run_id=run_id,
            user_id=user_id,
        )
        aggregated = self._aggregate_entries(entries)
        if not aggregated:
            return None
        aggregated["kvk_day"] = None
        aggregated["entries"] = entries
        return aggregated

    def _fetch_peers(self, run_id: int, day: Optional[int], limit: int = 100) -> List[Dict[str, Any]]:
        if not self.kvk_tracker:
            return []
        return self.kvk_tracker.fetch_leaderboard(
            run_id=run_id,
            day_number=day,
            limit=limit,
        )
    
    async def _check_rankings_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in the dedicated rankings channel."""
        if not interaction.channel:
            return False
        
        # If no rankings channel configured, allow in any channel
        if not self._rankings_channel_id:
            msg = (
                "❌ **Rankings channel not configured!**\n"
                "Please ask a server admin to set `RANKINGS_CHANNEL_ID` in the bot's `.env` file.\n\n"
                "This is the dedicated channel where members submit their Top Heroes event rankings."
            )
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return False
        
        # Must be in the rankings channel
        if interaction.channel.id != self._rankings_channel_id:
            channel_mention = f"<#{self._rankings_channel_id}>"
            msg = (
                f"📊 **Rankings submissions can only be done in {channel_mention}!**\n\n"
                f"This keeps all event rankings organized in one place.\n"
                f"Please go to {channel_mention} to submit your screenshot."
            )
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return False
        
        return True
    
    @ranking.command(
        name="submit",
        description="Submit a screenshot of your Top Heroes event ranking"
    )
    @app_commands.describe(
        screenshot="Upload your ranking screenshot",
        day="Which day is this for? (1-5 for prep, ignored for war)",
        stage="Which stage? (Prep or War)"
    )
    async def submit_ranking(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        day: int,
        stage: str
    ):
        """Submit an event ranking screenshot."""
        if not await self._check_rankings_channel(interaction):
            return

        kvk_run, run_is_active = self._resolve_kvk_run(interaction)
        is_admin = is_admin_or_helper(interaction.user, interaction.guild)
        if not kvk_run:
            await interaction.response.send_message(
                "No tracked KVK window is currently open. Please wait for the next KVK reminder.",
                ephemeral=True,
            )
            return

        if not run_is_active and not is_admin:
            closed_at = kvk_run.ends_at.strftime('%Y-%m-%d %H:%M UTC')
            await interaction.response.send_message(
                f"The KVK submission window closed on {closed_at}. Only admins or helpers can submit late updates.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        stage_lower = stage.lower()
        if stage_lower not in ("prep", "war"):
            await interaction.followup.send(
                "Stage must be 'Prep' or 'War'.",
                ephemeral=True,
            )
            return
        stage_type = StageType.PREP if stage_lower == "prep" else StageType.WAR

        if stage_type == StageType.PREP:
            if day < 1 or day > 5:
                await interaction.followup.send(
                    "Day must be between 1 and 5 for the prep stage.",
                    ephemeral=True,
                )
                return
        else:
            day = 6  # War stage is treated as the sixth slot

        if not screenshot.content_type or not screenshot.content_type.startswith('image/'):
            await interaction.followup.send(
                "Please upload an image file (PNG, JPG, etc.).",
                ephemeral=True,
            )
            return

        if screenshot.size > 10 * 1024 * 1024:
            await interaction.followup.send(
                "Image too large. Please upload a screenshot under 10MB.",
                ephemeral=True,
            )
            return

        event_week = self._format_event_week_label(kvk_run)
        normalized_day = self._normalize_day(stage_type, day)

        existing = self.storage.check_duplicate_submission(
            str(interaction.user.id),
            str(interaction.guild_id) if interaction.guild else "0",
            event_week,
            stage_type,
            normalized_day,
            kvk_run_id=kvk_run.id,
        )

        if existing:
            await interaction.followup.send(
                "You already submitted data for this run and day. The previous entry will be replaced.",
                ephemeral=True,
            )

        image_data = await screenshot.read()
        is_valid, error_msg = await self.processor.validate_screenshot(image_data)
        if not is_valid:
            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild else None,
                "failed",
                error_message=error_msg,
            )
            await interaction.followup.send(
                f"Screenshot validation failed: {error_msg}",
                ephemeral=True,
            )
            return

        ranking = await self.processor.process_screenshot(
            image_data,
            str(interaction.user.id),
            interaction.user.name,
            str(interaction.guild_id) if interaction.guild else None,
        )

        if not ranking:
            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild else None,
                "failed",
                error_message="Could not extract ranking data from image",
            )
            await interaction.followup.send(
                "Could not read ranking data from the screenshot. Please ensure all required information is visible.",
                ephemeral=True,
            )
            return

        detected_stage = ranking.stage_type
        if stage_type == StageType.PREP and ranking.day_number and ranking.day_number != normalized_day:
            await interaction.followup.send(
                "The highlighted day in the screenshot does not match the selected day.",
                ephemeral=True,
            )
            return

        if detected_stage not in (StageType.UNKNOWN, stage_type):
            await interaction.followup.send(
                "The screenshot appears to show a different stage than selected.",
                ephemeral=True,
            )
            return

        ranking.stage_type = stage_type
        ranking.day_number = normalized_day
        ranking.screenshot_url = screenshot.url
        ranking.event_week = event_week
        ranking.kvk_run_id = kvk_run.id
        ranking.is_test_run = kvk_run.is_test

        if existing:
            self.storage.update_ranking(
                existing["id"],
                ranking.rank,
                ranking.score,
                screenshot.url,
            )
            target_ranking_id = existing["id"]
            action = "Updated"
        else:
            target_ranking_id = self.storage.save_ranking(ranking)
            action = "Submitted"

        if self.kvk_tracker:
            self.kvk_tracker.record_submission(
                kvk_run_id=kvk_run.id,
                ranking_id=target_ranking_id,
                user_id=interaction.user.id,
                day_number=normalized_day,
                stage_type=ranking.stage_type.value,
                is_test=kvk_run.is_test,
            )

        self.storage.log_submission(
            str(interaction.user.id),
            str(interaction.guild_id) if interaction.guild else None,
            "success",
            ranking_id=target_ranking_id,
        )

        embed = discord.Embed(
            title=f"{action} ranking entry",
            description=f"Tracking label: {ranking.event_week}",
            color=discord.Color.green(),
            timestamp=ranking.submitted_at,
        )
        embed.add_field(
            name="Stored data",
            value=(
                f"Guild tag: {ranking.guild_tag or 'N/A'}\n"
                f"Player: {ranking.player_name or interaction.user.name}\n"
                f"Day: {self._format_day_label(normalized_day, stage_type)}\n"
                f"Rank: #{ranking.rank}\n"
                f"Score: {ranking.score:,}"
            ),
            inline=False,
        )
        run_label = "Test run" if kvk_run.is_test else f"Run #{kvk_run.run_number}"
        window_text = f"{kvk_run.started_at.strftime('%Y-%m-%d %H:%M UTC')} - {kvk_run.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
        status_text = "active" if run_is_active else "closed (admin update)"
        embed.add_field(
            name="KVK window",
            value=f"{run_label}\nPeriod: {window_text}\nStatus: {status_text}",
            inline=False,
        )
        embed.set_thumbnail(url=screenshot.url)
        embed.set_footer(text="Data saved to rankings database")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @ranking.command(
        name="view",
        description="📋 View your ranking submission history"
    )
    @app_commands.describe(
        limit="How many recent submissions to show (default: 5)"
    )
    async def view_rankings(
        self,
        interaction: discord.Interaction,
        limit: Optional[int] = 5
    ):
        """View your ranking history."""
        await interaction.response.defer(ephemeral=True)
        
        rankings = self.storage.get_user_rankings(
            str(interaction.user.id),
            str(interaction.guild_id) if interaction.guild else None,
            limit=min(limit, 20)
        )
        
        if not rankings:
            await interaction.followup.send(
                "📭 You haven't submitted any rankings yet! "
                "Use `/kvk ranking submit` to submit your first screenshot.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"📊 Your Ranking History",
            description=f"Showing your last {len(rankings)} submission(s)",
            color=discord.Color.blue()
        )
        
        for i, ranking in enumerate(rankings, 1):
            day_num = ranking.get('day_number', '?')
            category = ranking.get('category', 'Unknown')
            stage = ranking.get('stage_type', 'Unknown')
            rank = ranking.get('rank', 0)
            score = ranking.get('score', 0)
            
            embed.add_field(
                name=f"{i}. Day {day_num} - {stage}",
                value=f"**{category}**\n"
                      f"Rank: #{rank:,}\n"
                      f"Score: {score:,}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @ranking.command(
        name="leaderboard",
        description="🏆 View guild leaderboard for event rankings"
    )
    @app_commands.describe(
        day="Filter by day (1-5)",
        stage="Filter by stage (Prep or War)",
        guild_tag="Filter by guild tag (e.g., TAO)",
        show_all_weeks="Show all-time rankings instead of current week"
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        day: Optional[int] = None,
        stage: Optional[str] = None,
        guild_tag: Optional[str] = "TAO",
        show_all_weeks: Optional[bool] = False
    ):
        """View guild leaderboard."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Parse filters
        from discord_bot.core.engines.screenshot_processor import StageType
        stage_type = None
        if stage:
            stage_lower = stage.lower()
            if stage_lower == 'prep':
                stage_type = StageType.PREP
            elif stage_lower == 'war':
                stage_type = StageType.WAR
        
        # Default to current week unless show_all_weeks is True
        event_week = None if show_all_weeks else self.storage.get_current_event_week()
        
        leaderboard = self.storage.get_guild_leaderboard(
            str(interaction.guild.id),
            event_week=event_week,
            stage_type=stage_type,
            day_number=day,
            guild_tag=guild_tag,
            limit=20
        )
        
        if not leaderboard:
            week_text = f" for week {event_week}" if event_week else " (all-time)"
            await interaction.followup.send(
                f"📭 No rankings found{week_text} with these filters!\n\n"
                f"**Current filters:**\n"
                f"{'• Day: ' + str(day) if day else ''}\n"
                f"{'• Stage: ' + stage.title() if stage else ''}\n"
                f"{'• Guild Tag: ' + guild_tag if guild_tag else ''}\n\n"
                f"Try removing some filters or wait for members to submit rankings.",
                ephemeral=True
            )
            return
        
        # Build embed
        title = "🏆 Top Heroes Leaderboard"
        if guild_tag:
            title += f" - [{guild_tag}]"
        if event_week and not show_all_weeks:
            title += f" - Week {event_week}"
        else:
            title += " - All Time"
        if day:
            title += f" - Day {day}"
        if stage:
            title += f" - {stage.title()} Stage"
        
        embed = discord.Embed(
            title=title,
            description=f"Showing top {len(leaderboard)} players",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for i, entry in enumerate(leaderboard, 1):
            medal = medals[i-1] if i <= 3 else f"**{i}.**"
            player_name = entry.get('player_name', entry.get('username', 'Unknown'))
            guild_tag_str = entry.get('guild_tag', '')
            if guild_tag_str:
                player_name = f"[{guild_tag_str}] {player_name}"
            
            rank = entry.get('best_rank', 0)
            score = entry.get('highest_score', 0)
            category = entry.get('category', 'Unknown')
            
            embed.add_field(
                name=f"{medal} {player_name}",
                value=f"Rank: #{rank:,} | Score: {score:,}\n{category}",
                inline=False
            )
        
        embed.set_footer(text=f"Current Event Week: {self.storage.get_current_event_week()}")
        
        await interaction.followup.send(embed=embed)
    
    @ranking.command(
        name="report",
        description="📊 [ADMIN] Get current rankings report for the guild"
    )
    @app_commands.describe(
        week="Event week (YYYY-WW format), leave empty for current week",
        day="Filter by specific day (1-5)",
        stage="Filter by stage (Prep or War)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_report(
        self,
        interaction: discord.Interaction,
        week: Optional[str] = None,
        day: Optional[int] = None,
        stage: Optional[str] = None
    ):
        """Generate a rankings report for admins."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Parse filters
        from discord_bot.core.engines.screenshot_processor import StageType
        stage_type = None
        if stage:
            stage_lower = stage.lower()
            if stage_lower == 'prep':
                stage_type = StageType.PREP
            elif stage_lower == 'war':
                stage_type = StageType.WAR
        
        # Use provided week or current week
        event_week = week or self.storage.get_current_event_week()
        
        # Get all submissions for this week
        leaderboard = self.storage.get_guild_leaderboard(
            str(interaction.guild.id),
            event_week=event_week,
            stage_type=stage_type,
            day_number=day,
            guild_tag="TAO",  # Default to TAO guild
            limit=50
        )
        
        if not leaderboard:
            await interaction.followup.send(
                f"📭 No rankings found for week {event_week}!",
                ephemeral=True
            )
            return
        
        # Build comprehensive report embed
        title = f"📊 Rankings Report - Week {event_week}"
        if day:
            title += f" - Day {day}"
        if stage:
            title += f" - {stage.title()} Stage"
        
        embed = discord.Embed(
            title=title,
            description=f"**Total Submissions:** {len(leaderboard)} members",
            color=discord.Color.gold()
        )
        
        # Group by category if no day filter
        if not day:
            # Count submissions per day
            day_counts = {}
            for entry in leaderboard:
                day_num = entry.get('day_number', 0)
                day_counts[day_num] = day_counts.get(day_num, 0) + 1
            
            embed.add_field(
                name="📅 Submissions by Day",
                value="\n".join([
                    f"Day {d}: {count} members" 
                    for d, count in sorted(day_counts.items())
                ]),
                inline=False
            )
        
        # Show top 10
        embed.add_field(
            name="🏆 Top 10 Rankings",
            value="\n".join([
                f"{i}. [{entry.get('guild_tag', 'N/A')}] {entry.get('player_name', entry.get('username', 'Unknown'))} - "
                f"Rank #{entry.get('best_rank', 0):,} ({entry.get('highest_score', 0):,} pts)"
                for i, entry in enumerate(leaderboard[:10], 1)
            ]) or "No rankings yet",
            inline=False
        )
        
        embed.set_footer(text=f"Report generated by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Also send to modlog
        modlog_embed = embed.copy()
        modlog_embed.title = f"📋 Admin Report Requested - {interaction.user.name}"
        await self._send_to_modlog(interaction.guild, modlog_embed)
    
    @ranking.command(
        name="stats",
        description="📊 [ADMIN] View submission statistics"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_stats(
        self,
        interaction: discord.Interaction
    ):
        """View submission statistics."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get stats
        stats = self.storage.get_submission_stats(
            str(interaction.guild.id),
            days=7
        )
        
        current_week = self.storage.get_current_event_week()
        
        embed = discord.Embed(
            title="📊 Ranking Submission Statistics",
            description=f"**Current Event Week:** {current_week}\n**Last 7 days**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Total Submissions",
            value=f"{stats.get('total_submissions', 0)} submissions",
            inline=True
        )
        
        embed.add_field(
            name="Successful",
            value=f"✅ {stats.get('successful', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="Failed",
            value=f"❌ {stats.get('failed', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="Unique Users",
            value=f"👥 {stats.get('unique_users', 0)} members",
            inline=True
        )
        
        # Calculate success rate
        total = stats.get('total_submissions', 0)
        successful = stats.get('successful', 0)
        if total > 0:
            success_rate = (successful / total) * 100
            embed.add_field(
                name="Success Rate",
                value=f"📈 {success_rate:.1f}%",
                inline=True
            )
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @ranking.command(
        name="user",
        description="👤 [ADMIN] View a specific user's submission history"
    )
    @app_commands.describe(
        user="The user to look up"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_user_lookup(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):
        """View a specific user's ranking submissions."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get user's rankings
        user_rankings = self.storage.get_user_rankings(
            str(user.id),
            str(interaction.guild.id)
        )
        
        if not user_rankings:
            await interaction.followup.send(
                f"📭 {user.mention} has not submitted any rankings yet!",
                ephemeral=True
            )
            return
        
        current_week = self.storage.get_current_event_week()
        
        embed = discord.Embed(
            title=f"👤 Ranking History - {user.name}",
            description=f"**Total Submissions:** {len(user_rankings)}",
            color=discord.Color.purple()
        )
        
        # Show current week submissions
        current_week_data = [r for r in user_rankings if r.get('event_week') == current_week]
        if current_week_data:
            embed.add_field(
                name=f"📅 Current Week ({current_week})",
                value="\n".join([
                    f"**Day {r.get('day_number', 'N/A')}** - [{r.get('guild_tag', 'N/A')}] {r.get('player_name', 'Unknown')}\n"
                    f"  Rank #{r.get('rank', 0):,} | Score: {r.get('score', 0):,} pts"
                    for r in current_week_data[:5]
                ]) or "No submissions this week",
                inline=False
            )
        
        # Show best performances
        best_rank = min([r.get('rank', 999999) for r in user_rankings])
        best_score = max([r.get('score', 0) for r in user_rankings])
        
        embed.add_field(
            name="🏆 Best Performance",
            value=f"**Best Rank:** #{best_rank:,}\n**Highest Score:** {best_score:,} pts",
            inline=True
        )
        
        # Show recent submissions
        recent = user_rankings[:5]
        embed.add_field(
            name="🕐 Recent Submissions",
            value="\n".join([
                f"Week {r.get('event_week', 'N/A')} - Day {r.get('day_number', 'N/A')}"
                for r in recent
            ]) or "No recent submissions",
            inline=True
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


    @app_commands.command(name="rankings", description="View your KVK results for a specific run")
    @app_commands.describe(
        run="KVK run number (starting at 1)",
        day="Optional day (1-6; 6 represents the war stage total)"
    )
    async def rankings(self, interaction: discord.Interaction, run: int, day: Optional[int] = None):
        """Retrieve stored KVK data for the requesting user."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return
        if not self.kvk_tracker:
            await interaction.response.send_message("KVK tracking is not configured for this bot.", ephemeral=True)
            return
        if run < 1:
            await interaction.response.send_message("Run number must be at least 1.", ephemeral=True)
            return
        try:
            day = self._validate_day_argument(day)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        kvk_run = self.kvk_tracker.get_run_by_number(interaction.guild.id, run)
        if not kvk_run:
            await interaction.response.send_message(f"KVK run #{run} has not been tracked yet.", ephemeral=True)
            return

        user_stat = self._fetch_user_stat(kvk_run.id, interaction.user.id, day)
        if not user_stat:
            label = f"day {day}" if day else "this run"
            await interaction.response.send_message(f"No submission found for {label}.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"KVK results for {interaction.user.display_name}",
            description=self._format_run_header(kvk_run),
            color=discord.Color.blue(),
        )

        if day is None:
            entries = user_stat.get("entries", [])
            overall = self._aggregate_entries(entries) or {"score": 0, "rank": None, "samples": 0}
            overall_rank = overall.get("rank")
            rank_text = f"#{overall_rank:,}" if isinstance(overall_rank, int) else "N/A"
            embed.add_field(
                name="Summary",
                value=(
                    f"Total score: {overall.get('score', 0):,}\\n"
                    f"Best rank: {rank_text}"
                ),
                inline=False,
            )
            for entry in entries:
                kvk_day = entry.get("kvk_day") or entry.get("day_number") or 6
                stage_value = entry.get("stage_type", "Prep Stage")
                stage_enum = StageType.PREP if str(stage_value).lower().startswith("prep") else StageType.WAR
                label = self._format_day_label(int(kvk_day), stage_enum)
                rank_value = entry.get("rank")
                rank_line = f"#{rank_value:,}" if isinstance(rank_value, int) else "N/A"
                embed.add_field(
                    name=label,
                    value=(
                        f"Rank: {rank_line}\\n"
                        f"Score: {entry.get('score', 0):,}"
                    ),
                    inline=True,
                )
        else:
            stage_value = user_stat.get("stage_type", "Prep Stage")
            stage_enum = StageType.PREP if str(stage_value).lower().startswith("prep") else StageType.WAR
            label = self._format_day_label(day, stage_enum)
            rank_value = user_stat.get("rank")
            rank_line = f"#{rank_value:,}" if isinstance(rank_value, int) else "N/A"
            embed.add_field(
                name=label,
                value=(
                    f"Rank: {rank_line}\\n"
                    f"Score: {user_stat.get('score', 0):,}"
                ),
                inline=False,
            )

        screenshot_url = user_stat.get("screenshot_url")
        if screenshot_url:
            embed.set_thumbnail(url=screenshot_url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ranking_compare_me", description="Compare your performance between two KVK runs")
    @app_commands.describe(
        first_run="Earlier KVK run number",
        second_run="Later KVK run number",
        day="Optional day (1-6; omit for overall run)"
    )
    async def ranking_compare_me(
        self,
        interaction: discord.Interaction,
        first_run: int,
        second_run: int,
        day: Optional[int] = None
    ):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return
        if not self.kvk_tracker:
            await interaction.response.send_message("KVK tracking is not configured for this bot.", ephemeral=True)
            return
        if first_run < 1 or second_run < 1:
            await interaction.response.send_message("Run numbers must be at least 1.", ephemeral=True)
            return
        try:
            day = self._validate_day_argument(day)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        run_a = self.kvk_tracker.get_run_by_number(interaction.guild.id, first_run)
        run_b = self.kvk_tracker.get_run_by_number(interaction.guild.id, second_run)
        if not run_a or not run_b:
            await interaction.response.send_message("One of the requested runs could not be found.", ephemeral=True)
            return

        stat_a = self._fetch_user_stat(run_a.id, interaction.user.id, day)
        stat_b = self._fetch_user_stat(run_b.id, interaction.user.id, day)
        if not stat_a or not stat_b:
            await interaction.response.send_message("Missing submissions for one of the runs.", ephemeral=True)
            return

        score_a = stat_a.get("score", 0)
        score_b = stat_b.get("score", 0)
        score_diff = score_b - score_a
        percent_change = (score_diff / score_a * 100) if score_a else None

        rank_a = stat_a.get("rank")
        rank_b = stat_b.get("rank")
        if isinstance(rank_a, int) and isinstance(rank_b, int):
            rank_text = f"#{rank_a:,} → #{rank_b:,}"
            if rank_a > rank_b:
                rank_text += " (improved)"
            elif rank_a < rank_b:
                rank_text += " (declined)"
        else:
            rank_text = "N/A"

        label = "Overall run" if day is None else self._format_day_label(
            day,
            StageType.PREP if day <= 5 else StageType.WAR,
        )

        embed = discord.Embed(
            title=f"KVK comparison for {interaction.user.display_name}",
            description=f"Target: {label}",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name=f"Run #{first_run}",
            value=(
                f"Score: {score_a:,}\n"
                f"Rank: {f'#{rank_a:,}' if isinstance(rank_a, int) else 'N/A'}\n"
                f"{self._format_run_header(run_a)}"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"Run #{second_run}",
            value=(
                f"Score: {score_b:,}\n"
                f"Rank: {f'#{rank_b:,}' if isinstance(rank_b, int) else 'N/A'}\n"
                f"{self._format_run_header(run_b)}"
            ),
            inline=False,
        )
        change_lines = [f"Score change: {score_diff:+,}"]
        if percent_change is not None:
            change_lines.append(f"Percent change: {percent_change:+.2f}%")
        change_lines.append(f"Rank change: {rank_text}")
        embed.add_field(name="Summary", value="\n".join(change_lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ranking_compare_others", description="Compare your KVK results against peers or a friend")
    @app_commands.describe(
        run="KVK run number",
        day="Optional day (1-6; omit for overall run)",
        friend="Friend to compare against when using friend mode"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Power ±5% cohort", value="power"),
            app_commands.Choice(name="Compare with friend", value="friend"),
        ]
    )
    async def ranking_compare_others(
        self,
        interaction: discord.Interaction,
        run: int,
        mode: app_commands.Choice[str],
        day: Optional[int] = None,
        friend: Optional[discord.Member] = None
    ):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used inside a server.", ephemeral=True)
            return
        if not self.kvk_tracker:
            await interaction.response.send_message("KVK tracking is not configured for this bot.", ephemeral=True)
            return
        if run < 1:
            await interaction.response.send_message("Run number must be at least 1.", ephemeral=True)
            return
        try:
            day = self._validate_day_argument(day)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        kvk_run = self.kvk_tracker.get_run_by_number(interaction.guild.id, run)
        if not kvk_run:
            await interaction.response.send_message("Specified run was not found.", ephemeral=True)
            return

        user_stat = self._fetch_user_stat(kvk_run.id, interaction.user.id, day)
        if not user_stat:
            label = f"day {day}" if day else "this run"
            await interaction.response.send_message(f"You have no data recorded for {label}.", ephemeral=True)
            return

        score = user_stat.get("score", 0)
        label = "Overall run" if day is None else self._format_day_label(day, StageType.PREP if day <= 5 else StageType.WAR)

        if mode.value == "friend":
            if not friend or friend == interaction.user:
                await interaction.response.send_message("Select a different member to compare against.", ephemeral=True)
                return
            if friend.guild != interaction.guild:
                await interaction.response.send_message("That member is not part of this server.", ephemeral=True)
                return
            friend_stat = self._fetch_user_stat(kvk_run.id, friend.id, day)
            if not friend_stat:
                await interaction.response.send_message("The selected member has no data recorded for this run/day.", ephemeral=True)
                return
            friend_score = friend_stat.get("score", 0)
            diff = score - friend_score
            percent = (diff / friend_score * 100) if friend_score else None
            embed = discord.Embed(
                title=f"KVK friend comparison - {label}",
                description=self._format_run_header(kvk_run),
                color=discord.Color.purple(),
            )
            embed.add_field(
                name=interaction.user.display_name,
                value=f"Score: {score:,}",
                inline=True,
            )
            embed.add_field(
                name=friend.display_name,
                value=f"Score: {friend_score:,}",
                inline=True,
            )
            summary = [f"Score difference: {diff:+,}"]
            if percent is not None:
                summary.append(f"Percent difference: {percent:+.2f}%")
            embed.add_field(name="Summary", value="\n".join(summary), inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        peers = self._fetch_peers(kvk_run.id, day)
        peers = [row for row in peers if row.get("user_id") != str(interaction.user.id)]
        if not peers:
            await interaction.response.send_message("No peer data available for this run/day.", ephemeral=True)
            return
        tolerance = score * 0.05
        cohort = [row for row in peers if abs(row.get("score", 0) - score) <= tolerance]
        if not cohort:
            cohort = peers
        avg_score = sum(row.get("score", 0) for row in cohort) / len(cohort)
        diff = score - avg_score
        percent = (diff / avg_score * 100) if avg_score else None
        better = sum(1 for row in cohort if row.get("score", 0) <= score)
        embed = discord.Embed(
            title=f"KVK peer comparison - {label}",
            description=self._format_run_header(kvk_run),
            color=discord.Color.teal(),
        )
        embed.add_field(name="Your score", value=f"{score:,}", inline=True)
        embed.add_field(name="Cohort avg", value=f"{avg_score:,.0f}", inline=True)
        summary = [f"Difference: {diff:+,.0f}"]
        if percent is not None:
            summary.append(f"Vs average: {percent:+.2f}%")
        summary.append(f"Peers within range: {better}/{len(cohort)} scoring at or below you")
        embed.add_field(name="Summary", value="\n".join(summary), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(
    bot: commands.Bot,
    processor: Optional[ScreenshotProcessor] = None,
    storage: Optional[RankingStorageEngine] = None
):
    """Setup function for the cog."""
    if processor is None:
        from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
        processor = ScreenshotProcessor()

    if storage is None:
        from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
        game_storage = getattr(bot, "game_storage", None)
        storage = RankingStorageEngine(storage=game_storage)
    
    kvk_tracker = getattr(bot, "kvk_tracker", None)
    await bot.add_cog(RankingCog(bot, processor, storage, kvk_tracker=kvk_tracker))
