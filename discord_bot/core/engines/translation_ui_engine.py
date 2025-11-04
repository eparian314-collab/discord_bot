from __future__ import annotations

import asyncio
from typing import Any, Optional, Dict

import discord

from discord_bot.core.engines.base.engine_plugin import EnginePlugin
from discord_bot.core.engines.base.engine_registry import EngineRegistry


class TranslationUIEngine(EnginePlugin):
    """
    UI engine for translation interactions.

    Responsibilities:
      - Render translation results for users.
      - Prefer OutputEngine.send_response when available.
      - Fall back to direct interaction responses if OutputEngine is not injected.
    """

    def __init__(self, *, event_bus: Optional[Any] = None) -> None:
        super().__init__()
        self._bus = event_bus
        self._requires = ("engine_registry",)

        self.registry = None
        self.output = None  # Will be resolved after registration

    def on_register(self, loader: Any) -> None:
        """Called when the engine is registered."""
        try:
            self.registry = loader if isinstance(loader, EngineRegistry) else None
            if hasattr(loader, "event_bus"):
                self._bus = getattr(loader, "event_bus", self._bus)
        except Exception:
            self.registry = None

    def on_dependencies_ready(self) -> None:
        """Resolve injected dependencies once registry is available."""
        if not hasattr(self, "inject"):
            return
        try:
            self.output = self.inject.get("output_engine", None)  # type: ignore
        except Exception:
            self.output = None

    async def show_result(
        self,
        interaction: discord.Interaction,
        result: Any,
        *,
        ephemeral: bool = True,
    ) -> None:
        """
        Display a translation result using OutputEngine if available.
        If OutputEngine is unavailable, send directly.
        """
        text = self._extract_text(result)

        if not interaction:
            return

        try:
            if self.output and hasattr(self.output, "send_interaction_response"):
                await self.output.send_interaction_response(interaction, text, ephemeral=ephemeral)
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message(text, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(text, ephemeral=ephemeral)
        except Exception:
            # silent fail: UI should not crash bot
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Error displaying translation.", ephemeral=True)
                else:
                    await interaction.followup.send("Error displaying translation.", ephemeral=True)
            except Exception:
                pass

    async def show_error(
        self,
        interaction: discord.Interaction,
        msg: str = "An error occurred.",
        *,
        ephemeral: bool = True,
    ) -> None:
        """Display error message."""
        if not interaction:
            return
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=ephemeral)
            else:
                await interaction.followup.send(msg, ephemeral=ephemeral)
        except Exception:
            pass

    def _extract_text(self, result: Any) -> str:
        """Normalize text from various adapter/orchestrator return formats."""
        if result is None:
            return "No translation available."

        # If result is a dict
        if isinstance(result, dict):
            text = result.get("text")
            # Safety: Don't fallback to str(result) if text is explicitly None
            # This prevents echoing the dict structure back to users
            if text is not None:
                return str(text)
            # Check for metadata that explains why there's no text
            meta = result.get("meta", {})
            if meta.get("reason") == "no_translation_needed":
                src = result.get("src", "unknown")
                tgt = result.get("tgt", "unknown")
                return f"Text is already in {tgt.upper()}. No translation needed."
            return "No translation was produced."

        # Dataclass or object with .text
        text = getattr(result, "text", None)
        if text is not None:
            return str(text)

        # Check for metadata in object form
        meta = getattr(result, "meta", {}) or {}
        if meta.get("reason") == "no_translation_needed":
            src = getattr(result, "src", "unknown")
            tgt = getattr(result, "tgt", "unknown")
            return f"Text is already in {tgt.upper()}. No translation needed."

        # Last resort fallback
        return "No translation available."


