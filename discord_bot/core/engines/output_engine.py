from __future__ import annotations

from typing import Optional
import discord


class OutputEngine:
    """
    Handles all outbound messaging:
    - DM to user
    - Channel messages
    - Ephemeral replies (UI engines may override/extend)
    """

    def __init__(self, *, error_engine=None) -> None:
        self.error_engine = error_engine

    async def send_dm(self, user: discord.User | discord.Member, text: str) -> None:
        if not text:
            return
        try:
            await user.send(text)
        except Exception as e:
            if self.error_engine:
                await self.error_engine.log_error(e, context="send_dm")

    async def send_channel(self, channel: discord.TextChannel, text: str) -> None:
        if not text:
            return
        try:
            await channel.send(text)
        except Exception as e:
            if self.error_engine:
                await self.error_engine.log_error(e, context="send_channel")

    async def send_ephemeral(
        self,
        channel: discord.abc.Messageable,
        user: discord.User | discord.Member,
        text: str,
    ) -> None:
        """
        Ephemeral simulation: Message visible only to the target user via DM.
        (A UI engine may override for button-based or interaction-based ephemeral.)
        """
        if not text:
            return
        try:
            await user.send(f"(From {getattr(channel, 'name', 'channel')}): {text}")
        except Exception as e:
            if self.error_engine:
                await self.error_engine.log_error(e, context="send_ephemeral")


