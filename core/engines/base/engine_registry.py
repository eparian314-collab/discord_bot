from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional, Set, Callable, Iterable

from discord_bot.core.engines.base.logging_utils import get_logger

_logger = get_logger("engine_registry")


class EngineRegistry:
    """
    Registry to hold and manage engine/plugin instances.

    Improvements added:
      - Intensive, structured logging via logging_utils.get_logger
      - Concurrency protection using a reentrant threading.Lock
        (safe for sync startup code and quick operations)
      - Tracks per-instance remaining dependency requirements and ensures
        `on_dependencies_ready` is invoked once when all required injections arrive
      - Logs event-bus publish failures (no longer silently dropped)
      - Defensive validation of plugin interface and idempotent registration
      - Added helpers: names(), has(), all_instances() for diagnostics
    """

    def __init__(self, *, event_bus: Optional[Any] = None) -> None:
        self._instances: Dict[str, Any] = {}
        self._disabled: Set[str] = set()
        self._injected: Dict[str, Any] = {}
        self.event_bus = event_bus

        # Protect internal state for brief, concurrent access
        self._lock = threading.RLock()

        # Track remaining requirements for each registered plugin by name
        self._waiting_requirements: Dict[str, Set[str]] = {}

        # Track plugins we've signaled as ready to avoid double-calling on_dependencies_ready
        self._ready_signaled: Set[str] = set()

    # --------------------------
    # Registration / injection
    # --------------------------
    def register(self, instance: Any) -> None:
        """
        Register an engine/plugin instance.

        Expected plugin contract:
          - instance.plugin_name() -> str
          - instance.plugin_requires() -> Iterable[str]  (optional)
          - optional instance.on_register(loader)
          - optional instance.on_dependencies_ready()

        Registration is idempotent: existing instance with the same name will be
        replaced (logged).
        """
        if instance is None:
            _logger.error("Attempted to register None instance")
            return

        # Validate plugin_name callable
        name = None
        try:
            if not hasattr(instance, "plugin_name") or not callable(getattr(instance, "plugin_name")):
                _logger.error("Instance missing callable plugin_name(): %r", instance)
                # Best-effort: derive a fallback name from class
                name = getattr(instance, "__class__", type(instance)).__name__
            else:
                name = instance.plugin_name()
        except Exception as exc:
            _logger.exception("Failed to determine plugin_name for instance: %r", instance)
            name = getattr(instance, "__class__", type(instance)).__name__

        with self._lock:
            if name in self._instances:
                _logger.warning("Registering plugin '%s' which already exists; replacing previous instance", name)

            self._instances[name] = instance
            _logger.debug("Registered plugin '%s' -> %r", name, instance)

            # compute & store waiting requirements
            reqs = set()
            try:
                if hasattr(instance, "plugin_requires") and callable(getattr(instance, "plugin_requires")):
                    raw = instance.plugin_requires() or []
                    # allow iterable return values
                    reqs = set(str(x) for x in raw if x)
            except Exception as exc:
                _logger.exception("plugin_requires() failed for '%s'", name)
                reqs = set()

            self._waiting_requirements[name] = set(reqs)

            # call lifecycle hook
            try:
                if hasattr(instance, "on_register") and callable(getattr(instance, "on_register")):
                    instance.on_register(self)
                    _logger.debug("Called on_register for plugin '%s'", name)
            except Exception as exc:
                _logger.exception("on_register handler failed for plugin '%s'", name)

            # If no requirements, signal ready immediately
            if not self._waiting_requirements.get(name):
                self._signal_ready_if_needed(name, instance)

            # Announce registration via event bus (best-effort)
            if self.event_bus:
                self._publish_event_async("engine.registered", name=name)

    def inject(self, key: str, value: Any) -> None:
        """
        Inject a dependency value under `key` (string) for engines to consume.

        After storing, attempt to deliver the injected key to any registered
        plugin that required it; when a plugin's requirement set becomes empty,
        invoke its `on_dependencies_ready()` once.
        """
        if not key:
            _logger.error("inject called with empty key")
            return

        with self._lock:
            already = key in self._injected
            self._injected[key] = value
            if already:
                _logger.info("Re-injected key '%s' (overwriting previous value)", key)
            else:
                _logger.debug("Injected key '%s' -> %r", key, value)

            # Announce injection via event bus
            if self.event_bus:
                self._publish_event_async("engine.injected", key=key)

            # Deliver injected value to waiting plugins
            for name, inst in list(self._instances.items()):
                # skip if already signaled ready
                if name in self._ready_signaled:
                    continue

                # Only consider instances that declare plugin_requires
                if not hasattr(inst, "plugin_requires") or not callable(getattr(inst, "plugin_requires")):
                    continue

                # Get the remaining set; if not tracked, initialize from plugin_requires()
                remaining = self._waiting_requirements.get(name)
                if remaining is None:
                    try:
                        raw = inst.plugin_requires() or []
                        remaining = set(str(x) for x in raw if x)
                        self._waiting_requirements[name] = remaining
                    except Exception:
                        remaining = set()
                        self._waiting_requirements[name] = remaining

                # If the key is relevant, remove it
                if key in remaining:
                    remaining.discard(key)
                    _logger.debug("Delivering injected key '%s' to plugin '%s' (remaining=%s)", key, name, remaining)

                # If no more remaining, call on_dependencies_ready once
                if not remaining:
                    self._signal_ready_if_needed(name, inst)

    # --------------------------
    # Helpers & lifecycle
    # --------------------------
    def _signal_ready_if_needed(self, name: str, inst: Any) -> None:
        """
        Internal helper: call on_dependencies_ready and publish event if not already signaled.
        """
        if name in self._ready_signaled:
            return

        try:
            if hasattr(inst, "on_dependencies_ready") and callable(getattr(inst, "on_dependencies_ready")):
                try:
                    inst.on_dependencies_ready()
                    _logger.info("Plugin '%s' dependencies satisfied; called on_dependencies_ready", name)
                except Exception:
                    _logger.exception("on_dependencies_ready failed for plugin '%s'", name)
            else:
                _logger.debug("Plugin '%s' has no on_dependencies_ready hook; marking ready", name)

            # mark signaled regardless of whether hook existed to avoid repeated calls
            self._ready_signaled.add(name)

            # publish ready event
            if self.event_bus:
                self._publish_event_async("engine.ready", name=name, instance=inst)
        except Exception:
            _logger.exception("Failed to signal ready for plugin '%s'", name)

    def _publish_event_async(self, event_name: str, **kwargs: Any) -> None:
        """
        Publish an event on self.event_bus using asyncio.create_task, with logging on failure.
        Assumes event_bus.publish is an async coroutine function.
        """
        try:
            publish_fn = getattr(self.event_bus, "publish", None)
            if publish_fn is None or not callable(publish_fn):
                _logger.warning("event_bus provided but has no publish() callable")
                return

            # schedule the publish call and log failures in the created task
            async def _do_publish():
                try:
                    await publish_fn(event_name, **kwargs)
                except Exception as exc:
                    _logger.exception("event_bus.publish failed for event '%s' with kwargs=%r", event_name, kwargs)

            # Use existing loop if available, else create task in default loop
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop; create a task in a new loop via ensure_future on default
                loop = None

            if loop:
                loop.create_task(_do_publish())
            else:
                # Fallback: use asyncio.create_task which will use the running loop if present, else will error.
                try:
                    asyncio.create_task(_do_publish())
                except Exception:
                    # As a last resort, run synchronously but catch exceptions
                    try:
                        asyncio.get_event_loop().create_task(_do_publish())
                    except Exception:
                        _logger.exception("Unable to schedule event_bus.publish for event '%s'", event_name)
        except Exception:
            _logger.exception("Failed to schedule event publish for '%s'", event_name)

    # --------------------------
    # Enable / disable / inspect
    # --------------------------
    def enable(self, name: str) -> None:
        with self._lock:
            if name in self._disabled:
                self._disabled.discard(name)
                _logger.info("Enabled plugin '%s'", name)
            else:
                _logger.debug("Enable called for '%s' which was not disabled", name)

    def disable(self, name: str) -> None:
        with self._lock:
            if name not in self._disabled:
                self._disabled.add(name)
                _logger.info("Disabled plugin '%s'", name)
            else:
                _logger.debug("Disable called for '%s' which was already disabled", name)

    def status(self) -> Dict[str, Dict[str, Any]]:
        """
        Return status for each registered plugin:
          - ready: best-effort flag
          - requires: declared requirements
          - waiting_for: requirements not yet injected
          - disabled: boolean
        """
        out: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for name, inst in self._instances.items():
                try:
                    requires = set()
                    if hasattr(inst, "plugin_requires") and callable(getattr(inst, "plugin_requires")):
                        raw = inst.plugin_requires() or []
                        requires = set(str(x) for x in raw if x)
                except Exception:
                    _logger.exception("plugin_requires failed for '%s' while computing status", name)
                    requires = set()

                waiting = [r for r in requires if r not in self._injected]
                ready_flag = name in self._ready_signaled
                out[name] = {
                    "ready": ready_flag,
                    "requires": requires,
                    "waiting_for": waiting,
                    "disabled": name in self._disabled,
                }
        return out

    def get(self, name: str) -> Optional[Any]:
        with self._lock:
            if name in self._disabled:
                _logger.debug("get() called for disabled plugin '%s'", name)
                return None
            inst = self._instances.get(name)
            if inst is None:
                _logger.debug("get() returned None for plugin '%s'", name)
            return inst

    # --------------------------
    # Convenience inspectors
    # --------------------------
    def names(self) -> Iterable[str]:
        with self._lock:
            return tuple(self._instances.keys())

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._instances and name not in self._disabled

    def all_instances(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._instances)