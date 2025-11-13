"""Async bootstrapper for FunBot (lightweight, low-cost options by default)."""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from .config import FunBotConfig
from .core.error_engine import ErrorEngine


logger = logging.getLogger(__name__)


class FunBotRunner:
    def __init__(self) -> None:
        load_dotenv()
        self.config = FunBotConfig.from_env()
        self.error_engine = ErrorEngine()
        self.error_engine.catch_uncaught()

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.bot = commands.Bot(
            command_prefix=self.config.command_prefix,
            intents=intents,
            help_command=None,
        )

        @self.bot.event  # type: ignore[misc]
        async def on_ready() -> None:
            guild_names = ", ".join(guild.name for guild in self.bot.guilds)
            bot_user = self.bot.user
            user_id = bot_user.id if bot_user else "unknown"
            logger.info("FunBot connected as %s (%s) in %s", bot_user, user_id, guild_names)

        # Minimal fun commands to ensure working bot
        @self.bot.tree.command(name="ping", description="Check bot latency")
        async def ping(interaction: discord.Interaction) -> None:  # pragma: no cover - runtime behavior
            await interaction.response.send_message("Pong!", ephemeral=True)

        @self.bot.tree.command(name="roll", description="Roll a dice (1-6)")
        async def roll(interaction: discord.Interaction) -> None:  # pragma: no cover - runtime behavior
            import random

            await interaction.response.send_message(f"You rolled: {random.randint(1, 6)}")

        async def setup_hook() -> None:
            try:
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
        await self.bot.start(self.config.discord_token)

    async def close(self) -> None:
        await self.bot.close()


def run_fun_bot() -> None:
    runner = FunBotRunner()
    try:
        asyncio.run(runner.start())
    except KeyboardInterrupt:
        logger.info("FunBot interrupted by user")


__all__ = ["FunBotRunner", "run_fun_bot"]

