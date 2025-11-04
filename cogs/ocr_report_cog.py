"""
Admin Cog for OCR and AI System Reporting.
"""
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands, tasks

from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
from discord_bot.core.utils import is_admin_or_helper

class OCRReportCog(commands.Cog):
    """Commands for monitoring and reporting on the OCR learning system."""

    def __init__(self, bot: commands.Bot, storage: RankingStorageEngine):
        self.bot = bot
        self.storage = storage
        self.learning_loop.start()

    def cog_unload(self):
        self.learning_loop.cancel()

    @app_commands.command(name="ocr_report", description="[ADMIN] Get a report on the OCR correction system.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ocr_report(self, interaction: discord.Interaction):
        """Generates a report on the health and performance of the OCR learning loop."""
        if not is_admin_or_helper(interaction.user, interaction.guild):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        stats = self.storage.get_ocr_correction_stats()
        submission_stats = self.storage.get_submission_stats(str(interaction.guild_id))

        total_submissions = submission_stats.get("success", 0) + submission_stats.get("failed", 0)
        success_rate = (submission_stats.get("success", 0) / total_submissions * 100) if total_submissions > 0 else 100

        embed = discord.Embed(
            title="🤖 OCR & AI Learning System Report",
            description=f"Analysis of the system's performance and learning progress.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Submission Health",
            value=f"**Success Rate:** {success_rate:.2f}%\n"
                  f"**Total Submissions:** {total_submissions}\n"
                  f"**Corrections Made:** {stats['total_corrections']}",
            inline=False
        )

        if stats['total_corrections'] > 0:
            category_breakdown = "\n".join(
                f"- **{cat.replace('_', ' ').title()}**: {count}"
                for cat, count in stats['by_category'].items()
            )
            embed.add_field(
                name="Top Failure Categories",
                value=category_breakdown or "No categories recorded.",
                inline=False
            )

        recent_corrections = self.storage.get_recent_corrections(limit=3)
        if recent_corrections:
            recent_analysis = ""
            for i, correction in enumerate(recent_corrections):
                analysis = correction.get('ai_analysis', 'No analysis available.')
                # Truncate for display
                if len(analysis) > 200:
                    analysis = analysis[:200] + "..."
                recent_analysis += f"**{i+1}. {correction['failure_category'].title()}**\n> {analysis}\n"
            
            embed.add_field(
                name="Recent AI Analyses",
                value=recent_analysis,
                inline=False
            )

        embed.set_footer(text="This system learns from user corrections to improve accuracy over time.")
        await interaction.followup.send(embed=embed)

    @tasks.loop(hours=24)
    async def learning_loop(self):
        """A background task to analyze correction patterns and propose improvements."""
        # In a real implementation, this would be more robust.
        # For now, it just logs that it's running.
        print("Running nightly OCR learning loop...")
        
        # 1. Pull last 100 feedback records
        corrections = self.storage.get_recent_corrections(limit=100)
        if not corrections:
            print("No corrections to analyze.")
            return

        # 2. Cluster similar failure reasons
        category_counts = {}
        for c in corrections:
            cat = c.get('failure_category', 'unknown')
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        print(f"Analyzed {len(corrections)} corrections. Categories: {category_counts}")

        # 3. Propose changes (logging for now)
        for category, count in category_counts.items():
            if category == "regex_mismatch" and count > 3:
                print(f"High number of regex mismatches ({count}). Recommend reviewing score/rank patterns.")
            if category == "layout_shift" and count > 5:
                print(f"High number of layout shifts ({count}). Recommend creating new ROI templates.")


async def setup(bot: commands.Bot, storage: RankingStorageEngine):
    """Setup function for the OCR Report cog."""
    await bot.add_cog(OCRReportCog(bot, storage))
