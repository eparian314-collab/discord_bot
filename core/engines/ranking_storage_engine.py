"""
Storage Engine for Top Heroes Event Rankings.

Handles database operations for storing and retrieving event rankings.
"""

from __future__ import annotations
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from discord_bot.core.engines.screenshot_processor import RankingData, StageType, RankingCategory


class RankingStorageEngine:
    """Manages storage of Top Heroes event rankings."""
    
    def __init__(self, db_path: str = "event_rankings.db"):
        self.db_path = db_path
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_tables(self):
        """Create tables if they don't exist."""
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
            
            conn.commit()
        finally:
            conn.close()
    
    def save_ranking(self, ranking: RankingData) -> int:
        """
        Save ranking data to database.
        
        Returns:
            ID of saved ranking
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO event_rankings 
                (user_id, username, guild_id, guild_tag, player_name, event_week, 
                 stage_type, day_number, category, rank, score, submitted_at, screenshot_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ranking.screenshot_url
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def check_duplicate_submission(
        self,
        user_id: str,
        guild_id: str,
        event_week: str,
        stage_type: StageType,
        day_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user already submitted for this event week/stage/day.
        
        Returns:
            Existing ranking dict if duplicate, None if no duplicate
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM event_rankings
                WHERE user_id = ? AND guild_id = ? AND event_week = ? 
                AND stage_type = ? AND day_number = ?
                LIMIT 1
            """, (user_id, guild_id, event_week, stage_type.value, day_number))
            
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
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
            conn.close()
    
    def get_user_rankings(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent rankings for a user."""
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
            conn.close()
    
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
            
            if day_number:
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
            conn.close()
    
    def get_current_event_week(self) -> str:
        """Get current event week in YYYY-WW format."""
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
            conn.close()
    
    def get_ranking_history(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get ranking history for a user over time."""
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
            conn.close()
    
    def log_submission(
        self,
        user_id: str,
        guild_id: Optional[str],
        status: str,
        error_message: Optional[str] = None,
        ranking_id: Optional[int] = None
    ):
        """Log a submission attempt."""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO event_submissions
                (user_id, guild_id, submitted_at, status, error_message, ranking_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                guild_id,
                datetime.utcnow().isoformat(),
                status,
                error_message,
                ranking_id
            ))
            conn.commit()
        finally:
            conn.close()
    
    def get_submission_stats(
        self,
        guild_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get submission statistics."""
        conn = self._get_connection()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            query = """
                SELECT 
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    COUNT(DISTINCT user_id) as unique_users
                FROM event_submissions
                WHERE submitted_at >= ?
            """
            params = [cutoff.isoformat()]
            
            if guild_id:
                query += " AND guild_id = ?"
                params.append(guild_id)
            
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()
    
    def delete_old_rankings(self, days: int = 30) -> int:
        """Delete rankings older than specified days."""
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
            conn.close()
