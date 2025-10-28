from __future__ import annotations

import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.utils import is_admin_or_helper


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._welcome_channel_overrides = self._load_channel_overrides()
        self._default_welcome_channel = self._load_default_channel()

    # -----------------
    # Internal helpers
    # -----------------
    @staticmethod
    def _is_admin(member: Optional[discord.Member], guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin or has helper role."""
        return is_admin_or_helper(member, guild)

    def _create_help_embed(self, *, admin: bool = False) -> discord.Embed:
        embed = discord.Embed(
            title="🦛 Hippo Quick Guide",
            description=(
                "Your friendly multilingual companion with games, cookies, and more!\n"
                "Here's everything I can do for you:"
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🌍 Translation",
            value=(
                "`/translate <text> [language]` posts the result for everyone.\n"
                "Want it private? Right-click a message and pick **Translate**."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎭 Language Roles",
            value=(
                "`/language assign <code>` works with names *and* flag emojis "
                "(try `/language assign \N{REGIONAL INDICATOR SYMBOL LETTER J}\N{REGIONAL INDICATOR SYMBOL LETTER P}`).\n"
                "Claim one and I'll stash a cookie for you \N{COOKIE}"
            ),
            inline=False,
        )

        embed.add_field(
            name="🍪 Cookie System",
            value=(
                "Earn cookies by interacting with me! Use `/check_cookies` to see your stats.\n"
                "Cookies unlock features and power the Pokemon game!"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎮 Pokemon Game",
            value=(
                "Feed me 5 cookies with `/feed` to unlock the Pokemon game!\n"
                "Once unlocked: `/catch`, `/fish`, `/explore`, `/train`, `/evolve`\n"
                "Use `/pokemonhelp` for detailed game info."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎉 Fun & Easter Eggs",
            value=(
                "`/easteregg` - Random surprises!\n"
                "`/rps <choice>` - Rock Paper Scissors\n"
                "`/joke`, `/catfact`, `/weather`, `/8ball` - And more!"
            ),
            inline=False,
        )

        embed.add_field(
            name="🆘 SOS Alerts",
            value=(
                "`/sos list` shows the keywords everyone can trigger.\n"
                "Admins can manage them with `/sos add`, `/sos remove`, and `/sos clear`."
            ),
            inline=False,
        )

        if admin:
            embed.add_field(
                name="⚙️ Admin Controls",
                value=(
                    "- `/sos add/remove/clear` to adjust emergency triggers.\n"
                    "- `/keyword set/link/remove/list/clear` to manage custom phrases.\n"
                    "- `/language assign` works for other members too when you mention them."
                ),
                inline=False,
            )

        embed.set_footer(text="Build your relationship with me for better luck and rewards! 🦛💖")
        return embed

    def _create_welcome_embed(self, mention: Optional[discord.abc.User] = None) -> discord.Embed:
        description = (
            "Translate together, keep the vibes cozy, and share the cookie jar."
        )
        if mention is not None:
            description = (
                f"Welcome {mention.mention}! Grab a seat-let's translate together "
                "and keep the vibes cozy."
            )

        embed = discord.Embed(
            title="🦛 Baby Hippo at your service!",
            description=description,
            color=discord.Color.teal(),
        )

        embed.add_field(
            name="Share translations with the table",
            value=(
                "Use `/translate <text> [language]` to broadcast a translation for everyone. "
                "Need a secret whisper? Right-click a message and tap **Translate**."
            ),
            inline=False,
        )

        embed.add_field(
            name="Snag a language role (cookie inside!)",
            value=(
                "`/language assign <code>` understands names and flag emojis-try "
                "`/language assign \N{REGIONAL INDICATOR SYMBOL LETTER J}\N{REGIONAL INDICATOR SYMBOL LETTER P}`.\n"
                "As soon as you claim one, a fresh cookie \N{COOKIE} magically appears."
            ),
            inline=False,
        )

        embed.add_field(
            name="SOS safety net",
            value=(
                "Check the active trigger words with `/sos list` (everyone can see them).\n"
                "Admins can fine-tune the alerts via `/sos add`, `/sos remove`, `/sos clear`."
            ),
            inline=False,
        )

        embed.add_field(
            name="Need more details?",
            value="Use `/help` for a complete guide on all commands and features!",
            inline=False,
        )

        embed.set_footer(text="Glad you're here! Let's keep the translations rolling.")
        return embed

    @staticmethod
    def _load_default_channel() -> Optional[int]:
        # Try BOT_CHANNEL_ID first, fallback to WELCOME_CHANNEL_ID
        raw = os.getenv("BOT_CHANNEL_ID", "")
        if not raw:
            raw = os.getenv("WELCOME_CHANNEL_ID", "")
        if not raw:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None

    @staticmethod
    def _load_channel_overrides() -> dict[int, int]:
        raw = os.getenv("WELCOME_CHANNEL_IDS", "")
        overrides: dict[int, int] = {}
        if not raw:
            return overrides

        for chunk in raw.replace(";", ",").split(","):
            token = chunk.strip()
            if not token:
                continue
            if "=" not in token:
                continue
            guild_id_raw, channel_id_raw = token.split("=", 1)
            try:
                guild_id = int(guild_id_raw.strip())
                channel_id = int(channel_id_raw.strip())
            except ValueError:
                continue
            overrides[guild_id] = channel_id
        return overrides

    def _find_bot_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        me = guild.me

        def can_send(channel: discord.TextChannel) -> bool:
            perms = channel.permissions_for(me or guild.default_role)
            return perms.send_messages

        # First try configured BOT_CHANNEL_ID
        channel_id = self._welcome_channel_overrides.get(guild.id)
        if channel_id is None:
            channel_id = self._default_welcome_channel
        if channel_id:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel) and can_send(channel):
                return channel

        # Fallback: search by name
        preferred_names = ("bot", "bots", "bot-commands", "commands", "general")
        for name in preferred_names:
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel and can_send(channel):
                return channel

        if guild.system_channel and can_send(guild.system_channel):
            return guild.system_channel

        for channel in guild.text_channels:
            if can_send(channel):
                return channel
        return None

    async def _send_welcome(self, guild: discord.Guild, *, mention: Optional[discord.abc.User] = None) -> bool:
        channel = self._find_bot_channel(guild)
        if not channel:
            return False
        embed = self._create_welcome_embed(mention=mention)
        try:
            await channel.send(embed=embed)
            return True
        except Exception:
            return False

    # --------------
    # Slash command
    # --------------
    @app_commands.command(name="help", description="❓ Show a quick overview of HippoBot features")
    async def help(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        member = interaction.user if isinstance(interaction.user, discord.Member) else (guild.get_member(interaction.user.id) if guild else None)
        admin = self._is_admin(member, guild)
        await interaction.response.send_message(
            embed=self._create_help_embed(admin=admin),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self._send_welcome(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        await self._send_welcome(member.guild, mention=member)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
