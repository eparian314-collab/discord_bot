"""
Modern help command aligned with the engine-driven architecture.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Show a quick overview of HippoBot features.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="HippoBot Help",
            description="Key slash commands provided by the new engine stack.",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="/translate <text>",
            value="Translate text using the configured adapters/orchestrator. "
                  "Results are sent ephemeral by default.",
            inline=False,
        )

        embed.add_field(
            name="/language …",
            value="Manage language roles (assign, remove, sync). Requires server permissions as configured.",
            inline=False,
        )

        embed.add_field(
            name="/sos …",
            value="Configure SOS keywords/phrases that trigger emergency alerts in monitored channels.",
            inline=False,
        )

        if getattr(self.bot, "admin_ui", None):
            embed.add_field(
                name="/plugins /plugin_enable /plugin_disable /diag",
                value="Owner-only controls for the engine registry and guardian diagnostics.",
                inline=False,
            )

        embed.set_footer(text="Need more? Reach out to the maintainers or check the project README.")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
