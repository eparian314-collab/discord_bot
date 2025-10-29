"""
Event Ranking Cog - Submit and view Top Heroes event rankings.

Commands:
- /games ranking submit - Submit a screenshot of your event ranking (RANKINGS CHANNEL ONLY!)
- /games ranking view - View your ranking history
- /games ranking leaderboard - View guild leaderboard
- /games ranking stats - View submission statistics
"""

from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, TYPE_CHECKING
import aiohttp
import os

from discord_bot.core.utils import find_bot_channel
from discord_bot.core import ui_groups

if TYPE_CHECKING:
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor, StageType, RankingCategory
    from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine


class RankingCog(commands.Cog):
    """Top Heroes event ranking commands."""
    
    # Use ranking group from ui_groups
    ranking = ui_groups.games_ranking
    
    def __init__(
        self,
        bot: commands.Bot,
        processor: ScreenshotProcessor,
        storage: RankingStorageEngine
    ):
        self.bot = bot
        self.processor = processor
        self.storage = storage
        self._rankings_channel_id = self._get_rankings_channel_id()
    
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
    
    async def _check_rankings_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in the dedicated rankings channel."""
        if not interaction.channel:
            return False
        
        # If no rankings channel configured, allow in any channel
        if not self._rankings_channel_id:
            await interaction.response.send_message(
                "❌ **Rankings channel not configured!**\n"
                "Please ask a server admin to set `RANKINGS_CHANNEL_ID` in the bot's `.env` file.\n\n"
                "This is the dedicated channel where members submit their Top Heroes event rankings.",
                ephemeral=True
            )
            return False
        
        # Must be in the rankings channel
        if interaction.channel.id != self._rankings_channel_id:
            channel_mention = f"<#{self._rankings_channel_id}>"
            await interaction.response.send_message(
                f"📊 **Rankings submissions can only be done in {channel_mention}!**\n\n"
                f"This keeps all event rankings organized in one place.\n"
                f"Please go to {channel_mention} to submit your screenshot.",
                ephemeral=True
            )
            return False
        
        return True
    
    @ranking.command(
        name="submit",
        description="📊 Submit a screenshot of your Top Heroes event ranking"
    )
    @app_commands.describe(
        screenshot="Upload your ranking screenshot",
        day="Which day is this for? (1-5)",
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
        # Check if in rankings channel
        if not await self._check_rankings_channel(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate inputs
            if day < 1 or day > 5:
                await interaction.followup.send(
                    "❌ Day must be between 1 and 5!\n"
                    "• Day 1 = Construction\n"
                    "• Day 2 = Research\n"
                    "• Day 3 = Resource & Mob\n"
                    "• Day 4 = Hero\n"
                    "• Day 5 = Troop Training",
                    ephemeral=True
                )
                return
            
            stage_lower = stage.lower()
            if stage_lower not in ['prep', 'war']:
                await interaction.followup.send(
                    "❌ Stage must be 'Prep' or 'War'!",
                    ephemeral=True
                )
                return
            
            # Parse stage type
            from discord_bot.core.engines.screenshot_processor import StageType
            stage_type = StageType.PREP if stage_lower == 'prep' else StageType.WAR
            
            # Validate attachment
            if not screenshot.content_type or not screenshot.content_type.startswith('image/'):
                await interaction.followup.send(
                    "❌ Please upload an image file (PNG, JPG, etc.)!",
                    ephemeral=True
                )
                return
            
            if screenshot.size > 10 * 1024 * 1024:  # 10MB limit
                await interaction.followup.send(
                    "❌ Image too large! Please upload a screenshot under 10MB.",
                    ephemeral=True
                )
                return
            
            # Get current event week
            current_week = self.storage.get_current_event_week()
            
            # Check for duplicate submission
            existing = self.storage.check_duplicate_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild else "0",
                current_week,
                stage_type,
                day
            )
            
            if existing:
                # User already submitted - replace it
                await interaction.followup.send(
                    f"ℹ️ You already submitted Day {day} {stage.title()} Stage this week.\n"
                    f"This will replace your previous submission...",
                    ephemeral=True
                )
            
            # Download image
            image_data = await screenshot.read()
            
            # Validate screenshot
            is_valid, error_msg = await self.processor.validate_screenshot(image_data)
            if not is_valid:
                self.storage.log_submission(
                    str(interaction.user.id),
                    str(interaction.guild_id) if interaction.guild else None,
                    "failed",
                    error_message=error_msg
                )
                await interaction.followup.send(
                    f"❌ **Screenshot validation failed:**\n{error_msg}\n\n"
                    f"**Please make sure your screenshot shows:**\n"
                    f"• Stage type (Prep/War Stage button)\n"
                    f"• Day number (1-5 buttons with one highlighted)\n"
                    f"• Your rank (e.g., #10435)\n"
                    f"• Your score (e.g., 28,200,103 points)\n"
                    f"• Your player name with guild tag (e.g., [TAO] Mars)",
                    ephemeral=True
                )
                return
            
            # Process screenshot
            ranking = await self.processor.process_screenshot(
                image_data,
                str(interaction.user.id),
                interaction.user.name,
                str(interaction.guild_id) if interaction.guild else None
            )
            
            if not ranking:
                self.storage.log_submission(
                    str(interaction.user.id),
                    str(interaction.guild_id) if interaction.guild else None,
                    "failed",
                    error_message="Could not extract ranking data from image"
                )
                await interaction.followup.send(
                    "❌ **Could not read ranking data from screenshot.**\n\n"
                    "**The screenshot must clearly show:**\n"
                    "• Stage type button (Prep Stage / War Stage)\n"
                    "• Day number buttons (1-5)\n"
                    "• Your overall rank (e.g., #10435)\n"
                    "• Your score/points (e.g., 28,200,103)\n"
                    "• Your player name with guild tag (e.g., #10435 [TAO] Mars)\n\n"
                    "**Tips for better results:**\n"
                    "✅ Take screenshot in good lighting\n"
                    "✅ Make sure text is not blurry\n"
                    "✅ Use high resolution\n"
                    "✅ Don't crop too much - show the whole ranking screen",
                    ephemeral=True
                )
                return
            
            # Validate extracted data matches user input
            if ranking.day_number != day:
                await interaction.followup.send(
                    f"⚠️ **Data mismatch!**\n"
                    f"You selected Day {day}, but the screenshot appears to show Day {ranking.day_number}.\n"
                    f"Please check your screenshot and try again.",
                    ephemeral=True
                )
                return
            
            if ranking.stage_type != stage_type:
                await interaction.followup.send(
                    f"⚠️ **Data mismatch!**\n"
                    f"You selected {stage.title()} Stage, but the screenshot appears to show {ranking.stage_type.value}.\n"
                    f"Please check your screenshot and try again.",
                    ephemeral=True
                )
                return
            
            # Save to database (or update if duplicate)
            ranking.screenshot_url = screenshot.url
            
            if existing:
                # Update existing entry
                success = self.storage.update_ranking(
                    existing['id'],
                    ranking.rank,
                    ranking.score,
                    screenshot.url
                )
                action = "Updated"
            else:
                # New submission
                ranking_id = self.storage.save_ranking(ranking)
                action = "Submitted"
            
            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild else None,
                "success",
                ranking_id=existing['id'] if existing else None
            )
            
            # Create response embed
            embed = discord.Embed(
                title=f"✅ Ranking {action}!",
                description=f"Event Week: **{ranking.event_week}**",
                color=discord.Color.green(),
                timestamp=ranking.submitted_at
            )
            
            # Data stored
            embed.add_field(
                name="📊 Data Stored",
                value=(
                    f"**Guild Tag:** {ranking.guild_tag or 'N/A'}\n"
                    f"**Player:** {ranking.player_name or interaction.user.name}\n"
                    f"**Category:** Day {ranking.day_number} - {ranking.category.value}\n"
                    f"**Rank:** #{ranking.rank:,}\n"
                    f"**Score:** {ranking.score:,} points\n"
                    f"**Week:** {ranking.event_week}"
                ),
                inline=False
            )
            
            embed.set_thumbnail(url=screenshot.url)
            embed.set_footer(text=f"Submitted by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Send to modlog for admin tracking
            if interaction.guild:
                modlog_embed = discord.Embed(
                    title=f"📊 Ranking {action}",
                    description=f"**User:** {interaction.user.mention} ({interaction.user.name})",
                    color=discord.Color.blue(),
                    timestamp=ranking.submitted_at
                )
                modlog_embed.add_field(
                    name="Data Submitted",
                    value=(
                        f"**Guild Tag:** [{ranking.guild_tag or 'N/A'}]\n"
                        f"**Player Name:** {ranking.player_name or 'N/A'}\n"
                        f"**Category:** Day {ranking.day_number} - {ranking.category.value}\n"
                        f"**Rank:** #{ranking.rank:,}\n"
                        f"**Score:** {ranking.score:,} points\n"
                        f"**Event Week:** {ranking.event_week}"
                    ),
                    inline=False
                )
                modlog_embed.set_thumbnail(url=screenshot.url)
                
                await self._send_to_modlog(interaction.guild, modlog_embed)
            
            # Post to bot channel
            if interaction.guild:
                bot_channel = find_bot_channel(interaction.guild)
                if bot_channel:
                    public_embed = embed.copy()
                    public_embed.title = f"📊 {action} Ranking - {interaction.user.name}"
                    try:
                        await bot_channel.send(embed=public_embed)
                    except:
                        pass  # Silently fail if can't post
            
        except Exception as e:
            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild else None,
                "failed",
                error_message=str(e)
            )
            await interaction.followup.send(
                f"❌ An error occurred while processing your screenshot:\n```{str(e)}```\n"
                f"Please try again or contact a server admin if the issue persists.",
                ephemeral=True
            )
    
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
                "Use `/ranking submit` to submit your first screenshot.",
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
        storage = RankingStorageEngine()
    
    await bot.add_cog(RankingCog(bot, processor, storage))
