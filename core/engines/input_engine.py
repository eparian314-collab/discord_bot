"""
InputEngine
===========

Central hub for incoming Discord messages. Responsibilities:
 - filter/route inbound events
 - build translation jobs through ContextEngine
 - execute translations via ProcessingEngine / TranslationOrchestrator
 - hand results off to OutputEngine
 - surface SOS keywords and light automation hooks

Design goals:
 - resilient error handling (never crash the bot loop)
 - single place to enrich future context/session features
 - small, testable helpers with narrow responsibilities
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Any, Dict, Optional, Set

import discord
from discord.ext import commands

from discord_bot.language_context.context_engine import ContextEngine
from discord_bot.language_context.context_utils import safe_truncate
from discord_bot.language_context.translation_job import TranslationJob
from discord_bot.core.utils import find_bot_channel

logger = logging.getLogger("hippo_bot.input_engine")

EMERGENCY_KEYWORDS: Dict[str, str] = {
    "attack": "Everyone report to base immediately!",
    "help": "Emergency! Assistance required!",
    "intruder": "Security alert! Unknown intruder detected!",
}

SOS_REACTION_EMOJI = "🆘"
ROTATING_LIGHT = "🚨"

# Rate limiting: Prevent SOS spam (one trigger per guild every 60 seconds)
SOS_COOLDOWN_SECONDS = 60


class InputEngine:
    """
    Entry point for inbound Discord events.
    Routes through ContextEngine -> ProcessingEngine -> OutputEngine.
    """

    def __init__(
        self,
        bot: commands.Bot,
        *,
        context_engine: ContextEngine,
        processing_engine: Any,
        output_engine: Any,
        cache_manager: Any,
        role_manager: Any,
        alias_helper: Optional[Any] = None,
        ambiguity_resolver: Optional[Any] = None,
        session_memory: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        error_engine: Optional[Any] = None,
    ) -> None:
        self.bot = bot
        self.context = context_engine
        self.processing = processing_engine
        self.output = output_engine
        self.cache = cache_manager
        self.roles = role_manager
        self.alias = alias_helper
        self.ambig = ambiguity_resolver
        self.session_memory = session_memory
        self.event_bus = event_bus
        self.error_engine = error_engine or getattr(processing_engine, "error_engine", None)

        self._bot_alert_channel_cache: Dict[int, Optional[int]] = {}
        self.active_mirror_pairs: Set[frozenset[int]] = set()
        self._sos_overrides: Dict[int, Dict[str, str]] = {}
        self._sos_cooldowns: Dict[int, float] = {}  # guild_id -> last_trigger_timestamp
        self._processed_sos_messages: Set[int] = set()  # message_id tracking to prevent duplicates
        self._sos_message_cleanup_task: Optional[asyncio.Task] = None

        logger.info("InputEngine initialised")
        
        # Start background task to clean up old message IDs (if an event loop is running)
        self._ensure_cleanup_task()

    # ------------------------------------------------------------------
    # Public handlers
    # ------------------------------------------------------------------
    def _ensure_cleanup_task(self) -> None:
        """Start the SOS cleanup task when an event loop is available."""
        if self._sos_message_cleanup_task and not self._sos_message_cleanup_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop (e.g. during unit tests) - defer startup until later
            return
        self._sos_message_cleanup_task = loop.create_task(self._cleanup_processed_messages())

    async def handle_message(self, message: discord.Message) -> None:
        # Ensure deferred cleanup task starts once we are inside an event loop
        self._ensure_cleanup_task()

        if message.author.bot:
            return

        content = (message.content or "").strip()
        if not content:
            return

        await self._record_session_event(message, content)

        # Emergency keyword detection - but ignore if just mentioning SOS emoji
        # Check if the message is ONLY the emoji (user explaining the feature)
        if content == SOS_REACTION_EMOJI or content.strip() == "🆘":
            logger.debug("Ignoring standalone SOS emoji (user explaining feature)")
            return
        
        # Skip if we've already processed this message for SOS
        if message.id in self._processed_sos_messages:
            logger.debug("Skipping already processed message %s", message.id)
            return
            
        emergency_payload = self._match_emergency_keyword(content, message.guild.id if message.guild else None)
        if emergency_payload:
            # Mark message as processed BEFORE triggering to prevent race conditions
            self._processed_sos_messages.add(message.id)
            await self._trigger_sos(message, emergency_payload)
            return

        # Reply-based mirror translation
        if message.reference and message.reference.resolved:
            await self._handle_mirror_reply(message)
            return

        # Standard translation path
        await self._handle_standard(message)

    async def handle_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Optional hook invoked when bot listens to reaction events."""
        self._ensure_cleanup_task()

        if str(payload.emoji) != SOS_REACTION_EMOJI:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        alert = f"{ROTATING_LIGHT} **SOS reaction detected by <@{payload.user_id}>.** Investigate immediately."
        await channel.send(alert)

    # ------------------------------------------------------------------
    # Core routing helpers
    # ------------------------------------------------------------------
    async def _handle_standard(self, message: discord.Message) -> None:
        guild_id = message.guild.id if message.guild else 0
        author_id = message.author.id
        content = safe_truncate((message.content or "").strip())
        channel_id = getattr(message.channel, "id", None)

        job_env = await self._build_job_for_author(guild_id, author_id, content, channel_id=channel_id)
        if not job_env:
            return

        job = job_env.get("job")
        if not job:
            return

        translated = await self._execute_job(job, guild_id=guild_id, author_id=author_id, original_text=content, channel_id=channel_id)
        if not translated:
            return

        await self.output.send_dm(message.author, translated)

    async def _handle_mirror_reply(self, message: discord.Message) -> None:
        guild_id = message.guild.id if message.guild else 0
        author_id = message.author.id
        reference = message.reference.resolved
        if not isinstance(reference, discord.Message):
            return

        content = safe_truncate((message.content or "").strip())
        channel_id = getattr(message.channel, "id", None)

        job_env = await self._build_job_for_pair(guild_id, author_id, reference.author.id, content, channel_id=channel_id)
        if not job_env:
            return

        job = job_env.get("job")
        if not job:
            return

        translated = await self._execute_job(job, guild_id=guild_id, author_id=author_id, original_text=content, channel_id=channel_id)
        if not translated:
            return

        await self.output.send_ephemeral(message.channel, reference.author, translated)

    # ------------------------------------------------------------------
    # Translation orchestration
    # ------------------------------------------------------------------
    async def _execute_job(
        self,
        job: TranslationJob,
        *,
        guild_id: int,
        author_id: int,
        original_text: str,
        channel_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Execute job via orchestrator (preferred) or fallback adapters.
        Returns translated text or None.
        """
        orchestrator = getattr(self.processing, "orchestrator", None)

        if orchestrator:
            try:
                wrapper = await self.context.translate_for_author_via_orchestrator(
                    guild_id=guild_id,
                    author_id=author_id,
                    orchestrator=orchestrator,
                    text=original_text,
                    channel_id=channel_id,
                )
                resp = wrapper.get("response") if isinstance(wrapper, dict) else None
                if resp and getattr(resp, "text", None):
                    return resp.text
            except Exception as exc:
                await self._log_error(exc, context="orchestrator_path")

        try:
            result = await self.processing.execute_job(job)
            return result
        except Exception as exc:
            await self._log_error(exc, context="execute_job")
            return None

    async def _build_job_for_author(self, guild_id: int, author_id: int, text: str, *, channel_id: Optional[int]) -> Optional[Dict[str, Any]]:
        try:
            return await self.context.plan_for_author(guild_id, author_id, text=text, channel_id=channel_id)
        except Exception as exc:
            await self._log_error(exc, context="plan_for_author")
            return None

    async def _build_job_for_pair(self, guild_id: int, author_id: int, other_user_id: int, text: str, *, channel_id: Optional[int]) -> Optional[Dict[str, Any]]:
        try:
            return await self.context.plan_for_pair(guild_id, author_id, other_user_id, text=text, channel_id=channel_id)
        except Exception as exc:
            await self._log_error(exc, context="plan_for_pair")
            return None

    # ------------------------------------------------------------------
    # SOS helpers
    # ------------------------------------------------------------------
    def _match_emergency_keyword(self, content: str, guild_id: Optional[int]) -> Optional[str]:
        lowered = content.lower()

        if guild_id is not None:
            overrides = self._sos_overrides.get(guild_id, {})
            for keyword, response in overrides.items():
                if keyword in lowered:
                    return response

        for keyword, response in EMERGENCY_KEYWORDS.items():
            if keyword in lowered:
                return response
        return None

    async def _trigger_sos(self, message: discord.Message, mapped_msg: str) -> None:
        guild = message.guild
        guild_id = guild.id if guild else None
        if not guild_id:
            # No guild context (e.g. DM) - still acknowledge the SOS locally
            try:
                await message.channel.send(f"{ROTATING_LIGHT} **SOS Triggered:** {mapped_msg}")
            except Exception as exc:
                logger.warning("Failed to send SOS alert in DM context: %s", exc)
            return
            
        # Check cooldown to prevent spam
        now = time.time()
        last_trigger = self._sos_cooldowns.get(guild_id, 0)
        if now - last_trigger < SOS_COOLDOWN_SECONDS:
            remaining = int(SOS_COOLDOWN_SECONDS - (now - last_trigger))
            logger.info(
                "SOS cooldown active for guild %s (%d seconds remaining)",
                guild_id, remaining
            )
            # Send cooldown message to trigger channel
            await message.channel.send(
                f"⏳ SOS system on cooldown ({remaining}s remaining). Please wait before triggering again.",
                delete_after=10
            )
            return
        
        # Update cooldown timestamp
        self._sos_cooldowns[guild_id] = now
        
        alert = f"{ROTATING_LIGHT} **SOS Triggered:** {mapped_msg}"
        try:
            # Route alerts through the configured bot channel
            bot_channel = find_bot_channel(guild)

            if bot_channel:
                # Send alert in the bot channel
                logger.info(
                    "Sending SOS alert to channel '%s' (ID: %s) in guild %s",
                    bot_channel.name, bot_channel.id, guild_id
                )
                sent = await bot_channel.send(alert)
                with contextlib.suppress(Exception):
                    await sent.add_reaction(SOS_REACTION_EMOJI)
            else:
                # No bot channel found - log error and notify in trigger channel
                logger.error(
                    "No SOS/bot channel found for guild %s - cannot send alert! "
                    "Please configure a 'bot-channel', 'sos', or 'alerts' channel.",
                    guild_id
                )
                await message.channel.send(
                    f"{ROTATING_LIGHT} **SOS Alert Error:** No bot channel configured! "
                    "Please create a channel named 'bot-channel', 'sos', or 'alerts'.",
                    delete_after=15
                )
                return
            
            # Send translated DMs to all users with language roles
            if guild:
                await self._send_sos_dms(guild, mapped_msg, message.author)

            # Delete the triggering message to prevent retriggers
            try:
                await message.delete()
                logger.info(f"Deleted SOS-triggering message {message.id} in guild {guild_id}.")
            except Exception as exc:
                logger.warning(f"Failed to delete SOS-triggering message {message.id}: {exc}")

            # Log to modlog channel if configured
            import os
            modlog_channel_id = os.getenv("MODLOG_CHANNEL_ID")
            if modlog_channel_id:
                modlog_channel = None
                try:
                    modlog_channel = guild.get_channel(int(modlog_channel_id)) if guild else None
                except Exception:
                    modlog_channel = None
                if modlog_channel:
                    log_msg = (
                        f"🛡️ [MODLOG] Deleted SOS-triggering message from {message.author.mention} in #{message.channel.name} (ID: {message.id}).\n"
                        f"Content: {message.content}"
                    )
                    await modlog_channel.send(log_msg)
                else:
                    logger.warning(f"MODLOG_CHANNEL_ID set but channel not found in guild {guild_id}.")

        except Exception as exc:
            await self._log_error(exc, context="trigger_sos")

    def _clear_sos_context(
        self,
        guild_id: int,
        *,
        reset_keywords: bool = True,
        reset_cooldown: bool = True,
        reset_processed_messages: bool = False,
    ) -> None:
        """Clear SOS-related cache/context for a guild."""
        if reset_keywords and guild_id in self._sos_overrides:
            del self._sos_overrides[guild_id]
        if reset_cooldown and guild_id in self._sos_cooldowns:
            del self._sos_cooldowns[guild_id]
        if reset_processed_messages and self._processed_sos_messages:
            self._processed_sos_messages.clear()
        logger.info(
            "SOS context cleared for guild %s (keywords=%s, cooldown=%s, processed=%s)",
            guild_id,
            reset_keywords,
            reset_cooldown,
            reset_processed_messages,
        )

    async def _send_sos_dms(
        self, guild: discord.Guild, sos_message: str, sender: discord.User
    ) -> None:
        """
        Send SOS alert to all guild members with language roles.
        Messages are translated to each user's language role (if not English).
        """
        if not self.roles:
            logger.debug("RoleManager not available, skipping SOS DMs")
            return

        # Get translation orchestrator
        orchestrator = getattr(self.processing, "orchestrator", None) if self.processing else None
        if not orchestrator:
            logger.debug("TranslationOrchestrator not available, skipping translation for SOS DMs")
            # Fall back to sending English-only DMs
            orchestrator = None

        # Track sent DMs to avoid duplicates
        sent_users: Set[int] = set()
        failed_dms = 0

        try:
            # Iterate through all guild members
            for member in guild.members:
                # Skip bots and the sender
                if member.bot or member.id == sender.id or member.id in sent_users:
                    continue

                # Get user's language roles
                try:
                    user_languages = await self.roles.get_user_languages(member.id, guild.id)
                except Exception as exc:
                    logger.warning("Failed to get languages for user %s: %s", member.id, exc)
                    user_languages = []

                # Skip users with no language roles
                if not user_languages:
                    continue

                # Determine target language (use first language role, default to English)
                target_lang = user_languages[0] if user_languages else "en"
                
                # Translate message if not English and orchestrator is available
                translated_msg = sos_message
                if target_lang.lower() != "en" and orchestrator:
                    try:
                        translation, _, provider = await orchestrator.translate_text_for_user(
                            text=sos_message,
                            guild_id=guild.id,
                            user_id=member.id,
                            tgt_lang=target_lang
                        )
                        if translation:
                            translated_msg = translation
                            logger.debug(
                                "Translated SOS for user %s to %s via %s",
                                member.id, target_lang, provider
                            )
                        else:
                            logger.warning(
                                "Translation failed for user %s (target: %s), using original message",
                                member.id, target_lang
                            )
                    except Exception as exc:
                        logger.warning(
                            "Error translating SOS for user %s to %s: %s",
                            member.id, target_lang, exc
                        )

                # Send DM with translated message
                try:
                    dm_alert = (
                        f"{ROTATING_LIGHT} **SOS ALERT** {ROTATING_LIGHT}\n"
                        f"**From:** {sender.mention} in {guild.name}\n"
                        f"**Message:** {translated_msg}\n\n"
                        f"_This is an emergency alert from your server._"
                    )
                    await member.send(dm_alert)
                    sent_users.add(member.id)
                    logger.info("Sent SOS DM to user %s (%s) in language: %s", member.id, member.name, target_lang)
                except discord.Forbidden:
                    logger.debug("Cannot DM user %s (DMs disabled or blocked)", member.id)
                    failed_dms += 1
                except discord.HTTPException as exc:
                    logger.warning("Failed to send DM to user %s: %s", member.id, exc)
                    failed_dms += 1
                except Exception as exc:
                    logger.error("Unexpected error sending DM to user %s: %s", member.id, exc)
                    failed_dms += 1

            logger.info(
                "SOS DM broadcast complete: %d sent, %d failed",
                len(sent_users), failed_dms
            )
        except Exception as exc:
            logger.exception("Error during SOS DM broadcast: %s", exc)
            await self._log_error(exc, context="send_sos_dms")

    # ------------------------------------------------------------------
    # SOS configuration (managed by SOSPhraseCog)
    # ------------------------------------------------------------------
    def set_sos_mapping(self, guild_id: int, mapping: Dict[str, str]) -> None:
        if not mapping:
            # If mapping is empty, clear all SOS context for this guild
            self._clear_sos_context(guild_id, reset_processed_messages=True)
            logger.info(f"SOS mapping cleared for guild {guild_id} via set_sos_mapping.")
        else:
            self._sos_overrides[guild_id] = {k.lower(): v for k, v in mapping.items()}
            logger.info(f"SOS mapping set for guild {guild_id}: {self._sos_overrides[guild_id]}")

    def get_sos_mapping(self, guild_id: int) -> Dict[str, str]:
        return dict(self._sos_overrides.get(guild_id, {}))

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------
    async def _cleanup_processed_messages(self) -> None:
        """
        Background task to periodically clean up old message IDs from the tracking set.
        Keeps memory usage bounded by removing IDs older than the cooldown period.
        """
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                
                # Clear all message IDs since they're now outside cooldown window
                # (messages are only tracked during active cooldown period)
                if self._processed_sos_messages:
                    count = len(self._processed_sos_messages)
                    self._processed_sos_messages.clear()
                    logger.debug("Cleaned up %d processed message IDs", count)
            except asyncio.CancelledError:
                logger.info("SOS message cleanup task cancelled")
                break
            except Exception as exc:
                logger.exception("Error in cleanup task: %s", exc)
                await asyncio.sleep(60)  # Wait a bit before retrying

    async def _record_session_event(self, message: discord.Message, content: str) -> None:
        if not self.session_memory:
            return
        try:
            guild_id = message.guild.id if message.guild else 0
            channel_id = message.channel.id if isinstance(message.channel, discord.abc.GuildChannel) else None
            await self.session_memory.add_event(
                guild_id,
                channel_id=channel_id,
                user_id=message.author.id,
                text=content,
                metadata={"message_id": message.id},
            )
        except Exception as exc:
            await self._log_error(exc, context="session_record")

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    async def _log_error(self, exc: Exception, *, context: str) -> None:
        if not self.error_engine or not hasattr(self.error_engine, "log_error"):
            logger.exception("%s failed: %s", context, exc)
            return
        try:
            maybe = self.error_engine.log_error(exc, context=context)
            if asyncio.iscoroutine(maybe):
                await maybe
        except Exception:
            logger.exception("error_engine.log_error raised while handling %s", context)
