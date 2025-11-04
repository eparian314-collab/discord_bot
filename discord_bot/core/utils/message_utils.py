"""Helpers for safely replying to Discord interactions."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence

import discord

logger = logging.getLogger(__name__)


async def safe_send_interaction_response(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    embeds: Optional[Sequence[discord.Embed]] = None,
    ephemeral: bool = True,
    **kwargs: Any,
) -> bool:
    """Best-effort interaction response that tolerates expired tokens.

    Attempts the primary response first, then falls back to followup, and finally
    to channel.send when possible. Returns True if any attempt succeeds.
    """
    raw_kwargs: Dict[str, Any] = {
        "content": content,
        "embed": embed,
        "embeds": embeds,
        "ephemeral": ephemeral,
        **kwargs,
    }
    send_kwargs = {key: value for key, value in raw_kwargs.items() if value is not None}

    if not interaction.response.is_done():
        try:
            await interaction.response.send_message(**send_kwargs)
            return True
        except discord.HTTPException as exc:
            logger.debug(
                "Primary interaction response failed (%s); attempting followup",
                exc.__class__.__name__,
                exc_info=exc,
            )
    # If the response is already done or the first attempt failed, try followup.
    try:
        await interaction.followup.send(**send_kwargs)
        return True
    except discord.HTTPException as exc:
        logger.debug(
            "Followup interaction response failed (%s); attempting channel send",
            exc.__class__.__name__,
            exc_info=exc,
        )

    channel = interaction.channel
    if channel:
        channel_kwargs = {k: v for k, v in send_kwargs.items() if k != "ephemeral"}
        try:
            await channel.send(**channel_kwargs)
            return True
        except discord.HTTPException as exc:
            logger.warning(
                "Channel send fallback failed for interaction %s (%s)",
                interaction.id,
                exc.__class__.__name__,
                exc_info=exc,
            )
    else:
        logger.debug(
            "Unable to fall back to channel send; interaction %s has no channel",
            interaction.id,
        )

    return False


