"""
KVK Tracker Engine

Orchestrates KVK and GAR event tracking, combining timeline logic with database storage.
Provides a compatibility bridge to the legacy `KVKTracker` so existing ranking
commands keep working while the new event system comes online.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, cast

from .event_timeline import EventTimeline, EventPhase
from .kvk_storage_engine import KVKStorageEngine
from .kvk_tracker import KVKRun, KVKTracker

if TYPE_CHECKING:  # pragma: no cover - typing support only
    from discord.ext import commands
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class KVKTrackerEngine:
    """Central engine for tracking KVK events and legacy ranking runs."""

    def __init__(
        self,
        *,
        storage_engine: Optional[KVKStorageEngine] = None,
        tracker: Optional[KVKTracker] = None,
        game_storage: Optional["GameStorageEngine"] = None,
    ) -> None:
        self.storage = storage_engine or KVKStorageEngine()
        self.active_event: Optional[Dict[str, Any]] = None
        self.timeline: Optional[EventTimeline] = None

        self._bot: Optional["commands.Bot"] = None
        self._legacy_storage: Optional["GameStorageEngine"] = game_storage
        self._legacy_tracker: Optional[KVKTracker] = None
        self.tracker: Optional[KVKTracker] = None  # Public handle for diagnostics

        if tracker is not None:
            self.attach_tracker(tracker)
        elif game_storage is not None:
            self.attach_tracker(KVKTracker(storage=game_storage))

    # ------------------------------------------------------------------ #
    # Wiring helpers
    # ------------------------------------------------------------------ #
    def attach_tracker(self, tracker: KVKTracker) -> None:
        """Attach a legacy KVKTracker instance for ranking compatibility."""
        self._legacy_tracker = tracker
        self.tracker = tracker
        if hasattr(tracker, "storage"):
            self._legacy_storage = getattr(tracker, "storage")
        if self._bot:
            tracker.set_bot(self._bot)

    def set_bot(self, bot: "commands.Bot") -> None:
        """Store bot reference and forward to the legacy tracker."""
        self._bot = bot
        tracker = self._ensure_tracker()
        tracker.set_bot(bot)

    def _ensure_tracker(self) -> KVKTracker:
        """Lazily create the legacy tracker if missing."""
        if self._legacy_tracker is None:
            if self._legacy_storage is None:
                # Local import to avoid heavy dependency at module import time.
                from discord_bot.games.storage.game_storage_engine import GameStorageEngine

                self._legacy_storage = GameStorageEngine(db_path="data/game_data.db")
            self.attach_tracker(KVKTracker(storage=self._legacy_storage))
        return cast(KVKTracker, self._legacy_tracker)

    # ------------------------------------------------------------------ #
    # Lifecycle hooks
    # ------------------------------------------------------------------ #
    async def on_startup(self) -> None:
        """
        Loads the current active event and initializes the timeline.
        Also ensures the legacy tracker is ready for command usage.
        """
        self.active_event = self.storage.get_active_event()
        if self.active_event:
            start_date = datetime.fromisoformat(self.active_event["start_date"])
            self.timeline = EventTimeline(event_start_date=start_date)
            self.storage.log_audit(
                "system",
                "kvk_tracker_startup",
                {"event_id": self.active_event["id"]},
            )
        tracker = self._ensure_tracker()
        if self._bot:
            tracker.set_bot(self._bot)

    async def on_ready(self) -> None:
        """Propagate ready event to the legacy tracker for timer rescheduling."""
        tracker = self._ensure_tracker()
        if hasattr(tracker, "on_ready"):
            await tracker.on_ready()

    # ------------------------------------------------------------------ #
    # New event API
    # ------------------------------------------------------------------ #
    def get_current_event(self) -> Optional[Dict[str, Any]]:
        """Returns the currently active event from memory."""
        return self.active_event

    def get_event_phase(self) -> EventPhase:
        """Determines the current phase of the active event."""
        if not self.timeline:
            return EventPhase.UNKNOWN
        return self.timeline.get_current_phase()

    def get_event_day(self) -> Optional[int]:
        """Determines the current day number of the active event."""
        if not self.timeline:
            return None
        return self.timeline.get_current_day_number()

    # ------------------------------------------------------------------ #
    # Legacy ranking compatibility layer
    # ------------------------------------------------------------------ #
    async def ensure_run(
        self,
        *,
        guild_id: int,
        title: str,
        initiated_by: Optional[int],
        channel_id: Optional[int],
        is_test: bool = False,
        event_id: Optional[str] = None,
        duration_minutes: Optional[int] = None,
    ) -> Tuple[KVKRun, bool]:
        tracker = self._ensure_tracker()
        return await tracker.ensure_run(
            guild_id=guild_id,
            title=title,
            initiated_by=initiated_by,
            channel_id=channel_id,
            is_test=is_test,
            event_id=event_id,
            duration_minutes=duration_minutes,
        )

    async def close_run(self, run_id: int, *, reason: str = "timer") -> Optional[KVKRun]:
        tracker = self._ensure_tracker()
        return await tracker.close_run(run_id, reason=reason)

    def get_active_run(self, guild_id: int, *, include_tests: bool = True) -> Optional[KVKRun]:
        tracker = self._ensure_tracker()
        return tracker.get_active_run(guild_id, include_tests=include_tests)

    def list_runs(self, guild_id: int, *, include_tests: bool = False) -> List[KVKRun]:
        tracker = self._ensure_tracker()
        return tracker.list_runs(guild_id, include_tests=include_tests)

    def get_run_by_number(self, guild_id: int, run_number: int) -> Optional[KVKRun]:
        tracker = self._ensure_tracker()
        return tracker.get_run_by_number(guild_id, run_number)

    def record_submission(
        self,
        *,
        kvk_run_id: int,
        ranking_id: int,
        user_id: int,
        day_number: int,
        stage_type: str,
        is_test: bool,
    ) -> None:
        tracker = self._ensure_tracker()
        tracker.record_submission(
            kvk_run_id=kvk_run_id,
            ranking_id=ranking_id,
            user_id=user_id,
            day_number=day_number,
            stage_type=stage_type,
            is_test=is_test,
        )

    def get_submission(
        self,
        *,
        kvk_run_id: int,
        user_id: int,
        day_number: int,
        stage_type: str,
    ) -> Optional[Dict[str, Any]]:
        tracker = self._ensure_tracker()
        return tracker.get_submission(
            kvk_run_id=kvk_run_id,
            user_id=user_id,
            day_number=day_number,
            stage_type=stage_type,
        )

    def fetch_user_entries(
        self,
        *,
        run_id: int,
        user_id: int,
        day_number: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        tracker = self._ensure_tracker()
        return tracker.fetch_user_entries(
            run_id=run_id,
            user_id=user_id,
            day_number=day_number,
        )

    def fetch_leaderboard(
        self,
        *,
        run_id: int,
        day_number: Optional[int] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        tracker = self._ensure_tracker()
        return tracker.fetch_leaderboard(
            run_id=run_id,
            day_number=day_number,
            limit=limit,
        )
