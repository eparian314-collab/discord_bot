"""Async bootstrapper for FunBot (lightweight, low-cost options by default)."""

from __future__ import annotations

import asyncio
import logging
import os
import time

import discord
from discord.ext import commands
from dotenv import load_dotenv

from .config import FunBotConfig
from .core.error_engine import ErrorEngine
from .core.game_storage_engine import GameStorageEngine
from .core.cookie_manager import CookieManager
from .core.personality_engine import PersonalityEngine
from .core.personality_memory import PersonalityMemory
from .games.pokemon_data_manager import PokemonDataManager
from .cogs.game_cog import GameCog
from .cogs.help_cog import HelpCog
from .cogs.easteregg_cog import EasterEggCog
from .cogs.battle_cog import BattleCog


logger = logging.getLogger("FunBot")


def _configure_logging() -> None:
    """Configure simple console logging for FunBot if not already set."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )


class FunBotRunner:
    def __init__(self) -> None:
        load_dotenv()
        self.config = FunBotConfig.from_env()
        self.error_engine = ErrorEngine()
        self.error_engine.catch_uncaught()

        # Shared persistent storage and personality for all game systems.
        self.storage = GameStorageEngine(self.config.db_path)
        self.cookie_manager = CookieManager(self.storage)
        self.pokemon_data_manager = PokemonDataManager(self.storage)
        self.personality = PersonalityEngine(persona="classic")
        self.personality_memory = PersonalityMemory(self.storage)

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.bot = commands.Bot(
            command_prefix=self.config.command_prefix,
            intents=intents,
            help_command=None,
        )

        # Expose config and shared managers on the bot instance so cogs can
        # easily depend on them without re-creating connections.
        setattr(self.bot, "config", self.config)
        setattr(self.bot, "game_storage", self.storage)
        setattr(self.bot, "cookie_manager", self.cookie_manager)
        setattr(self.bot, "pokemon_data_manager", self.pokemon_data_manager)
        setattr(self.bot, "personality", self.personality)
        setattr(self.bot, "personality_memory", self.personality_memory)

        # Record startup time and a grace window during which channel
        # restrictions are disabled (for launch celebrations, etc.).
        # Default: first hour after the bot starts.
        unrestricted_seconds_raw = os.getenv("FUNBOT_UNRESTRICTED_SECONDS", "3600").strip()
        try:
            unrestricted_seconds = int(unrestricted_seconds_raw) if unrestricted_seconds_raw else 0
        except ValueError:
            unrestricted_seconds = 3600
        setattr(self.bot, "funbot_start_time", time.time())
        setattr(self.bot, "funbot_grace_window", max(unrestricted_seconds, 0))

        self._log_prelaunch_sequence()

        @self.bot.event  # type: ignore[misc]
        async def on_ready() -> None:
            guild_names = ", ".join(guild.name for guild in self.bot.guilds)
            bot_user = self.bot.user
            user_id = bot_user.id if bot_user else "unknown"
            logger.info("FunBot connected as %s (%s) in %s", bot_user, user_id, guild_names)

        async def setup_hook() -> None:
            try:
                await self.storage.initialize()
                await self.bot.add_cog(GameCog(self.bot))
                await self.bot.add_cog(HelpCog(self.bot))
                await self.bot.add_cog(EasterEggCog(self.bot))
                await self.bot.add_cog(BattleCog(self.bot))
                if os.getenv("TEST_GUILDS"):
                    for chunk in os.getenv("TEST_GUILDS", "").split(","):
                        chunk = chunk.strip()
                        if not chunk:
                            continue
                        await self.bot.tree.sync(guild=discord.Object(id=int(chunk)))
                else:
                    await self.bot.tree.sync()
                logger.info("FunBot slash commands synced")
            except Exception as exc:
                logger.warning("FunBot failed to sync slash commands: %s", exc)

        self.bot.setup_hook = setup_hook  # type: ignore[assignment]

    async def start(self) -> None:
        logger.info("Launch sequence complete. Ignition… connecting to Discord gateway.")
        await self.bot.start(self.config.discord_token)

    async def close(self) -> None:
        await self.storage.close()
        await self.bot.close()

    def _log_prelaunch_sequence(self) -> None:
        """Emit a fun, detailed pre-launch sequence to the terminal."""
        verbose_raw = os.getenv("FUNBOT_VERBOSE_LAUNCH", "1").strip().lower()
        verbose = verbose_raw not in {"0", "false", "no", "off"}
        if not verbose:
            return

        logger.info("==============================================")
        logger.info("      FunBot Launch Control: sequence start    ")
        logger.info("==============================================")

        logger.info("[T-30] Checking environment and configuration…")
        bot_profile = os.getenv("BOT_PROFILE", "fun")
        logger.info("       BOT_PROFILE=%s", bot_profile)
        logger.info("       DB path=%s", self.config.db_path)

        if self.config.bot_channel_ids:
            channels = ", ".join(str(cid) for cid in sorted(self.config.bot_channel_ids))
            logger.info("       Restricted bot channels: %s", channels)
        else:
            logger.info("       Restricted bot channels: <none> (global)")

        if self.config.owner_ids:
            owners = ", ".join(str(oid) for oid in sorted(self.config.owner_ids))
            logger.info("       Owner IDs: %s", owners)

        grace_window = getattr(self.bot, "funbot_grace_window", 0)
        if grace_window:
            logger.info("       Unrestricted play window: %s seconds", grace_window)

        logger.info("[T-20] Initialising storage engine and services…")
        logger.info("       Storage: GameStorageEngine at %s", self.config.db_path)
        logger.info(
            "       Services: CookieManager, PokemonDataManager, PersonalityEngine, PersonalityMemory"
        )

        logger.info("[T-10] Preparing Discord client and cogs…")
        logger.info("       Intents: guilds=%s, message_content=%s", True, True)
        logger.info("       Cogs queued: GameCog, HelpCog, EasterEggCog, BattleCog")

        logger.info("[T-0 ] Ignition command armed. Standing by for Discord connection.")


def run_fun_bot() -> None:
    _configure_logging()
    runner = FunBotRunner()
    try:
        asyncio.run(runner.start())
    except KeyboardInterrupt:
        logger.info("FunBot interrupted by user")


__all__ = ["FunBotRunner", "run_fun_bot"]
