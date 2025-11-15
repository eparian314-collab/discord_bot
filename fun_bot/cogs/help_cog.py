from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from fun_bot.core.personality_engine import PersonalityEngine


class HelpView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], owner_id: int) -> None:
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0
        self.owner_id = owner_id
        self._update_button_states()

    def _update_button_states(self) -> None:
        prev_btn = self.prev_button
        next_btn = self.next_button
        prev_btn.disabled = self.index <= 0
        next_btn.disabled = self.index >= len(self.pages) - 1

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the user who opened this help can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_owner(interaction):
            return
        if self.index > 0:
            self.index -= 1
            self._update_button_states()
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_owner(interaction):
            return
        if self.index < len(self.pages) - 1:
            self.index += 1
            self._update_button_states()
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)


class HelpCog(commands.Cog):
    """High-level help and overview for FunBot.

    Provides a paginated `/help` command that explains available game
    and cookie commands, as well as the designated bot channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.personality: PersonalityEngine = getattr(bot, "personality", PersonalityEngine())
        self.config = getattr(bot, "config", None)

    @app_commands.command(name="help", description="Show FunBot help and commands")
    async def help_command(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        intro = self.personality.format("help_intro")

        bot_channel_ids = getattr(self.config, "bot_channel_ids", set()) or set()
        channel_hint = "No channel restriction; commands work in any server channel."
        if bot_channel_ids:
            channel_mentions = ", ".join(f"<#{cid}>" for cid in bot_channel_ids)
            channel_hint = f"Most game commands should be used in: {channel_mentions}"

        # Overview page
        overview = discord.Embed(title="FunBot Help — Overview")
        overview.description = intro
        overview.add_field(
            name="What FunBot does",
            value=(
                "- Run light-weight Pokémon mini-games and collection.\n"
                "- Handle turn-based battles between members.\n"
                "- Track and grant helper cookies.\n"
                "- Provide fun easter eggs and utility commands."
            ),
            inline=False,
        )
        overview.add_field(
            name="Bot channel",
            value=channel_hint,
            inline=False,
        )

        # Pokémon page
        pokemon_page = discord.Embed(title="FunBot Help — Pokémon")
        pokemon_page.add_field(
            name="Catching & collection",
            value=(
                "`/pokemon catch` — Catch a random Pokémon with unique stats.\n"
                "`/pokemon stats` — View your high-level Pokémon stats.\n"
                "`/pokemon collection` — See IDs, levels, IV quality and natures "
                "for each Pokémon you own."
            ),
            inline=False,
        )
        pokemon_page.add_field(
            name="Training & evolution",
            value=(
                "`/pokemon train` — Train a Pokémon by ID to gain XP and levels "
                "(up to level 100; level never goes down).\n"
                "`/pokemon evolve` — Evolve a Pokémon using a duplicate and cookies; "
                "level and XP are preserved, IVs and nature carry over."
            ),
            inline=False,
        )

        # Battles page
        battles_page = discord.Embed(title="FunBot Help — Battles")
        battles_page.add_field(
            name="Member battles",
            value=(
                "`/battle challenge @user` — Start a 1v1 battle in the current channel.\n"
                "`/battle moves` — Show available moves and descriptions.\n"
                "`/battle move <name>` — Use a move during your turn.\n"
                "`/battle forfeit` — Concede the battle."
            ),
            inline=False,
        )
        battles_page.add_field(
            name="Battle notes",
            value=(
                "- Only one active battle per channel.\n"
                "- You must take turns; using `/battle move` out of turn will be rejected.\n"
                "- Wins and losses are tracked in your Pokémon stats profile."
            ),
            inline=False,
        )

        # Cookies / admin page
        cookies_page = discord.Embed(title="FunBot Help — Cookies & Admin")
        cookies_page.add_field(
            name="Cookies",
            value=(
                "`/cookies balance` — Check how many helper cookies you have.\n"
                "`/cookies give` — Admin/owner-only command to grant cookies to members."
            ),
            inline=False,
        )
        cookies_page.add_field(
            name="Who can give cookies?",
            value=(
                "- Server administrators.\n"
                "- Bot owners configured via the `OWNER_IDS` env variable."
            ),
            inline=False,
        )

        pages = [overview, pokemon_page, battles_page, cookies_page]
        view = HelpView(pages, owner_id=interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)


__all__ = ["HelpCog"]
