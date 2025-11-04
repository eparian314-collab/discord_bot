from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Sequence

from discord_bot.core.engines.base.logging_utils import get_logger

_logger = get_logger("engine_plugin")


class PluginBase:
    """
    Base class for plugin-style engines.
    Provides dependency readiness tracking and lifecycle hooks.

    Recommended lifecycle patterns:
      - Prefer implementing `on_register(self, loader)` as a synchronous method.
      - If you need async work at register-time, implement `async_on_register(self, loader)`
        instead; the base class will schedule/run it safely.
      - Similarly prefer `on_dependencies_ready(self)` sync; use
        `async_on_dependencies_ready(self)` for async implementations.

    The EngineRegistry expects `plugin_name()` and (optionally) `plugin_requires()`.
    """

    def __init__(self) -> None:
        self._ready: bool = False
        self._requires: Sequence[str] = ()
        self._name: Optional[str] = None

    # ---------- identity / metadata ----------
    def plugin_name(self) -> str:
        return self._name or self.__class__.__name__.lower()

    def set_plugin_name(self, name: str) -> None:
        """Set an explicit plugin name (useful for registry keys)."""
        self._name = name

    def plugin_requires(self) -> Sequence[str]:
        return self._requires

    def set_requires(self, requires: Sequence[str]) -> None:
        """Set required injected keys for this plugin."""
        self._requires = requires

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ---------- lifecycle hooks ----------
    def on_register(self, loader: Any) -> None:
        """
        Called by EngineRegistry when the plugin is registered.

        Default behavior:
          - If subclass defines `async_on_register`, schedule or run it.
          - Otherwise no-op. Subclasses may override this method (sync).
        """
        # run async variant if provided
        fn = getattr(self, "async_on_register", None)
        if callable(fn):
            try:
                _call_maybe_async(fn, loader)
            except Exception:
                _logger.exception("async_on_register failed for %s", self.plugin_name())

    def on_dependencies_ready(self) -> None:
        """
        Called by EngineRegistry when required injections have all arrived.

        Default behavior:
          - mark plugin as ready
          - if subclass defines `async_on_dependencies_ready`, schedule/run it
          - subclasses may override this method (sync)
        """
        # set ready flag first so re-entrant checks see the state
        self._ready = True

        fn = getattr(self, "async_on_dependencies_ready", None)
        if callable(fn):
            try:
                _call_maybe_async(fn)
            except Exception:
                _logger.exception("async_on_dependencies_ready failed for %s", self.plugin_name())

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<{self.__class__.__name__} name={self.plugin_name()} ready={self._ready} requires={self._requires!r}>"


class EnginePlugin(PluginBase):
    """
    Marker base for engines that act as plugins with a defined name + deps.

    Default naming convention: Strip "Engine" from the class name, lower-case and
    append "_engine". Example: `TranslationOrchestratorEngine` -> "translationorchestrator_engine".
    """

    def plugin_name(self) -> str:
        return self.__class__.__name__.replace("Engine", "").lower() + "_engine"

    def plugin_requires(self) -> Sequence[str]:
        return getattr(self, "_requires", ())


# -------------------------
# Internal helpers
# -------------------------
def _call_maybe_async(func: Any, *args: Any, **kwargs: Any) -> None:
    """
    Call a function that may be synchronous or asynchronous.

    Behavior:
      - If `func` is a coroutine function and an event loop is running, schedules it
        with `create_task`.
      - If no running loop exists, uses `asyncio.run` to execute to completion.
      - If `func` is synchronous, calls it directly.
    """
    try:
        if asyncio.iscoroutinefunction(func):
            # coroutine function
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(func(*args, **kwargs))
                return
            except RuntimeError:
                # no running loop -- execute to completion in a new loop
                asyncio.run(func(*args, **kwargs))
                return
        # callable sync
        func(*args, **kwargs)
    except Exception:
        _logger.exception("Error while calling possibly-async function %r", func)