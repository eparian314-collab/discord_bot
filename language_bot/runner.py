"""Async bootstrapper for LanguageBot."""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from language_bot.config import LanguageBotConfig
from language_bot.core.error_engine import ErrorEngine
from language_bot.core.translation_orchestrator import TranslationOrchestrator
from language_bot.core.translation_ui_engine import TranslationUIEngine
from language_bot.cogs.translation_cog import TranslationCog
from language_bot.cogs.role_management_cog import LanguageRoleManager
from language_bot.language_context.flag_map import LanguageDirectory


logger = logging.getLogger(__name__)


class LanguageBotRunner:
    """Full lifecycle manager for the discord.py bot instance."""

    def __init__(self) -> None:
        load_dotenv()
        self.config = LanguageBotConfig.from_env()
        self.error_engine = ErrorEngine()
        self.error_engine.catch_uncaught()

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        self.bot = commands.Bot(
            command_prefix=os.getenv("BOT_PREFIX", "!"),
            intents=intents,
            help_command=None,
        )

        self.language_directory = LanguageDirectory.default()
        orchestrator = TranslationOrchestrator(self.config)
        ui_engine = TranslationUIEngine()

        async def setup_hook() -> None:
            await self.bot.add_cog(
                TranslationCog(
                    self.bot,
                    self.config,
                    orchestrator,
                    ui_engine,
                    self.language_directory,
                )
            )
            await self.bot.add_cog(
                LanguageRoleManager(
                    self.bot,
                    self.config,
                    self.language_directory,
                )
            )

        self.bot.setup_hook = setup_hook  # type: ignore[assignment]

        @self.bot.event  # type: ignore[misc]
        async def on_ready() -> None:
            guild_names = ", ".join(guild.name for guild in self.bot.guilds)
            bot_user = self.bot.user
            user_id = bot_user.id if bot_user else "unknown"
            logger.info("LanguageBot connected as %s (%s) in %s", bot_user, user_id, guild_names)

    async def start(self) -> None:
        await self.bot.start(self.config.discord_token)

    async def close(self) -> None:
        await self.bot.close()


def run_language_bot() -> None:
    runner = LanguageBotRunner()
    try:
        asyncio.run(runner.start())
    except KeyboardInterrupt:
        logger.info("LanguageBot interrupted by user")


__all__ = ["LanguageBotRunner", "run_language_bot"]
