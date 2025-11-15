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
            try:
                wipe_raw = os.getenv("LANGUAGEBOT_WIPE_COMMANDS", "").strip().lower()
                wipe_commands = wipe_raw in {"1", "true", "yes", "on"}

                if wipe_commands:
                    logger.warning(
                        "LANGUAGEBOT_WIPE_COMMANDS is enabled – clearing all registered "
                        "slash commands for LanguageBot from Discord."
                    )
                    # Clear global commands from the local tree and propagate the empty
                    # state to Discord (removes any existing global app commands).
                    self.bot.tree.clear_commands(guild=None)
                    await self.bot.tree.sync()

                    # Also clear any guild-scoped commands that may have been synced
                    # using TEST_GUILDS / per‑guild registration.
                    if self.config.test_guild_ids:
                        for gid in self.config.test_guild_ids:
                            guild = discord.Object(id=gid)
                            self.bot.tree.clear_commands(guild=guild)
                            await self.bot.tree.sync(guild=guild)

                    logger.info(
                        "LanguageBot slash commands wiped from Discord. "
                        "Restart without LANGUAGEBOT_WIPE_COMMANDS to resync fresh commands."
                    )
                    return

                # Normal boot path: load cogs and sync the current command set.
                translation_cog = TranslationCog(
                    self.bot,
                    self.config,
                    orchestrator,
                    ui_engine,
                    self.language_directory,
                )
                await self.bot.add_cog(translation_cog)
                await self.bot.add_cog(
                    LanguageRoleManager(
                        self.bot,
                        self.config,
                        self.language_directory,
                    )
                )

                translation_cog.setup_slash(self.bot)
                if self.config.test_guild_ids:
                    for gid in self.config.test_guild_ids:
                        guild = discord.Object(id=gid)
                        await self.bot.tree.sync(guild=guild)
                else:
                    await self.bot.tree.sync()
                logger.info("Slash commands synced")
            except Exception as exc:
                logger.warning("Failed to sync slash commands: %s", exc)

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
