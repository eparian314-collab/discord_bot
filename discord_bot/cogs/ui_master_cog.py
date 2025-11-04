from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Sequence

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class PageKey(str, Enum):
    """Enumeration of the available Hippo UI sections."""

    HOME = "home"
    HELP = "help"
    TRANSLATE = "translate"
    GAMES = "games"
    ADMIN = "admin"


@dataclass(frozen=True)
class PageField:
    """A single embed field definition."""

    name: str
    value: str
    inline: bool = False


@dataclass(frozen=True)
class PageDescriptor:
    """Defines static metadata for a UI page."""

    key: PageKey
    title: str
    description: str
    fields: Sequence[PageField] = ()
    footer: Optional[str] = None


UI_PAGES: Dict[PageKey, PageDescriptor] = {
    PageKey.HOME: PageDescriptor(
        key=PageKey.HOME,
        title="HippoBot Command Center",
        description=(
            "Welcome to the unified HippoBot panel. Use the navigation controls below to jump "
            "between feature areas. Everything in this UI is live, so you can stay on this message "
            "while exploring the bot."
        ),
        fields=(
            PageField(
                name="Getting Started",
                value=(
                    "- `/hippo` - reopen this panel anytime.\n"
                    "- Use the **Help** and **Translate** buttons for quick how-to references.\n"
                    "- The **Jump to section** select mirrors the buttons if you prefer menus."
                ),
            ),
            PageField(
                name="What's New",
                value=(
                    "- Faster translation shortcuts via context menus.\n"
                    "- Weekly ranking automation with helper tools.\n"
                    "- Game modules with cookie-powered mini adventures."
                ),
            ),
        ),
        footer="Baby Hippo is ready to help!",
    ),
    PageKey.HELP: PageDescriptor(
        key=PageKey.HELP,
        title="Help and Support",
        description=(
            "Need a refresher? This page highlights the primary commands and resources that keep "
            "your community moving."
        ),
        fields=(
            PageField(
                name="Core Commands",
                value=(
                    "- `/help` - legacy multi-page help navigator.\n"
                    "- `/translate` - translate text to any supported language.\n"
                    "- `/sos_list` - review active SOS keywords and alerts.\n"
                    "- `/language_assign` - self-assign language roles."
                ),
            ),
            PageField(
                name="Need a Human?",
                value=(
                    "Helpers and admins can contact the Hippo team via `/admin escalate` (if enabled) "
                    "or the support channel linked in onboarding guides."
                ),
                inline=True,
            ),
            PageField(
                name="Documentation",
                value=(
                    "- `docs/QUICK_START_GUIDE.md`\n"
                    "- `docs/RANKING_IMPLEMENTATION.md`\n"
                    "- `docs/RANKING_SETUP_CHECKLIST.md`"
                ),
                inline=True,
            ),
        ),
        footer="Tip: use the buttons below for faster navigation.",
    ),
    PageKey.TRANSLATE: PageDescriptor(
        key=PageKey.TRANSLATE,
        title="Translation Toolkit",
        description=(
            "HippoBot makes cross-language conversations painless. Share translations publicly or "
            "privately depending on the context."
        ),
        fields=(
            PageField(
                name="Slash Commands",
                value=(
                    "- `/translate text:<message> language:<code>` - inline translation with optional "
                    "language code.\n"
                    "- `/language_list` - review roles and auto-detect hints.\n"
                    "- `/language_remove` - drop a language role you no longer need."
                ),
            ),
            PageField(
                name="Context Menu",
                value=(
                    "Right-click a message and pick **Apps -> Translate** for a private, clutter-free result."
                ),
                inline=True,
            ),
            PageField(
                name="Automation",
                value=(
                    "Auto-detection learns from assigned roles and past translations to reduce manual prompts."
                ),
                inline=True,
            ),
        ),
        footer="Translations respect server language policies and cooldowns.",
    ),
    PageKey.GAMES: PageDescriptor(
        key=PageKey.GAMES,
        title="Games and Cookies",
        description=(
            "Break the ice with cookie economy games and Pokemon adventures. All game commands use the "
            "cookie balance you earn from events."
        ),
        fields=(
            PageField(
                name="Cookie Hub",
                value=(
                    "- `/game cookies balance` - check balance and streaks.\n"
                    "- `/game cookies leaderboard` - compare progress.\n"
                    "- `/feed` - unlock the Pokemon mini-game for your guild."
                ),
            ),
            PageField(
                name="Pokemon Adventures",
                value=(
                    "- `/game pokemon catch`\n"
                    "- `/game pokemon fish`\n"
                    "- `/game pokemon explore`\n"
                    "- `/game pokemon collection`\n"
                    "See `docs/QUICK_START_GUIDE.md` for mechanics and rarity tables."
                ),
            ),
            PageField(
                name="Party Games",
                value="Rock-paper-scissors, jokes, weather checks, and more under `/games fun ...`.",
            ),
        ),
        footer="Cookies fuel everything. Keep daily streaks alive!",
    ),
    PageKey.ADMIN: PageDescriptor(
        key=PageKey.ADMIN,
        title="Admin and Operations",
        description=(
            "Administrative shortcuts for server owners, helpers, and moderators. Sensitive commands "
            "respect Discord permissions and HippoBot role checks."
        ),
        fields=(
            PageField(
                name="Moderation",
                value=(
                    "- `/admin sync_roles` - align helper roles.\n"
                    "- `/admin escalate` - reach core maintainers.\n"
                    "- `/role audit` - inspect automated role assignments."
                ),
            ),
            PageField(
                name="Ranking Automation",
                value=(
                    "- `/kvk ranking submit`\n"
                    "- `/kvk ranking leaderboard`\n"
                    "- `/kvk ranking report`\n"
                    "Reference `docs/RANKING_SETUP.md` and `docs/RANKING_WEEKLY_SYSTEM.md` for workflows."
                ),
            ),
            PageField(
                name="Preflight and Deploy",
                value=(
                    "Scripts in `scripts/` - `preflight_check.py`, `push_and_deploy.ps1`, and `deploy.sh` "
                    "handle CI hand-offs and on-demand sync."
                ),
            ),
        ),
        footer="Only show this card to trusted staff. Non-staff users get a reminder.",
    ),
}


BUTTON_CUSTOM_IDS = {
    PageKey.HOME: "hippo:home",
    PageKey.HELP: "hippo:help",
    PageKey.TRANSLATE: "hippo:translate",
    PageKey.GAMES: "hippo:games",
    PageKey.ADMIN: "hippo:admin",
}

SELECT_CUSTOM_ID = "hippo:select"


class HippoMainView(discord.ui.View):
    """Persistent navigation view for the Hippo master UI."""

    def __init__(
        self,
        *,
        cog: "UIMasterCog",
        owner_id: Optional[int] = None,
        initial_page: PageKey = PageKey.HOME,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id
        self.current_page = initial_page
        self._sync_component_state()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Restrict interactions to the invoking user when owner_id is set."""
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            message = "This Hippo panel is locked to its original user. Run `/hippo` to open your own copy."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return False
        return True

    async def _handle_page_request(self, interaction: discord.Interaction, page: PageKey) -> None:
        """Render the requested page into the active message."""
        self.current_page = page
        embed = self.cog.build_page(page, requester=interaction.user, guild=interaction.guild)
        self._sync_component_state()
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    def _sync_component_state(self) -> None:
        """Keep button disable states and select defaults aligned with the active page."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                target = self._button_to_page(child.custom_id)
                child.disabled = target == self.current_page
            elif isinstance(child, discord.ui.Select):
                for option in child.options:
                    option.default = option.value == self.current_page.value

    @staticmethod
    def _button_to_page(custom_id: Optional[str]) -> Optional[PageKey]:
        for page, cid in BUTTON_CUSTOM_IDS.items():
            if custom_id == cid:
                return page
        return None

    @discord.ui.button(
        label="Home",
        style=discord.ButtonStyle.primary,
        custom_id=BUTTON_CUSTOM_IDS[PageKey.HOME],
        row=0,
    )
    async def home_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_page_request(interaction, PageKey.HOME)

    @discord.ui.button(
        label="Help",
        style=discord.ButtonStyle.secondary,
        custom_id=BUTTON_CUSTOM_IDS[PageKey.HELP],
        row=0,
    )
    async def help_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_page_request(interaction, PageKey.HELP)

    @discord.ui.button(
        label="Translate",
        style=discord.ButtonStyle.secondary,
        custom_id=BUTTON_CUSTOM_IDS[PageKey.TRANSLATE],
        row=0,
    )
    async def translate_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_page_request(interaction, PageKey.TRANSLATE)

    @discord.ui.button(
        label="Games",
        style=discord.ButtonStyle.secondary,
        custom_id=BUTTON_CUSTOM_IDS[PageKey.GAMES],
        row=0,
    )
    async def games_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_page_request(interaction, PageKey.GAMES)

    @discord.ui.button(
        label="Admin",
        style=discord.ButtonStyle.danger,
        custom_id=BUTTON_CUSTOM_IDS[PageKey.ADMIN],
        row=0,
    )
    async def admin_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        is_admin = self.cog.user_is_admin(interaction.user)
        await self._handle_page_request(interaction, PageKey.ADMIN)
        if not is_admin:
            warning = (
                "The admin panel contains staff tooling. You can review it, but you need the appropriate "
                "Discord permissions to run the commands listed here."
            )
            await interaction.followup.send(warning, ephemeral=True)

    @discord.ui.select(
        placeholder="Jump to section",
        custom_id=SELECT_CUSTOM_ID,
        options=[
            discord.SelectOption(label="Home", value=PageKey.HOME.value, description="Overview and uptime"),
            discord.SelectOption(label="Help", value=PageKey.HELP.value, description="Commands and docs"),
            discord.SelectOption(label="Translate", value=PageKey.TRANSLATE.value, description="Language tooling"),
            discord.SelectOption(label="Games", value=PageKey.GAMES.value, description="Cookies and mini-games"),
            discord.SelectOption(label="Admin", value=PageKey.ADMIN.value, description="Moderator utilities"),
        ],
        row=1,
    )
    async def section_select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        choice = select.values[0]
        await self._handle_page_request(interaction, PageKey(choice))


class UIMasterCog(commands.Cog):
    """Provides the master `/hippo` slash command and persistent control panel."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = datetime.now(timezone.utc)
        self.version = (
            os.getenv("HIPPO_VERSION")
            or os.getenv("APP_VERSION")
            or os.getenv("BUILD_VERSION")
            or "dev"
        )

    async def cog_load(self) -> None:
        """Register the persistent view once the cog is loaded."""
        try:
            self.bot.add_view(HippoMainView(cog=self))
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to register HippoMainView as a persistent view")

    def user_is_admin(self, member: discord.abc.User) -> bool:
        """Return True when the member has guild-level admin rights."""
        if not isinstance(member, discord.Member):
            return False
        perms = member.guild_permissions
        return perms.administrator or perms.manage_guild or perms.manage_channels

    def build_page(
        self,
        page: PageKey,
        *,
        requester: discord.abc.User,
        guild: Optional[discord.Guild],
    ) -> discord.Embed:
        """Return the embed for the requested page, enriched with runtime metadata."""
        descriptor = UI_PAGES.get(page, UI_PAGES[PageKey.HOME])
        embed = discord.Embed(
            title=descriptor.title,
            description=descriptor.description,
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        if page is PageKey.HOME:
            embed.add_field(
                name="Bot Uptime",
                value=self._format_uptime(),
                inline=True,
            )
            embed.add_field(
                name="Version",
                value=self.version,
                inline=True,
            )
            embed.add_field(
                name="Servers",
                value=str(len(self.bot.guilds)),
                inline=True,
            )
            last_sync = getattr(self.bot, "last_command_sync", None)
            if isinstance(last_sync, datetime):
                embed.add_field(
                    name="Command Tree",
                    value=f"Synced {discord.utils.format_dt(last_sync, style='R')}",
                    inline=True,
                )

        for field in descriptor.fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

        footer = descriptor.footer or "Use the buttons below to explore."
        embed.set_footer(text=f"{footer} - Requested by {requester.display_name}")

        if guild:
            embed.add_field(
                name="Current Server",
                value=guild.name,
                inline=False,
            )

        return embed

    def _format_uptime(self) -> str:
        """Format the bot uptime as a human-readable string."""
        delta = discord.utils.utcnow() - self.started_at
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if days or hours:
            parts.append(f"{hours}h")
        if days or hours or minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    @app_commands.command(name="hippo", description="Open the HippoBot help and control panel.")
    async def hippo(self, interaction: discord.Interaction) -> None:
        """Slash command entry point for the master Hippo UI."""
        view = HippoMainView(cog=self, owner_id=interaction.user.id)
        embed = self.build_page(PageKey.HOME, requester=interaction.user, guild=interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    """Load the UI master cog into the bot."""
    await bot.add_cog(UIMasterCog(bot))
    # Integration loader hint:
    # Import this module and await `bot.add_cog(UIMasterCog(bot))` inside IntegrationLoader once engines are ready.


