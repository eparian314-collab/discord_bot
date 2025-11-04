"""
Helper utilities for localizing bot responses in cogs.

Import and use these functions in your cogs to automatically translate
bot dialog to users' preferred languages.
"""
from __future__ import annotations

from typing import Optional
import discord

from discord_bot.core.engines.localization_engine import get_localization_engine


async def localize(
    text: str,
    user: discord.User | discord.Member,
    guild_id: Optional[int] = None
) -> str:
    """
    Translate text to user's preferred language if they have a language role.
    
    Args:
        text: The English text to translate
        user: The user to translate for
        guild_id: Optional guild context
        
    Returns:
        Translated text or original if user has no language role
        
    Example:
        ```python
        message = await localize("Role assigned successfully!", interaction.user, interaction.guild_id)
        await interaction.response.send_message(message, ephemeral=True)
        ```
    """
    engine = get_localization_engine()
    if not engine:
        return text
    
    return await engine.localize_response(text, user, guild_id)


async def send_localized(
    interaction: discord.Interaction,
    text: str,
    **kwargs
) -> None:
    """
    Send a localized response to an interaction.
    
    Automatically translates the text to the user's preferred language
    and sends it as either a response or followup.
    
    Args:
        interaction: The interaction to respond to
        text: The English text to send
        **kwargs: Additional arguments for send_message/followup.send
        
    Example:
        ```python
        await send_localized(interaction, "Your Pokemon evolved!", ephemeral=True)
        ```
    """
    engine = get_localization_engine()
    if engine:
        await engine.localize_interaction_response(interaction, text, **kwargs)
    else:
        # Fallback if engine not available
        if not interaction.response.is_done():
            await interaction.response.send_message(text, **kwargs)
        else:
            await interaction.followup.send(text, **kwargs)


async def localize_embed(
    embed: discord.Embed,
    user: discord.User | discord.Member,
    guild_id: Optional[int] = None
) -> discord.Embed:
    """
    Translate embed content to user's preferred language.
    
    Args:
        embed: The embed to translate
        user: The user to translate for
        guild_id: Optional guild context
        
    Returns:
        New embed with translated content
        
    Example:
        ```python
        embed = discord.Embed(title="Battle Results", description="You won!")
        localized_embed = await localize_embed(embed, interaction.user, interaction.guild_id)
        await interaction.response.send_message(embed=localized_embed)
        ```
    """
    engine = get_localization_engine()
    if not engine:
        return embed
    
    return await engine.localize_embed(embed, user, guild_id)
