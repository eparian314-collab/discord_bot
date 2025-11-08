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
    Enhanced error engine with categorization, aggregation, and ranking-specific tracking.
    
    Features:
    - Error categorization (ranking.submission, ranking.ocr, etc.)
    - Time-windowed aggregation for pattern detection
    - Detailed ranking error context capture
    - Admin-friendly error reports
    """

    def __init__(self, *, event_bus: Optional[Any] = None, max_errors: int = 200) -> None:
        super().__init__(max_errors=max_errors)
        self._event_bus = event_bus
        
        # Category-specific error tracking
        self._categorized_errors: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=50))
        
        # Ranking-specific error tracking
        self._ranking_errors: Deque[Dict[str, Any]] = deque(maxlen=100)
        
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
            category: Optional category (e.g., "ranking.submission", "ranking.ocr")
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
        
        # Special handling for ranking errors
        if category and category.startswith("ranking."):
            self._ranking_errors.appendleft(error_record)
        
        # Emit to event bus
        if self._event_bus:
            await self._emit_error_event(error_record)

    async def _emit_error_event(self, error_record: Dict[str, Any]) -> None:
        """Emit error to event bus based on category."""
        try:
            category = error_record.get("category", "general")
            
            # Determine topic based on category
            if category.startswith("ranking."):
                topic = self._get_ranking_topic(category)
            else:
                from discord_bot.core.event_topics import ENGINE_ERROR
                topic = ENGINE_ERROR
            
            emit = getattr(self._event_bus, "emit", None)
            if callable(emit):
                payload = {
                    "context": error_record["context"],
                    "message": error_record["message"],
                    "severity": error_record["severity"],
                    "category": category,
                    "metadata": error_record.get("metadata", {}),
                }
                maybe = emit(topic, **payload)
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            # Best-effort: guardian logging should never raise
            pass
    
    def _get_ranking_topic(self, category: str) -> str:
        """Map category to specific ranking error topic."""
        from discord_bot.core import event_topics
        
        topic_map = {
            "ranking.submission": event_topics.RANKING_SUBMISSION_ERROR,
            "ranking.ocr": event_topics.RANKING_OCR_ERROR,
            "ranking.validation": event_topics.RANKING_VALIDATION_ERROR,
            "ranking.db": event_topics.RANKING_DB_ERROR,
            "ranking.permission": event_topics.RANKING_PERMISSION_ERROR,
        }
        return topic_map.get(category, event_topics.ENGINE_ERROR)
    
    async def log_ranking_error(
        self,
        error: Exception,
        *,
        category: str,
        user_id: str,
        guild_id: Optional[str] = None,
        kvk_run_id: Optional[int] = None,
        stage: Optional[str] = None,
        day: Optional[int] = None,
        confidence: Optional[float] = None,
        screenshot_url: Optional[str] = None,
        context: str = "",
        **extra_metadata: Any
    ) -> None:
        """
        Specialized logging for ranking system errors with full context.
        
        Args:
            error: The exception
            category: Specific ranking category (submission|ocr|validation|db|permission)
            user_id: Discord user ID
            guild_id: Discord guild ID
            kvk_run_id: KVK run identifier
            stage: prep|war
            day: Day number (1-5 for prep, None for war)
            confidence: OCR confidence score if applicable
            screenshot_url: URL to the screenshot if available
            context: Human-readable context
            **extra_metadata: Additional context data
        """
        full_category = f"ranking.{category}"
        
        metadata = {
            "user_id": user_id,
            "guild_id": guild_id,
            "kvk_run_id": kvk_run_id,
            "stage": stage,
            "day": day,
            "confidence": confidence,
            "screenshot_url": screenshot_url,
            **extra_metadata
        }
        
        await self.log_error(
            error,
            context=context,
            severity="error",
            category=full_category,
            **metadata
        )
    
    def get_errors_by_category(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent errors for a specific category."""
        errors = self._categorized_errors.get(category, deque())
        return list(errors)[:limit]
    
    def get_ranking_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent ranking-specific errors."""
        return list(self._ranking_errors)[:limit]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors by category."""
        summary = {
            "total_errors": len(self._errors),
            "by_category": {},
            "ranking_errors": len(self._ranking_errors),
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
    
    def get_ranking_error_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate detailed ranking error report for the specified time window.
        
        Args:
            hours: Look back this many hours
            
        Returns:
            Dictionary with error breakdown, patterns, and affected users
        """
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_ranking_errors = [
            err for err in self._ranking_errors
            if datetime.fromisoformat(err["timestamp"]) > cutoff
        ]
        
        # Aggregate by category
        by_category = defaultdict(list)
        affected_users = set()
        affected_kvk_runs = set()
        low_confidence_count = 0
        
        for err in recent_ranking_errors:
            category = err.get("category", "unknown")
            by_category[category].append(err)
            
            metadata = err.get("metadata", {})
            if metadata.get("user_id"):
                affected_users.add(metadata["user_id"])
            if metadata.get("kvk_run_id"):
                affected_kvk_runs.add(metadata["kvk_run_id"])
            if metadata.get("confidence") and metadata["confidence"] < 0.90:
                low_confidence_count += 1
        
        return {
            "time_window_hours": hours,
            "total_ranking_errors": len(recent_ranking_errors),
            "by_category": {
                cat: {
                    "count": len(errors),
                    "errors": errors[:5]  # Last 5 per category
                }
                for cat, errors in by_category.items()
            },
            "affected_users": len(affected_users),
            "affected_kvk_runs": len(affected_kvk_runs),
            "low_confidence_ocr_errors": low_confidence_count,
            "most_common_error": max(by_category.items(), key=lambda x: len(x[1]))[0] if by_category else None,
        }


_error_engine: Optional[ErrorEngine] = None


def get_error_engine() -> ErrorEngine:
    global _error_engine
    if _error_engine is None:
        _error_engine = ErrorEngine()
    return _error_engine
