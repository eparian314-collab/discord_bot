"""
Enhanced KVK Visual Ranking Cog

Extends the ranking cog with visual-aware KVK screenshot parsing.
Integrates the KVK Visual Manager for complete parsing workflow.
"""

from typing import Optional, TYPE_CHECKING, List, Dict, Any, Union
from datetime import datetime, timezone
import aiohttp
import os
import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.engines.screenshot_processor import (
    StageType,
    RankingData,
    RankingCategory,
)
from discord_bot.core.utils import find_bot_channel, is_admin_or_helper
from discord_bot.core.engines.kvk_visual_manager import KVKVisualManager, create_kvk_visual_manager
from discord_bot.core.engines.kvk_tracker import KVKRun
from discord_bot.core import ui_groups

if TYPE_CHECKING:
    pass


def _parse_channel_id(env_var: str) -> Optional[int]:
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class EnhancedKVKRankingCog(commands.Cog):
    """Enhanced ranking cog with visual KVK parsing."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.visual_manager: Optional[KVKVisualManager] = None
        self.kvk_tracker = None  # Will be injected
        self.storage = None      # Will be injected
        self.guardian = None     # Will be injected (GuardianErrorEngine)
        self._rankings_channel_id = None
        self._modlog_channel_id = None
        
        # Initialize upload folders
        self.upload_folder = "uploads/screenshots"
        self.log_folder = "logs"
        self.cache_folder = "cache"
    
    async def setup_dependencies(self, 
                                kvk_tracker=None,
                                storage=None,
                                guardian=None,
                                rankings_channel_id: Optional[int] = None,
                                modlog_channel_id: Optional[int] = None):
        """Setup injected dependencies."""
        self.kvk_tracker = kvk_tracker
        self.storage = storage
        self.guardian = guardian
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

    def _normalize_day(self, stage_type: StageType, day: Optional[Union[int, str]]) -> int:
        """Return the normalized day index used in storage."""
        if stage_type == StageType.WAR:
            return 6
        if isinstance(day, str):
            return 0  # Reserve 0 for Prep overall submissions
        return day if day is not None else 0

    def _format_event_week_label(self, kvk_run: Optional[KVKRun]) -> str:
        """Create a human-friendly label for the current event week."""
        if not kvk_run:
            return self.storage.get_current_event_week() if self.storage else "KVK-UNKNOWN"

        if kvk_run.is_test:
            return f"KVK-TEST-{kvk_run.id}"
        if getattr(kvk_run, "run_number", None):
            return f"KVK-{int(kvk_run.run_number):02d}"
        return f"KVK-{kvk_run.id}"

    def _map_day_to_category(
        self, stage_type: StageType, day: Optional[Union[int, str]]
    ) -> RankingCategory:
        """Map a prep day to a ranking category."""
        if stage_type == StageType.WAR:
            return RankingCategory.UNKNOWN

        category_map = {
            1: RankingCategory.CONSTRUCTION,
            2: RankingCategory.RESEARCH,
            3: RankingCategory.RESOURCE_MOB,
            4: RankingCategory.HERO,
            5: RankingCategory.TROOP_TRAINING,
        }
        if isinstance(day, int):
            return category_map.get(day, RankingCategory.UNKNOWN)
        return RankingCategory.UNKNOWN

    def _format_day_label(self, stage_type: StageType, day: Optional[Union[int, str]]) -> str:
        """Human-readable label for prep or war submissions."""
        if stage_type == StageType.WAR:
            return "War"
        if isinstance(day, str):
            return day.title()
        if isinstance(day, int):
            return f"Day {day}"
        return "Unknown"
    
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
                validation_error = validation['error']
                await interaction.followup.send(
                    f"Screenshot validation failed: {validation_error}\n"
                    "Full-device screenshots are fine -- just make sure the in-game KVK ranking tab fills the shot and is readable.\n"
                    "You can retry with a clearer screenshot or use `/kvk manual` to enter the data manually.",
                    ephemeral=True,
                )
                
                # Log validation error
                if self.guardian:
                    await self.guardian.log_ranking_error(
                        error=ValueError(f"Screenshot validation failed: {validation_error}"),
                        category="validation",
                        user_id=str(interaction.user.id),
                        guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                        kvk_run_id=kvk_run.id if kvk_run else None,
                        screenshot_url=screenshot.url,
                        context="KVK screenshot validation failed",
                        validation_reason=validation_error,
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
                parsing_error = result.get('error', 'Unknown error')
                await interaction.followup.send(
                    f"Visual parsing failed: {parsing_error}\n"
                    "You can use `/kvk manual` to submit the numbers manually while we investigate the OCR issue.",
                    ephemeral=True,
                )
                
                # Log OCR/parsing error
                if self.guardian:
                    await self.guardian.log_ranking_error(
                        error=RuntimeError(f"Visual parsing failed: {parsing_error}"),
                        category="ocr",
                        user_id=str(interaction.user.id),
                        guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                        kvk_run_id=kvk_run.id if kvk_run else None,
                        screenshot_url=screenshot.url,
                        context="KVK visual parsing failed",
                        parsing_details=result,
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
            
            # Log submission error with full context
            if self.guardian:
                await self.guardian.log_ranking_error(
                    error=e,
                    category="submission",
                    user_id=str(interaction.user.id),
                    guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                    kvk_run_id=kvk_run.id if kvk_run else None,
                    screenshot_url=screenshot.url,
                    context="KVK submission processing failed",
                    stage=kvk_run.started_at if kvk_run else None,
                )

    @kvk.command(
        name="manual",
        description="dY? Manually submit your KVK day data when OCR parsing fails"
    )
    @app_commands.describe(
        stage="Prep or War stage",
        rank="Your rank for this submission",
        score="Your score/points for the day",
        day="Prep day (1-5) when stage is Prep; ignored for War",
        overall="Enable to submit the combined Prep total (all 5 days)",
        player_name="Optional player name",
        guild_tag="Optional guild tag (3 letters)",
        kingdom_id="Optional kingdom ID (if known)"
    )
    async def manual_submission(
        self,
        interaction: discord.Interaction,
        stage: str,
        rank: app_commands.Range[int, 1, 10000],
        score: app_commands.Range[int, 1000, 1000000000],
        day: Optional[app_commands.Range[int, 1, 5]] = None,
        overall: bool = False,
        player_name: Optional[str] = None,
        guild_tag: Optional[str] = None,
        kingdom_id: Optional[int] = None,
    ):
        """Submit manual ranking values when the OCR parser cannot read the screenshot."""
        if not await self._check_rankings_channel(interaction):
            return

        kvk_run, run_is_active = self._resolve_kvk_run(interaction)
        is_admin = is_admin_or_helper(interaction.user, interaction.guild)
        if not kvk_run:
            await interaction.response.send_message(
                "No tracked KVK window is currently open. Please wait for the next reminder before submitting manually.",
                ephemeral=True,
            )
            return

        if not run_is_active and not is_admin:
            closed_at = kvk_run.ends_at.strftime("%Y-%m-%d %H:%M UTC")
            await interaction.response.send_message(
                f"The KVK submission window closed on {closed_at}. Only admins or helpers can submit manual updates now.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        stage_value = stage.strip().lower()
        if stage_value not in ("prep", "war"):
            await interaction.followup.send(
                "Stage must be either 'Prep' or 'War'.",
                ephemeral=True,
            )
            return

        stage_type = StageType.PREP if stage_value == "prep" else StageType.WAR

        prep_day: Optional[Union[int, str]]
        if stage_type == StageType.PREP:
            if overall and day is not None:
                await interaction.followup.send(
                    "Overall submissions cannot include a specific day. Remove the day or disable the overall option.",
                    ephemeral=True,
                )
                return
            if overall:
                prep_day = "overall"
            elif day is None:
                await interaction.followup.send(
                    "Prep submissions require a day (1-5) or set overall to true for the combined total.",
                    ephemeral=True,
                )
                return
            else:
                prep_day = day
        else:
            if overall:
                await interaction.followup.send(
                    "Overall totals are only available for the Prep stage.",
                    ephemeral=True,
                )
                return
            prep_day = None

        normalized_day = self._normalize_day(stage_type, prep_day)

        if kingdom_id is not None and kingdom_id <= 0:
            await interaction.followup.send(
                "Kingdom ID must be a positive number.",
                ephemeral=True,
            )
            return

        player_display = player_name.strip() if player_name and player_name.strip() else interaction.user.display_name

        normalized_tag: Optional[str] = None
        if guild_tag:
            cleaned = "".join(ch for ch in guild_tag.upper() if ch.isalpha())
            cleaned = cleaned[:3]
            normalized_tag = cleaned if cleaned else None

        event_week = self._format_event_week_label(kvk_run)
        existing = self.storage.check_duplicate_submission(
            str(interaction.user.id),
            str(interaction.guild_id) if interaction.guild_id else "0",
            event_week,
            stage_type,
            normalized_day,
            kvk_run_id=kvk_run.id,
        )
        if existing:
            await interaction.followup.send(
                "A previous submission exists for this run/day. It will be replaced with the manual entry.",
                ephemeral=True,
            )

        manual_data = {
            "stage_type": stage_value,
            "prep_day": prep_day,
            "kingdom_id": kingdom_id,
            "rank": rank,
            "score": score,
            "player_name": player_display,
            "guild_tag": normalized_tag,
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
            "kvk_run_id": kvk_run.id,
            "screenshot_url": None,
        }

        manual_result = None
        manual_error: Optional[str] = None
        if self.visual_manager:
            try:
                manual_result = await self.visual_manager.process_manual_submission(manual_data)
                if not manual_result.get("success"):
                    manual_error = manual_result.get("error", "Manual processing failed.")
            except Exception as exc:
                manual_error = str(exc)

        if self.visual_manager and manual_error:
            error_message = manual_error or "Manual processing failed."
            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild_id else None,
                "failed",
                error_message=error_message,
            )
            if self.guardian:
                await self.guardian.log_ranking_error(
                    RuntimeError(f"Manual submission failed: {error_message}"),
                    category="manual",
                    user_id=str(interaction.user.id),
                    guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                    kvk_run_id=kvk_run.id,
                    stage=stage_value,
                    day=prep_day,
                    context="Manual submission processing failed",
                )
            await interaction.followup.send(
                f"Manual processing failed: {error_message}\nPlease try again or ask an admin for help.",
                ephemeral=True,
            )
            return

        ranking_data = RankingData(
            user_id=str(interaction.user.id),
            username=interaction.user.display_name,
            guild_tag=normalized_tag,
            event_week=event_week,
            stage_type=stage_type,
            day_number=normalized_day,
            category=self._map_day_to_category(stage_type, prep_day),
            rank=rank,
            score=score,
            player_name=player_display,
            submitted_at=datetime.now(timezone.utc),
            screenshot_url=None,
            guild_id=str(interaction.guild_id) if interaction.guild_id else None,
            kvk_run_id=kvk_run.id,
            is_test_run=kvk_run.is_test,
        )

        action = "Updated" if existing else "Submitted"
        try:
            if existing:
                self.storage.update_ranking(
                    existing["id"],
                    ranking_data.rank,
                    ranking_data.score,
                    None,
                )
                target_ranking_id = existing["id"]
            else:
                target_ranking_id = self.storage.save_ranking(ranking_data)

            if self.kvk_tracker:
                self.kvk_tracker.record_submission(
                    kvk_run_id=kvk_run.id,
                    ranking_id=target_ranking_id,
                    user_id=interaction.user.id,
                    day_number=normalized_day,
                    stage_type=stage_type.value,
                    is_test=kvk_run.is_test,
                )

            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild_id else None,
                "success",
                ranking_id=target_ranking_id,
            )
        except Exception as exc:
            error_message = str(exc)
            self.storage.log_submission(
                str(interaction.user.id),
                str(interaction.guild_id) if interaction.guild_id else None,
                "failed",
                error_message=error_message,
            )
            if self.guardian:
                await self.guardian.log_ranking_error(
                    exc,
                    category="manual",
                    user_id=str(interaction.user.id),
                    guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                    kvk_run_id=kvk_run.id,
                    stage=stage_value,
                    day=prep_day,
                    context="Manual submission storage failed",
                )
            await interaction.followup.send(
                "There was an error saving your manual submission. Please try again later.",
                ephemeral=True,
            )
            return

        day_label = self._format_day_label(stage_type, prep_day)
        if manual_result and manual_result.get("success"):
            embed = await self._create_success_embed(manual_result, None, kvk_run, run_is_active)
            embed.title = "Manual KVK Submission Recorded"
            embed.description = "Manual data was applied to the visual tracking system."
        else:
            embed = discord.Embed(
                title="Manual KVK Submission Recorded",
                description=(
                    f"{action} your {stage_type.value} entry for {day_label}"
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Stored data",
                value=(
                    f"Rank: #{rank}\n"
                    f"Score: {score:,}\n"
                    f"Player: {player_display}\n"
                    f"Guild: {normalized_tag or 'N/A'}"
                ),
                inline=False,
            )
            embed.add_field(
                name="Event",
                value=(
                    f"{event_week}\n"
                    f"{stage_type.value} | {day_label}"
                ),
                inline=False,
            )
            embed.set_footer(text="Visual parsing system was unavailable for this submission.")

        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _create_success_embed(self, 
                                  result: Dict[str, Any], 
                                  screenshot: Optional[discord.Attachment],
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
        
        if screenshot:
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
    
    @kvk.command(
        name="errors",
        description="🔍 View ranking system error diagnostics (Admin only)"
    )
    @app_commands.describe(
        hours="Hours to look back (default: 24)"
    )
    async def view_errors(
        self,
        interaction: discord.Interaction,
        hours: app_commands.Range[int, 1, 168] = 24
    ):
        """View detailed ranking error diagnostics."""
        if not is_admin_or_helper(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "Only admins or helpers can view error diagnostics.",
                ephemeral=True
            )
            return
        
        if not self.guardian:
            await interaction.response.send_message(
                "Error tracking system not available.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get comprehensive error report
        report = self.guardian.get_ranking_error_report(hours=hours)
        summary = self.guardian.get_error_summary()
        
        embed = discord.Embed(
            title="🔍 Ranking System Error Diagnostics",
            description=f"Error analysis for the past {hours} hours",
            color=discord.Color.red() if report["total_ranking_errors"] > 10 else discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Overall health
        embed.add_field(
            name="📊 Overall Health",
            value=(
                f"Total ranking errors: {report['total_ranking_errors']}\n"
                f"Affected users: {report['affected_users']}\n"
                f"Affected KVK runs: {report['affected_kvk_runs']}\n"
                f"Low confidence OCR: {report['low_confidence_ocr_errors']}"
            ),
            inline=False
        )
        
        # Error breakdown by category
        if report["by_category"]:
            category_text = ""
            for category, data in report["by_category"].items():
                category_name = category.replace("ranking.", "").title()
                category_text += f"**{category_name}**: {data['count']} errors\n"
            
            embed.add_field(
                name="🏷️ By Category",
                value=category_text or "No errors recorded",
                inline=True
            )
        
        # Most common error type
        if report["most_common_error"]:
            most_common = report["most_common_error"].replace("ranking.", "").title()
            embed.add_field(
                name="⚠️ Most Common",
                value=most_common,
                inline=True
            )
        
        # Recent error samples
        recent_ranking_errors = self.guardian.get_ranking_errors(limit=5)
        if recent_ranking_errors:
            error_samples = ""
            for i, err in enumerate(recent_ranking_errors[:3], 1):
                timestamp = datetime.fromisoformat(err["timestamp"])
                time_str = timestamp.strftime("%H:%M:%S")
                category = err.get("category", "unknown").replace("ranking.", "")
                msg = err.get("message", "")[:80]
                
                metadata = err.get("metadata", {})
                user_id = metadata.get("user_id", "Unknown")
                confidence = metadata.get("confidence")
                conf_str = f" (conf: {confidence:.2%})" if confidence else ""
                
                error_samples += f"`{time_str}` **{category}**{conf_str}\n"
                error_samples += f"User: <@{user_id}> • {msg}\n\n"
            
            embed.add_field(
                name="🔴 Recent Errors (Last 3)",
                value=error_samples or "No recent errors",
                inline=False
            )
        
        # Safe mode status
        if summary.get("safe_mode"):
            embed.add_field(
                name="🚨 SAFE MODE ACTIVE",
                value="System has detected repeated failures and entered safe mode",
                inline=False
            )
        
        embed.set_footer(text="Use this data to identify patterns and improve system reliability")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Setup the enhanced KVK ranking cog with dependency injection."""
    cog = EnhancedKVKRankingCog(bot)
    guardian = getattr(bot, "error_engine", None)
    kvk_tracker = getattr(bot, "kvk_tracker", None)
    storage = getattr(bot, "ranking_storage", None)
    if storage is None:
        from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
        game_storage = getattr(bot, "game_storage", None)
        storage = RankingStorageEngine(storage=game_storage)
    rankings_channel_id = getattr(bot, "rankings_channel_id", None) or _parse_channel_id("RANKINGS_CHANNEL_ID")
    modlog_channel_id = getattr(bot, "modlog_channel_id", None) or _parse_channel_id("MODLOG_CHANNEL_ID")

    await cog.setup_dependencies(
        kvk_tracker=kvk_tracker,
        storage=storage,
        guardian=guardian,
        rankings_channel_id=rankings_channel_id,
        modlog_channel_id=modlog_channel_id,
    )
    await bot.add_cog(cog, override=True)
