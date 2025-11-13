"""UI helpers for presenting translations back to Discord users."""

from __future__ import annotations

from dataclasses import dataclass
import discord

from .translation_orchestrator import TranslationResult


@dataclass(slots=True)
class TranslationPresentation:
    """Lightweight description of how to present a translation."""

    headline: str
    body: str
    footer: str


class TranslationUIEngine:
    """Formatting helpers that keep discord.py concerns outside the cog."""

    def build_private_embed(
        self,
        *,
        author_name: str,
        message_link: str,
        original_text: str,
        result: TranslationResult,
    ) -> discord.Embed:
        """Return a Discord embed tailored for DM delivery."""

        embed = discord.Embed(
            title=f"Message translated ({result.source_language} → {result.target_language})",
            description=result.translated_text,
            colour=discord.Colour.blurple(),
        )
        embed.add_field(name="Original", value=self._truncate(original_text), inline=False)
        embed.add_field(name="Source", value=f"[Jump to message]({message_link})", inline=False)
        embed.set_footer(text=f"Provider: {result.provider}")
        return embed

    async def notify_user(
        self,
        *,
        member: discord.abc.Messageable,
        embed: discord.Embed,
    ) -> bool:
        """Send a DM; returns False when delivery fails (DMs disabled)."""

        try:
            await member.send(embed=embed)
            return True
        except discord.Forbidden:
            return False
        except discord.HTTPException:
            return False

    @staticmethod
    def _truncate(text: str, limit: int = 1000) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."


__all__ = ["TranslationUIEngine", "TranslationPresentation"]
