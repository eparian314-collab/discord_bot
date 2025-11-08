"""
Storage Engine for Top Heroes Event Rankings.

Handles database operations for storing and retrieving event rankings.
"""

from __future__ import annotations
import sqlite3
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
from pathlib import Path

from discord_bot.core.engines.screenshot_processor import RankingData, StageType, RankingCategory

if TYPE_CHECKING:
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class RankingStorageEngine:
    """Manages storage of Top Heroes event rankings."""
    
    def __init__(
        self,
        db_path: str = "data/event_rankings.db",
        storage: Optional["GameStorageEngine"] = None,
    ):
        self.db_path = db_path
        self.storage = storage
        self._standalone_conn: Optional[sqlite3.Connection] = None
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self.storage:
            return self.storage.conn  # type: ignore[attr-defined]
        # For standalone mode, reuse connection for :memory: databases
        if self.db_path == ":memory:":
            if not self._standalone_conn:
                self._standalone_conn = sqlite3.connect(self.db_path)
                self._standalone_conn.row_factory = sqlite3.Row
            return self._standalone_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _maybe_close(self, conn: sqlite3.Connection) -> None:
        """Close connection when operating in standalone mode."""
        if not self.storage and self.db_path != ":memory:":
            conn.close()
    
    def _ensure_tables(self):
        """Create tables if they don't exist."""
        if self.storage:
            # GameStorageEngine handles schema migrations centrally.
            return
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    guild_id TEXT,
                    guild_tag TEXT,
                    player_name TEXT,
                    
                    event_week TEXT NOT NULL,
                    stage_type TEXT NOT NULL,
                    day_number INTEGER,
                    category TEXT NOT NULL,
                    
                    rank INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    
                    submitted_at TEXT NOT NULL,
                    screenshot_url TEXT,
                    
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(user_id, guild_id, event_week, stage_type, day_number)
                )
            """)
            
            # Index for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_user 
                ON event_rankings(user_id, guild_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_guild_stage 
                ON event_rankings(guild_id, stage_type, day_number)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_guild_tag 
                ON event_rankings(guild_tag)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rankings_event_week 
                ON event_rankings(event_week, guild_id)
            """)
            
            # Event submissions table for tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    guild_id TEXT,
                    submitted_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    ranking_id INTEGER,
                    
                    FOREIGN KEY(ranking_id) REFERENCES event_rankings(id)
                )
            """)
            
            # OCR corrections table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ocr_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ranking_id INTEGER,
                    user_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    image_url TEXT,
                    initial_ocr_text TEXT,
                    failure_category TEXT, -- New field for classification
                    initial_rank INTEGER,
                    initial_score INTEGER,
                    corrected_rank INTEGER,
                    corrected_score INTEGER,
                    ai_analysis TEXT,
                    FOREIGN KEY(ranking_id) REFERENCES event_rankings(id)
                )
            """)
            
            conn.commit()
            self._ensure_event_ranking_columns(conn)
        finally:
            self._maybe_close(conn)
    
    def _ensure_event_ranking_columns(self, conn: sqlite3.Connection) -> None:
        """Ensure new KVK-related columns exist when running standalone."""
        cursor = conn.execute("PRAGMA table_info(event_rankings)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "kvk_run_id" not in columns:
            conn.execute("ALTER TABLE event_rankings ADD COLUMN kvk_run_id INTEGER")
        if "is_test_run" not in columns:
            conn.execute("ALTER TABLE event_rankings ADD COLUMN is_test_run INTEGER DEFAULT 0")
    
    def save_ranking(self, ranking: RankingData) -> int:
        """
        Save ranking data to database.
        
        Returns:
            ID of saved ranking
        """
        if self.storage:
            return self.storage.save_event_ranking(ranking)  # type: ignore[attr-defined]
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO event_rankings 
                (user_id, username, guild_id, guild_tag, player_name, event_week, 
                 stage_type, day_number, category, rank, score, submitted_at, screenshot_url,
                 kvk_run_id, is_test_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ranking.user_id,
                ranking.username,
                ranking.guild_id,
                ranking.guild_tag,
                ranking.player_name,
                ranking.event_week,
                ranking.stage_type.value,
                ranking.day_number,
                ranking.category.value,
                ranking.rank,
                ranking.score,
                ranking.submitted_at.isoformat(),
                ranking.screenshot_url,
                ranking.kvk_run_id,
                1 if ranking.is_test_run else 0
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            self._maybe_close(conn)
    
    def check_duplicate_submission(
        self,
        user_id: str,
        guild_id: str,
        event_week: str,
        stage_type: StageType,
        day_number: int,
        kvk_run_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user already submitted for this event week/stage/day.
        
        Returns:
            Existing ranking dict if duplicate, None if no duplicate
        """
        if self.storage:
            return self.storage.check_duplicate_event_submission(
                user_id, guild_id, event_week, stage_type, day_number, kvk_run_id  # type: ignore[attr-defined]
            )
        conn = self._get_connection()
        try:
            if kvk_run_id is not None:
                cursor = conn.execute("""
                    SELECT * FROM event_rankings
                    WHERE user_id = ? AND guild_id = ? AND kvk_run_id = ? 
                      AND stage_type = ? AND day_number = ?
                    LIMIT 1
                """, (user_id, guild_id, kvk_run_id, stage_type.value, day_number))
            else:
                cursor = conn.execute("""
                    SELECT * FROM event_rankings
                    WHERE user_id = ? AND guild_id = ? AND event_week = ? 
                    AND stage_type = ? AND day_number = ?
                    LIMIT 1
                """, (user_id, guild_id, event_week, stage_type.value, day_number))
            
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self._maybe_close(conn)
    
    def update_ranking(
        self,
        ranking_id: int,
        rank: int,
        score: int,
        screenshot_url: Optional[str] = None
    ) -> bool:
        """
        Update an existing ranking entry.
        
        Returns:
            True if updated, False if not found
        """
        if self.storage:
            return self.storage.update_event_ranking(  # type: ignore[attr-defined]
                ranking_id,
                rank,
                score,
                screenshot_url,
            )
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                UPDATE event_rankings
                SET rank = ?, score = ?, screenshot_url = ?, submitted_at = ?
                WHERE id = ?
            """, (rank, score, screenshot_url, datetime.utcnow().isoformat(), ranking_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._maybe_close(conn)
    
    def get_user_rankings(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent rankings for a user."""
        if self.storage:
            return self.storage.get_user_event_rankings(  # type: ignore[attr-defined]
                user_id, guild_id=guild_id, limit=limit
            )
        conn = self._get_connection()
        try:
            query = """
                SELECT * FROM event_rankings
                WHERE user_id = ?
            """
            params = [user_id]
            
            if guild_id:
                query += " AND guild_id = ?"
                params.append(guild_id)
            
            query += " ORDER BY submitted_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self._maybe_close(conn)
    
    def get_guild_leaderboard(
        self,
        guild_id: str,
        event_week: Optional[str] = None,
        stage_type: Optional[StageType] = None,
        day_number: Optional[int] = None,
        category: Optional[RankingCategory] = None,
        guild_tag: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get guild leaderboard.
        
        Shows best ranking for each user based on filters.
        
        Args:
            guild_id: Discord guild ID
            event_week: Filter by event week (YYYY-WW format)
            stage_type: Filter by stage (Prep/War)
            day_number: Filter by day (1-5)
            category: Filter by category (Construction/Research/etc)
            guild_tag: Filter by in-game guild tag (e.g., "TAO")
            limit: Max results to return
        """
        if self.storage:
            return self.storage.get_guild_event_leaderboard(  # type: ignore[attr-defined]
                guild_id,
                event_week=event_week,
                stage_type=stage_type,
                day_number=day_number,
                category=category,
                guild_tag=guild_tag,
                limit=limit,
            )
        conn = self._get_connection()
        try:
            query = """
                SELECT 
                    user_id,
                    username,
                    guild_tag,
                    player_name,
                    event_week,
                    MIN(rank) as best_rank,
                    MAX(score) as highest_score,
                    stage_type,
                    day_number,
                    category,
                    MAX(submitted_at) as last_submission
                FROM event_rankings
                WHERE guild_id = ?
            """
            params = [guild_id]
            
            if event_week:
                query += " AND event_week = ?"
                params.append(event_week)
            
            if stage_type:
                query += " AND stage_type = ?"
                params.append(stage_type.value)
            
            if day_number is not None:
                query += " AND day_number = ?"
                params.append(day_number)
            
            if category:
                query += " AND category = ?"
                params.append(category.value)
            
            if guild_tag:
                query += " AND guild_tag = ?"
                params.append(guild_tag)
            
            query += """
                GROUP BY user_id
                ORDER BY best_rank ASC, highest_score DESC
                LIMIT ?
            """
            params.append(limit)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self._maybe_close(conn)
    
    def get_current_event_week(self) -> str:
        """Get current event week in YYYY-WW format."""
        if self.storage:
            return self.storage.get_current_event_week()  # type: ignore[attr-defined]
        from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
        processor = ScreenshotProcessor()
        return processor._get_current_event_week()
    
    def delete_old_event_weeks(self, weeks_to_keep: int = 4) -> int:
        """
        Delete event weeks older than specified weeks.
        
        Args:
            weeks_to_keep: Number of recent weeks to keep (default 4 = 1 month)
            
        Returns:
            Number of rankings deleted
        """
        if self.storage:
            return self.storage.prune_event_weeks(weeks_to_keep)  # type: ignore[attr-defined]
        conn = self._get_connection()
        try:
            # Get all unique event weeks
            cursor = conn.execute("""
                SELECT DISTINCT event_week 
                FROM event_rankings 
                ORDER BY event_week DESC
            """)
            all_weeks = [row['event_week'] for row in cursor.fetchall()]
            
            if len(all_weeks) <= weeks_to_keep:
                return 0  # Nothing to delete
            
            # Delete old weeks
            weeks_to_delete = all_weeks[weeks_to_keep:]
            placeholders = ','.join(['?'] * len(weeks_to_delete))
            
            cursor = conn.execute(f"""
                DELETE FROM event_rankings
                WHERE event_week IN ({placeholders})
            """, weeks_to_delete)
            
            conn.commit()
            return cursor.rowcount
        finally:
            self._maybe_close(conn)
    
    def get_ranking_history(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get ranking history for a user over time."""
        if self.storage:
            return self.storage.get_event_ranking_history(  # type: ignore[attr-defined]
                user_id, guild_id=guild_id, days=days
            )
        conn = self._get_connection()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            query = """
                SELECT * FROM event_rankings
                WHERE user_id = ? AND submitted_at >= ?
            """
            params = [user_id, cutoff.isoformat()]
            
            if guild_id:
                query += " AND guild_id = ?"
                params.append(guild_id)
            
            query += " ORDER BY submitted_at ASC"
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self._maybe_close(conn)
    
    def log_submission(
        self,
        user_id: str,
        guild_id: Optional[str],
        status: str,
        error_message: Optional[str] = None,
        ranking_id: Optional[int] = None
    ):
        """Log a submission attempt."""
        if self.storage:
            self.storage.log_event_submission(  # type: ignore[attr-defined]
                user_id,
                guild_id,
                status,
                error_message=error_message,
                ranking_id=ranking_id,
            )
            return
        conn = self._get_connection()
        try:
            params = (
                user_id,
                guild_id,
                datetime.utcnow().isoformat(),
                status,
                ranking_id,
                error_message
            )
            conn.execute("""
                INSERT INTO event_submissions (user_id, guild_id, submitted_at, status, ranking_id, error_message) VALUES (?, ?, ?, ?, ?, ?)
            """, params)
            conn.commit()
        finally:
            self._maybe_close(conn)
    
    def save_ocr_correction(
        self,
        ranking_id: int,
        user_id: str,
        image_url: str,
        initial_text: str,
        failure_category: str,
        initial_rank: Optional[int],
        initial_score: Optional[int],
        corrected_rank: int,
        corrected_score: int,
        ai_analysis: Optional[str] = None,
    ):
        """Save a record of an OCR correction."""
        params = (
            ranking_id,
            user_id,
            datetime.now(timezone.utc).isoformat(),
            image_url,
            initial_text,
            failure_category,
            initial_rank,
            initial_score,
            corrected_rank,
            corrected_score,
            ai_analysis,
        )
        if self.storage:
            self.storage.execute_query(
                """
                INSERT INTO ocr_corrections (
                    ranking_id, user_id, submitted_at, image_url, initial_ocr_text,
                    failure_category, initial_rank, initial_score, corrected_rank, corrected_score, ai_analysis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        else:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO ocr_corrections (
                        ranking_id, user_id, submitted_at, image_url, initial_ocr_text,
                        failure_category, initial_rank, initial_score, corrected_rank, corrected_score, ai_analysis
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
                conn.commit()
            finally:
                self._maybe_close(conn)

    def get_recent_corrections(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch recent OCR corrections to use as few-shot examples."""
        query = "SELECT * FROM ocr_corrections ORDER BY submitted_at DESC LIMIT ?"
        rows = self.storage.fetch_all(query, (limit,))
        return [dict(row) for row in rows]

    def get_total_submission_count(self, guild_id: Optional[str] = None) -> int:
        """
        Get the total number of submissions logged.
        
        Args:
            guild_id: If provided, count is scoped to this guild.
            
        Returns:
            Total count of submissions.
        """
        conn = self._get_connection()
        try:
            if guild_id:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM event_submissions WHERE guild_id = ?",
                    (guild_id,)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM event_submissions")
            
            count = cursor.fetchone()[0]
            return count or 0
        finally:
            self._maybe_close(conn)
    
    def get_ocr_correction_stats(self, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics on OCR corrections.
        
        Args:
            guild_id: If provided, scope stats to this guild.
            
        Returns:
            Dictionary with total corrections and breakdown by category
        """
        if self.storage:
            total_corrections = self.storage.fetch_one("SELECT COUNT(*) FROM ocr_corrections")[0]
            category_query = "SELECT failure_category, COUNT(*) FROM ocr_corrections GROUP BY failure_category"
            category_rows = self.storage.fetch_all(category_query)
            category_stats = {row['failure_category']: row['COUNT(*)'] for row in category_rows}
        else:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM ocr_corrections")
                total_corrections = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT failure_category, COUNT(*) as count FROM ocr_corrections GROUP BY failure_category")
                category_rows = cursor.fetchall()
                category_stats = {row['failure_category']: row['count'] for row in category_rows}
            finally:
                self._maybe_close(conn)

        return {
            "total_corrections": total_corrections,
            "failure_categories": category_stats
        }

    def get_submission_stats(self, guild_id: str) -> Dict[str, int]:
        """Get submission statistics for a guild."""
        if self.storage:
            return self.storage.get_event_submission_stats(  # type: ignore[attr-defined]
                guild_id=guild_id
            )
        conn = self._get_connection()
        try:
            query = """
                SELECT 
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    COUNT(DISTINCT user_id) as unique_users
                FROM event_submissions
                WHERE guild_id = ?
            """
            params = [guild_id]
            
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else {}
        finally:
            self._maybe_close(conn)
    
    def delete_old_rankings(self, days: int = 30) -> int:
        """Delete rankings older than specified days."""
        if self.storage:
            return self.storage.delete_old_event_rankings(days)  # type: ignore[attr-defined]
        conn = self._get_connection()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            cursor = conn.execute("""
                DELETE FROM event_rankings
                WHERE submitted_at < ?
            """, (cutoff.isoformat(),))
            conn.commit()
            return cursor.rowcount
        finally:
            self._maybe_close(conn)
