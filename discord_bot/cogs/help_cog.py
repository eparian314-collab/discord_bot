from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Sequence, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.core.utils import find_bot_channel, is_admin_or_helper

#
# Interactive help metadata
#


@dataclass(frozen=True)
class HelpPage:
    """Represents a single page in the interactive help navigator."""

    key: str
    title: str
    body: str
    commands: Sequence[Tuple[str, str]]
    use_summary_embed: bool = False


class HelpSession:
    """Tracks per-user navigation state for the interactive help view."""

    _EXPIRY = timedelta(minutes=5)

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.page = 0
        self.updated_at: datetime = datetime.now(timezone.utc)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) - self.updated_at > self._EXPIRY

    def move(self, delta: int, total: int) -> None:
        self.set_index(self.page + delta, total)

    def set_index(self, index: int, total: int) -> None:
        total = max(total, 1)
        self.page = index % total
        self.touch()


COMMAND_HINTS: Dict[str, str] = {
    "/help": "Show this quick guide. Use the buttons to browse categories.",
    "/translate": (
        "**Usage:** `/translate text:Hello world language:es`\n"
        "• Share translations with everyone in the channel.\n"
        "• Leave `language` blank to auto-detect a preferred target."
    ),
    "Context ▸ Translate": (
        "Right-click (or long-press) a message → **Apps → Translate** to grab a private translation without cluttering chat."
    ),
    "/language_assign": (
        "Add a language role. Accepts ISO codes (`en`, `es`, `fr`) and flag emojis.\n"
        "Assigning a role rewards a cookie and improves auto-detection."
    ),
    "/language_remove": "Remove one of your language roles when you no longer need it.",
    "/language_list": "List all language roles currently applied to you.",
    "/language_sync": "Admin: align known language roles across the guild based on user preferences.",
    "/sos_list": "Everyone can review active SOS keywords and their alerts.",
    "/sos_add": "Admin: add or update an SOS keyword → phrase mapping.",
    "/sos_remove": "Admin: remove a specific SOS keyword.",
    "/sos_clear": "Admin: clear every SOS keyword for a clean slate.",
    "/check_cookies": (
        "Review your cookie balance, streaks, and relationship progress.\n"
        "Cookies unlock mini-games and additional rewards."
    ),
    "/feed": "Spend 5 cookies to unlock the Pokemon mini-game for your guild.",
    "/game cookies balance": "Detailed cookie breakdown with lifetime totals and relationship milestones.",
    "/game cookies leaderboard": "See the top cookie earners in your community.",
    "/game pokemon help": "Read the Pokemon mini-game rules and tips.",
    "/game pokemon catch": "Attempt to catch a random Pokemon (costs 1 cookie).",
    "/game pokemon fish": "Fish for water-type Pokemon (costs 1 cookie).",
    "/game pokemon explore": "Search for rare Pokemon (costs 3 cookies).",
    "/game pokemon collection": "View every Pokemon you have collected so far.",
    "/game pokemon train": "Train a Pokemon with cookies to increase its level.",
    "/game pokemon evolve": "Evolve a Pokemon when you have enough duplicates.",
    "/game pokemon evolve_list": "See which Pokemon are ready to evolve.",
    "/game pokemon info": "Get detailed information about any Pokemon in the game.",
    "/games fun rps": "Play Rock, Paper, Scissors with Baby Hippo.",
    "/games fun joke": "Receive a random joke.",
    "/games fun catfact": "Learn an adorable cat fact.",
    "/games fun weather": "Check the weather for a city of your choice.",
    "/games fun 8ball": "Consult the magic 8-ball about your future.",
    "/easteregg": "Trigger a random surprise. Collect them all!",
    "/kvk ranking submit": (
        "Upload your Top Heroes (KVK) screenshot. Choose day `1-5` for prep stages or `6` for the war-stage total.\n"
        "Only helpers or admins can submit after the window closes."
    ),
    "/kvk ranking view": "Review your recent KVK submissions and scores.",
    "/kvk ranking leaderboard": "See the guild leaderboard. Filter by day, stage, guild tag, or all weeks.",
    "/kvk ranking report": "Admin: generate a detailed KVK report and log it to the moderator channel.",
    "/kvk ranking stats": "Admin: review KVK submission success and failure stats.",
    "/rankings": "Quick summary of your performance for any KVK run.",
    "/ranking_compare_me": "Compare your scores across two different KVK runs.",
    "/ranking_compare_others": "Contrast your results with a similar-power cohort or a specific friend.",
    "/events": "List all upcoming Top Heroes and community events.",
    "/event_create": "Admin: schedule a new event reminder (supports recurring schedules).",
    "/event_list": "Admin: list every configured event reminder.",
    "/event_delete": "Admin: delete an existing event reminder.",
    "/admin mute": "Timeout (mute) a member by specifying duration and reason.",
    "/admin unmute": "Remove an active timeout from a member.",
    "/admin give": "Gift helper cookies to a community member (respects daily limits).",
    "/keyword set": "Admin: link a keyword to a broadcast phrase or embed.",
    "/keyword list": "Admin: display all keyword → phrase mappings.",
    "/keyword remove": "Admin: delete a specific keyword mapping.",
    "/keyword clear": "Admin: clear all keyword mappings at once.",
}

DEFAULT_COMMAND_HELP = "Start typing the command in Discord to see argument hints and auto-complete details."

SUMMARY_PAGE = HelpPage(
    key="summary",
    title="🦛 Baby Hippo Quick Guide",
    body="Use the buttons below to explore each feature area or skim the highlights here.",
    commands=(
        ("/translate", "Share translations with the channel."),
        ("/language_assign", "Claim a language role (and a cookie)."),
        ("/check_cookies", "Review your cookie stats and relationship progress."),
        ("/kvk ranking submit", "Upload your Top Heroes screenshot."),
    ),
    use_summary_embed=True,
)

NAVIGATION_PAGES_USER: Tuple[HelpPage, ...] = (
    SUMMARY_PAGE,
    HelpPage(
        key="translation",
        title="🌍 Translation Workflows",
        body=(
            "• `/translate` supports 100+ languages and can auto-detect your preferred target.\n"
            "• Right-click a message → **Apps → Translate** to keep the response private.\n"
            "• Pair translations with language roles so I know what you speak."
        ),
        commands=(
            ("/translate", "Translate text for everyone in the channel."),
            ("Context ▸ Translate", "Right-click a message to translate it privately."),
        ),
    ),
    HelpPage(
        key="language",
        title="🗣️ Language Roles",
        body=(
            "Manage language roles to personalise translations (and earn cookies).\n"
            "• `/language_assign <code>` understands ISO codes and emoji flags.\n"
            "• `/language_list` shows what you already have.\n"
            "• `/language_remove <code>` tidies up old roles."
        ),
        commands=(
            ("/language_assign", "Add a language role to yourself."),
            ("/language_list", "List your current language roles."),
            ("/language_remove", "Remove a language role."),
        ),
    ),
    HelpPage(
        key="cookies",
        title="🍪 Cookie System",
        body=(
            "Cookies fuel relationship growth and unlock games.\n"
            "• `/check_cookies` tracks your balance, streaks, and relationship level.\n"
            "• `/feed` spends 5 cookies to unlock the Pokemon game.\n"
            "• `/game cookies balance/leaderboard` offer deeper stats."
        ),
        commands=(
            ("/check_cookies", "See your cookie stats and relationship progress."),
            ("/feed", "Spend cookies to unlock the Pokemon game."),
            ("/game cookies balance", "Detailed cookie breakdown."),
            ("/game cookies leaderboard", "Top cookie earners."),
        ),
    ),
    HelpPage(
        key="pokemon",
        title="✨ Pokemon Adventure",
        body=(
            "Unlock the game with `/feed` then grow your collection.\n"
            "• `/game pokemon help` recaps rules and tips.\n"
            "• `/game pokemon catch/fish/explore` gather new friends.\n"
            "• `/game pokemon train/evolve` level up and evolve favourites."
        ),
        commands=(
            ("/game pokemon help", "Review the Pokemon mini-game rules."),
            ("/game pokemon catch", "Catch a random Pokemon (costs 1 cookie)."),
            ("/game pokemon fish", "Fish for water-type Pokemon."),
            ("/game pokemon explore", "Explore for rare Pokemon."),
            ("/game pokemon train", "Train a Pokemon with cookies."),
            ("/game pokemon evolve", "Evolve a Pokemon using duplicates."),
            ("/game pokemon collection", "View your Pokemon collection."),
        ),
    ),
    HelpPage(
        key="fun",
        title="🎉 Fun & Ice-breakers",
        body=(
            "Light-hearted commands keep chat lively.\n"
            "• `/easteregg` triggers a random surprise.\n"
            "• `/games fun rps`, `joke`, `catfact`, `weather`, `8ball` cover games, trivia, and utilities."
        ),
        commands=(
            ("/easteregg", "Trigger a random easter egg surprise."),
            ("/games fun rps", "Play Rock, Paper, Scissors."),
            ("/games fun joke", "Hear a random joke."),
            ("/games fun catfact", "Learn a cat fact."),
            ("/games fun weather", "Check the weather for a city."),
            ("/games fun 8ball", "Ask the magic 8-ball a question."),
        ),
    ),
    HelpPage(
        key="sos",
        title="🚨 SOS Alerts",
        body=(
            "SOS keywords broadcast urgent messages across the guild.\n"
            "• Everyone can check triggers with `/sos_list`.\n"
            "• Admins manage them via `/sos_add`, `/sos_remove`, `/sos_clear`."
        ),
        commands=(
            ("/sos_list", "List all configured SOS keywords."),
            ("/sos_add", "Admin: add or update an SOS keyword."),
            ("/sos_remove", "Admin: remove an SOS keyword."),
            ("/sos_clear", "Admin: clear all SOS keywords."),
        ),
    ),
    HelpPage(
        key="kvk",
        title="🏅 Top Heroes (KVK)",
        body=(
            "Automate KVK reporting with screenshot parsing.\n"
            "• `/kvk ranking submit` uploads your screenshot (use day `6` for War totals).\n"
            "• `/kvk ranking view` and `/kvk ranking leaderboard` track progress.\n"
            "• `/rankings`, `/ranking_compare_me`, and `/ranking_compare_others` analyse the data."
        ),
        commands=(
            ("/kvk ranking submit", "Upload a KVK screenshot."),
            ("/kvk ranking view", "Review your submissions."),
            ("/kvk ranking leaderboard", "Guild leaderboard filters."),
            ("/rankings", "Quick summary of a run."),
            ("/ranking_compare_me", "Compare two runs for yourself."),
            ("/ranking_compare_others", "Compare yourself with a cohort or friend."),
        ),
    ),
    HelpPage(
        key="events",
        title="🗓️ Event Reminders",
        body=(
            "Stay organised for Top Heroes and community events.\n"
            "• `/events` lists upcoming reminders for everyone.\n"
            "• Admins manage entries with `/event_create`, `/event_list`, `/event_delete`."
        ),
        commands=(
            ("/events", "Show upcoming Top Heroes events."),
            ("/event_create", "Admin: schedule a new event."),
            ("/event_list", "Admin: list configured events."),
            ("/event_delete", "Admin: delete an existing event."),
        ),
    ),
)

ADMIN_PAGE = HelpPage(
    key="admin",
    title="🛡️ Admin Toolkit",
    body=(
        "Moderation shortcuts and automation tools.\n"
        "• `/admin mute` / `/admin unmute` manage timeouts.\n"
        "• `/admin give` rewards helper cookies.\n"
        "• `/keyword set/list/remove/clear` control keyword broadcasts.\n"
        "• `/language_sync` plus `/kvk ranking report/stats` keep data fresh."
    ),
    commands=(
        ("/admin mute", "Timeout a member for a set duration."),
        ("/admin unmute", "Remove an active timeout."),
        ("/admin give", "Share helper cookies with a member."),
        ("/keyword set", "Link a keyword to a broadcast phrase."),
        ("/keyword list", "Show all keyword mappings."),
        ("/keyword remove", "Remove a keyword mapping."),
        ("/keyword clear", "Clear every keyword mapping."),
        ("/language_sync", "Sync known language roles across the guild."),
        ("/kvk ranking report", "Generate and log a detailed KVK report."),
        ("/kvk ranking stats", "Review submission statistics."),
    ),
)

NAVIGATION_PAGES_ADMIN: Tuple[HelpPage, ...] = NAVIGATION_PAGES_USER + (ADMIN_PAGE,)


class HelpCommandSelect(discord.ui.Select):
    """Dropdown that shows quick command descriptions for the current help page."""

    NO_COMMAND_VALUE = "_noop"

    def __init__(self, navigator: HelpNavigator) -> None:  # type: ignore[name-defined]
        super().__init__(placeholder="Command cheat-sheet…", min_values=1, max_values=1, options=[])
        self.navigator = navigator
        self.rebuild(self.navigator.current_page.commands)

    def rebuild(self, commands: Sequence[Tuple[str, str]]) -> None:
        if commands:
            options = [
                discord.SelectOption(
                    label=cmd if cmd.startswith("/") else cmd,
                    value=cmd,
                    description=(desc[:97] + "...") if len(desc) > 100 else desc,
                )
                for cmd, desc in commands
            ]
            self.disabled = False
            self.placeholder = f"Command cheat-sheet ({len(commands)})"
        else:
            options = [
                discord.SelectOption(
                    label="No command shortcuts here",
                    value=self.NO_COMMAND_VALUE,
                    description="Browse other pages to see command tips.",
                )
            ]
            self.disabled = True
            self.placeholder = "No commands on this page"
        self.options = options

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.navigator.user_id:
            await interaction.response.send_message(
                "This help panel is locked to the user who opened it. Run `/help` to get your own.",
                ephemeral=True,
            )
            return

        choice = self.values[0]
        if choice == self.NO_COMMAND_VALUE:
            await interaction.response.defer()
            return

        self.navigator.session.touch()
        description = self.navigator.cog._format_command_help(choice)
        embed = discord.Embed(
            title=f"{choice}",
            description=description,
            color=discord.Color.green(),
        )
        embed.set_footer(text="Tip: start typing the command in Discord to see live argument hints.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class HelpNavigator(discord.ui.View):
    """Interactive view that lets users page through help categories."""

    def __init__(self, cog: "HelpCog", *, admin: bool, user_id: int) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.admin = admin
        self.pages = NAVIGATION_PAGES_ADMIN if admin else NAVIGATION_PAGES_USER
        self.total_pages = max(len(self.pages), 1)
        self.session = self.cog._get_or_create_session(user_id)
        self.session.set_index(self.session.page, self.total_pages)

        self.command_select = HelpCommandSelect(self)
        self.add_item(self.command_select)
        self.message: Optional[discord.Message] = None

    @property
    def current_page(self) -> HelpPage:
        return self.pages[self.session.page % self.total_pages]

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This help panel belongs to someone else. Run `/help` to open your own guide.",
                ephemeral=True,
            )
            return False
        return True

    def _sync_select(self) -> None:
        self.command_select.rebuild(self.current_page.commands)

    async def _change_page(self, interaction: discord.Interaction, delta: int) -> None:
        self.session.move(delta, self.total_pages)
        self._sync_select()
        embed = self.cog._build_navigation_embed(session=self.session, user_is_admin=self.admin)
        self.message = interaction.message
        await interaction.response.edit_message(embed=embed, view=self)

    async def _go_home(self, interaction: discord.Interaction) -> None:
        self.session.set_index(0, self.total_pages)
        self._sync_select()
        embed = self.cog._build_navigation_embed(session=self.session, user_is_admin=self.admin)
        self.message = interaction.message
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self._change_page(interaction, -1)

    @discord.ui.button(label="Summary", style=discord.ButtonStyle.primary)
    async def jump_home(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self._go_home(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_page(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self._change_page(interaction, 1)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_panel(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        self.disable_all_items()
        self.cog._session_cache.pop(self.user_id, None)
        await interaction.response.edit_message(view=None)
        self.stop()

    async def on_timeout(self) -> None:
        self.disable_all_items()
        self.cog._session_cache.pop(self.user_id, None)
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


#
# Help cog
#


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._welcome_channel_overrides = self._load_channel_overrides()
        self._session_cache: Dict[int, HelpSession] = {}

    # ---------------
    # Help session
    # ---------------

    def _get_or_create_session(self, user_id: int) -> HelpSession:
        session = self._session_cache.get(user_id)
        if session and session.is_expired():
            self._session_cache.pop(user_id, None)
            session = None
        if session is None:
            session = HelpSession(user_id=user_id)
            self._session_cache[user_id] = session
        return session

    def _build_navigation_embed(
        self,
        *,
        session: HelpSession,
        user_is_admin: bool,
    ) -> discord.Embed:
        """Create the paginated navigation embed for the current page."""
        pages = NAVIGATION_PAGES_ADMIN if user_is_admin else NAVIGATION_PAGES_USER
        idx = session.page % len(pages)
        page = pages[idx]

        if page.use_summary_embed:
            return self._create_help_embed(admin=user_is_admin)

        embed = discord.Embed(
            title=page.title,
            description=page.body,
            color=discord.Color.blurple(),
        )
        if page.commands:
            command_lines = "\n".join(f"• `{cmd}` - {desc}" for cmd, desc in page.commands)
            embed.add_field(name="Quick commands", value=command_lines, inline=False)
        embed.set_footer(text=f"Page {idx + 1} of {len(pages)} • Use the buttons to explore commands.")
        return embed

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
                "Your friendly multilingual companion with games, cookies, and translation superpowers!\n"
                "Use the buttons below or run `/help` any time you need a refresher."
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🌍 Translation",
            value=(
                "`/translate <text> [language]` shares translations with the channel.\n"
                "Want it private? Right-click a message and pick **Translate**."
            ),
            inline=False,
        )

        embed.add_field(
            name="🗣️ Language Roles",
            value=(
                "`/language_assign <code>` supports ISO codes and emoji flags.\n"
                "`/language_list` and `/language_remove` help you manage preferences."
            ),
            inline=False,
        )

        embed.add_field(
            name="🍪 Cookie System",
            value=(
                "Earn cookies by interacting with me! Use `/check_cookies` to see stats.\n"
                "Cookies unlock special features and power the Pokemon game."
            ),
            inline=False,
        )

        embed.add_field(
            name="✨ Pokemon Game",
            value=(
                "Feed me 5 cookies with `/feed` to unlock the adventure.\n"
                "Try `/game pokemon help`, `/game pokemon catch`, `/game pokemon train`, and more."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎉 Fun & Easter Eggs",
            value=(
                "`/easteregg` triggers surprises.\n"
                "`/games fun rps`, `/games fun joke`, `/games fun weather`, `/games fun 8ball` keep things lively."
            ),
            inline=False,
        )

        embed.add_field(
            name="🚨 SOS Alerts",
            value=(
                "`/sos_list` shows active trigger words.\n"
                "Admins manage them with `/sos_add`, `/sos_remove`, and `/sos_clear`."
            ),
            inline=False,
        )

        if admin:
            embed.add_field(
                name="🛡️ Admin Controls",
                value=(
                    "- `/admin mute` / `/admin unmute` to manage timeouts.\n"
                    "- `/keyword set/list/remove/clear` to maintain keyword responses.\n"
                    "- `/language_sync`, `/kvk ranking report`, `/kvk ranking stats` for automation and analytics."
                ),
                inline=False,
            )

        embed.set_footer(text="Build your relationship with me for better luck and rewards! 🍪")
        return embed

    def _format_command_help(self, command: str) -> str:
        return COMMAND_HINTS.get(command, DEFAULT_COMMAND_HELP)

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
                "Use `/translate <text> [language]` to broadcast a translation for everyone.\n"
                "Need a secret whisper? Right-click a message and tap **Translate**."
            ),
            inline=False,
        )

        embed.add_field(
            name="Snag a language role (cookie inside!)",
            value=(
                "`/language_assign <code>` understands names and flag emojis-try "
                "`/language_assign 🇯🇵`.\n"
                "As soon as you claim one, a fresh cookie 🍪 magically appears."
            ),
            inline=False,
        )

        embed.add_field(
            name="SOS safety net",
            value=(
                "Check the trigger words with `/sos_list` (everyone can see them).\n"
                "Admins can fine-tune alerts via `/sos_add`, `/sos_remove`, `/sos_clear`."
            ),
            inline=False,
        )

        embed.add_field(
            name="Need more details?",
            value="Use `/help` for a complete guide on all commands and features.",
            inline=False,
        )

        embed.set_footer(text="Glad you're here! Let's keep the translations rolling.")
        return embed

    @staticmethod
    def _load_channel_overrides() -> Dict[int, int]:
        raw = os.getenv("WELCOME_CHANNEL_IDS", "")
        overrides: Dict[int, int] = {}
        if not raw:
            return overrides

        for chunk in raw.replace(";", ",").split(","):
            token = chunk.strip()
            if not token or "=" not in token:
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

        channel_id = self._welcome_channel_overrides.get(guild.id)
        if channel_id:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel) and can_send(channel):
                return channel

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
            # Clean up older welcome embeds so the channel stays tidy.
            perms = channel.permissions_for(guild.me or guild.default_role)
            if perms.manage_messages:
                try:
                    async for message in channel.history(limit=25, oldest_first=False):
                        if message.author != guild.me:
                            continue
                        if any(e.title == embed.title for e in message.embeds):
                            try:
                                await message.delete()
                            except (discord.Forbidden, discord.HTTPException):
                                break
                except discord.HTTPException:
                    pass

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
        member = (
            interaction.user
            if isinstance(interaction.user, discord.Member)
            else (guild.get_member(interaction.user.id) if guild else None)
        )
        admin = self._is_admin(member, guild)

        session = self._get_or_create_session(interaction.user.id)
        pages = NAVIGATION_PAGES_ADMIN if admin else NAVIGATION_PAGES_USER
        session.set_index(0, len(pages))

        navigator = HelpNavigator(self, admin=admin, user_id=interaction.user.id)
        await interaction.response.send_message(
            embed=self._create_help_embed(admin=admin),
            view=navigator,
            ephemeral=True,
        )

        try:
            message = await interaction.original_response()
            navigator.set_message(message)
        except Exception:
            pass

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
