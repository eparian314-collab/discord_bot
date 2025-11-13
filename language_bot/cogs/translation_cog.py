"""Discord cog responsible for auto-translation workflows."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Iterable, List, Sequence, cast

import discord
from discord.ext import commands
from discord import app_commands

from language_bot.config import LanguageBotConfig
from language_bot.core.translation_orchestrator import TranslationError, TranslationOrchestrator
from language_bot.core.translation_ui_engine import TranslationUIEngine
from language_bot.language_context.flag_map import LanguageDirectory
from language_bot.language_context.localization.personality_phrases import get_madlib_phrase, PERSONALITY_PHRASES, KNOWN_FRIENDS
from language_bot.core.personality_engine import PersonalityEngine


logger = logging.getLogger(__name__)


class TranslationCog(commands.Cog):
    """Listens for mentions and relays private translations."""

    def __init__(
        self,
        bot: commands.Bot,
        config: LanguageBotConfig,
        orchestrator: TranslationOrchestrator,
        ui_engine: TranslationUIEngine,
        language_directory: LanguageDirectory,
    ) -> None:
        self.bot = bot
        self.config = config
        self.orchestrator = orchestrator
        self.ui = ui_engine
        self.language_directory = language_directory
        self.personality_engine = PersonalityEngine(api_key=config.openai_api_key, model=config.openai_model)
        self._jitter_task = self.bot.loop.create_task(self._background_jitter())

    # --------------------------------------------------------------
    # Events
    # --------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or not message.content:
            return
        bot_user = self.bot.user
        if message.author.bot and bot_user and message.author.id == bot_user.id:
            return
        # Personality phrase trigger when bot is mentioned
        if bot_user and bot_user in message.mentions:
            phrase = self.get_personality_phrase("madlibs")
            await message.channel.send(phrase)
            # Optionally, return here to avoid translation logic on mention
            # return
        mention_members = cast(Sequence[discord.Member], message.mentions)
        mentions = [member for member in mention_members if member.id != message.author.id]

        # Always define targets
        if mentions:
            target_map = {member: self._extract_languages(member.roles) for member in mentions}
            targets = {member: langs for member, langs in target_map.items() if langs}
        else:
            targets = {}

        detected_language = self.orchestrator.detect_language(message.content)
        if not detected_language:
            logger.debug("Unable to detect language for message %s", message.id)
            return

        # Auto-translate to server default language if needed
        default_lang = self.config.default_fallback_language.upper()
        if detected_language.upper() != default_lang:
            try:
                result = await self.orchestrator.translate(
                    text=message.content,
                    target_language=default_lang,
                    source_language=detected_language,
                )
                await message.channel.send(
                    f"**Auto-translation ({result.provider}):** {result.translated_text}\n"
                    f"From `{result.source_language}` to `{result.target_language}`"
                )
            except Exception as exc:
                logger.warning(f"Auto-translation failed for message {message.id}: {exc}")

        if targets:
            await self._fan_out_translations(
                message=message,
                detected_language=detected_language,
                targets=targets,
            )

    # --------------------------------------------------------------
    # Slash Commands
    # --------------------------------------------------------------

    @app_commands.command(name="translate", description="Translate text to another language (context-aware)")
    @app_commands.describe(text="Text to translate", target_language="Target language code (e.g. en, es, fr)")
    async def translate_slash(self, interaction: discord.Interaction, text: str, target_language: str):
        await interaction.response.defer()
        # Context-aware: auto-detect source language
        source_language = self.orchestrator.detect_language(text)
        try:
            result = await self.orchestrator.translate(
                text=text,
                target_language=target_language,
                source_language=source_language,
            )
            await interaction.followup.send(
                f"**Translated ({result.provider}):** {result.translated_text}\n"
                f"From `{result.source_language}` to `{result.target_language}`"
            )
        except Exception as exc:
            await interaction.followup.send(f"Translation failed: {exc}")

    def setup_slash(self, bot):
        bot.tree.add_command(self.translate_slash)

    # --------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------

    async def _fan_out_translations(
        self,
        *,
        message: discord.Message,
        detected_language: str,
        targets: dict[discord.Member, List[str]],
    ) -> None:
        tasks: List[asyncio.Task[None]] = []
        for member, languages in targets.items():
            if self._language_supported(detected_language, languages):
                continue
            target_language = languages[0]
            tasks.append(
                asyncio.create_task(
                    self._translate_for_member(
                        member=member,
                        message=message,
                        source_language=detected_language,
                        target_language=target_language,
                    )
                )
            )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _translate_for_member(
        self,
        *,
        member: discord.Member,
        message: discord.Message,
        source_language: str,
        target_language: str,
    ) -> None:
        try:
            result = await self.orchestrator.translate(
                text=message.content,
                target_language=target_language,
                source_language=source_language,
            )
        except TranslationError as exc:
            logger.warning(
                "Unable to translate mention for %s in message %s: %s",
                member.id,
                message.id,
                exc,
            )
            return

        embed = self.ui.build_private_embed(
            author_name=str(message.author),
            message_link=message.jump_url,
            original_text=message.content,
            result=result,
        )
        delivered = await self.ui.notify_user(member=member, embed=embed)
        if not delivered:
            logger.info("DM delivery failed for %s – user has DMs disabled", member.id)

    async def _background_jitter(self):
        await self.bot.wait_until_ready()
        channel_id = self.config.bot_channel_id
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        while not self.bot.is_closed():
            await asyncio.sleep(random.randint(3600, 7200))  # 1-2 hours
            phrase = self.get_personality_phrase()
            if channel:
                await channel.send(phrase)

    def get_personality_phrase(self, category="madlibs"):
        """
        Get a random personality phrase from any category.
        If category is 'madlibs', use get_madlib_phrase for full randomization.
        """
        if category == "madlibs":
            return get_madlib_phrase()
        friend = random.choice(KNOWN_FRIENDS)
        template = random.choice(PERSONALITY_PHRASES.get(category, PERSONALITY_PHRASES["madlibs"]))
        return template.format(friend=friend)

    # For testing: direct invocation
    async def test_send_personality_phrase(self, channel, category="madlibs"):
        phrase = self.get_personality_phrase(category)
        await channel.send(phrase)

    async def send_ai_personality_reply(self, channel, persona, user_message):
        reply = await self.personality_engine.get_ai_personality_reply(persona, user_message)
        await channel.send(reply)

    def _extract_languages(self, roles: Iterable[discord.Role]) -> List[str]:
        languages: List[str] = []
        prefix = self.config.language_role_prefix.lower()
        for role in roles:
            name = role.name.lower()
            if not name.startswith(prefix):
                continue
            fragment = name[len(prefix) :].split(" ", 1)[0]
            iso_code = self.language_directory.iso_from_fragment(fragment)
            if iso_code:
                languages.append(iso_code)
        return languages

    @staticmethod
    def _language_supported(source_language: str, languages: Sequence[str]) -> bool:
        normalized_source = source_language.split("-", 1)[0].lower()
        normalized = {lang.split("-", 1)[0].lower() for lang in languages}
        return normalized_source in normalized


async def setup(bot: commands.Bot) -> None:
    raise RuntimeError("Use LanguageBotRunner to load TranslationCog")


__all__ = ["TranslationCog"]
