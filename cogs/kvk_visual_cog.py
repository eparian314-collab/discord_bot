"""
Enhanced KVK Visual Ranking Cog

Extends the ranking cog with visual-aware KVK screenshot parsing.
Integrates the KVK Visual Manager for complete parsing workflow.
"""

from typing import Optional, TYPE_CHECKING, List, Dict, Any
from datetime import datetime, timezone
import aiohttp
import os
import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.engines.screenshot_processor import StageType
from discord_bot.core.utils import find_bot_channel, is_admin_or_helper
from discord_bot.core.engines.kvk_visual_manager import KVKVisualManager, create_kvk_visual_manager
from discord_bot.core.engines.kvk_tracker import KVKRun
from discord_bot.core import ui_groups

if TYPE_CHECKING:
    pass


class EnhancedKVKRankingCog(commands.Cog):
    """Enhanced ranking cog with visual KVK parsing."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.visual_manager: Optional[KVKVisualManager] = None
        self.kvk_tracker = None  # Will be injected
        self.storage = None      # Will be injected
        self._rankings_channel_id = None
        self._modlog_channel_id = None
        
        # Initialize upload folders
        self.upload_folder = "uploads/screenshots"
        self.log_folder = "logs"
        self.cache_folder = "cache"
    
    async def setup_dependencies(self, 
                                kvk_tracker=None,
                                storage=None,
                                rankings_channel_id: Optional[int] = None,
                                modlog_channel_id: Optional[int] = None):
        """Setup injected dependencies."""
        self.kvk_tracker = kvk_tracker
        self.storage = storage
        self._rankings_channel_id = rankings_channel_id
        self._modlog_channel_id = modlog_channel_id
        
        # Initialize visual manager
        self.visual_manager = await create_kvk_visual_manager(
            upload_folder=self.upload_folder,
            log_folder=self.log_folder,
            cache_folder=self.cache_folder
        )
        
        # Verify system status
        status = await self.visual_manager.get_system_status()
        if not status.get("system_active", False):
            print(f"⚠️ KVK Visual System not fully active: {status}")
        else:
            print("✅ KVK Visual Parsing System initialized successfully")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages in rankings channel - delete non-commands."""
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
                    "This channel is reserved for KVK ranking submissions and commands only. "
                    "Please use the available slash commands: /kvk submit, /kvk view, /kvk status, /kvk power."
                )
            except Exception:
                pass  # User has DMs disabled
    
    # Use the existing KVK group from ui_groups (don't create a new one)
    # This will add commands to the top-level /kvk group
    kvk = ui_groups.kvk
    
    async def _check_rankings_channel(self, interaction: discord.Interaction) -> bool:
        """Check if interaction is in the rankings channel."""
        if not self._rankings_channel_id:
            await interaction.response.send_message(
                "Rankings channel not configured. Please contact an admin.",
                ephemeral=True
            )
            return False
        
        if interaction.channel_id != self._rankings_channel_id:
            channel = self.bot.get_channel(self._rankings_channel_id)
            channel_mention = channel.mention if channel else f"<#{self._rankings_channel_id}>"
            await interaction.response.send_message(
                f"This command can only be used in the rankings channel {channel_mention}.",
                ephemeral=True
            )
            return False
        
        return True
    
    def _resolve_kvk_run(self, interaction: discord.Interaction) -> tuple[Optional[KVKRun], bool]:
        """Resolve the current KVK run for the guild."""
        if not self.kvk_tracker or not interaction.guild:
            return None, False
        
        run = self.kvk_tracker.get_active_run(interaction.guild.id, include_tests=True)
        return run, run.is_active if run else False
    
    @kvk.command(
        name="submit",
        description="🔍 Submit a KVK ranking screenshot with visual parsing"
    )
    @app_commands.describe(
        screenshot="Upload your KVK ranking screenshot"
    )
    async def submit_kvk_visual(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment
    ):
        """Submit a KVK ranking screenshot with enhanced visual parsing."""
        if not await self._check_rankings_channel(interaction):
            return
        
        if not self.visual_manager:
            await interaction.response.send_message(
                "Visual parsing system not available. Please contact an admin.",
                ephemeral=True
            )
            return
        
        # Resolve KVK run
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
        
        # Validate attachment
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
        
        try:
            # Read image data
            image_data = await screenshot.read()
            
            # Validate screenshot first
            validation = await self.visual_manager.validate_screenshot_requirements(image_data)
            if not validation["valid"]:
                await interaction.followup.send(
                    f"Screenshot validation failed: {validation['error']}",
                    ephemeral=True,
                )
                return
            
            # Process with visual parsing system
            result = await self.visual_manager.process_kvk_screenshot(
                image_data=image_data,
                user_id=str(interaction.user.id),
                username=interaction.user.display_name,
                filename=screenshot.filename
            )
            
            if not result["success"]:
                await interaction.followup.send(
                    f"Visual parsing failed: {result.get('error', 'Unknown error')}",
                    ephemeral=True,
                )
                return
            
            # Create success embed
            embed = await self._create_success_embed(result, screenshot, kvk_run, run_is_active)
            
            # Send success response
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Send modlog notification if configured
            await self._send_modlog_notification(interaction, result, screenshot)
            
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while processing your screenshot: {str(e)}",
                ephemeral=True,
            )
            print(f"KVK visual parsing error: {e}")
    
    async def _create_success_embed(self, 
                                  result: Dict[str, Any], 
                                  screenshot: discord.Attachment,
                                  kvk_run: KVKRun,
                                  run_is_active: bool) -> discord.Embed:
        """Create success embed for KVK submission."""
        parse_data = result["parse_result"]
        self_score = result.get("self_score", {})
        comparison = result.get("comparison", {})
        
        embed = discord.Embed(
            title="✅ KVK Screenshot Processed",
            description="Visual parsing completed successfully",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Parsing results
        stage_desc = f"{parse_data['stage_type']} stage"
        day_desc = f"day {parse_data['prep_day']}" if parse_data['prep_day'] else "unknown day"
        
        embed.add_field(
            name="📊 Detected Data",
            value=(
                f"Stage: {stage_desc.title()}\n"
                f"Day: {day_desc.title()}\n"
                f"Kingdom: #{parse_data['kingdom_id'] or 'Unknown'}\n"
                f"Entries parsed: {parse_data['entries_count']}"
            ),
            inline=True
        )
        
        # Self score if found
        if self_score:
            embed.add_field(
                name="🎯 Your Score",
                value=(
                    f"Rank: #{self_score['rank']:,}\n"
                    f"Points: {self_score['points']:,}\n"
                    f"Player: {self_score.get('player_name', 'N/A')}\n"
                    f"Guild: {self_score.get('guild_tag', 'N/A')}"
                ),
                inline=True
            )
        else:
            embed.add_field(
                name="⚠️ Self Score",
                value="Could not identify your entry in the screenshot",
                inline=True
            )
        
        # Comparison results if available
        if comparison:
            ahead_count = comparison.get("peer_count", 0) - comparison.get("behind", 0)
            embed.add_field(
                name="⚔️ Power Band Comparison",
                value=(
                    f"Power Level: {comparison['user_power']:,}\n"
                    f"Peers tracked: {comparison['peer_count']}\n"
                    f"Ahead of: {ahead_count}/{comparison['peer_count']}\n"
                    f"Top performer gap: {comparison.get('top_peer_ahead_by', 0):,}"
                ),
                inline=False
            )
        
        # KVK run info
        run_label = "Test run" if kvk_run.is_test else f"Run #{kvk_run.run_number}"
        status_text = "active" if run_is_active else "closed (admin update)"
        embed.add_field(
            name="🏰 KVK Window",
            value=f"{run_label} ({status_text})",
            inline=True
        )
        
        # Processing time
        processing_time = result.get("processing_time_seconds", 0)
        embed.add_field(
            name="⚡ Processing",
            value=f"{processing_time:.2f}s",
            inline=True
        )
        
        embed.set_thumbnail(url=screenshot.url)
        embed.set_footer(text="Data synced to comparison system")
        
        return embed
    
    async def _send_modlog_notification(self,
                                      interaction: discord.Interaction,
                                      result: Dict[str, Any],
                                      screenshot: discord.Attachment):
        """Send notification to modlog channel."""
        if not self._modlog_channel_id:
            return
        
        try:
            channel = self.bot.get_channel(self._modlog_channel_id)
            if not channel:
                return
            
            parse_data = result["parse_result"]
            self_score = result.get("self_score", {})
            
            embed = discord.Embed(
                title="🔍 KVK Visual Submission",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="Submitter",
                value=f"{interaction.user.mention} ({interaction.user.display_name})",
                inline=True
            )
            
            stage_desc = f"{parse_data['stage_type']} stage"
            day_desc = f"day {parse_data['prep_day']}" if parse_data['prep_day'] else "unknown"
            
            embed.add_field(
                name="Detected",
                value=f"{stage_desc} {day_desc}",
                inline=True
            )
            
            if self_score:
                embed.add_field(
                    name="Score",
                    value=f"#{self_score['rank']:,} • {self_score['points']:,} pts",
                    inline=True
                )
            
            embed.set_thumbnail(url=screenshot.url)
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Failed to send modlog notification: {e}")
    
    @kvk.command(
        name="status",
        description="📊 Check your current KVK comparison status"
    )
    async def kvk_status(self, interaction: discord.Interaction):
        """Check current KVK comparison status."""
        if not self.visual_manager:
            await interaction.response.send_message(
                "Visual parsing system not available.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get comparison status for prep stage
        prep_status = await self.visual_manager.get_user_comparison_status(
            str(interaction.user.id), "prep"
        )
        
        # Get comparison status for war stage
        war_status = await self.visual_manager.get_user_comparison_status(
            str(interaction.user.id), "war"
        )
        
        if not prep_status and not war_status:
            await interaction.followup.send(
                "No comparison data found. Submit a KVK screenshot with `/kvk submit` to start tracking.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="⚔️ Your KVK Status",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add prep stage status
        if prep_status:
            prep_text = (
                f"Score: {prep_status['user_score']:,} pts\n"
                f"Rank: #{prep_status['user_rank']:,}\n"
                f"Power: {prep_status['user_power']:,}\n"
                f"Ahead of: {prep_status['ahead_of']}/{prep_status['peer_count']} peers"
            )
            embed.add_field(name="🛠️ Prep Stage", value=prep_text, inline=True)
        
        # Add war stage status
        if war_status:
            war_text = (
                f"Score: {war_status['user_score']:,} pts\n"
                f"Rank: #{war_status['user_rank']:,}\n"
                f"Power: {war_status['user_power']:,}\n"
                f"Ahead of: {war_status['ahead_of']}/{war_status['peer_count']} peers"
            )
            embed.add_field(name="⚔️ War Stage", value=war_text, inline=True)
        
        # Add system info
        system_status = await self.visual_manager.get_system_status()
        status_icon = "✅" if system_status.get("system_active") else "⚠️"
        embed.add_field(
            name=f"{status_icon} System Status",
            value="Visual parsing active" if system_status.get("system_active") else "System issues detected",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @kvk.command(
        name="power",
        description="⚡ Set your power level for comparison tracking"
    )
    @app_commands.describe(
        power_level="Your current power level (e.g., 25000000 for 25M)"
    )
    async def set_power_level(
        self,
        interaction: discord.Interaction,
        power_level: app_commands.Range[int, 1000000, 1000000000]
    ):
        """Set power level for comparison tracking."""
        if not self.visual_manager:
            await interaction.response.send_message(
                "Visual parsing system not available.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        success = await self.visual_manager.set_user_power_level(
            str(interaction.user.id),
            power_level,
            interaction.user.display_name
        )
        
        if success:
            # Format power level for display
            if power_level >= 1000000:
                power_display = f"{power_level / 1000000:.1f}M"
            else:
                power_display = f"{power_level:,}"
            
            embed = discord.Embed(
                title="⚡ Power Level Updated",
                description=f"Your power level has been set to **{power_display}** ({power_level:,})",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Comparison Tracking",
                value=(
                    "You'll now be compared with players within ±10% of your power level.\n"
                    "Submit KVK screenshots with `/kvk submit` to track your progress!"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "Failed to update power level. Please try again.",
                ephemeral=True
            )
    
    @kvk.command(
        name="system",
        description="🔧 Check KVK visual parsing system status (Admin only)"
    )
    async def system_status(self, interaction: discord.Interaction):
        """Check system status (admin only)."""
        if not is_admin_or_helper(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "Only admins or helpers can check system status.",
                ephemeral=True
            )
            return
        
        if not self.visual_manager:
            await interaction.response.send_message(
                "Visual parsing system not available.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        status = await self.visual_manager.get_system_status()
        
        embed = discord.Embed(
            title="🔧 KVK Visual System Status",
            color=discord.Color.green() if status.get("system_active") else discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # System health
        health_icon = "✅" if status.get("system_active") else "❌"
        embed.add_field(
            name=f"{health_icon} System Health",
            value="Active" if status.get("system_active") else "Issues detected",
            inline=True
        )
        
        # Dependencies
        deps_icon = "✅" if status.get("dependencies_available") else "❌"
        embed.add_field(
            name=f"{deps_icon} Dependencies",
            value="Available" if status.get("dependencies_available") else "Missing",
            inline=True
        )
        
        # Directories
        dirs_icon = "✅" if status.get("directories_ready") else "❌"
        embed.add_field(
            name=f"{dirs_icon} Directories",
            value="Ready" if status.get("directories_ready") else "Issues",
            inline=True
        )
        
        # Cache files status
        cache_files = status.get("cache_files", {})
        cache_status = []
        for file_name, exists in cache_files.items():
            icon = "✅" if exists else "❌"
            cache_status.append(f"{icon} {file_name}")
        
        if cache_status:
            embed.add_field(
                name="📂 Cache Files",
                value="\n".join(cache_status),
                inline=False
            )
        
        # Paths
        embed.add_field(
            name="📁 Configured Paths",
            value=(
                f"Upload: `{status.get('upload_folder')}`\n"
                f"Logs: `{status.get('log_folder')}`\n"
                f"Cache: `{status.get('cache_folder')}`"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Setup the enhanced KVK ranking cog."""
    await bot.add_cog(EnhancedKVKRankingCog(bot))