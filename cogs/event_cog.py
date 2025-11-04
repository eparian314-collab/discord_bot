import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from core.engines.event_engine import EventEngine
from core.ui_groups import event

class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot, event_engine: EventEngine):
        self.bot = bot
        self.event_engine = event_engine

    @event.command(name="submit", description="Submit an event screenshot for parsing.")
    @app_commands.describe(
        attachment='The screenshot of the event.',
        notes='Optional notes or keywords to help identify the event (e.g., "Prep Stage", "Guild Assault").'
    )
    async def submit(self, interaction: discord.Interaction, attachment: discord.Attachment, notes: str = ""):
        await interaction.response.defer(ephemeral=True)

        if not attachment.content_type or not attachment.content_type.startswith('image/'):
            await interaction.followup.send("Please upload an image file.", ephemeral=True)
            return

        message_content = notes

        parsed_data = await self.event_engine.process_submission(
            attachment_url=attachment.url,
            message_content=message_content
        )

        if not parsed_data:
            await interaction.followup.send(
                "Could not determine the event type from your submission. "
                "Please include keywords like 'KVK', 'GAR', 'Prep Stage', or 'Guild Assault' in the notes.",
                ephemeral=True
            )
            return

        event_id = parsed_data.get("event")
        event_info = self.event_engine.event_registry.get(event_id, {})
        display_name = event_info.get("display_name", event_id)
        
        color = discord.Color.gold() if event_id == "KVK" else discord.Color.blue()
        embed = discord.Embed(
            title=f"🧩 Event Submission Received: {display_name}",
            color=color
        )
        embed.set_image(url=attachment.url)
        embed.add_field(name="Stage/Round", value=str(parsed_data.get("stage", "N/A")), inline=True)
        embed.add_field(name="Rank", value=f"#{parsed_data.get('rank', 'N/A')}", inline=True)
        embed.add_field(name="Score", value=f"{parsed_data.get('score', 0):,}", inline=True)
        embed.set_footer(text=f"Submitted by {interaction.user.display_name}")

        await interaction.followup.send(
            f"✅ Successfully parsed your **{display_name}** submission!",
            embed=embed
        )

    @event.command(name="status", description="Check your current event status.")
    @app_commands.describe(event="Optional: Filter status by a specific event (KVK or GAR).")
    async def status(self, interaction: discord.Interaction, event: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)

        user_scores = self.event_engine.get_user_status(interaction.user.id, event)

        if not user_scores:
            await interaction.followup.send("No event data found for you. Use `/event submit` to add a score.", ephemeral=True)
            return

        embed = discord.Embed(title="Your Event Status", color=discord.Color.purple())
        
        for score_data in user_scores:
            event_id = score_data.get("event")
            display_name = self.event_engine.event_registry.get(event_id, {}).get("display_name", event_id)
            
            value = (
                f"**Rank:** #{score_data.get('rank', 'N/A')} | "
                f"**Score:** {score_data.get('score', 0):,}\n"
                f"**Stage/Round:** {score_data.get('stage', 'N/A')}"
            )
            embed.add_field(name=f"🏟️ {display_name}", value=value, inline=False)

        await interaction.followup.send(embed=embed)

    @event_group.command(name="compare", description="Compare your score with peers.")
    async def compare(self, interaction: discord.Interaction, event: str = None):
        await interaction.response.defer()
        # TODO: Implement score comparison
        await interaction.followup.send("Comparing your score with others...")

    @event_group.command(name="leaderboard", description="View the event leaderboard.")
    @app_commands.describe(event="The event to show the leaderboard for (KVK or GAR).")
    async def leaderboard(self, interaction: discord.Interaction, event: str):
        await interaction.response.defer()

        if event.upper() not in ["KVK", "GAR"]:
            await interaction.followup.send("Please specify a valid event: `KVK` or `GAR`.", ephemeral=True)
            return

        leaderboard_data = self.event_engine.get_leaderboard(event.upper())

        if not leaderboard_data:
            await interaction.followup.send(f"No leaderboard data found for **{event.upper()}**.", ephemeral=True)
            return
            
        event_info = self.event_engine.event_registry.get(event.upper(), {})
        display_name = event_info.get("display_name", event.upper())
        color = discord.Color.gold() if event.upper() == "KVK" else discord.Color.blue()

        embed = discord.Embed(title=f"🏆 {display_name} Leaderboard", color=color)
        
        description = ""
        for i, entry in enumerate(leaderboard_data):
            user_name = entry.get('user', 'Unknown') # In a real app, you'd fetch the user's name
            score = entry.get('score', 0)
            rank = entry.get('rank', i + 1)
            description += f"**{rank}. {user_name}** - {score:,}\n"
            
        embed.description = description
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    event_engine = bot.get_engine("event_engine")
    await bot.add_cog(EventCog(bot, event_engine))
