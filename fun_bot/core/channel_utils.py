from __future__ import annotations

from typing import Iterable, Set
import time

import discord


async def ensure_bot_channel(
    interaction: discord.Interaction,
    allowed_channel_ids: Iterable[int],
) -> bool:
    """Ensure a slash command is used in an allowed bot channel.

    Returns ``True`` when the command should proceed, or ``False`` when a
    friendly message has been sent and the caller should return early.
    If ``allowed_channel_ids`` is empty, no restriction is enforced.

    FunBot-specific behaviour: if the bot was configured with a
    ``funbot_grace_window`` (in seconds) and the current time is still
    within that window from ``funbot_start_time``, channel restrictions
    are temporarily disabled so commands can be used anywhere.
    """

    client = getattr(interaction, "client", None)
    if client is not None:
        try:
            grace_window = int(getattr(client, "funbot_grace_window", 0))
            start_time = float(getattr(client, "funbot_start_time", 0.0))
        except (TypeError, ValueError):
            grace_window = 0
            start_time = 0.0

        if grace_window > 0 and start_time > 0:
            now = time.time()
            if now - start_time <= grace_window:
                return True

    allowed: Set[int] = {int(x) for x in allowed_channel_ids}
    if not allowed:
        return True

    channel = interaction.channel
    if channel is None or not isinstance(channel, discord.abc.GuildChannel):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "This command can only be used in a server bot channel.",
                ephemeral=True,
            )
        return False

    if channel.id not in allowed:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Please use this command in the designated bot channel.",
                ephemeral=True,
            )
        return False

    return True


__all__ = ["ensure_bot_channel"]
