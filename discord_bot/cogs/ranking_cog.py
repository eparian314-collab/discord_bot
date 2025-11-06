"""
Event Ranking Cog - Submit and view Top Heroes event rankings.

Commands:
- /kvk ranking submit - Submit a screenshot of your event ranking (RANKINGS CHANNEL ONLY!)
- /kvk ranking view - View your ranking history
- /kvk ranking leaderboard - View guild leaderboard
- /kvk ranking stats - View submission statistics
"""

from __future__ import annotations

import logging
import textwrap
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiohttp
import discord
from discord import app_commands, ui, Interaction
from discord.ext import commands

from discord_bot.core import ui_groups
from discord_bot.core.engines.screenshot_processor import RankingData, StageType
from discord_bot.core.utils import find_bot_channel, is_admin_or_helper

logger = logging.getLogger("hippo_bot.ranking_cog")

if TYPE_CHECKING:
    from discord_bot.core.engines.kvk_tracker import KVKRun
    from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
    from discord_bot.core.engines.kvk_tracker import KVKRun


class SubmissionValidationError(Exception):
    """Raised when a ranking submission fails validation."""


@dataclass(slots=True)
class SubmissionValidationResult:
    """Normalized results from the submission validation flow."""

    ranking: RankingData
    stage_type: StageType
    normalized_day: int
    event_week: str
    existing_entry: Optional[Dict[str, Any]]


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
    
    # Register ranking commands under /kvk ranking
    ranking = app_commands.Group(
        name=ui_groups.KVK_RANKING_NAME,
        description=ui_groups.KVK_RANKING_DESCRIPTION,
        parent=ui_groups.kvk,
    )
    
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
        loop = getattr(self.bot, "loop", None)
        if loop and hasattr(loop, "create_task"):
            loop.create_task(self._post_guidance_message())


    async def _post_guidance_message(self):
        await self.bot.wait_until_ready()
        channel_id = self._rankings_channel_id
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        guidance = textwrap.dedent(
            """
            **Rankings Channel Guidance**
            This channel is reserved for Top Heroes event ranking submissions and commands only.
            
            **Allowed actions:**
            - Submit your event ranking screenshot using `/kvk ranking submit`
            - View your ranking history with `/kvk ranking view`
            - See the leaderboard with `/kvk ranking leaderboard`
            - Compare your results with `/ranking_compare_me` and `/ranking_compare_others`
            
            Please do not chat or post unrelated messages here. Use the available slash commands for all ranking-related actions.
            """
        ).strip()
        # Try to find an existing guidance message
        try:
            async for msg in channel.history(limit=20):
                if msg.author == self.bot.user and "Rankings Channel Guidance" in msg.content:
                    return  # Already posted
        except discord.Forbidden:
            logger.warning(
                "Insufficient permissions to read history in rankings channel %s; skipping guidance message",
                channel_id,
            )
            return
        except discord.HTTPException as exc:
            logger.warning(
                "Failed to inspect rankings channel %s history: %s",
                channel_id,
                exc,
            )
            return

        try:
            await channel.send(guidance)
        except discord.Forbidden:
            logger.warning(
                "Insufficient permissions to post guidance in rankings channel %s",
                channel_id,
            )
        except discord.HTTPException as exc:
            logger.warning(
                "Failed to send rankings guidance message to channel %s: %s",
                channel_id,
                exc,
            )

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

    def _calculate_event_day(self, kvk_run: "KVKRun") -> tuple[str, Optional[int | str]]:
        """
        Calculate event phase and day based on kvk_run.started_at.
        
        6-Day Model:
        - Days 1-5: PREP phase
        - Day 6: WAR phase
        - Day 7+: Late submissions (still allowed, map to day 6 WAR)
        
        Returns:
            (phase, day) where phase is "prep" or "war"
            day is 1-5 for prep, None for war
        """
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        event_start = kvk_run.started_at
        
        if event_start.tzinfo is None:
            event_start = event_start.replace(tzinfo=timezone.utc)
        
        # Calculate days elapsed since event start
        elapsed = now - event_start
        event_day = elapsed.days + 1  # Day 1 starts at elapsed=0
        
        if event_day <= 0:
            # Before event start → default to Day 1 PREP
            return "prep", 1
        elif event_day <= 5:
            # Days 1-5: PREP phase
            return "prep", event_day
        else:
            # Day 6+: WAR phase (no day subdivision)
            return "war", None
    
    def _format_event_week_label(self, kvk_run: Optional["KVKRun"]) -> str:
        if not kvk_run:
            return self.storage.get_current_event_week()
        if getattr(kvk_run, "is_test", False):
            return f"KVK-TEST-{kvk_run.id}"
        if getattr(kvk_run, "run_number", None):
            return f"KVK-{int(kvk_run.run_number):02d}"
        return f"KVK-{kvk_run.id}"

    async def _validate_submission_payload(
        self,
        *,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        stage_value: Optional[str],
        day: Optional[int],
        kvk_run: "KVKRun",
    ) -> SubmissionValidationResult:
        # AUTO-CALCULATION: If stage not provided, calculate from event start time
        if stage_value is None:
            phase, auto_day = self._calculate_event_day(kvk_run)
            # Use auto-calculated values
            stage_type = StageType.PREP if phase == "prep" else StageType.WAR
            # If day also not provided, use auto-calculated day
            if day is None:
                normalized_day = auto_day
            else:
                # Manual day override
                if day == -1:
                    normalized_day = "overall"
                elif 1 <= day <= 5:
                    normalized_day = day
                else:
                    raise SubmissionValidationError(
                        "Day must be 1-5 for specific prep days, or 'Overall' for prep aggregation."
                    )
        else:
            # MANUAL OVERRIDE: User specified stage explicitly
            stage_key = stage_value.strip().lower()
            stage_map = {"prep": StageType.PREP, "war": StageType.WAR}
            stage_type = stage_map.get(stage_key)
            if stage_type is None:
                raise SubmissionValidationError("Stage must be 'Prep' or 'War'.")

            # CANONICAL PHASE/DAY LOGIC
            # Convert stage_type to canonical phase string
            phase = "prep" if stage_type == StageType.PREP else "war"
            
            if phase == "prep":
                # PREP phase REQUIRES day
                if day is None:
                    raise SubmissionValidationError(
                        "Prep phase requires a day selection (1-5 or Overall).\n"
                        "Please select which prep day you're submitting."
                    )
                # Valid prep days: 1-5 or -1 (Overall)
                if day == -1:
                    normalized_day = "overall"  # Canonical: string "overall"
                elif 1 <= day <= 5:
                    normalized_day = day  # Canonical: integer 1-5
                else:
                    raise SubmissionValidationError(
                        "Day must be 1-5 for specific prep days, or 'Overall' for prep aggregation."
                    )
            else:  # WAR phase
                # WAR phase does NOT use day subdivisions
                if day is not None:
                    raise SubmissionValidationError(
                        "War phase does not use day subdivisions.\n"
                        "Please leave the 'day' field blank when submitting war scores."
                    )
                normalized_day = None  # Canonical: None for war

        content_type = (screenshot.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise SubmissionValidationError("Please upload an image file (PNG, JPG, etc.).")

        if screenshot.size and screenshot.size > 10 * 1024 * 1024:
            raise SubmissionValidationError("Image too large. Please upload a screenshot under 10MB.")

        event_week = self._format_event_week_label(kvk_run)
        guild_id = str(interaction.guild_id) if interaction.guild else None
        user_id = str(interaction.user.id)

        # Use canonical phase/day for duplicate check
        existing = self.storage.check_duplicate_submission(
            user_id,
            guild_id or "0",
            event_week,
            phase,  # canonical "prep" or "war"
            normalized_day,  # 1-5, "overall", or None
            kvk_run_id=kvk_run.id,
        )

        try:
            image_data = await screenshot.read()
        except Exception:
            raise SubmissionValidationError("Could not read the uploaded screenshot. Please try again.")

        is_valid, error_msg = await self.processor.validate_screenshot(image_data)
        if not is_valid:
            self.storage.log_submission(
                user_id,
                guild_id,
                "failed",
                error_message=error_msg,
            )
            raise SubmissionValidationError(f"Screenshot validation failed: {error_msg}")

        try:
            ranking = await self.processor.process_screenshot(
                image_data,
                user_id,
                interaction.user.name,
                guild_id,
            )
        except Exception as exc:
            self.storage.log_submission(
                user_id,
                guild_id,
                "failed",
                error_message=str(exc),
            )
            raise SubmissionValidationError(
                "An unexpected error occurred while processing the screenshot. Please try again."
            ) from exc

        if not ranking:
            self.storage.log_submission(
                user_id,
                guild_id,
                "failed",
                error_message="Could not extract ranking data from image",
            )
            raise SubmissionValidationError(
                "Could not read ranking data from the screenshot. Please ensure all required information is visible."
            )

        detected_phase = ranking.phase
        
        # Validate phase consistency
        if detected_phase != phase:
            self.storage.log_submission(
                user_id,
                guild_id,
                "failed",
                error_message=f"Phase mismatch: selected={phase}, detected={detected_phase}",
            )
            raise SubmissionValidationError(
                f"The screenshot appears to show {detected_phase} phase, but you selected {phase} phase."
            )
        
        # Validate day consistency for PREP phase only
        if phase == "prep":
            detected_day = ranking.day
            # Allow OCR to detect day, but warn if mismatch with user selection
            if detected_day is not None and detected_day != normalized_day:
                # Log warning but don't fail - OCR may be unreliable for day detection
                logger.warning(
                    "Day mismatch for user %s: selected=%s, detected=%s. Using selected day.",
                    user_id, normalized_day, detected_day
                )

        if ranking.rank <= 0:
            self.storage.log_submission(
                user_id,
                guild_id,
                "failed",
                error_message="Extracted rank was non-positive",
            )
            raise SubmissionValidationError("The extracted rank must be a positive number.")

        if ranking.score < 0:
            self.storage.log_submission(
                user_id,
                guild_id,
                "failed",
                error_message="Extracted score was negative",
            )
            raise SubmissionValidationError("The extracted score cannot be negative.")

        # Update ranking with canonical values
        ranking.phase = phase  # Canonical: "prep" or "war"
        ranking.day = normalized_day  # Canonical: 1-5, "overall", or None
        ranking.screenshot_url = screenshot.url
        ranking.event_week = event_week
        ranking.kvk_run_id = kvk_run.id
        ranking.is_test_run = kvk_run.is_test
        ranking.guild_id = guild_id
        ranking.username = interaction.user.display_name or interaction.user.name
        
        # Update legacy fields for backward compatibility
        ranking.stage_type = stage_type
        ranking.day_number = self._canonical_day_to_legacy(normalized_day, phase)

        return SubmissionValidationResult(
            ranking=ranking,
            stage_type=stage_type,
            normalized_day=normalized_day,
            event_week=event_week,
            existing_entry=existing,
        )
    
    def _canonical_day_to_legacy(self, day: Optional[int | str], phase: str) -> Optional[int]:
        """Convert canonical day format to legacy day_number format."""
        if phase == "war":
            return None
        if day == "overall":
            return -1
        if isinstance(day, int):
            return day
        return None

    def _persist_validated_submission(
        self,
        *,
        interaction: discord.Interaction,
        ranking: RankingData,
        kvk_run: "KVKRun",
        normalized_day: int,
        existing: Optional[Dict[str, Any]],
    ) -> tuple[int, str]:
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id) if interaction.guild else None

        action = "Submitted"
        ranking_id: Optional[int] = None
        if existing:
            updated = self.storage.update_ranking(
                existing["id"],
                ranking.rank,
                ranking.score,
                ranking.screenshot_url,
            )
            if updated:
                ranking_id = existing["id"]
                action = "Updated"
            else:
                logger.warning(
                    "Expected to update ranking entry %s but no rows were affected. Falling back to insert.",
                    existing["id"],
                )

        if ranking_id is None:
            ranking_id = self.storage.save_ranking(ranking)

        if self.kvk_tracker:
            try:
                self.kvk_tracker.record_submission(
                    kvk_run_id=kvk_run.id,
                    ranking_id=ranking_id,
                    user_id=interaction.user.id,
                    day_number=normalized_day,
                    stage_type=ranking.stage_type.value,
                    is_test=kvk_run.is_test,
                )
            except Exception:
                logger.exception("Failed to record submission for KVK run %s", kvk_run.id)

        self.storage.log_submission(
            user_id,
            guild_id,
            "success",
            ranking_id=ranking_id,
        )

        return ranking_id, action

    def _build_submission_embed(
        self,
        *,
        ranking: RankingData,
        kvk_run: "KVKRun",
        normalized_day: int,
        run_is_active: bool,
        screenshot_url: Optional[str],
        action: str,
        interaction: discord.Interaction,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{action} ranking entry",
            description=f"Tracking label: {ranking.event_week}",
            color=discord.Color.green(),
            timestamp=ranking.submitted_at,
        )
        player_label = ranking.player_name or interaction.user.display_name or interaction.user.name
        embed.add_field(
            name="Stored data",
            value=(
                f"Guild tag: {ranking.guild_tag or 'N/A'}\n"
                f"Player: {player_label}\n"
                f"Day: {self._format_day_label(normalized_day, ranking.stage_type)}\n"
                f"Rank: #{ranking.rank:,}\n"
                f"Score: {ranking.score:,}"
            ),
            inline=False,
        )

        run_label = "Test run" if kvk_run.is_test else f"Run #{kvk_run.run_number}"
        window_text = (
            f"{kvk_run.started_at.strftime('%Y-%m-%d %H:%M UTC')} - "
            f"{kvk_run.ends_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        status_text = "active" if run_is_active else "closed (admin update)"
        embed.add_field(
            name="KVK window",
            value=f"{run_label}\nPeriod: {window_text}\nStatus: {status_text}",
            inline=False,
        )

        if screenshot_url:
            embed.set_thumbnail(url=screenshot_url)
        embed.set_footer(text="Data saved to rankings database")
        return embed

    def _normalize_day(self, stage_type: "StageType", day: Optional[int]) -> Optional[int]:
        """
        Normalize day value for storage consistency.
        
        Returns:
        - 1-5: Specific prep days
        - -1: Overall prep aggregation
        - None: War stage (no day component)
        """
        if stage_type == StageType.WAR:
            return None  # War has no day subdivision
        return day  # Prep keeps its day value (1-5 or -1)

    def _format_day_label(self, day: Optional[int], stage_type: "StageType") -> str:
        """
        Format day for display.
        
        Args:
            day: 1-5 (prep days), -1 (overall prep), None (war), or legacy 6 (old war format)
            stage_type: PREP or WAR
        """
        if day is None or stage_type == StageType.WAR:
            return "War Stage Total"
        if day == -1:
            return "Prep Stage Overall"
        if day == 6:  # Legacy support for old war format
            return "War Stage Total"
        if stage_type == StageType.PREP:
            mapping = {
                1: "Day 1 - Construction",
                2: "Day 2 - Research",
                3: "Day 3 - Resource & Mob",
                4: "Day 4 - Hero",
                5: "Day 5 - Troop Training",
            }
            return mapping.get(day, f"Day {day}")
        return f"Day {day}"

    def _resolve_entry_stage(self, entry: Dict[str, Any]) -> "StageType":
        """
        Determine stage type from entry data.
        
        Rules:
        - Explicit stage_type field takes precedence
        - day_number=None or 6 → WAR (6 is legacy support)
        - day_number=1-5 or -1 → PREP
        """
        stage_value = entry.get("stage_type")
        if isinstance(stage_value, StageType):
            return stage_value
        if isinstance(stage_value, str):
            if stage_value.lower().startswith("war"):
                return StageType.WAR
            elif stage_value.lower().startswith("prep"):
                return StageType.PREP
        
        # Infer from day_number
        day_number = entry.get("kvk_day") or entry.get("day_number")
        if day_number is None or day_number == 6:  # None or legacy 6 = WAR
            return StageType.WAR
        # Any other day value = PREP
        return StageType.PREP

    def _aggregate_entries(
        self,
        entries: List[Dict[str, Any]],
        *,
        stage: Optional["StageType"] = None,
    ) -> Optional[Dict[str, Any]]:
        if not entries:
            return None
        filtered = [
            row for row in entries
            if stage is None or self._resolve_entry_stage(row) == stage
        ]
        if not filtered:
            return None
        scores = [row.get("score", 0) for row in filtered]
        ranks = [row.get("rank") for row in filtered if row.get("rank") is not None]
        return {
            "score": sum(scores),
            "rank": min(ranks) if ranks else None,
            "samples": len(filtered),
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
        prep_total = self._aggregate_entries(entries, stage=StageType.PREP)
        war_total = self._aggregate_entries(entries, stage=StageType.WAR)
        aggregate_source = prep_total or war_total or self._aggregate_entries(entries)
        if not aggregate_source:
            return None
        summary = {
            "score": aggregate_source.get("score", 0),
            "rank": aggregate_source.get("rank"),
            "samples": aggregate_source.get("samples", 0),
            "kvk_day": None,
            "entries": entries,
            "prep_total": prep_total,
            "war_total": war_total,
        }
        return summary

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
        description="Submit a screenshot of your Top Heroes event ranking",
    )
    @app_commands.choices(
        stage=[
            app_commands.Choice(name="Prep Stage", value="prep"),
            app_commands.Choice(name="War Stage", value="war"),
        ],
        day=[
            app_commands.Choice(name="Day 1 - Construction", value=1),
            app_commands.Choice(name="Day 2 - Research", value=2),
            app_commands.Choice(name="Day 3 - Resource & Mob", value=3),
            app_commands.Choice(name="Day 4 - Hero", value=4),
            app_commands.Choice(name="Day 5 - Troop Training", value=5),
            app_commands.Choice(name="Overall Prep", value=-1),
        ]
    )
    @app_commands.describe(
        screenshot="Upload your ranking screenshot",
        stage="[OPTIONAL] Override auto-detected stage (Prep/War). Leave blank for auto-detect.",
        day="[OPTIONAL] Override auto-detected day (1-5 for Prep). Leave blank for auto-detect.",
    )
    async def submit_ranking(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        stage: Optional[str] = None,
        day: Optional[int] = None
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

        try:
            validation = await self._validate_submission_payload(
                interaction=interaction,
                screenshot=screenshot,
                stage_value=stage,
                day=day,
                kvk_run=kvk_run,
            )
        except SubmissionValidationError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        ranking = validation.ranking
        normalized_day = validation.normalized_day
        stage_type = validation.stage_type

        # ═══════════════════════════════════════════════════════════════════
        # R8 CONFIDENCE-BASED VALIDATION
        # ═══════════════════════════════════════════════════════════════════
        
        # Extract confidence scores from ranking data
        confidence = getattr(ranking, 'confidence', 1.0)  # Default to high if not present
        confidence_map = getattr(ranking, 'confidence_map', {})
        
        # CASE 1: High confidence (≥ 0.99) → Auto-accept
        if confidence >= 0.99:
            if validation.existing_entry:
                await interaction.followup.send(
                    "You already submitted data for this run and day. The previous entry will be replaced.",
                    ephemeral=True,
                )
            
            # R9-P4 - Handle event cycle conflicts and duplicates
            try:
                _ranking_id, action = self._persist_validated_submission(
                    interaction=interaction,
                    ranking=ranking,
                    kvk_run=kvk_run,
                    normalized_day=normalized_day,
                    existing=validation.existing_entry,
                )
            except ValueError as e:
                if str(e) == "duplicate_submission":
                    await interaction.followup.send(
                        "⚠️ This submission was already logged. No changes made.",
                        ephemeral=True
                    )
                    return
                
                if str(e) == "event_cycle_conflict":
                    # Define nested View for cycle confirmation
                    class CycleConfirmView(ui.View):
                        def __init__(self, cog_self):
                            super().__init__(timeout=120)
                            self.cog_self = cog_self
                        
                        @ui.button(label="✅ This is from the CURRENT KVK", style=discord.ButtonStyle.green)
                        async def confirm_btn(self, button_interaction: Interaction, button: ui.Button):
                            await button_interaction.response.defer(ephemeral=False)
                            
                            try:
                                _ranking_id, action = self.cog_self.storage.force_store_submission(
                                    ranking=ranking,
                                    kvk_run_id=kvk_run.id if kvk_run else None
                                )
                                
                                embed = self.cog_self._build_submission_embed(
                                    ranking=ranking,
                                    kvk_run=kvk_run,
                                    normalized_day=normalized_day,
                                    run_is_active=run_is_active,
                                    screenshot_url=screenshot.url,
                                    action=f"{action} (Confirmed)",
                                    interaction=button_interaction,
                                )
                                
                                await button_interaction.followup.send(embed=embed, ephemeral=False)
                            except Exception as ex:
                                await button_interaction.followup.send(
                                    f"❌ Failed to store submission: {ex}",
                                    ephemeral=True
                                )
                            self.stop()
                        
                        @ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
                        async def cancel_btn(self, button_interaction: Interaction, button: ui.Button):
                            await button_interaction.response.send_message(
                                "❌ Submission cancelled.",
                                ephemeral=True
                            )
                            self.stop()
                    
                    warning_embed = discord.Embed(
                        title="⚠️ Event Cycle Conflict Detected",
                        description=(
                            "This screenshot appears to be from a **previous KVK cycle** based on score comparison.\n\n"
                            "If you're certain this is from the **current** event, click **Confirm** below."
                        ),
                        color=discord.Color.orange()
                    )
                    warning_embed.add_field(name="Player", value=ranking.player_name or "Unknown", inline=True)
                    warning_embed.add_field(name="Guild", value=ranking.guild_tag or "Unknown", inline=True)
                    warning_embed.add_field(name="Score", value=f"{ranking.score:,}", inline=True)
                    
                    await interaction.followup.send(
                        embed=warning_embed,
                        view=CycleConfirmView(self),
                        ephemeral=True
                    )
                    return
                
                # Unknown ValueError, re-raise
                raise
            # Continue to success embed below
            
        # CASE 2: Medium confidence (0.95-0.989) → Soft confirm
        elif confidence >= 0.95:
            
            class ConfirmView(ui.View):
                def __init__(self, cog_self):
                    super().__init__(timeout=120)
                    self.cog_self = cog_self
                
                @ui.button(label="✅ Confirm Submission", style=discord.ButtonStyle.success)
                async def confirm_btn(self, button_interaction: Interaction, button: ui.Button):
                    await button_interaction.response.defer(ephemeral=False)
                    
                    # R9 - learn confirmed names/guilds
                    if ranking.player_name:
                        self.cog_self.processor.normalization_cache[("player_name", ranking.player_name)] = ranking.player_name
                    if ranking.guild_tag:
                        self.cog_self.processor.normalization_cache[("guild", ranking.guild_tag)] = ranking.guild_tag
                    
                    # R9-P4 - Handle event cycle conflicts
                    try:
                        _ranking_id, action = self.cog_self._persist_validated_submission(
                            interaction=button_interaction,
                            ranking=ranking,
                            kvk_run=kvk_run,
                            normalized_day=normalized_day,
                            existing=validation.existing_entry,
                        )
                        
                        embed = self.cog_self._build_submission_embed(
                            ranking=ranking,
                            kvk_run=kvk_run,
                            normalized_day=normalized_day,
                            run_is_active=run_is_active,
                            screenshot_url=screenshot.url,
                            action=action,
                            interaction=button_interaction,
                        )
                        
                        await button_interaction.followup.send(embed=embed, ephemeral=False)
                    
                    except ValueError as e:
                        if str(e) == "duplicate_submission":
                            await button_interaction.followup.send(
                                "⚠️ This submission was already logged. No changes made.",
                                ephemeral=True
                            )
                        elif str(e) == "event_cycle_conflict":
                            await button_interaction.followup.send(
                                "⚠️ This screenshot appears to be from a previous KVK cycle. Please submit current event data only.",
                                ephemeral=True
                            )
                        else:
                            raise
                    
                    self.stop()
                
                @ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
                async def cancel_btn(self, button_interaction: Interaction, button: ui.Button):
                    await button_interaction.response.send_message(
                        "❌ Submission cancelled.",
                        ephemeral=True
                    )
                    self.stop()
            
            # Build preview embed
            preview_embed = discord.Embed(
                title="⚠️ Please Confirm Submission",
                description=f"**Confidence: {confidence:.1%}**\n\nPlease verify the extracted data is correct:",
                color=discord.Color.orange()
            )
            preview_embed.add_field(
                name="Player",
                value=ranking.player_name or "*Unknown*",
                inline=True
            )
            preview_embed.add_field(
                name="Guild",
                value=f"[{ranking.guild_tag}]" if ranking.guild_tag else "*Unknown*",
                inline=True
            )
            preview_embed.add_field(
                name="Score",
                value=f"{ranking.score:,}",
                inline=True
            )
            preview_embed.add_field(
                name="Phase",
                value=f"{ranking.phase.title()}",
                inline=True
            )
            if ranking.day:
                preview_embed.add_field(
                    name="Day",
                    value=str(ranking.day).title(),
                    inline=True
                )
            preview_embed.set_footer(text="Click 'Confirm' to proceed or 'Cancel' to abort")
            
            await interaction.followup.send(
                embed=preview_embed,
                view=ConfirmView(self),
                ephemeral=True
            )
            return  # Exit early, wait for button interaction
        
        # CASE 3: Low confidence (< 0.95) → Correction modal
        else:
            
            class CorrectionModal(ui.Modal, title='Correct Ranking Data'):
                def __init__(self, cog_self):
                    super().__init__()
                    self.cog_self = cog_self
                    
                    self.player_name = ui.TextInput(
                        label='Player Name',
                        default=ranking.player_name or '',
                        required=True,
                        max_length=30
                    )
                    self.add_item(self.player_name)
                    
                    self.guild = ui.TextInput(
                        label='Guild Tag',
                        default=ranking.guild_tag or '',
                        required=True,
                        max_length=6
                    )
                    self.add_item(self.guild)
                    
                    self.score = ui.TextInput(
                        label='Score (numbers only)',
                        default=str(ranking.score),
                        required=True,
                        max_length=15
                    )
                    self.add_item(self.score)
                
                async def on_submit(self, modal_interaction: Interaction):
                    await modal_interaction.response.defer(ephemeral=False)
                    
                    # Apply corrections
                    try:
                        corrected_score = int(str(self.score.value).replace(',', '').strip())
                    except ValueError:
                        await modal_interaction.followup.send(
                            "❌ Invalid score format. Please use numbers only.",
                            ephemeral=True
                        )
                        return
                    
                    # Store original OCR values before overwriting
                    original_player_name = ranking.player_name
                    original_guild_tag = ranking.guild_tag
                    
                    # Apply user corrections
                    ranking.player_name = str(self.player_name.value).strip()
                    ranking.guild_tag = str(self.guild.value).strip().upper()
                    ranking.score = corrected_score
                    
                    # R9 - learn corrected canonical forms
                    if original_player_name and original_player_name != ranking.player_name:
                        self.cog_self.processor.normalization_cache[("player_name", original_player_name)] = ranking.player_name
                    if original_guild_tag and original_guild_tag != ranking.guild_tag:
                        self.cog_self.processor.normalization_cache[("guild", original_guild_tag)] = ranking.guild_tag
                    
                    # R9-P4 - Handle event cycle conflicts
                    try:
                        _ranking_id, action = self.cog_self._persist_validated_submission(
                            interaction=modal_interaction,
                            ranking=ranking,
                            kvk_run=kvk_run,
                            normalized_day=normalized_day,
                            existing=validation.existing_entry,
                        )
                        
                        embed = self.cog_self._build_submission_embed(
                            ranking=ranking,
                            kvk_run=kvk_run,
                            normalized_day=normalized_day,
                            run_is_active=run_is_active,
                            screenshot_url=screenshot.url,
                            action=f"{action} (Corrected)",
                            interaction=modal_interaction,
                        )
                        
                        await modal_interaction.followup.send(embed=embed, ephemeral=False)
                    
                    except ValueError as e:
                        if str(e) == "duplicate_submission":
                            await modal_interaction.followup.send(
                                "⚠️ This submission was already logged. No changes made.",
                                ephemeral=True
                            )
                        elif str(e) == "event_cycle_conflict":
                            await modal_interaction.followup.send(
                                "⚠️ This screenshot appears to be from a previous KVK cycle. Please submit current event data only.",
                                ephemeral=True
                            )
                        else:
                            raise
            
            warning_embed = discord.Embed(
                title="🔍 Low Confidence Detected",
                description=f"**Confidence: {confidence:.1%}**\n\nOCR had difficulty reading some values. Please review and correct:",
                color=discord.Color.red()
            )
            warning_embed.add_field(
                name="Detected Player",
                value=ranking.player_name or "*Unknown*",
                inline=True
            )
            warning_embed.add_field(
                name="Detected Guild",
                value=f"[{ranking.guild_tag}]" if ranking.guild_tag else "*Unknown*",
                inline=True
            )
            warning_embed.add_field(
                name="Detected Score",
                value=f"{ranking.score:,}",
                inline=True
            )
            warning_embed.set_footer(text="A correction form will appear - please verify all fields")
            
            await interaction.followup.send(embed=warning_embed, ephemeral=True)
            await interaction.followup.send_modal(CorrectionModal(self))
            return  # Exit early, wait for modal submission
        
        # ═══════════════════════════════════════════════════════════════════
        # END R8 CONFIDENCE VALIDATION
        # Continue with auto-accept path (confidence >= 0.99)
        # ═══════════════════════════════════════════════════════════════════

        embed = self._build_submission_embed(
            ranking=ranking,
            kvk_run=kvk_run,
            normalized_day=normalized_day,
            run_is_active=run_is_active,
            screenshot_url=screenshot.url,
            action=action,
            interaction=interaction,
        )

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
        # Convert stage to canonical phase
        phase = None
        if stage:
            stage_lower = stage.lower()
            if stage_lower == 'prep':
                phase = "prep"
            elif stage_lower == 'war':
                phase = "war"
        
        # Default to current week unless show_all_weeks is True
        event_week = None if show_all_weeks else self.storage.get_current_event_week()
        
        # Use canonical phase/day for leaderboard query
        leaderboard = self.storage.get_guild_leaderboard(
            str(interaction.guild.id),
            event_week=event_week,
            phase=phase,
            day=day,
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
        name="guild_analytics",
        description="🏰 View guild power bracket analysis and rankings"
    )
    @app_commands.describe(
        event_week="Event week (e.g., 2025-45), leave empty for current event"
    )
    async def guild_analytics(
        self,
        interaction: discord.Interaction,
        event_week: Optional[str] = None
    ):
        """
        Display guild-aggregated analytics with power bracket distribution.
        Shows top performers per guild with fair power-based comparisons.
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Resolve KVK run to get event week
        kvk_run, _ = self._resolve_kvk_run(interaction)
        if not event_week:
            if kvk_run:
                event_week = self._format_event_week_label(kvk_run)
            else:
                event_week = self.storage.get_current_event_week()
        
        # Get guild analytics
        guilds = self.storage.get_guild_analytics(event_week, str(interaction.guild.id))
        
        if not guilds:
            await interaction.followup.send(
                f"📭 No guild data found for event week: **{event_week}**\n\n"
                f"Rankings will appear here once members submit their scores using `/kvk ranking submit`.",
                ephemeral=True
            )
            return
        
        # Single guild focus - show detailed member analysis
        if not guilds:
            await interaction.followup.send(
                f"📭 No data found for event week: **{event_week}**",
                ephemeral=True
            )
            return
        
        # Get the first (and likely only) guild
        guild_name, data = list(guilds.items())[0]
        
        # Build output embed
        embed = discord.Embed(
            title=f"🏰 Guild Performance Analytics - {event_week}",
            description=f"**{guild_name}** - {len(data['members'])} active members",
            color=discord.Color.blue()
        )
        
        # Format brackets with emojis
        bracket_text = (
            f"🟫 Bronze: {data['brackets']['Bronze']}  "
            f"⬜ Silver: {data['brackets']['Silver']}  "
            f"🟨 Gold: {data['brackets']['Gold']}  "
            f"💎 Diamond: {data['brackets']['Diamond']}"
        )
        if data['brackets']['Unranked'] > 0:
            bracket_text += f"\n❓ Unranked: {data['brackets']['Unranked']}"
        
        embed.add_field(
            name="📊 Power Distribution",
            value=bracket_text,
            inline=False
        )
        
        # Show top performers by growth
        top_by_growth = sorted(data['members'], key=lambda m: m[3], reverse=True)[:10]
        growth_text = "\n".join([
            f"{i+1}. **{name}** - `{score:,}` [{bracket}] **+{growth}%**"
            for i, (name, score, bracket, growth) in enumerate(top_by_growth)
        ])
        
        embed.add_field(
            name="🔥 Top Performers by Growth",
            value=growth_text or "No data",
            inline=False
        )
        
        # Show top performers by absolute score
        top_by_score = sorted(data['members'], key=lambda m: m[1], reverse=True)[:10]
        score_text = "\n".join([
            f"{i+1}. **{name}** - `{score:,}` [{bracket}] (+{growth}%)"
            for i, (name, score, bracket, growth) in enumerate(top_by_score)
        ])
        
        embed.add_field(
            name="💪 Top Performers by Score",
            value=score_text or "No data",
            inline=False
        )
        
        embed.add_field(
            name="📈 Guild Totals",
            value=f"**Combined Power: `{data['total']:,}`**\nUse `/kvk ranking my_performance` to see your peer comparison!",
            inline=False
        )
        
        embed.set_footer(text=f"Power Brackets: Bronze (0-250k) | Silver (250k-800k) | Gold (800k-2M) | Diamond (2M+)")
        
        await interaction.followup.send(embed=embed)
    
    @ranking.command(
        name="my_performance",
        description="📊 View your personal performance and peer comparison"
    )
    @app_commands.describe(
        event_week="Event week (e.g., 2025-45), leave empty for current event"
    )
    async def my_performance(
        self,
        interaction: discord.Interaction,
        event_week: Optional[str] = None
    ):
        """
        Show personalized performance review with peer comparison.
        Compares you against players with similar power levels (±10%).
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Resolve KVK run to get event week
        kvk_run, _ = self._resolve_kvk_run(interaction)
        if not event_week:
            if kvk_run:
                event_week = self._format_event_week_label(kvk_run)
            else:
                event_week = self.storage.get_current_event_week()
        
        # Get peer comparison
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        comparison = self.storage.get_peer_comparison(user_id, event_week, guild_id)
        
        if not comparison:
            await interaction.followup.send(
                f"❌ No performance data found for you in event week: **{event_week}**\n\n"
                f"Submit your rankings using `/kvk ranking submit` to see your analysis!",
                ephemeral=True
            )
            return
        
        if 'error' in comparison:
            error_type = comparison.get('error')
            
            if error_type == 'no_power':
                embed = discord.Embed(
                    title="⚡ Power Submission Required",
                    description=comparison['message'],
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="📝 How to Submit Power",
                    value=(
                        f"Use `/kvk ranking set_power <your_power>` to submit your account power.\n\n"
                        f"**Example:**\n"
                        f"`/kvk ranking set_power 985000`"
                    ),
                    inline=False
                )
                embed.add_field(
                    name="💡 Why Power Matters",
                    value=(
                        "Power determines your peer group (±10% range).\n"
                        "This ensures you're compared against players of similar account strength!"
                    ),
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            elif error_type == 'no_peers':
                embed = discord.Embed(
                    title="👥 No Peers Found",
                    description=comparison['message'],
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="🔍 What This Means",
                    value=(
                        "No other players with similar power (±10%) have submitted rankings yet.\n"
                        "Check back later as more submissions come in!"
                    ),
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            else:
                # Generic error fallback
                await interaction.followup.send(
                    f"❌ {comparison['message']}",
                    ephemeral=True
                )
                return
        
        user = comparison['user']
        peer_group = comparison['peer_group']
        percentile = comparison['percentile']
        
        # Build personalized embed
        embed = discord.Embed(
            title=f"📊 Your Performance Review - {event_week}",
            description=f"**{user['player_name']}** [{user['bracket']}]",
            color=discord.Color.green() if percentile >= 75 else discord.Color.orange() if percentile >= 50 else discord.Color.red()
        )
        
        # Performance stats
        embed.add_field(
            name="💪 Your Stats",
            value=(
                f"**Final Score:** `{user['power']:,}`\n"
                f"**Growth:** **+{user['growth']}%** (Prep → War)\n"
                f"**Power Bracket:** {user['bracket']}"
            ),
            inline=False
        )
        
        # Peer comparison
        embed.add_field(
            name="👥 Peer Comparison (±10% Power)",
            value=(
                f"**Peer Group Size:** {peer_group['size']} players\n"
                f"**Power Range:** `{peer_group['power_range'][0]:,}` - `{peer_group['power_range'][1]:,}`\n"
                f"**Avg Peer Growth:** +{peer_group['avg_growth']}%"
            ),
            inline=False
        )
        
        # Percentile ranking
        rank_emoji = "🥇" if percentile >= 90 else "🥈" if percentile >= 75 else "🥉" if percentile >= 60 else "📊"
        embed.add_field(
            name=f"{rank_emoji} Your Percentile",
            value=(
                f"**{percentile}th Percentile**\n"
                f"Ranked **#{comparison['rank_in_peers']}** of {peer_group['size']}\n"
                f"Outperformed **{comparison['outperformed_count']}** peers"
            ),
            inline=False
        )
        
        # Performance evaluation
        if percentile >= 90:
            evaluation = "🌟 **Outstanding!** You're in the top 10% of your power bracket."
        elif percentile >= 75:
            evaluation = "🔥 **Excellent!** You're performing in the top quartile."
        elif percentile >= 60:
            evaluation = "✅ **Good!** Above-average performance in your peer group."
        elif percentile >= 40:
            evaluation = "📈 **Average** - Room for improvement compared to similar players."
        else:
            evaluation = "💡 **Below Average** - Consider strategy adjustments for next event."
        
        # Growth analysis
        if user['growth'] > peer_group['avg_growth']:
            growth_eval = f"Your growth (+{user['growth']}%) **exceeds** the peer average (+{peer_group['avg_growth']}%)! 🚀"
        elif user['growth'] > peer_group['avg_growth'] * 0.8:
            growth_eval = f"Your growth (+{user['growth']}%) is **competitive** with peers (+{peer_group['avg_growth']}% avg)."
        else:
            growth_eval = f"Your growth (+{user['growth']}%) is **below** peer average (+{peer_group['avg_growth']}%). Focus on prep → war scaling!"
        
        embed.add_field(
            name="🎯 Evaluation",
            value=f"{evaluation}\n\n{growth_eval}",
            inline=False
        )
        
        # Day-by-day prep progression
        if user['prep_scores']:
            prep_text = "\n".join([
                f"Day {day}: `{score:,}`" for day, score in sorted(user['prep_scores'].items()) if day != 'overall'
            ])
            if 'overall' in user['prep_scores']:
                prep_text += f"\nOverall: `{user['prep_scores']['overall']:,}`"
            
            embed.add_field(
                name="📅 Prep Phase Progression",
                value=prep_text or "No prep data",
                inline=True
            )
        
        if user['war_score']:
            embed.add_field(
                name="⚔️ War Phase",
                value=f"**`{user['war_score']:,}`**",
                inline=True
            )
        
        embed.set_footer(text=f"Compared against {peer_group['size']} players with similar power (±10%)")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @ranking.command(
        name="set_power",
        description="⚡ Submit or update your account power for this event"
    )
    @app_commands.describe(
        power="Your in-game account power (e.g., 985000 or 1200000)"
    )
    async def set_power(
        self,
        interaction: discord.Interaction,
        power: int
    ):
        """
        Submit or update your account power for the current event.
        Power is used to find fair peer comparisons (±10% power range).
        Submit at event start and optionally update at event end.
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        if power < 0:
            await interaction.response.send_message(
                "❌ Power must be a positive number!",
                ephemeral=True
            )
            return
        
        if power > 10_000_000_000:  # 10 billion sanity check
            await interaction.response.send_message(
                "❌ Power value seems unrealistic. Please check and try again.",
                ephemeral=True
            )
            return
        
        # Get current event
        kvk_run, _ = self._resolve_kvk_run(interaction)
        if kvk_run:
            event_week = self._format_event_week_label(kvk_run)
        else:
            event_week = self.storage.get_current_event_week()
        
        # Store power
        user_id = str(interaction.user.id)
        self.storage.set_power(user_id, event_week, power)
        
        # Check if this is an update
        embed = discord.Embed(
            title="⚡ Power Recorded",
            description=f"Your account power for **{event_week}** has been set to **{power:,}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="💡 What's Next?",
            value=(
                "• Submit your daily rankings with `/kvk ranking submit`\n"
                "• View your performance with `/kvk ranking my_performance`\n"
                "• Update power at event end if it changed significantly"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 How Power is Used",
            value=(
                "Your power determines your peer group (±10% range).\n"
                "You'll be ranked against players with similar account strength,\n"
                "ensuring fair performance comparisons!"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
        # Convert stage to canonical phase
        phase = None
        if stage:
            stage_lower = stage.lower()
            if stage_lower == 'prep':
                phase = "prep"
            elif stage_lower == 'war':
                phase = "war"
        
        # Use provided week or current week
        event_week = week or self.storage.get_current_event_week()
        
        # Get all submissions for this week using canonical phase/day
        leaderboard = self.storage.get_guild_leaderboard(
            str(interaction.guild.id),
            event_week=event_week,
            phase=phase,
            day=day,
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

    @ranking.command(
        name="validate",
        description="🔍 [ADMIN] Run data integrity checks for the current KVK event"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def validate_submissions(
        self,
        interaction: discord.Interaction,
        event_week: Optional[str] = None
    ):
        """Admin command to validate event data integrity."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Resolve event week
        if not event_week:
            kvk_run, _ = self._resolve_kvk_run(interaction)
            if kvk_run:
                event_week = self._format_event_week_label(kvk_run)
            else:
                event_week = self.storage.get_current_event_week()
        
        # Run validation checks
        issues = self.storage.validate_event(
            guild_id=str(interaction.guild.id),
            event_week=event_week
        )
        
        if not issues:
            embed = discord.Embed(
                title="✅ Validation Passed",
                description=f"All submissions for **{event_week}** appear valid and consistent.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Checks Performed",
                value=(
                    "✓ Prep score progression\n"
                    "✓ Duplicate war submissions\n"
                    "✓ Missing power data\n"
                    "✓ Data consistency"
                ),
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Build issues report
        embed = discord.Embed(
            title="⚠️ Validation Issues Found",
            description=f"Found **{len(issues)}** potential issues in **{event_week}**:",
            color=discord.Color.orange()
        )
        
        # Group issues by type
        prep_issues = [i for i in issues if "PREP" in i]
        war_issues = [i for i in issues if "WAR" in i or "war" in i]
        power_issues = [i for i in issues if "POWER" in i or "power" in i]
        other_issues = [i for i in issues if i not in prep_issues + war_issues + power_issues]
        
        if prep_issues:
            embed.add_field(
                name="📊 Prep Stage Issues",
                value="\n".join(f"• {issue}" for issue in prep_issues[:5]),
                inline=False
            )
        
        if war_issues:
            embed.add_field(
                name="⚔️ War Stage Issues",
                value="\n".join(f"• {issue}" for issue in war_issues[:5]),
                inline=False
            )
        
        if power_issues:
            embed.add_field(
                name="⚡ Power Data Issues",
                value="\n".join(f"• {issue}" for issue in power_issues[:5]),
                inline=False
            )
        
        if other_issues:
            embed.add_field(
                name="🔍 Other Issues",
                value="\n".join(f"• {issue}" for issue in other_issues[:5]),
                inline=False
            )
        
        if len(issues) > 15:
            embed.set_footer(text=f"Showing first 15 of {len(issues)} issues")
        
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
            prep_total = user_stat.get("prep_total") or {"score": 0, "rank": None, "samples": 0}
            war_total = user_stat.get("war_total") or None
            combined = self._aggregate_entries(entries) or prep_total

            def _format_summary_block(label: str, summary: Dict[str, Any]) -> str:
                rank_value = summary.get("rank")
                rank_line = f"#{rank_value:,}" if isinstance(rank_value, int) else "N/A"
                return f"Rank: {rank_line}\\nScore: {summary.get('score', 0):,}"

            embed.add_field(
                name="Prep Stage Total",
                value=_format_summary_block("Prep Stage Total", prep_total),
                inline=False,
            )
            if war_total:
                embed.add_field(
                    name="War Stage",
                    value=_format_summary_block("War Stage", war_total),
                    inline=False,
                )
                embed.add_field(
                    name="All Stages",
                    value=_format_summary_block("All Stages", combined),
                    inline=False,
                )
            for entry in entries:
                kvk_day = entry.get("kvk_day") or entry.get("day_number") or 6
                stage_enum = self._resolve_entry_stage(entry)
                label = self._format_day_label(int(kvk_day), stage_enum)
                rank_value = entry.get("rank")
                rank_line = f"#{rank_value:,}" if isinstance(rank_value, int) else "N/A"
                embed.add_field(
                    name=label,
                    value=(
                        f"Rank: {rank_line}\n"
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
    
    # ══════════════════════════════════════════════════════════════════
    # PHASE R6: STANDARDIZED EMBED RESPONSE BUILDERS
    # ══════════════════════════════════════════════════════════════════
    
    def _build_prep_day_success_embed(
        self,
        day: int,
        score: int,
        player_name: str,
        guild_tag: str,
        rank: Optional[int],
        was_update: bool
    ) -> discord.Embed:
        """Build success embed for Prep Day submission."""
        action = "Updated" if was_update else "Submitted"
        title = f"✅ Prep Day {day} Ranking {action}!"
        
        embed = discord.Embed(
            title=title,
            description=f"Your **Day {day}** score has been recorded.",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Player", value=f"{player_name} [{guild_tag}]", inline=True)
        embed.add_field(name="Score", value=f"{score:,} points", inline=True)
        if rank:
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        
        if was_update:
            embed.set_footer(text="⚠️ Previous submission for this day was overwritten.")
        else:
            embed.set_footer(text="Day submission saved successfully.")
        
        return embed
    
    def _build_prep_overall_success_embed(
        self,
        score: int,
        player_name: str,
        guild_tag: str,
        rank: Optional[int],
        was_update: bool
    ) -> discord.Embed:
        """Build success embed for Prep Overall submission."""
        action = "Updated" if was_update else "Submitted"
        title = f"✅ Prep Overall Ranking {action}!"
        
        embed = discord.Embed(
            title=title,
            description="Your **Prep Stage Overall** score has been recorded.",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Player", value=f"{player_name} [{guild_tag}]", inline=True)
        embed.add_field(name="Total Score", value=f"{score:,} points", inline=True)
        if rank:
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        
        if was_update:
            embed.set_footer(text="⚠️ Previous overall prep submission was overwritten.")
        else:
            embed.set_footer(text="Overall prep score saved successfully.")
        
        return embed
    
    def _build_war_success_embed(
        self,
        score: int,
        player_name: str,
        guild_tag: str,
        rank: Optional[int],
        was_update: bool
    ) -> discord.Embed:
        """Build success embed for War Day submission."""
        action = "Updated" if was_update else "Submitted"
        title = f"✅ War Stage Ranking {action}!"
        
        embed = discord.Embed(
            title=title,
            description="Your **War Stage** score has been recorded.",
            color=discord.Color.red()
        )
        
        embed.add_field(name="Player", value=f"{player_name} [{guild_tag}]", inline=True)
        embed.add_field(name="Score", value=f"{score:,} points", inline=True)
        if rank:
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        
        if was_update:
            embed.set_footer(text="⚠️ Previous war submission was overwritten.")
        else:
            embed.set_footer(text="War stage score saved successfully.")
        
        return embed
    
    def _build_no_change_embed(self, phase: str, day: Optional[int | str]) -> discord.Embed:
        """Build embed when score hasn't changed."""
        if phase == "prep":
            if day == "overall":
                title = "Prep Overall - No Change"
                desc = "Your overall prep score is already up to date."
            else:
                title = f"Prep Day {day} - No Change"
                desc = f"Your Day {day} score is already up to date."
        else:  # war
            title = "War Stage - No Change"
            desc = "Your war stage score is already up to date."
        
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=desc,
            color=discord.Color.greyple()
        )
        embed.set_footer(text="Submit a new screenshot if your score has changed.")
        return embed
    
    def _build_out_of_phase_error_embed(
        self,
        submitted_phase: str,
        current_phase: str,
        current_day: int
    ) -> discord.Embed:
        """Build error embed for out-of-phase submission."""
        embed = discord.Embed(
            title="❌ Wrong Event Phase",
            description=f"You submitted a **{submitted_phase.title()} Stage** screenshot, but the current phase is **{current_phase.title()} Stage**.",
            color=discord.Color.orange()
        )
        
        if current_phase == "prep":
            embed.add_field(
                name="Current Status",
                value=f"📅 Prep Stage - Day {current_day}",
                inline=False
            )
            embed.add_field(
                name="What to do",
                value="Please submit a screenshot from the **Prep Stage** rankings.",
                inline=False
            )
        else:  # war
            embed.add_field(
                name="Current Status",
                value="⚔️ War Stage - Active",
                inline=False
            )
            embed.add_field(
                name="What to do",
                value="Please submit a screenshot from the **War Stage** rankings.",
                inline=False
            )
        
        return embed
    
    def _build_day_not_unlocked_error_embed(
        self,
        submitted_day: int,
        current_day: int
    ) -> discord.Embed:
        """Build error embed for submitting a future day."""
        embed = discord.Embed(
            title="❌ Day Not Unlocked Yet",
            description=f"You submitted a Day {submitted_day} screenshot, but we're currently on Day {current_day}.",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Current Day",
            value=f"📅 Day {current_day}",
            inline=True
        )
        embed.add_field(
            name="Your Submission",
            value=f"Day {submitted_day}",
            inline=True
        )
        
        embed.add_field(
            name="What to do",
            value=f"Please submit a screenshot from **Day {current_day}** or earlier.",
            inline=False
        )
        
        return embed
    
    def _build_previous_day_update_warning_embed(
        self,
        day: int,
        current_day: int,
        score: int,
        player_name: str,
        guild_tag: str
    ) -> discord.Embed:
        """Build warning embed for updating a previous day (backfill)."""
        embed = discord.Embed(
            title=f"⚠️ Updating Previous Day",
            description=f"You're submitting a Day {day} score, but we're currently on Day {current_day}.",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Submitted Day", value=f"Day {day}", inline=True)
        embed.add_field(name="Current Day", value=f"Day {current_day}", inline=True)
        embed.add_field(name="Score", value=f"{score:,} points", inline=True)
        
        embed.add_field(
            name="✅ Submission Accepted",
            value=f"Your Day {day} score has been updated (backfill).",
            inline=False
        )
        
        embed.set_footer(text=f"Player: {player_name} [{guild_tag}]")
        
        return embed

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
    await bot.add_cog(RankingCog(bot, processor, storage, kvk_tracker=kvk_tracker), override=True)


