from __future__ import annotations

from typing import Optional
import discord


class OutputEngine:
    """
    Handles outbound messaging helpers:
    - Direct messages
    - Channel messages
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

