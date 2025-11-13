"""Auto-manage language roles by watching for flag emojis."""

from __future__ import annotations

import logging
from typing import List, Sequence, cast

import discord
from discord.ext import commands
from discord.utils import find

from language_bot.config import LanguageBotConfig
from language_bot.language_context.flag_map import LanguageDirectory, LanguageSpec


logger = logging.getLogger(__name__)


class LanguageRoleManager(commands.Cog):
    """Assigns/removes language roles based on flag usage."""

    def __init__(self, bot: commands.Bot, config: LanguageBotConfig, directory: LanguageDirectory) -> None:
        self.bot = bot
        self.config = config
        self.directory = directory

    # --------------------------------------------------------------
    # Message + reaction listeners
    # --------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        author = cast(discord.Member, message.author)
        specs = self.directory.specs_from_text(message.content)
        if specs:
            await self._assign_roles(author, specs)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        bot_user = self.bot.user
        if payload.guild_id is None or (bot_user and payload.user_id == bot_user.id):
            return
        emoji = str(payload.emoji)
        spec = self.directory.resolve_by_flag(emoji)
        if not spec:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.HTTPException:
                return
        member = payload.member or guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException:
                return
        await self._assign_roles(cast(discord.Member, member), [spec])

    # --------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------

    async def _assign_roles(self, member: discord.Member, specs: Sequence[LanguageSpec]) -> None:
        if member.bot:
            return

        roles_to_add: List[discord.Role] = []
        for spec in specs:
            role = await self._ensure_role(member.guild, spec)
            if role and role not in member.roles:
                roles_to_add.append(role)
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Auto language role assignment via flag emoji")
            except discord.Forbidden:
                logger.warning("Missing permissions to add language roles in guild %s", member.guild.id)
            except discord.HTTPException as exc:
                logger.warning("Failed to add language roles: %s", exc)

    async def _ensure_role(self, guild: discord.Guild, spec: LanguageSpec) -> discord.Role | None:
        target_name = f"{self.config.language_role_prefix}{spec.default_role_slug}"
        role = find(lambda r: r.name.lower() == target_name.lower(), guild.roles)
        if role:
            return role
        try:
            role = await guild.create_role(
                name=target_name,
                mentionable=True,
                reason="Auto-created language role",
            )
            logger.info("Created missing language role %s in guild %s", target_name, guild.id)
            return role
        except discord.Forbidden:
            logger.warning("Missing permissions to create role %s in guild %s", target_name, guild.id)
        except discord.HTTPException as exc:
            logger.warning("Failed to create language role %s: %s", target_name, exc)
        return None


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - dynamic loading guard
    raise RuntimeError("Use LanguageBotRunner to load LanguageRoleManager")


__all__ = ["LanguageRoleManager"]
