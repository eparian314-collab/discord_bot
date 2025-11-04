from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Sequence

import discord

from discord_bot.core.engines.base.engine_plugin import EnginePlugin, PluginBase
from discord_bot.core.engines.base.engine_registry import EngineRegistry
from discord_bot.core.event_bus import EventBus

try:
    from discord_bot.core.engines.role_manager import RoleManager
except Exception:
    RoleManager = Any  # type: ignore

try:
    from discord_bot.core.engines.error_engine import GuardianErrorEngine
except Exception:
    GuardianErrorEngine = Any  # type: ignore


GREEN = 0x2ecc71
YELLOW = 0xf1c40f
RED = 0xe74c3c
BLUE = 0x3498db
GRAY = 0x95a5a6


class AdminUIEngine(EnginePlugin):
    def __init__(self, *, event_bus: Optional[EventBus] = None) -> None:
        super().__init__()
        self._bus: EventBus = event_bus or EventBus()
        self.registry: Optional[EngineRegistry] = None
        self.roles: Optional[RoleManager] = None
        self.error_engine: Optional[GuardianErrorEngine] = None

    def plugin_name(self) -> str:
        return "admin_ui_engine"

    def plugin_requires(self) -> Sequence[str]:
        return ("engine_registry",)

    def on_register(self, loader: Any) -> None:
        if isinstance(loader, EngineRegistry):
            self.registry = loader

        self._bus = getattr(loader, "event_bus", self._bus)

        if self._bus:
            self._bus.subscribe("engine.ready", self._on_engine_ready)

        if self.registry is not None:
            self.on_dependencies_ready()

    def _on_engine_ready(self, *, name: str, instance: Any) -> None:
        try:
            if name == "engine_registry" and isinstance(instance, EngineRegistry):
                self.registry = instance
            elif name == "role_manager":
                self.roles = instance  # type: ignore
            elif name == "error_engine":
                self.error_engine = instance  # type: ignore

            if self.registry is not None:
                self.on_dependencies_ready()
        except Exception as e:
            self._safe_log(e, "_on_engine_ready")

    def _ok(self) -> bool:
        return self.is_ready and self.registry is not None

    def _safe_log(self, e: Exception, context: str, extra: Optional[Dict[str, Any]] = None) -> None:
        try:
            if self.error_engine and hasattr(self.error_engine, "log_error"):
                asyncio.create_task(self.error_engine.log_error(
                    e,
                    source="admin_ui_engine",
                    category="ui",
                    severity="error",
                    context={"where": context, **(extra or {})}
                ))
        except Exception:
            pass

    def _embed(self, title: str, desc: str = "", color: int = BLUE) -> discord.Embed:
        return discord.Embed(title=title, description=desc or discord.Embed.Empty, color=color)

    async def handle_plugins_list(self, *, interaction: discord.Interaction) -> None:
        if not self._ok():
            await self._say_loading(interaction)
            return
        try:
            status = self.registry.status()  # type: ignore
            emb = self._embed("Plugins", color=BLUE)

            if not status:
                emb.description = "No plugins registered."
            else:
                for name, info in sorted(status.items()):
                    ready = bool(info.get("ready"))
                    requires = ", ".join(info.get("requires", [])) or "-"
                    waiting = ", ".join(info.get("waiting_for", [])) or "-"
                    color_emoji = "GREEN" if ready else ("YELLOW" if not waiting else "ORANGE")
                    emb.add_field(
                        name=f"{color_emoji} {name}",
                        value=f"Requires: {requires}\nWaiting for: {waiting}",
                        inline=False
                    )

            await self._respond(interaction, emb, ephemeral=True)
        except Exception as e:
            self._safe_log(e, "handle_plugins_list")
            await self._respond(interaction, self._embed("Error", "Failed to fetch plugins.", RED), ephemeral=True)

    async def handle_plugin_enable(self, *, interaction: discord.Interaction, name: str) -> None:
        if not self._ok():
            await self._say_loading(interaction)
            return
        try:
            self.registry.enable(name)  # type: ignore
            await self.handle_plugins_list(interaction=interaction)
        except Exception as e:
            self._safe_log(e, "handle_plugin_enable", {"plugin": name})
            await self._respond(interaction, self._embed("Error", f"Could not enable {name}.", RED), ephemeral=True)

    async def handle_plugin_disable(self, *, interaction: discord.Interaction, name: str) -> None:
        if not self._ok():
            await self._say_loading(interaction)
            return
        try:
            self.registry.disable(name)  # type: ignore
            await self.handle_plugins_list(interaction=interaction)
        except Exception as e:
            self._safe_log(e, "handle_plugin_disable", {"plugin": name})
            await self._respond(interaction, self._embed("Error", f"Could not disable {name}.", RED), ephemeral=True)

    async def handle_diag(self, *, interaction: discord.Interaction) -> None:
        if not self._ok():
            await self._say_loading(interaction)
            return
        try:
            emb = self._embed("Diagnostics", color=BLUE)
            emb.add_field(name="Registry", value="Ready" if self.registry else "Missing", inline=True)
            emb.add_field(name="RoleManager", value=("Ready" if self.roles else "Optional"), inline=True)

            guard = self.error_engine
            if guard:
                safe_mode = bool(getattr(guard, "is_safe_mode", False))
                disabled = list(getattr(guard, "disabled_plugins", lambda: [])())
                if safe_mode:
                    emb.add_field(
                        name="SAFE MODE ACTIVE",
                        value=f"Disabled: {', '.join(disabled) if disabled else 'unknown'}",
                        inline=False,
                    )
                else:
                    emb.add_field(name="Guardian Status", value="Guardian active. Safe mode not active.", inline=False)
            else:
                emb.add_field(name="Guardian Status", value="No ErrorEngine attached.", inline=False)

            await self._respond(interaction, emb, ephemeral=True)
        except Exception as e:
            self._safe_log(e, "handle_diag")
            await self._respond(interaction, self._embed("Error", "Diagnostics failed.", RED), ephemeral=True)

    async def _respond(self, interaction: discord.Interaction, embed: discord.Embed, *, ephemeral: bool = False, file: Optional[discord.File] = None) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=ephemeral, file=file)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=ephemeral, file=file)
        except Exception:
            try:
                await interaction.user.send(embed=embed)
            except Exception:
                pass

    async def _say_loading(self, interaction: discord.Interaction) -> None:
        await self._respond(interaction, self._embed("Admin UI", "Loading or not ready yet.", GRAY), ephemeral=True)

    @staticmethod
    def _to_bytesio(text: str) -> Any:
        from io import BytesIO
        bio = BytesIO(text.encode("utf-8", errors="replace"))
        bio.seek(0)
        return bio


