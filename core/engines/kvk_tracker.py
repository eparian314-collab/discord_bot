"""
KVK Tracker Engine

Coordinates Kingdom vs Kingdom (KVK) event windows, ensuring that every run
stays isolated, timed, and queryable for ranking analytics.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing support only
    from discord.ext import commands
    from discord import TextChannel
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine

logger = logging.getLogger("hippo_bot.kvk_tracker")


@dataclass(slots=True)
class KVKRun:
    """Lightweight representation of a tracked KVK window."""

    id: int
    guild_id: int
    title: str
    run_number: Optional[int]
    is_test: bool
    started_at: datetime
    ends_at: datetime
    closed_at: Optional[datetime]
    status: str
    channel_id: Optional[int]
    initiated_by: Optional[int]
    event_id: Optional[str]

    @property
    def is_active(self) -> bool:
        return self.status == "active" and (self.closed_at is None) and self.ends_at > datetime.now(timezone.utc)

    @property
    def remaining(self) -> timedelta:
        return max(self.ends_at - datetime.now(timezone.utc), timedelta())


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class KVKTracker:
    """Manage KVK run lifecycle, submissions, and analytics queries."""

    def __init__(self, storage: GameStorageEngine, *, reminder_days: int = 14) -> None:
        self.storage = storage
        self.reminder_days = reminder_days
        self.bot: Optional[commands.Bot] = None
        self._closure_tasks: Dict[int, asyncio.Task] = {}

    # ------------------------------------------------------------------ #
    # Bot wiring & lifecycle helpers
    # ------------------------------------------------------------------ #
    def set_bot(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def on_ready(self) -> None:
        """Reschedule timers for any active runs on startup."""
        active_runs = self._fetch_active_runs()
        for run in active_runs:
            self._schedule_closure(run)

    # ------------------------------------------------------------------ #
    # Run management
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
        """
        Ensure there is an active run for the guild. Returns (run, created_flag).
        If a compatible run already exists, it is returned with created_flag=False.
        """
        now = datetime.now(timezone.utc)
        guild_key = str(guild_id)
        if is_test:
            run = self._fetch_active_run(guild_key, include_tests=True, is_test=True)
        else:
            run = self._fetch_active_run(guild_key, include_tests=False, is_test=False)
        if run and run.is_active:
            return run, False

        run_number = None
        if not is_test:
            query = """
                SELECT MAX(run_number) FROM kvk_runs
                WHERE guild_id = ? AND is_test = 0
            """
            cursor = self.storage.conn.execute(query, (guild_key,))
            max_num = cursor.fetchone()[0]
            run_number = (max_num or 0) + 1

        if duration_minutes is not None and duration_minutes > 0:
            ends_at = now + timedelta(minutes=duration_minutes)
        else:
            ends_at = now + timedelta(days=self.reminder_days)
        insert = """
            INSERT INTO kvk_runs (
                guild_id, title, initiated_by, event_id, channel_id,
                run_number, is_test, started_at, ends_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """
        with self.storage.conn:
            cursor = self.storage.conn.execute(
                insert,
                (
                    guild_key,
                    title,
                    str(initiated_by) if initiated_by else None,
                    event_id,
                    channel_id,
                    run_number,
                    1 if is_test else 0,
                    now.isoformat(),
                    ends_at.isoformat(),
                ),
            )
            run_id = cursor.lastrowid

        run = self._fetch_run_by_id(run_id)
        if not run:
            raise RuntimeError("Failed to fetch KVK run after creation")

        self._schedule_closure(run)
        await self._announce_run_start(run, channel_id)
        return run, True

    async def close_run(self, run_id: int, *, reason: str = "timer") -> Optional[KVKRun]:
        run = self._fetch_run_by_id(run_id)
        if not run or run.status != "active":
            return run

        closed_at = datetime.now(timezone.utc)
        with self.storage.conn:
            self.storage.conn.execute(
                """
                UPDATE kvk_runs
                   SET status = 'closed',
                       closed_at = ?
                 WHERE id = ?
                """,
                (closed_at.isoformat(), run_id),
            )

        if task := self._closure_tasks.pop(run_id, None):
            task.cancel()

        run = self._fetch_run_by_id(run_id)
        await self._announce_run_closed(run, reason)
        return run

    # ------------------------------------------------------------------ #
    # Submission tracking
    # ------------------------------------------------------------------ #
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
        """Link a ranking entry to a specific KVK run/day. Uses upsert semantics."""
        run = self._fetch_run_by_id(kvk_run_id)
        is_test_submission = run.is_test if run else False

        with self.storage.conn:
            self.storage.conn.execute(
                """
                INSERT INTO kvk_submissions (
                    kvk_run_id, ranking_id, user_id, day_number,
                    stage_type, submitted_at, is_test
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(kvk_run_id, user_id, day_number, stage_type)
                DO UPDATE SET
                    ranking_id = excluded.ranking_id,
                    submitted_at = excluded.submitted_at,
                    is_test = excluded.is_test
                """,
                (
                    kvk_run_id,
                    ranking_id,
                    str(user_id),
                    day_number,
                    stage_type,
                    datetime.now(timezone.utc).isoformat(),
                    1 if is_test_submission else 0,
                ),
            )

    def get_submission(
        self,
        *,
        kvk_run_id: int,
        user_id: int,
        day_number: int,
        stage_type: str,
    ) -> Optional[Dict[str, Any]]:
        cursor = self.storage.conn.execute(
            """
            SELECT * FROM kvk_submissions
             WHERE kvk_run_id = ?
               AND user_id = ?
               AND day_number = ?
               AND stage_type = ?
            """,
            (kvk_run_id, str(user_id), day_number, stage_type),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ #
    # Analytics helpers
    # ------------------------------------------------------------------ #
    def get_run_by_number(self, guild_id: int, run_number: int) -> Optional[KVKRun]:
        cursor = self.storage.conn.execute(
            """
            SELECT * FROM kvk_runs
             WHERE guild_id = ? AND run_number = ? AND is_test = 0
            """,
            (str(guild_id), run_number),
        )
        row = cursor.fetchone()
        return self._row_to_run(row) if row else None

    def get_active_run(self, guild_id: int, *, include_tests: bool = True) -> Optional[KVKRun]:
        return self._fetch_active_run(str(guild_id), include_tests=include_tests)

    def list_runs(self, guild_id: int, *, include_tests: bool = False) -> List[KVKRun]:
        query = "SELECT * FROM kvk_runs WHERE guild_id = ?"
        params: List[Any] = [str(guild_id)]
        if not include_tests:
            query += " AND is_test = 0"
        query += " ORDER BY started_at DESC"
        cursor = self.storage.conn.execute(query, params)
        return [self._row_to_run(row) for row in cursor.fetchall()]

    def fetch_user_entries(
        self,
        *,
        run_id: int,
        user_id: int,
        day_number: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [run_id, str(user_id)]
        query = """
            SELECT er.*, ks.day_number AS kvk_day
              FROM event_rankings er
              JOIN kvk_submissions ks ON ks.ranking_id = er.id
             WHERE ks.kvk_run_id = ?
               AND ks.user_id = ?
        """
        if day_number is not None:
            query += " AND ks.day_number = ?"
            params.append(day_number)
        query += " ORDER BY ks.day_number ASC"
        cursor = self.storage.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def fetch_leaderboard(
        self,
        *,
        run_id: int,
        day_number: Optional[int] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [run_id]
        query = """
            SELECT er.*, ks.day_number AS kvk_day
              FROM event_rankings er
              JOIN kvk_submissions ks ON ks.ranking_id = er.id
             WHERE ks.kvk_run_id = ?
        """
        if day_number is not None:
            query += " AND ks.day_number = ?"
            params.append(day_number)
        query += """
             ORDER BY er.score DESC
             LIMIT ?
        """
        params.append(limit)
        cursor = self.storage.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _fetch_run_by_id(self, run_id: int) -> Optional[KVKRun]:
        cursor = self.storage.conn.execute(
            "SELECT * FROM kvk_runs WHERE id = ?", (run_id,)
        )
        row = cursor.fetchone()
        return self._row_to_run(row) if row else None

    def _fetch_active_run(
        self,
        guild_id: str,
        *,
        include_tests: bool,
        is_test: Optional[bool] = None,
    ) -> Optional[KVKRun]:
        query = """
            SELECT * FROM kvk_runs
             WHERE guild_id = ?
               AND status = 'active'
        """
        params: List[Any] = [guild_id]
        if is_test is True:
            query += " AND is_test = 1"
        elif is_test is False:
            query += " AND is_test = 0"
        query += " ORDER BY started_at DESC LIMIT 1"
        cursor = self.storage.conn.execute(query, params)
        row = cursor.fetchone()
        run = self._row_to_run(row) if row else None
        if run and not include_tests and run.is_test:
            return None
        return run

    def _fetch_active_runs(self) -> List[KVKRun]:
        cursor = self.storage.conn.execute(
            """
            SELECT * FROM kvk_runs
             WHERE status = 'active'
            """
        )
        return [self._row_to_run(row) for row in cursor.fetchall()]

    def get_run_by_event_id(self, event_id: str, *, include_closed: bool = False) -> Optional[KVKRun]:
        query = """
            SELECT * FROM kvk_runs
             WHERE event_id = ?
        """
        params: List[Any] = [event_id]
        if not include_closed:
            query += " AND status = 'active'"
        query += " ORDER BY started_at DESC LIMIT 1"
        cursor = self.storage.conn.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None
        run = self._row_to_run(row)
        if run and run.is_test and not include_closed and run.status != "active":
            return None
        return run

    async def close_run_for_event(self, event_id: str, *, reason: str = "event deleted") -> Optional[KVKRun]:
        run = self.get_run_by_event_id(event_id, include_closed=False)
        if not run:
            return None
        return await self.close_run(run.id, reason=reason)

    def _row_to_run(self, row: Any) -> Optional[KVKRun]:
        if row is None:
            return None
        started_at = _parse_dt(row["started_at"])
        ends_at = _parse_dt(row["ends_at"])
        closed_at = _parse_dt(row["closed_at"]) if row["closed_at"] else None
        return KVKRun(
            id=row["id"],
            guild_id=int(row["guild_id"]),
            title=row["title"],
            run_number=row["run_number"],
            is_test=bool(row["is_test"]),
            started_at=started_at,
            ends_at=ends_at,
            closed_at=closed_at,
            status=row["status"],
            channel_id=row["channel_id"],
            initiated_by=int(row["initiated_by"]) if row["initiated_by"] else None,
            event_id=row["event_id"],
        )

    def _schedule_closure(self, run: KVKRun) -> None:
        if not run.is_active:
            return
        remaining = (run.ends_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            asyncio.create_task(self.close_run(run.id, reason="expired"))
            return

        if run.id in self._closure_tasks:
            self._closure_tasks[run.id].cancel()

        async def _close_later() -> None:
            try:
                await asyncio.sleep(remaining)
                await self.close_run(run.id, reason="timer")
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Failed to close KVK run %s on timer", run.id)

        self._closure_tasks[run.id] = asyncio.create_task(_close_later())

    async def _announce_run_start(self, run: KVKRun, channel_id: Optional[int]) -> None:
        channel = await self._resolve_channel(channel_id)
        if not channel:
            return
        title = "Test KVK" if run.is_test else f"KVK Run #{run.run_number}"
        closing = run.ends_at.strftime("%Y-%m-%d %H:%M UTC")
        await self._safe_send(
            channel,
            (
                f"🔔 **{title} has started!**\n"
                f"You have the next **{self.reminder_days} days** to submit your ranking screenshots.\n"
                f"Collection window closes on **{closing}**."
            ),
        )

    async def _announce_run_closed(self, run: Optional[KVKRun], reason: str) -> None:
        if not run:
            return
        channel = await self._resolve_channel(run.channel_id)
        if not channel:
            return
        title = "Test KVK" if run.is_test else f"KVK Run #{run.run_number}"
        await self._safe_send(
            channel,
            (
                f"⏳ **{title} is now closed.**\n"
                "Admins and helpers may continue to upload corrections, but member submissions are locked."
            ),
        )

    async def _resolve_channel(self, channel_id: Optional[int]) -> Optional["TextChannel"]:
        if not self.bot or not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel:
            return channel  # type: ignore[return-value]
        try:
            return await self.bot.fetch_channel(channel_id)  # type: ignore[return-value]
        except Exception:
            logger.warning("Failed to resolve channel %s for KVK notifications", channel_id)
            return None

    async def _safe_send(self, channel: "TextChannel", content: str) -> None:
        try:
            await channel.send(content)
        except Exception:
            logger.exception("Failed to send KVK notification to %s", channel.id)
