from __future__ import annotations

import asyncio
import traceback
from collections import deque
from typing import Any, Deque, Dict, Optional


class ErrorEngine:
    """
    Centralized error logging and guardian fail-safe.
    Stores recent errors, exposes inspection helpers, and can trigger safe-mode.
    """

    def __init__(self, *, max_errors: int = 200) -> None:
        self._errors: Deque[Dict[str, Any]] = deque(maxlen=max_errors)
        self._safe_mode: bool = False
        self._disabled_plugins: set[str] = set()
        self._registry: Optional[Any] = None

    @property
    def is_safe_mode(self) -> bool:
        return self._safe_mode

    def disabled_plugins(self) -> set[str]:
        return set(self._disabled_plugins)

    def attach_registry(self, registry: Any) -> None:
        """Optional hook to retain the registry for guardian actions."""
        self._registry = registry

    async def log_error(self, error: Exception, *, context: str = "") -> None:
        data = {
            "context": context,
            "message": str(error),
            "trace": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        }
        self._errors.appendleft(data)

        # auto-safe-mode trigger if repeated failures
        if len(self._errors) >= 10:
            recent = list(self._errors)[:10]
            contexts = [e.get("context") for e in recent]
            if len(set(contexts)) <= 2:  # repeated same failure
                self._safe_mode = True

    async def peek_last(self) -> Optional[Dict[str, Any]]:
        return self._errors[0] if self._errors else None

    async def dump_recent_text(self, *, limit: int = 100) -> str:
        out = []
        for e in list(self._errors)[:limit]:
            out.append(f"[{e.get('context','')}] {e.get('message','')}")
        return "\n".join(out)

    def disable_plugin(self, name: str) -> None:
        self._disabled_plugins.add(name)
        if self._registry and hasattr(self._registry, "disable"):
            try:
                self._registry.disable(name)  # type: ignore[attr-defined]
            except Exception:
                pass


class GuardianErrorEngine(ErrorEngine):
    """
    Extended error engine that can emit structured events and keep the registry informed.
    """

    def __init__(self, *, event_bus: Optional[Any] = None, max_errors: int = 200) -> None:
        super().__init__(max_errors=max_errors)
        self._event_bus = event_bus

    async def log_error(self, error: Exception, *, context: str = "", severity: str = "error", **metadata: Any) -> None:
        await super().log_error(error, context=context)
        if not self._event_bus:
            return

        try:
            payload = {
                "context": context,
                "message": str(error),
                "severity": severity,
                "extra": metadata,
            }
            emit = getattr(self._event_bus, "emit", None)
            if callable(emit):
                maybe = emit("engine.error", **payload)
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            # Best-effort: guardian logging should never raise
            pass


_error_engine: Optional[ErrorEngine] = None


def get_error_engine() -> ErrorEngine:
    global _error_engine
    if _error_engine is None:
        _error_engine = ErrorEngine()
    return _error_engine
