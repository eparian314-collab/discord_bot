from __future__ import annotations

import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.utils import find_bot_channel, is_admin_or_helper


class HelpMenuView(discord.ui.View):
    """Carousel-style navigation for the help embeds."""

    def __init__(self, *, pages: list[discord.Embed], user_id: int) -> None:
        if not pages:
            raise ValueError("HelpMenuView requires at least one page.")
        super().__init__(timeout=180)
        self._pages = pages
        self._user_id = user_id
        self._index = 0
        self._sync_button_state()

    def render(self) -> discord.Embed:
        embed = self._pages[self._index].copy()
        embed.set_footer(
            text=f"Page {self._index + 1}/{len(self._pages)} • Build your relationship with me for better luck!"
        )
        return embed

    def _sync_button_state(self) -> None:
        disable_prev = self._index == 0
        disable_next = self._index >= len(self._pages) - 1
        if hasattr(self, "previous_button"):
            self.previous_button.disabled = disable_prev
        if hasattr(self, "next_button"):
            self.next_button.disabled = disable_next

    async def _update(self, interaction: discord.Interaction) -> None:
        self._sync_button_state()
        await interaction.response.edit_message(embed=self.render(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._user_id:
            await interaction.response.send_message(
                "Only the person who opened this help menu can use the navigation buttons.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Back", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self._index > 0:
            self._index -= 1
        await self._update(interaction)

    @discord.ui.button(label="Next", emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self._index < len(self._pages) - 1:
            self._index += 1
        await self._update(interaction)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._welcome_channel_overrides = self._load_channel_overrides()

    # -----------------
    # Internal helpers
    # -----------------
    @staticmethod
    def _is_admin(member: Optional[discord.Member], guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin or has helper role."""
        return is_admin_or_helper(member, guild)

    def _build_help_pages(self, *, admin: bool = False) -> list[discord.Embed]:
        color = discord.Color.blurple()
        pages: list[discord.Embed] = []

        overview = discord.Embed(
            title="Hippo Quick Guide",
            description="Use `/help` any time for this interactive menu. Tap the arrows below to explore categories.",
            color=color,
        )
        overview.add_field(
            name="Translate anything",
            value=(
                "- `/translate <text> [language]` shares results with the whole channel.\n"
                "- Prefer a private copy? Right-click a message and choose **Translate**."
            ),
            inline=False,
        )
        overview.add_field(
            name="Grab a language role",
            value=(
                "- `/language assign <code>` accepts names or flag emojis "
                "(try `/language assign \N{REGIONAL INDICATOR SYMBOL LETTER J}\N{REGIONAL INDICATOR SYMBOL LETTER P}`).\n"
                "- Claiming a role drops a fresh cookie into your stash."
            ),
            inline=False,
        )
        overview.add_field(
            name="Cookie economy",
            value=(
                "- Earn cookies by hanging out with me and running commands.\n"
                "- `/check_cookies` keeps track of your total.\n"
                "- Cookies unlock mini-games and power-ups."
            ),
            inline=False,
        )
        overview.set_footer(text="Need extra help? Ping an admin or helper!")
        pages.append(overview)

        activities = discord.Embed(
            title="Play & Discover",
            description="Ready for more than translations? Try these features next.",
            color=color,
        )
        activities.add_field(
            name="Pokemon adventure",
            value=(
                "- Feed me 5 cookies with `/feed` to unlock the Pokemon game.\n"
                "- Core commands: `/catch`, `/fish`, `/explore`, `/train`, `/evolve`.\n"
                "- `/pokemonhelp` shows every move and bonus."
            ),
            inline=False,
        )
        activities.add_field(
            name="Fun commands & easter eggs",
            value=(
                "- `/easteregg`, `/rps <choice>`, `/joke`, `/catfact`, `/weather`, `/8ball`, and more.\n"
                "- Run them in a chill channel so main chats stay tidy."
            ),
            inline=False,
        )
        activities.add_field(
            name="SOS safety net",
            value=(
                "- Anyone can run `/sos list` to see the current trigger words.\n"
                "- Helpers and admins keep the list fresh so alerts stay useful."
            ),
            inline=False,
        )
        activities.set_footer(text="Tip: keeping cookies stocked boosts your luck in games.")
        pages.append(activities)

        if admin:
            admin_embed = discord.Embed(
                title="Admin & Helper Toolkit",
                description="Extra controls for moderators, helpers, and staff.",
                color=discord.Color.teal(),
            )
            admin_embed.add_field(
                name="Manage SOS alerts",
                value="- `/sos add`, `/sos remove`, `/sos clear` keep emergency keywords relevant.",
                inline=False,
            )
            admin_embed.add_field(
                name="Keyword automations",
                value="- `/keyword set/link/remove/list/clear` tune automatic replies and helper phrases.",
                inline=False,
            )
            admin_embed.add_field(
                name="Assign roles for others",
                value="- Mention a member when using `/language assign` to help them pick a role.",
                inline=False,
            )
            admin_embed.set_footer(text="Thanks for keeping the community safe and organized.")
            pages.append(admin_embed)

        return pages

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
            title="dY�> Baby Hippo at your service!",
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

        return find_bot_channel(guild)

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
    @app_commands.command(name="help", description="Show a modern interactive overview of HippoBot features.")
    async def help(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        member = interaction.user if isinstance(interaction.user, discord.Member) else (
            guild.get_member(interaction.user.id) if guild else None
        )
        admin = self._is_admin(member, guild)
        pages = self._build_help_pages(admin=admin)
        view = HelpMenuView(pages=pages, user_id=interaction.user.id)
        await interaction.response.send_message(
            embed=view.render(),
            view=view,
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
