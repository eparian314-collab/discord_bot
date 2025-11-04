"""
Unified Event Ranking Cog - Visual-aware screenshot parsing for any in-game event.

Combines classic ranking submission with enhanced visual parsing for stage/day detection.
Supports Top Heroes events and any game events with similar day-based formats.

Commands:
- /ranking_submit - Submit a screenshot with optional visual parsing
- /ranking_view - View your ranking history
- /ranking_leaderboard - View guild leaderboard
- /ranking_stats - View submission statistics
- /ranking_report - Admin report generation
- /ranking_user - Admin user lookup
- /ranking_status - Check comparison status
- /ranking_power - Set power level for peer comparisons
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
from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
from discord_bot.core.engines.kvk_visual_manager import KVKVisualManager, create_kvk_visual_manager
from discord_bot.core.engines.kvk_tracker import KVKRun
from discord_bot.core import ui_groups
from discord_bot.core.engines.openai_engine import OpenAIEngine

if TYPE_CHECKING:
    pass


class UnifiedRankingCog(commands.Cog):
    """Universal event ranking commands with visual parsing support."""
    
    def __init__(
        self,
        bot: commands.Bot,
        processor: ScreenshotProcessor,
        storage: RankingStorageEngine,
        kvk_tracker=None,
        openai_engine: Optional[OpenAIEngine] = None
    ):
        self.bot = bot
        self.processor = processor
        self.storage = storage
        self.openai_engine = openai_engine
        self._rankings_channel_id = self._get_rankings_channel_id()
        self._modlog_channel_id = self._get_modlog_channel_id()
        self.kvk_tracker = kvk_tracker or getattr(bot, "kvk_tracker", None)
        
        # Visual parsing components (initialized async)
        self.visual_manager: Optional[KVKVisualManager] = None
        self.visual_parsing_enabled = False
        
        # Initialize upload folders
        self.upload_folder = "uploads/screenshots"
        self.log_folder = "logs"
        self.cache_folder = "cache"
        
        # Post guidance message once bot is ready
        if hasattr(self.bot, 'loop') and self.bot.loop:
            self.bot.loop.create_task(self._initialize_visual_system())
            self.bot.loop.create_task(self._post_guidance_message())
    
    async def _initialize_visual_system(self):
        """Initialize visual parsing system asynchronously."""
        try:
            await self.bot.wait_until_ready()
            self.visual_manager = await create_kvk_visual_manager(
                upload_folder=self.upload_folder,
                log_folder=self.log_folder,
                cache_folder=self.cache_folder
            )
            
            status = await self.visual_manager.get_system_status()
            if status.get("system_active", False):
                self.visual_parsing_enabled = True
                print("✅ Visual parsing system initialized successfully")
            else:
                print(f"⚠️ Visual parsing system not fully active: {status}")
        except Exception as e:
            print(f"⚠️ Visual parsing system failed to initialize: {e}")
            self.visual_parsing_enabled = False

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
            "This channel is reserved for event ranking submissions and commands only.\n\n"
            "**Allowed actions:**\n"
            "• Submit your event ranking screenshot using `/ranking_submit`\n"
            "• View your ranking history with `/ranking_view`\n"
            "• See the leaderboard with `/ranking_leaderboard`\n"
            "• Check your comparison status with `/ranking_status`\n\n"
            "Please do not chat or post unrelated messages here. Use the available slash commands for all ranking-related actions."
        )
        # Try to find an existing guidance message
        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user and "Rankings Channel Guidance" in msg.content:
                return  # Already posted
        await channel.send(guidance)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Delete non-command messages in rankings channel."""
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
                    "Please use the available slash commands: /ranking_submit, /ranking_view, /ranking_leaderboard, /ranking_status."
                )
            except Exception:
                pass

    def _get_rankings_channel_id(self) -> Optional[int]:
        """Get the dedicated rankings channel ID from environment."""
        raw = os.getenv("RANKINGS_CHANNEL_ID", "")
        if not raw:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None
    
    def _get_modlog_channel_id(self) -> Optional[int]:
        """Get the modlog channel ID from environment."""
        raw = os.getenv("MODLOG_CHANNEL_ID", "")
        if not raw:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None
    
    def _get_modlog_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Find the modlog channel in guild."""
        # First try configured channel ID
        if self._modlog_channel_id:
            channel = guild.get_channel(self._modlog_channel_id)
            if channel:
                return channel
        
        # Fallback: look for channel named "modlog" or "mod-log"
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
        """Resolve the current KVK run for the guild."""
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
        """Format event week label from KVK run."""
        if not kvk_run:
            return self.storage.get_current_event_week()
        if getattr(kvk_run, "is_test", False):
            return f"KVK-TEST-{kvk_run.id}"
        if getattr(kvk_run, "run_number", None):
            return f"KVK-{int(kvk_run.run_number):02d}"
        return f"KVK-{kvk_run.id}"

    def _normalize_day(self, stage_type: "StageType", day: int) -> int:
        """Normalize day number for storage."""
        if stage_type == StageType.WAR:
            return 6
        return day

    def _format_day_label(self, day: int, stage_type: "StageType") -> str:
        """Format day label for display."""
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
        """Aggregate multiple entries."""
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
        """Format KVK run header."""
        run_label = "Test run" if kvk_run.is_test else f"Run #{kvk_run.run_number}"
        window = f"{kvk_run.started_at.strftime('%Y-%m-%d %H:%M UTC')} - {kvk_run.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
        status = "active" if kvk_run.is_active else "closed"
        return f"{run_label} | {window} | {status}"

    def _validate_day_argument(self, day: Optional[int]) -> Optional[int]:
        """Validate day argument."""
        if day is None:
            return None
        if day < 1 or day > 6:
            raise ValueError("Day must be between 1 and 6")
        return day

    def _fetch_user_stat(self, run_id: int, user_id: int, day: Optional[int]) -> Optional[Dict[str, Any]]:
        """Fetch user statistics."""
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
        """Fetch peer data."""
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
                "This is the dedicated channel where members submit their event rankings."
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
    
    @app_commands.command(
        name="ranking_submit",
        description="Submit a screenshot of your event ranking (auto-detects stage/day if possible)"
    )
    @app_commands.describe(
        screenshot="Upload your ranking screenshot",
        day="Which day? (1-5 for prep, ignored for war) - Leave blank for auto-detection",
        stage="Which stage? (Prep or War) - Leave blank for auto-detection"
    )
    async def submit_ranking(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        day: Optional[int] = None,
        stage: Optional[str] = None
    ):
        """Submit an event ranking screenshot with optional visual parsing."""
        if not await self._check_rankings_channel(interaction):
            return

        kvk_run, run_is_active = self._resolve_kvk_run(interaction)
        is_admin = is_admin_or_helper(interaction.user, interaction.guild)
        
        if not kvk_run:
            await interaction.response.send_message(
                "No tracked event window is currently open. Please wait for the next event reminder.",
                ephemeral=True,
            )
            return

        if not run_is_active and not is_admin:
            closed_at = kvk_run.ends_at.strftime('%Y-%m-%d %H:%M UTC')
            await interaction.response.send_message(
                f"The submission window closed on {closed_at}. Only admins or helpers can submit late updates.",
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

        image_data = await screenshot.read()
        
        # Try visual parsing first if enabled and user didn't provide stage/day
        visual_result = None
        if self.visual_parsing_enabled and self.visual_manager and (day is None or stage is None):
            try:
                validation = await self.visual_manager.validate_screenshot_requirements(image_data)
                if validation["valid"]:
                    visual_result = await self.visual_manager.process_kvk_screenshot(
                        image_data=image_data,
                        user_id=str(interaction.user.id),
                        username=interaction.user.display_name,
                        filename=screenshot.filename
                    )
                    if visual_result["success"]:
                        parse_data = visual_result["parse_result"]
                        # Use visual parsing results
                        if stage is None and parse_data.get("stage_type"):
                            stage = parse_data["stage_type"]
                        if day is None and parse_data.get("prep_day"):
                            day = parse_data["prep_day"]
                        
                        # Show visual parsing success in response later
                        await interaction.followup.send(
                            f"✨ **Visual parsing successful!**\n"
                            f"Detected: {parse_data['stage_type']} stage, day {parse_data.get('prep_day', '?')}\n"
                            f"Processing submission...",
                            ephemeral=True
                        )
            except Exception as e:
                print(f"Visual parsing failed (falling back to manual): {e}")
                visual_result = None
        
        # If still missing stage/day after visual parsing attempt, require manual input
        if stage is None:
            await interaction.followup.send(
                "Could not auto-detect stage. Please specify: **Prep** or **War**",
                ephemeral=True,
            )
            return
        
        if day is None:
            await interaction.followup.send(
                "Could not auto-detect day. Please specify day (1-5 for prep stage).",
                ephemeral=True,
            )
            return
        
        # Parse and validate stage
        stage_lower = stage.lower()
        if stage_lower not in ("prep", "war"):
            await interaction.followup.send(
                "Stage must be 'Prep' or 'War'.",
                ephemeral=True,
            )
            return
        stage_type = StageType.PREP if stage_lower == "prep" else StageType.WAR

        # Validate day for prep stage
        if stage_type == StageType.PREP:
            if day < 1 or day > 5:
                await interaction.followup.send(
                    "Day must be between 1 and 5 for the prep stage.",
                    ephemeral=True,
                )
                return
        else:
            day = 6  # War stage is treated as the sixth slot

        # Validate screenshot with classic processor
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

        event_week = self._format_event_week_label(kvk_run)
        normalized_day = self._normalize_day(stage_type, day)

        # Check for duplicate submission
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

        # Process screenshot with classic processor
        ranking_result = await self.processor.process_screenshot_with_ai(
            image_data,
            str(interaction.user.id),
            interaction.user.name,
            str(interaction.guild_id) if interaction.guild else None,
            screenshot.url
        )

        if not ranking_result.is_successful:
            # If parsing fails, start interactive correction
            await self.start_correction_flow(interaction, ranking_result)
            return

        ranking = ranking_result.ranking_data

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

        # Validate detected vs selected stage/day
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

        # Update ranking data
        ranking.stage_type = stage_type
        ranking.day_number = normalized_day
        ranking.screenshot_url = screenshot.url
        ranking.event_week = event_week
        ranking.kvk_run_id = kvk_run.id
        ranking.is_test_run = kvk_run.is_test

        # Save or update ranking
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

        # Record in KVK tracker
        if self.kvk_tracker:
            self.kvk_tracker.record_submission(
                kvk_run_id=kvk_run.id,
                ranking_id=target_ranking_id,
                user_id=interaction.user.id,
                day_number=normalized_day,
                stage_type=ranking.stage_type.value,
            )

        self.storage.log_submission(
            str(interaction.user.id),
            str(interaction.guild_id) if interaction.guild else None,
            "success",
            ranking_id=target_ranking_id,
        )

        # Create success embed
        embed = discord.Embed(
            title=f"{action} ranking entry",
            description=f"Tracking label: {ranking.event_week}",
            color=discord.Color.green(),
            timestamp=ranking.submitted_at,
        )
        
        # Add visual parsing indicator if used
        if visual_result and visual_result.get("success"):
            embed.add_field(
                name="✨ Visual Parsing",
                value="Stage and day auto-detected from screenshot",
                inline=False
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
            name="Event window",
            value=f"{run_label}\nPeriod: {window_text}\nStatus: {status_text}",
            inline=False,
        )
        
        # Add comparison data if available from visual parsing
        if visual_result and visual_result.get("comparison"):
            comparison = visual_result["comparison"]
            ahead_count = comparison.get("peer_count", 0) - comparison.get("behind", 0)
            embed.add_field(
                name="⚔️ Power Band Comparison",
                value=(
                    f"Peers tracked: {comparison['peer_count']}\n"
                    f"Ahead of: {ahead_count}/{comparison['peer_count']}"
                ),
                inline=False
            )
        
        embed.set_thumbnail(url=screenshot.url)
        embed.set_footer(text="Data saved to rankings database")

        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Send modlog notification
        if interaction.guild:
            modlog_embed = discord.Embed(
                title=f"📊 {action} Ranking Entry",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            modlog_embed.add_field(
                name="User",
                value=f"{interaction.user.mention} ({interaction.user.display_name})",
                inline=True
            )
            modlog_embed.add_field(
                name="Details",
                value=f"{self._format_day_label(normalized_day, stage_type)}\nRank: #{ranking.rank:,}\nScore: {ranking.score:,}",
                inline=True
            )
            if ranking_result.confidence < 1.0:
                 modlog_embed.add_field(
                    name="Method",
                    value=f"✨ AI Assisted ({ranking_result.confidence:.0%})",
                    inline=True
                )
            elif visual_result and visual_result.get("success"):
                modlog_embed.add_field(
                    name="Method",
                    value="✨ Visual parsing",
                    inline=True
                )
            modlog_embed.set_thumbnail(url=screenshot.url)
            await self._send_to_modlog(interaction.guild, modlog_embed)

    async def start_correction_flow(self, interaction: discord.Interaction, result: "OCRParseResult"):
        """Initiate an interactive flow to correct missing OCR data."""
        
        missing_fields = result.fields_missing
        embed = discord.Embed(
            title="📝 OCR Data Correction",
            description=f"I couldn't read everything from your screenshot. Please help me fill in the blanks for: **{', '.join(missing_fields)}**.",
            color=discord.Color.orange()
        )
        if result.ranking_data:
            embed.add_field(name="Partial Data Found", value=f"Rank: {result.ranking_data.rank or '?'}\nScore: {result.ranking_data.score or '?'}", inline=False)

        await interaction.followup.send(embed=embed, view=CorrectionView(result, self.storage, self.openai_engine), ephemeral=True)


class CorrectionView(discord.ui.View):
    """A view to handle the interactive correction of OCR data."""

    def __init__(self, result: "OCRParseResult", storage: "RankingStorageEngine", openai_engine: Optional["OpenAIEngine"] = None):
        super().__init__(timeout=300)
        self.result = result
        self.storage = storage
        self.openai_engine = openai_engine

    @discord.ui.button(label="Correct Data", style=discord.ButtonStyle.primary)
    async def correct_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CorrectionModal(self.result)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.is_successful():
            corrected_data = modal.get_corrected_data()
            
            # Save the corrected data
            ranking_id = self.storage.save_ranking(corrected_data)
            
            # Perform AI analysis on the correction
            ai_analysis = "AI analysis not available."
            failure_category = "unknown"
            if self.openai_engine and corrected_data.screenshot_url:
                try:
                    # Fetch few-shot examples
                    few_shot_examples = self.storage.get_recent_corrections(limit=3)

                    # Get initial text from the result if available
                    initial_text = self.result.raw_ocr_text or "Raw OCR text not available."

                    ai_analysis, failure_category = await self.openai_engine.analyze_correction(
                        image_url=corrected_data.screenshot_url,
                        initial_text=initial_text,
                        initial_data={"rank": self.result.ranking_data.rank, "score": self.result.ranking_data.score},
                        corrected_data={"rank": corrected_data.rank, "score": corrected_data.score},
                        few_shot_examples=few_shot_examples
                    )
                except Exception as e:
                    ai_analysis = f"Error during AI analysis: {e}"

            # Save the correction record
            self.storage.save_ocr_correction(
                ranking_id=ranking_id,
                user_id=corrected_data.user_id,
                image_url=corrected_data.screenshot_url,
                initial_text=initial_text,
                failure_category=failure_category,
                initial_rank=self.result.ranking_data.rank,
                initial_score=self.result.ranking_data.score,
                corrected_rank=corrected_data.rank,
                corrected_score=corrected_data.score,
                ai_analysis=ai_analysis
            )
            
            embed = discord.Embed(title="✅ Corrected Data Saved", color=discord.Color.green())
            embed.add_field(name="Corrected Info", value=f"Rank: {corrected_data.rank}\nScore: {corrected_data.score}")
            embed.add_field(name="AI Analysis", value=f"**Category:** {failure_category.title()}\n{ai_analysis}", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.stop()
        else:
            await interaction.followup.send("Correction cancelled or timed out.", ephemeral=True)


class CorrectionModal(discord.ui.Modal):
    """A modal for users to input missing OCR data."""

    def __init__(self, result: "OCRParseResult"):
        super().__init__(title="Correct OCR Data")
        self.result = result
        self.corrected_data = result.ranking_data

        if "rank" in result.fields_missing:
            self.add_item(discord.ui.TextInput(label="Rank", placeholder="Enter your rank", default=str(result.ranking_data.rank or "")))
        if "score" in result.fields_missing:
            self.add_item(discord.ui.TextInput(label="Score", placeholder="Enter your score", default=str(result.ranking_data.score or "")))

    async def on_submit(self, interaction: discord.Interaction):
        if "rank" in self.result.fields_missing:
            self.corrected_data.rank = int(self.children[0].value)
        if "score" in self.result.fields_missing:
            score_index = 1 if "rank" in self.result.fields_missing else 0
            self.corrected_data.score = int(self.children[score_index].value.replace(',', ''))
        
        await interaction.response.defer()
        self.stop()

    def is_successful(self) -> bool:
        return self.corrected_data.rank > 0 and self.corrected_data.score > 0

    def get_corrected_data(self) -> "RankingData":
        return self.corrected_data

    # Continue in next message due to length...

    @app_commands.command(
        name="ranking_test",
        description="🔬 Open a temporary event test window for ranking checks (Admin only)",
    )
    @app_commands.describe(
        duration_minutes="How long the test window remains open (minutes)",
    )
    async def start_test_run(
        self,
        interaction: discord.Interaction,
        duration_minutes: app_commands.Range[int, 5, 720] = 60,
    ) -> None:
        """Create a short-lived event test window for manual ranking validation."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        if not is_admin_or_helper(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "Only admins or helpers can start an event test window.",
                ephemeral=True,
            )
            return

        if not self.kvk_tracker:
            await interaction.response.send_message(
                "Event tracker engine is not available on this bot instance.",
                ephemeral=True,
            )
            return

        active_test = None
        try:
            for run in self.kvk_tracker.list_runs(interaction.guild.id, include_tests=True):
                if run.is_active and run.is_test:
                    active_test = run
                    break
        except Exception:
            active_test = None

        if active_test:
            await interaction.response.send_message(
                (
                    "An event test window is already active until "
                    f"{active_test.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
                ),
                ephemeral=True,
            )
            return

        channel_id = self._rankings_channel_id or getattr(interaction.channel, "id", None)
        title = f"Test Event {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

        run, _ = await self.kvk_tracker.ensure_run(
            guild_id=interaction.guild.id,
            title=title,
            initiated_by=interaction.user.id,
            channel_id=channel_id,
            is_test=True,
            duration_minutes=duration_minutes,
        )

        embed = discord.Embed(
            title="🧪 Test event window ready",
            description=(
                f"Test event run **#{run.id}** is live now and will auto-close at "
                f"{run.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
            ),
            color=discord.Color.teal(),
        )
        if channel_id and channel_id != interaction.channel_id:
            embed.add_field(name="Rankings channel", value=f"<#{channel_id}>", inline=False)
        embed.set_footer(text="Use /ranking_submit in the rankings channel to validate OCR & storage.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="ranking_view",
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
                "Use `/ranking_submit` to submit your first screenshot.",
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
    
    @app_commands.command(
        name="ranking_leaderboard",
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
        title = "🏆 Event Leaderboard"
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
    
    @app_commands.command(
        name="ranking_report",
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
        if interaction.guild:
            modlog_embed = embed.copy()
            modlog_embed.title = f"📋 Admin Report Requested - {interaction.user.name}"
            await self._send_to_modlog(interaction.guild, modlog_embed)
    
    @app_commands.command(
        name="ranking_stats",
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
    
    @app_commands.command(
        name="ranking_user",
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
    
    @app_commands.command(
        name="ranking_status",
        description="📊 Check your current comparison status with power band peers"
    )
    async def ranking_status(self, interaction: discord.Interaction):
        """Check current comparison status."""
        if not self.visual_parsing_enabled or not self.visual_manager:
            await interaction.response.send_message(
                "Visual comparison system is not available. Please use `/ranking_view` instead.",
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
                "No comparison data found. Submit a screenshot with `/ranking_submit` to start tracking.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="⚔️ Your Comparison Status",
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
    
    @app_commands.command(
        name="ranking_power",
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
        if not self.visual_parsing_enabled or not self.visual_manager:
            await interaction.response.send_message(
                "Visual comparison system is not available.",
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
                    "Submit screenshots with `/ranking_submit` to track your progress!"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "Failed to update power level. Please try again.",
                ephemeral=True
            )


async def setup(
    bot: commands.Bot,
    processor: Optional[ScreenshotProcessor] = None,
    storage: Optional[RankingStorageEngine] = None
):
    """Setup function for the unified ranking cog."""
    if processor is None:
        from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
        processor = ScreenshotProcessor()
    if storage is None:
        from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
        game_storage = getattr(bot, "game_storage", None)
        storage = RankingStorageEngine(storage=game_storage)
    
    openai_engine = None
    if os.getenv("OPEN_AI_API_KEY"):
        try:
            from discord_bot.core.engines.openai_engine import OpenAIEngine
            openai_engine = OpenAIEngine()
        except (ImportError, ValueError):
            pass # OpenAI engine is optional

    kvk_tracker = getattr(bot, "kvk_tracker", None)
    await bot.add_cog(UnifiedRankingCog(bot, processor, storage, kvk_tracker=kvk_tracker, openai_engine=openai_engine))
