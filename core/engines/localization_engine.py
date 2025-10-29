"""
Localization Engine - Translates bot responses to user's preferred language.

This engine checks if a user has a language role and automatically translates
all bot dialog/responses to that language for better UX.
"""
from __future__ import annotations

import logging
from typing import Optional, Any
import discord

from discord_bot.core.engines.base.engine_plugin import EnginePlugin

logger = logging.getLogger("hippo_bot.localization_engine")


class LocalizationEngine(EnginePlugin):
    """
    Automatically localizes bot responses based on user's language role.
    
    When a user has a language role assigned, all bot dialog is translated
    to their preferred language for seamless experience.
    """
    
    def __init__(self, *, event_bus: Optional[Any] = None) -> None:
        super().__init__()
        self._bus = event_bus
        self._requires = ("role_manager", "translation_orchestrator")
        
        self.roles = None
        self.orchestrator = None
        
    def on_dependencies_ready(self) -> None:
        """Resolve injected dependencies."""
        if not hasattr(self, "inject"):
            return
        try:
            self.roles = self.inject.get("role_manager", None)
            self.orchestrator = self.inject.get("translation_orchestrator", None)
        except Exception as exc:
            logger.warning(f"Failed to resolve dependencies: {exc}")
    
    async def localize_response(
        self,
        text: str,
        user: discord.User | discord.Member,
        guild_id: Optional[int] = None
    ) -> str:
        """
        Translate bot response text to user's preferred language.
        
        Args:
            text: The bot response text in English
            user: The user to localize for
            guild_id: Guild context for role lookup
            
        Returns:
            Translated text if user has language role, otherwise original text
        """
        if not text or not user:
            return text
        
        # Skip for bots
        if user.bot:
            return text
        
        # Determine guild ID
        if guild_id is None and hasattr(user, 'guild'):
            guild_id = user.guild.id if user.guild else None
        
        if guild_id is None:
            return text
        
        try:
            # Get user's language preference
            user_lang = await self._get_user_language(user.id, guild_id)
            
            # If user has no language role or is English, return as-is
            if not user_lang or user_lang.lower() in ('en', 'english'):
                return text
            
            # Translate the response
            translated = await self._translate_text(text, target_lang=user_lang)
            
            if translated:
                logger.debug(f"Localized response for user {user.id} to {user_lang}")
                return translated
            
        except Exception as exc:
            logger.error(f"Failed to localize response: {exc}")
        
        # Fallback to original text
        return text
    
    async def localize_interaction_response(
        self,
        interaction: discord.Interaction,
        text: str,
        **kwargs
    ) -> None:
        """
        Send a localized interaction response.
        
        Args:
            interaction: The interaction to respond to
            text: The English response text
            **kwargs: Additional arguments for send_message/followup.send
        """
        if not interaction or not text:
            return
        
        guild_id = interaction.guild_id if interaction.guild else None
        localized = await self.localize_response(text, interaction.user, guild_id)
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(localized, **kwargs)
            else:
                await interaction.followup.send(localized, **kwargs)
        except Exception as exc:
            logger.error(f"Failed to send localized response: {exc}")
    
    async def localize_embed(
        self,
        embed: discord.Embed,
        user: discord.User | discord.Member,
        guild_id: Optional[int] = None
    ) -> discord.Embed:
        """
        Translate embed content to user's preferred language.
        
        Args:
            embed: The embed to localize
            user: The user to localize for
            guild_id: Guild context
            
        Returns:
            New embed with localized content
        """
        if not embed or not user:
            return embed
        
        # Determine guild ID
        if guild_id is None and hasattr(user, 'guild'):
            guild_id = user.guild.id if user.guild else None
        
        if guild_id is None:
            return embed
        
        try:
            # Get user's language preference
            user_lang = await self._get_user_language(user.id, guild_id)
            
            # If user has no language role or is English, return as-is
            if not user_lang or user_lang.lower() in ('en', 'english'):
                return embed
            
            # Create new embed to avoid mutating original
            new_embed = discord.Embed(color=embed.color)
            
            # Translate title
            if embed.title:
                new_embed.title = await self._translate_text(embed.title, target_lang=user_lang) or embed.title
            
            # Translate description
            if embed.description:
                new_embed.description = await self._translate_text(embed.description, target_lang=user_lang) or embed.description
            
            # Translate fields
            for field in embed.fields:
                translated_name = await self._translate_text(field.name, target_lang=user_lang) or field.name
                translated_value = await self._translate_text(field.value, target_lang=user_lang) or field.value
                new_embed.add_field(name=translated_name, value=translated_value, inline=field.inline)
            
            # Copy footer (usually don't translate footer)
            if embed.footer:
                new_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
            
            # Copy other attributes
            if embed.thumbnail:
                new_embed.set_thumbnail(url=embed.thumbnail.url)
            if embed.image:
                new_embed.set_image(url=embed.image.url)
            if embed.author:
                new_embed.set_author(name=embed.author.name, icon_url=embed.author.icon_url, url=embed.author.url)
            
            logger.debug(f"Localized embed for user {user.id} to {user_lang}")
            return new_embed
            
        except Exception as exc:
            logger.error(f"Failed to localize embed: {exc}")
            return embed
    
    async def _get_user_language(self, user_id: int, guild_id: int) -> Optional[str]:
        """Get user's primary language from roles."""
        if not self.roles:
            return None
        
        try:
            # Get user's language roles
            languages = await self.roles.get_user_languages(user_id, guild_id)
            
            if languages:
                # Return first language (primary)
                return languages[0]
        except Exception as exc:
            logger.debug(f"Could not get user language: {exc}")
        
        return None
    
    async def _translate_text(self, text: str, target_lang: str) -> Optional[str]:
        """Translate text using the orchestrator."""
        if not text or not target_lang or not self.orchestrator:
            return None
        
        try:
            # Use orchestrator to translate from English to target
            from discord_bot.language_context.translation_job import TranslationJob
            
            job = TranslationJob(
                text=text,
                source='en',
                target=target_lang,
                author_id=0,  # System translation
                guild_id=0
            )
            
            translated = await self.orchestrator.translate_job(job)
            return translated
            
        except Exception as exc:
            logger.debug(f"Translation failed: {exc}")
            return None


# Singleton instance for easy import
_localization_engine: Optional[LocalizationEngine] = None


def get_localization_engine() -> Optional[LocalizationEngine]:
    """Get the global localization engine instance."""
    return _localization_engine


def set_localization_engine(engine: LocalizationEngine) -> None:
    """Set the global localization engine instance."""
    global _localization_engine
    _localization_engine = engine
