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
from typing import Any, Dict, Optional, Set

import discord
from discord.ext import commands

from discord_bot.language_context.context_engine import ContextEngine
from discord_bot.language_context.context_utils import safe_truncate
from discord_bot.language_context.translation_job import TranslationJob

logger = logging.getLogger("hippo_bot.input_engine")

EMERGENCY_KEYWORDS: Dict[str, str] = {
    "attack": "Everyone report to base immediately!",
    "help": "Emergency! Assistance required!",
    "intruder": "Security alert! Unknown intruder detected!",
}

SOS_REACTION_EMOJI = "🆘"
ROTATING_LIGHT = "🚨"


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

        logger.info("InputEngine initialised")

    # ------------------------------------------------------------------
    # Public handlers
    # ------------------------------------------------------------------
    async def handle_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        content = (message.content or "").strip()
        if not content:
            return

        await self._record_session_event(message, content)

        # Emergency keyword detection
        emergency_payload = self._match_emergency_keyword(content, message.guild.id if message.guild else None)
        if emergency_payload:
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

        job_env = await self._build_job_for_author(guild_id, author_id, content)
        if not job_env:
            return

        job = job_env.get("job")
        if not job:
            return

        translated = await self._execute_job(job, guild_id=guild_id, author_id=author_id, original_text=content)
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

        job_env = await self._build_job_for_pair(guild_id, author_id, reference.author.id, content)
        if not job_env:
            return

        job = job_env.get("job")
        if not job:
            return

        translated = await self._execute_job(job, guild_id=guild_id, author_id=author_id, original_text=content)
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

    async def _build_job_for_author(self, guild_id: int, author_id: int, text: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.context.plan_for_author(guild_id, author_id, text=text)
        except Exception as exc:
            await self._log_error(exc, context="plan_for_author")
            return None

    async def _build_job_for_pair(self, guild_id: int, author_id: int, other_user_id: int, text: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.context.plan_for_pair(guild_id, author_id, other_user_id, text=text)
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
        alert = f"{ROTATING_LIGHT} **SOS Triggered:** {mapped_msg}"
        try:
            sent = await message.channel.send(alert)
            with contextlib.suppress(Exception):
                await sent.add_reaction(SOS_REACTION_EMOJI)
        except Exception as exc:
            await self._log_error(exc, context="trigger_sos")

    # ------------------------------------------------------------------
    # SOS configuration (managed by SOSPhraseCog)
    # ------------------------------------------------------------------
    def set_sos_mapping(self, guild_id: int, mapping: Dict[str, str]) -> None:
        self._sos_overrides[guild_id] = {k.lower(): v for k, v in mapping.items()}

    def get_sos_mapping(self, guild_id: int) -> Dict[str, str]:
        return dict(self._sos_overrides.get(guild_id, {}))

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------
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
