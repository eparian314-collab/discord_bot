from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.engines.translation_ui_engine import TranslationUIEngine
from discord_bot.language_context.context_utils import (
    is_valid_lang_code,
    map_alias_to_code,
    safe_truncate,
)

logger = logging.getLogger("hippo_bot.translation_cog")


class TranslationCog(commands.Cog):
    """Slash and context-menu translations backed by the new engine stack."""

    def __init__(self, bot: commands.Bot, ui_engine: TranslationUIEngine) -> None:
        self.bot = bot
        self.ui = ui_engine

        self.context = getattr(bot, "context_engine", None)
        self.processing = getattr(bot, "processing_engine", None)
        self.orchestrator = getattr(bot, "translation_orchestrator", None) or getattr(
            self.processing, "orchestrator", None
        )
        self.error_engine = getattr(bot, "error_engine", None)
        self.alias_helper = getattr(self.context, "alias_helper", None)
        self.language_map = getattr(bot, "language_map", None)

        # Surface dependencies on the bot so other components stay compatible.
        if not hasattr(bot, "translation_ui"):
            setattr(bot, "translation_ui", ui_engine)

        self._context_menu = app_commands.ContextMenu(
            name="Translate",
            callback=self.translate_message_context,
        )
        try:
            bot.tree.add_command(self._context_menu)
        except app_commands.errors.CommandAlreadyRegistered:
            bot.tree.remove_command(self._context_menu.name, type=self._context_menu.type)
            bot.tree.add_command(self._context_menu)
        except Exception:
            logger.exception("Failed to register translation context menu.")

    def cog_unload(self) -> None:
        try:
            if self._context_menu:
                self.bot.tree.remove_command(self._context_menu.name, type=self._context_menu.type)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to remove translation context menu during unload.")

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

    async def _show(self, interaction: discord.Interaction, result: Any, *, ephemeral: bool) -> None:
        await self.ui.show_result(interaction, result, ephemeral=ephemeral)

    def _normalize_target_code(self, token: str) -> Optional[str]:
        code = map_alias_to_code(token, alias_helper=self.alias_helper, language_map=self.language_map)
        if not code:
            return None
        if not is_valid_lang_code(code, language_map=self.language_map):
            return None
        return code

    async def _perform_translation(
        self,
        interaction: discord.Interaction,
        *,
        text: str,
        force_tgt: Optional[str],
        guild_id: int,
        user_id: int,
        ephemeral: bool = True,
    ) -> None:
        if not self.context:
            await self.ui.show_error(interaction, "Translation engine is not configured.", ephemeral=True)
            return

        text = safe_truncate(text)
        logger.debug(
            "Translation request guild=%s user=%s force_tgt=%s text_len=%d",
            guild_id,
            user_id,
            force_tgt or "auto",
            len(text),
        )

        fail_hints: List[str] = []

        try:
            env = await self.context.translate_for_author_via_orchestrator(
                guild_id,
                user_id,
                orchestrator=self.orchestrator,
                text=text,
                force_tgt=force_tgt,
                timeout=10.0,
                channel_id=getattr(interaction, "channel_id", None),
            )
        except Exception as exc:
            await self._log_error(exc, context="translation.perform")
            fail_hints.append(f"context-engine error: {type(exc).__name__}: {exc}")
            await self.ui.show_error(interaction, "Translation failed. Please try again later.", ephemeral=True)
            return

        response = env.get("response")
        job = env.get("job")

        if response and getattr(response, "text", None):
            payload = {
                "text": response.text,
                "src": getattr(response, "src", None),
                "tgt": getattr(response, "tgt", force_tgt),
                "provider": getattr(response, "provider", None),
            }
            logger.info(
                "Translation succeeded via context engine provider=%s guild=%s user=%s",
                payload.get("provider"),
                guild_id,
                user_id,
            )
            await self._show(interaction, payload, ephemeral=ephemeral)
            return
        elif response:
            meta = getattr(response, "meta", {}) or {}
            error_msg = meta.get("error")
            provider = getattr(response, "provider", None)
            if error_msg:
                prefix = f"{provider} " if provider else ""
                fail_hints.append(f"{prefix}response: {error_msg}")
            elif provider:
                fail_hints.append(f"{provider} returned no text")

        if job and self.processing:
            try:
                translated = await self.processing.execute_job(job)
            except Exception as exc:
                await self._log_error(exc, context="translation.processing_fallback")
                fail_hints.append(f"processing fallback error: {type(exc).__name__}: {exc}")
            else:
                if translated:
                    payload = {"text": translated, "src": job.src_lang, "tgt": job.tgt_lang}
                    logger.info(
                        "Translation succeeded via processing fallback guild=%s user=%s tgt=%s",
                        guild_id,
                        user_id,
                        job.tgt_lang,
                    )
                    await self._show(interaction, payload, ephemeral=ephemeral)
                    return
            fail_hints.append("processing fallback produced no translation")

        if self.orchestrator:
            try:
                translated, src, provider = await self.orchestrator.translate_text_for_user(
                    text=text,
                    guild_id=guild_id,
                    user_id=user_id,
                    tgt_lang=force_tgt,
                )
            except Exception as exc:
                await self._log_error(exc, context="translation.orchestrator_fallback")
                fail_hints.append(f"orchestrator fallback error: {type(exc).__name__}: {exc}")
            else:
                if translated:
                    payload = {"text": translated, "src": src, "tgt": force_tgt, "provider": provider}
                    logger.info(
                        "Translation succeeded via orchestrator fallback provider=%s guild=%s user=%s",
                        provider,
                        guild_id,
                        user_id,
                    )
                    await self._show(interaction, payload, ephemeral=ephemeral)
                    return
            fail_hints.append("orchestrator fallback produced no translation")

        detail = ""
        if fail_hints:
            joined = "; ".join(dict.fromkeys(fail_hints))  # preserve order, drop duplicates
            detail = f"\nDetails: {joined}"

        await self.ui.show_error(
            interaction,
            "No translation was produced. Check engine configuration or try a different input." + detail,
            ephemeral=ephemeral,
        )
        logger.warning(
            "Translation failed guild=%s user=%s force_tgt=%s hints=%s",
            guild_id,
            user_id,
            force_tgt or "auto",
            "; ".join(fail_hints) if fail_hints else "none",
        )

    @app_commands.command(name="translate", description="Translate text to a specific language (optional).")
    @app_commands.describe(
        text="Text to translate.",
        target="Optional language code or name (e.g., en, French).",
    )
    async def translate(self, interaction: discord.Interaction, text: str, target: Optional[str] = None) -> None:
        payload = text.strip()
        if not payload:
            await self.ui.show_error(interaction, "Please provide some text to translate.", ephemeral=True)
            return

        target_code = None
        if target:
            target_code = self._normalize_target_code(target)
            if not target_code:
                await self.ui.show_error(
                    interaction,
                    "I couldn't recognise that language. Try standard codes like `en`, `es`, or spell it out like `French`.",
                    ephemeral=True,
                )
                return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False)

        guild_id = interaction.guild_id or 0
        await self._perform_translation(
            interaction,
            text=payload,
            force_tgt=target_code,
            guild_id=guild_id,
            user_id=interaction.user.id,
            ephemeral=False,
        )

    @translate.autocomplete("target")
    async def translate_target_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        manager = getattr(self.bot, "role_manager", None)
        if not manager:
            return []

        guild_id = interaction.guild_id or (interaction.guild.id if interaction.guild else 0)
        user_codes: List[str] = []
        if guild_id:
            try:
                user_codes = await manager.get_user_languages(interaction.user.id, guild_id)
            except Exception:
                user_codes = []

        suggestions: List[Tuple[str, str]] = []
        seen: set[str] = set()

        def extend(codes: Optional[List[str]], limit: int) -> None:
            if codes is None:
                pool = manager.suggest_languages(current, limit=limit)
            else:
                pool = manager.suggest_languages(current, limit=limit, restrict_to=codes)
            for code, label in pool:
                if code not in seen:
                    seen.add(code)
                    suggestions.append((code, label))

        if user_codes:
            extend(user_codes, limit=10)
        if len(suggestions) < 25:
            extend(None, limit=25 - len(suggestions))

        return [app_commands.Choice(name=f"{label} ({code})", value=code) for code, label in suggestions]

    async def translate_message_context(self, interaction: discord.Interaction, message: discord.Message) -> None:
        if not message.content:
            await interaction.response.send_message("That message doesn't contain any text to translate.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        guild_id = message.guild.id if message.guild else (interaction.guild_id or 0)
        await self._perform_translation(
            interaction,
            text=message.content,
            force_tgt=None,
            guild_id=guild_id,
            user_id=interaction.user.id,
            ephemeral=True,
        )


async def setup_translation_cog(bot: commands.Bot, ui_engine: TranslationUIEngine) -> None:
    await bot.add_cog(TranslationCog(bot, ui_engine))
