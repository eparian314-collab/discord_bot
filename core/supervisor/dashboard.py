import discord
from discord import app_commands
from discord.ext import commands
from .sentinel import GuardianSentinel

class DashboardCog(commands.Cog):
    def __init__(self, sentinel: GuardianSentinel):
        self.sentinel = sentinel

    @app_commands.command(name="system_health", description="Show system health and safe mode status.")
    async def system_health(self, interaction: discord.Interaction):
        import json, io
        from core.visualization.confidence_graph import generate_confidence_graph
        score = self.sentinel.scorecard.score()
        safe_mode = self.sentinel.safe_mode
        reason = self.sentinel.last_trigger_reason or "N/A"
        embed = discord.Embed(
            title="System Health",
            description=f"Stability Score: {score:.2f}\nSafe Mode: {'ON' if safe_mode else 'OFF'}\nLast Trigger: {reason}",
            color=discord.Color.yellow() if safe_mode else discord.Color.green()
        )
        if safe_mode:
            embed.add_field(name="Safe Mode", value="⚠️ Safe Mode: System is isolating unstable components", inline=False)
        # Load last 50 confidence samples for this guild
        guild_id = str(interaction.guild.id) if interaction.guild else None
        history = []
        try:
            with open("storage/ocr_confidence.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if guild_id and guild_id in data:
                    history = data[guild_id].get("samples", [])[-50:]
        except Exception:
            pass
        image_bytes = generate_confidence_graph(history, score)
        await interaction.response.send_message(
            content=f"System Stability Score: {score:.2f}",
            file=discord.File(io.BytesIO(image_bytes), filename="system_health.png"),
            embed=embed,
            ephemeral=True
        )
