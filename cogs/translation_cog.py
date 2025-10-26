from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.engines.translation_ui_engine import TranslationUIEngine

logger = logging.getLogger("hippo_bot.translation_cog")


class TranslationCog(commands.Cog):
    """Slash command translations backed by the new engine stack."""

    def __init__(self, bot: commands.Bot, ui_engine: TranslationUIEngine) -> None:
        self.bot = bot
        self.ui = ui_engine

        self.context = getattr(bot, "context_engine", None)
        self.processing = getattr(bot, "processing_engine", None)
        self.orchestrator = getattr(bot, "translation_orchestrator", None) or getattr(
            self.processing, "orchestrator", None
        )
        self.error_engine = getattr(bot, "error_engine", None)

        # Surface dependencies on the bot so other components stay compatible.
        if not hasattr(bot, "translation_ui"):
            setattr(bot, "translation_ui", ui_engine)

    async def _log_error(self, exc: Exception, *, context: str) -> None:
        if self.error_engine and hasattr(self.error_engine, "log_error"):
            try:
                maybe = self.error_engine.log_error(exc, context=context)
                if asyncio.iscoroutine(maybe):
                    await maybe
                return
            except Exception:
                pass
        logger.exception("%s failed: %s", context, exc)

    async def _show(self, interaction: discord.Interaction, result: Any) -> None:
        await self.ui.show_result(interaction, result, ephemeral=True)

    @app_commands.command(name="translate", description="Translate text using the configured engines.")
    async def translate(self, interaction: discord.Interaction, text: str) -> None:
        payload = text.strip()
        if not payload:
            await self.ui.show_error(interaction, "Please provide some text to translate.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id or 0
        user_id = interaction.user.id

        # Preferred path: ContextEngine orchestration (plans + orchestrator + processing fallback)
        try:
            if self.context:
                env = await self.context.translate_for_author_via_orchestrator(
                    guild_id,
                    user_id,
                    orchestrator=self.orchestrator,
                    text=payload,
                    timeout=10.0,
                )
                response = env.get("response")
                job = env.get("job")

                if response and getattr(response, "text", None):
                    await self._show(interaction, response)
                    return

                if job and self.processing:
                    translated = await self.processing.execute_job(job)
                    if translated:
                        await self._show(
                            interaction,
                            {"text": translated, "src": job.src_lang, "tgt": job.tgt_lang},
                        )
                        return

            # Secondary path: orchestrator-only (no planning info)
            if self.orchestrator:
                translated, src, provider = await self.orchestrator.translate_text_for_user(
                    text=payload,
                    guild_id=guild_id,
                    user_id=user_id,
                )
                if translated:
                    await self._show(
                        interaction,
                        {"text": translated, "src": src, "provider": provider},
                    )
                    return
        except Exception as exc:
            await self._log_error(exc, context="translation_cog.translate")
            await self.ui.show_error(interaction, "Translation failed. Please try again later.", ephemeral=True)
            return

        await self.ui.show_error(
            interaction,
            "No translation was produced. Check engine configuration or try a different input.",
            ephemeral=True,
        )


async def setup_translation_cog(bot: commands.Bot, ui_engine: TranslationUIEngine) -> None:
    await bot.add_cog(TranslationCog(bot, ui_engine))
