"""
KVK Storage Engine

Manages all database interactions for the KVK and GAR tracking system.
"""
from __future__ import annotations
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

class KVKStorageEngine:
    """Manages storage for KVK and GAR events."""

    def __init__(self, db_path: str = "data/kvk_events.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self.conn = self._get_connection()
        self._create_tables()

    def _ensure_db_directory(self):
        """Ensure the data directory exists."""
        Path(self.db_path).parent.mkdir(exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Create all necessary tables for the tracking system."""
        cursor = self.conn.cursor()
        
        # Event metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                event_type TEXT NOT NULL, -- 'kvk' or 'gar'
                is_active INTEGER DEFAULT 0
            )
        """)

        # Player information
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_user_id TEXT UNIQUE NOT NULL,
                in_game_name TEXT,
                guild_tag TEXT,
                last_seen TEXT
            )
        """)

        # Raw submissions from users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                category TEXT NOT NULL,
                rank INTEGER,
                score INTEGER,
                screenshot_url TEXT,
                submitted_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected
                FOREIGN KEY(event_id) REFERENCES events(id),
                FOREIGN KEY(player_id) REFERENCES players(id)
            )
        """)

        # OCR processing results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                raw_text TEXT,
                confidence REAL,
                parsed_data_json TEXT,
                processed_at TEXT NOT NULL,
                FOREIGN KEY(submission_id) REFERENCES submissions(id)
            )
        """)

        # User-provided corrections
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                user_id TEXT NOT NULL, -- Discord user ID of corrector
                corrected_data_json TEXT NOT NULL,
                reason TEXT, -- e.g., 'ocr_error', 'user_mistake'
                analyzed_at TEXT NOT NULL,
                FOREIGN KEY(submission_id) REFERENCES submissions(id)
            )
        """)

        # Aggregated daily scores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                total_score INTEGER NOT NULL,
                rank INTEGER,
                updated_at TEXT NOT NULL,
                UNIQUE(player_id, event_id, day_number),
                FOREIGN KEY(player_id) REFERENCES players(id),
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)

        # Audit log for system actions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracker_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL, -- e.g., 'system', 'user:12345'
                action TEXT NOT NULL, -- e.g., 'submission_approved', 'ocr_failed'
                details_json TEXT
            )
        """)

        self.conn.commit()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def get_active_event(self) -> Optional[Dict[str, Any]]:
        """Fetches the currently active event."""
        cursor = self.conn.execute("SELECT * FROM events WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    # Placeholder for future methods
    def log_audit(self, actor: str, action: str, details: Optional[Dict] = None):
        """Logs an action to the audit table."""
        import json
        details_json = json.dumps(details) if details else None
        self.conn.execute("""
            INSERT INTO tracker_audit (timestamp, actor, action, details_json)
            VALUES (?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), actor, action, details_json))
        self.conn.commit()

if __name__ == '__main__':
    # Example of creating and initializing the database
    engine = KVKStorageEngine()
    print("Database tables created successfully in 'data/kvk_events.db'")
    engine.log_audit('system', 'db_initialized', {'message': 'Database created and tables ensured.'})
    engine.close()
