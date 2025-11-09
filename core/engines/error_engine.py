from __future__ import annotations

import asyncio
import traceback
from collections import deque, defaultdict
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, List


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
    Enhanced error engine with categorization, aggregation, and guardian safeguards.
    
    Features:
    - Error categorization (adapter, event, storage, etc.)
    - Time-windowed aggregation for pattern detection
    - Structured metadata capture for downstream diagnostics
    - Admin-friendly error reports
    """

    def __init__(self, *, event_bus: Optional[Any] = None, max_errors: int = 200) -> None:
        super().__init__(max_errors=max_errors)
        self._event_bus = event_bus
        
        # Category-specific error tracking
        self._categorized_errors: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=50))
        
        # Error rate tracking for pattern detection
        self._error_counts: Dict[str, int] = defaultdict(int)

    async def log_error(
        self, 
        error: Exception, 
        *, 
        context: str = "", 
        severity: str = "error", 
        category: Optional[str] = None,
        **metadata: Any
    ) -> None:
        """
        Log an error with optional categorization.
        
        Args:
            error: The exception that occurred
            context: Human-readable context string
            severity: error|warning|critical
            category: Optional category identifier (e.g., "translation.request", "event.reminder")
            **metadata: Additional context data
        """
        await super().log_error(error, context=context)
        
        # Build enhanced error record
        error_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "message": str(error),
            "severity": severity,
            "category": category or "general",
            "trace": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            "metadata": metadata,
        }
        
        # Store in category-specific deque
        if category:
            self._categorized_errors[category].appendleft(error_record)
            self._error_counts[category] += 1
        
        # Emit to event bus
        if self._event_bus:
            await self._emit_error_event(error_record)

    async def _emit_error_event(self, error_record: Dict[str, Any]) -> None:
        """Emit error to event bus based on category."""
        try:
            from discord_bot.core.event_topics import ENGINE_ERROR
            emit = getattr(self._event_bus, "emit", None)
            if callable(emit):
                payload = {
                    "context": error_record["context"],
                    "message": error_record["message"],
                    "severity": error_record["severity"],
                    "category": error_record.get("category", "general"),
                    "metadata": error_record.get("metadata", {}),
                }
                maybe = emit(ENGINE_ERROR, **payload)
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            # Best-effort: guardian logging should never raise
            pass
    
    def get_errors_by_category(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent errors for a specific category."""
        errors = self._categorized_errors.get(category, deque())
        return list(errors)[:limit]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors by category."""
        summary = {
            "total_errors": len(self._errors),
            "by_category": {},
            "safe_mode": self._safe_mode,
        }
        
        for category, count in self._error_counts.items():
            recent_errors = self._categorized_errors.get(category, deque())
            summary["by_category"][category] = {
                "total_count": count,
                "recent_count": len(recent_errors),
                "last_error": recent_errors[0] if recent_errors else None,
            }
        
        return summary
    


_error_engine: Optional[ErrorEngine] = None


def get_error_engine() -> ErrorEngine:
    global _error_engine
    if _error_engine is None:
        _error_engine = ErrorEngine()
    return _error_engine
