"""
Storage Engine for Top Heroes Event Rankings.

Handles database operations for storing and retrieving event rankings.
"""

from __future__ import annotations
import sqlite3
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime, timedelta
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
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self.storage:
            return self.storage.conn  # type: ignore[attr-defined]
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _maybe_close(self, conn: sqlite3.Connection) -> None:
        """Close connection when operating in standalone mode."""
        if not self.storage:
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
            
            # R8 - Player profile table for identity memory
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_profile (
                    user_id INTEGER PRIMARY KEY,
                    player_name TEXT,
                    guild TEXT
                )
            """)
            
            # R10B - Player event power tracking (separate from scores)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_event_power (
                    user_id TEXT NOT NULL,
                    event_week TEXT NOT NULL,
                    power INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, event_week)
                )
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
            self._ensure_event_ranking_columns(conn)
        finally:
            self._maybe_close(conn)
    
    def _ensure_event_ranking_columns(self, conn: sqlite3.Connection) -> None:
        """Ensure new KVK-related and canonical model columns exist when running standalone."""
        cursor = conn.execute("PRAGMA table_info(event_rankings)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "kvk_run_id" not in columns:
            conn.execute("ALTER TABLE event_rankings ADD COLUMN kvk_run_id INTEGER")
        if "is_test_run" not in columns:
            conn.execute("ALTER TABLE event_rankings ADD COLUMN is_test_run INTEGER DEFAULT 0")
        # Canonical model columns
        if "phase" not in columns:
            conn.execute("ALTER TABLE event_rankings ADD COLUMN phase TEXT")
            # Migrate existing data: stage_type → phase
            conn.execute("""
                UPDATE event_rankings 
                SET phase = CASE 
                    WHEN LOWER(stage_type) LIKE '%prep%' THEN 'prep'
                    WHEN LOWER(stage_type) LIKE '%war%' THEN 'war'
                    WHEN day_number IS NULL OR day_number = 6 THEN 'war'
                    ELSE 'prep'
                END
                WHERE phase IS NULL
            """)
        if "day" not in columns:
            conn.execute("ALTER TABLE event_rankings ADD COLUMN day TEXT")
            # Migrate existing data: day_number → day
            conn.execute("""
                UPDATE event_rankings 
                SET day = CASE 
                    WHEN day_number = -1 THEN 'overall'
                    WHEN day_number BETWEEN 1 AND 5 THEN CAST(day_number AS TEXT)
                    ELSE NULL
                END
                WHERE day IS NULL
            """)
        conn.commit()
    
    # ------------------------------------------------------------
    # (R8) Player Profile Memory
    # ------------------------------------------------------------
    def _get_profile(self, user_id: int):
        """Fetch player profile (guild + player_name) from memory cache."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT player_name, guild FROM player_profile WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            return {"player_name": row[0], "guild": row[1]} if row else None
        finally:
            self._maybe_close(conn)

    def _update_profile(self, user_id: int, player_name: str, guild: str):
        """Update or insert player profile in memory cache."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO player_profile (user_id, player_name, guild)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                player_name = excluded.player_name,
                guild = excluded.guild
                """,
                (user_id, player_name, guild)
            )
            conn.commit()
        finally:
            self._maybe_close(conn)
    
    # ------------------------------------------------------------
    # (R10B) Power Per Event Storage
    # ------------------------------------------------------------
    def set_power(self, user_id: str, event_week: str, power: int) -> None:
        """
        Store or update player's power for a specific event.
        Power is separate from score - represents account strength.
        """
        conn = self._get_connection()
        try:
            from datetime import datetime
            conn.execute("""
                INSERT INTO player_event_power (user_id, event_week, power, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, event_week) DO UPDATE SET 
                    power = excluded.power,
                    updated_at = excluded.updated_at
            """, (user_id, event_week, power, datetime.utcnow().isoformat()))
            conn.commit()
        finally:
            self._maybe_close(conn)
    
    def get_power(self, user_id: str, event_week: str) -> Optional[int]:
        """Get player's stored power for a specific event."""
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT power FROM player_event_power
                WHERE user_id = ? AND event_week = ?
            """, (user_id, event_week)).fetchone()
            return row[0] if row else None
        finally:
            self._maybe_close(conn)
    
    def get_all_powers(self, event_week: str, guild_id: Optional[str] = None) -> Dict[str, int]:
        """
        Get all power values for an event.
        Returns dict mapping user_id -> power.
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT pep.user_id, pep.power
                FROM player_event_power pep
                WHERE pep.event_week = ?
            """
            params = [event_week]
            
            if guild_id is not None:
                # Filter by guild_id via event_rankings
                query = """
                    SELECT DISTINCT pep.user_id, pep.power
                    FROM player_event_power pep
                    JOIN event_rankings er ON pep.user_id = er.user_id AND pep.event_week = er.event_week
                    WHERE pep.event_week = ? AND er.guild_id = ?
                """
                params.append(guild_id)
            
            rows = conn.execute(query, params).fetchall()
            return {row[0]: row[1] for row in rows}
        finally:
            self._maybe_close(conn)
    
    # ------------------------------------------------------------
    # (R9-P4) Event Cycle Boundary Helpers
    # ------------------------------------------------------------
    def _get_last_event_and_score(self, user_id: str, guild_id: str) -> tuple[Optional[str], Optional[int]]:
        """Get user's last event_week and their maximum score from that event."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT event_week, MAX(score) as max_score
                FROM event_rankings
                WHERE user_id = ? AND guild_id = ?
                GROUP BY event_week
                ORDER BY event_week DESC
                LIMIT 1
                """,
                (user_id, guild_id)
            ).fetchone()
            if not row:
                return None, None
            return row[0], row[1]
        finally:
            self._maybe_close(conn)
    
    def _get_existing_entry(
        self,
        user_id: str,
        guild_id: str,
        event_week: str,
        phase: str,
        day: Optional[int | str],
        kvk_run_id: Optional[int] = None
    ) -> Optional[int]:
        """Get existing score for exact (user_id, event_week, phase, day) match."""
        conn = self._get_connection()
        try:
            query = """
                SELECT score FROM event_rankings
                WHERE user_id = ? AND guild_id = ? AND event_week = ? AND phase = ? AND (day IS ? OR day = ?)
            """
            params = [user_id, guild_id, event_week, phase, day, day]
            
            if kvk_run_id is not None:
                query += " AND kvk_run_id = ?"
                params.append(kvk_run_id)
            
            row = conn.execute(query, params).fetchone()
            return row[0] if row else None
        finally:
            self._maybe_close(conn)
    
    def save_or_update_ranking(
        self,
        ranking: RankingData,
        kvk_run_id: Optional[int] = None
    ) -> tuple[int, bool, bool]:
        """
        LOCKED WRITE LOGIC: Save or update ranking with overwrite rules.
        
        Overwrite Rules:
        - Primary Key: (user_id, event_id, phase, day)
        - War submission overwrites previous war submission
        - Prep Day N overwrites only that specific day N
        - Prep Overall overwrites only overall prep
        
        Returns:
            (ranking_id, was_updated, score_changed)
        """
        # ------------------------------------------------------------
        # R9-P4 - Event Cycle Boundary & Duplicate Detection
        # ------------------------------------------------------------
        current_event_week = ranking.event_week
        new_score = ranking.score
        new_phase = ranking.phase
        new_day = ranking.day
        guild_id = ranking.guild_id or "0"
        
        prev_event_week, prev_event_max_score = self._get_last_event_and_score(ranking.user_id, guild_id)
        
        # Case 1: No prior data → accept
        if prev_event_week is None:
            pass
        
        # Case 2: Same event → check duplicate entries
        elif prev_event_week == current_event_week:
            existing_score = self._get_existing_entry(
                ranking.user_id,
                guild_id,
                current_event_week,
                new_phase,
                new_day,
                kvk_run_id
            )
            if existing_score is not None:
                # SAME SCORE? → Duplicate, ignore.
                if existing_score == new_score:
                    raise ValueError("duplicate_submission")  # Cog handles response
        
        # Case 3: Different event cycle
        else:
            # If new score is **significantly lower** -> this is a NEW EVENT START
            if prev_event_max_score and new_score is not None and new_score < (prev_event_max_score * 0.60):
                # Accept as new event, nothing to override
                pass
            else:
                # Likely screenshot from old event → require confirm UI
                raise ValueError("event_cycle_conflict")
        
        # R8 - Player Profile Memory Logic
        user_profile = self._get_profile(int(ranking.user_id))
        
        # R8 - GUILD correction using memory cache
        guild_confidence = getattr(ranking, 'confidence_map', {}).get('guild', 1.0)
        if guild_confidence < 0.95:
            if user_profile and user_profile.get('guild'):
                ranking.guild_tag = user_profile['guild']
        
        # R8 - PLAYER NAME rename suspicion logic
        if user_profile and user_profile.get('player_name'):
            if ranking.player_name != user_profile['player_name']:
                # If OCR is uncertain → keep old name
                name_confidence = getattr(ranking, 'confidence_map', {}).get('player_name', 1.0)
                if name_confidence < 0.98:
                    ranking.player_name = user_profile['player_name']
                else:
                    # OCR is confident → treat as intentional rename
                    # Accept rename and update stored profile
                    self._update_profile(
                        int(ranking.user_id),
                        ranking.player_name,
                        ranking.guild_tag or ""
                    )
        else:
            # First-time profile creation
            self._update_profile(
                int(ranking.user_id),
                ranking.player_name,
                ranking.guild_tag or ""
            )
        
        existing = self.check_duplicate_submission(
            ranking.user_id,
            ranking.guild_id or "0",
            ranking.event_week,
            ranking.phase,
            ranking.day,
            kvk_run_id=kvk_run_id
        )
        
        if existing:
            # Check if score changed
            score_changed = existing.get('score') != ranking.score
            
            if score_changed:
                # UPDATE existing record
                ranking_id = self._update_ranking(existing['id'], ranking)
                return ranking_id, True, True
            else:
                # No change in score
                return existing['id'], False, False
        else:
            # INSERT new record
            ranking_id = self.save_ranking(ranking)
            return ranking_id, False, False
    
    def _update_ranking(self, ranking_id: int, ranking: RankingData) -> int:
        """Update existing ranking record with new data."""
        conn = self._get_connection()
        
        try:
            day_str = str(ranking.day) if ranking.day is not None else None
            stage_type_str = "Prep Stage" if ranking.phase == "prep" else "War Stage"
            day_number = None
            if ranking.phase == "prep":
                if ranking.day == "overall":
                    day_number = -1
                elif isinstance(ranking.day, int):
                    day_number = ranking.day
            
            conn.execute("""
                UPDATE event_rankings 
                SET 
                    username = ?,
                    guild_tag = ?,
                    player_name = ?,
                    phase = ?,
                    day = ?,
                    category = ?,
                    rank = ?,
                    score = ?,
                    submitted_at = ?,
                    screenshot_url = ?,
                    stage_type = ?,
                    day_number = ?
                WHERE id = ?
            """, (
                ranking.username,
                ranking.guild_tag,
                ranking.player_name,
                ranking.phase,
                day_str,
                ranking.category.value,
                ranking.rank,
                ranking.score,
                ranking.submitted_at.isoformat(),
                ranking.screenshot_url,
                stage_type_str,
                day_number,
                ranking_id
            ))
            conn.commit()
            return ranking_id
        finally:
            self._maybe_close(conn)
    
    def save_ranking(self, ranking: RankingData) -> int:
        """
        Save ranking data to database using canonical model.
        
        Canonical Schema:
            phase: "prep" or "war"
            day: "1"-"5", "overall", or NULL
        
        Returns:
            ID of saved ranking
        """
        if self.storage:
            return self.storage.save_event_ranking(ranking)  # type: ignore[attr-defined]
        
        # Ensure canonical columns exist
        conn = self._get_connection()
        self._ensure_event_ranking_columns(conn)
        
        try:
            # Convert day to string for storage (canonical format)
            day_str = str(ranking.day) if ranking.day is not None else None
            
            # Legacy compatibility: compute stage_type and day_number
            stage_type_str = "Prep Stage" if ranking.phase == "prep" else "War Stage"
            day_number = None
            if ranking.phase == "prep":
                if ranking.day == "overall":
                    day_number = -1
                elif isinstance(ranking.day, int):
                    day_number = ranking.day
            
            cursor = conn.execute("""
                INSERT INTO event_rankings 
                (user_id, username, guild_id, guild_tag, player_name, event_week, 
                 phase, day, category, rank, score, submitted_at, screenshot_url,
                 kvk_run_id, is_test_run, stage_type, day_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ranking.user_id,
                ranking.username,
                ranking.guild_id,
                ranking.guild_tag,
                ranking.player_name,
                ranking.event_week,
                ranking.phase,  # Canonical: "prep" or "war"
                day_str,  # Canonical: "1"-"5", "overall", or NULL
                ranking.category.value,
                ranking.rank,
                ranking.score,
                ranking.submitted_at.isoformat(),
                ranking.screenshot_url,
                ranking.kvk_run_id,
                1 if ranking.is_test_run else 0,
                stage_type_str,  # Legacy compatibility
                day_number,  # Legacy compatibility
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            self._maybe_close(conn)
    
    def force_store_submission(
        self,
        ranking: RankingData,
        kvk_run_id: Optional[int] = None
    ) -> tuple[int, bool, bool]:
        """
        Force store submission without cycle validation or duplicate rejection.
        Used when user confirms a cross-cycle submission is intentional.
        
        Returns:
            (ranking_id, was_updated, score_changed)
        """
        # Skip R9-P4 validation, go straight to normal flow
        # Still apply R8 profile memory logic
        user_profile = self._get_profile(int(ranking.user_id))
        
        # R8 - GUILD correction using memory cache
        guild_confidence = getattr(ranking, 'confidence_map', {}).get('guild', 1.0)
        if guild_confidence < 0.95:
            if user_profile and user_profile.get('guild'):
                ranking.guild_tag = user_profile['guild']
        
        # R8 - PLAYER NAME rename suspicion logic
        if user_profile and user_profile.get('player_name'):
            if ranking.player_name != user_profile['player_name']:
                name_confidence = getattr(ranking, 'confidence_map', {}).get('player_name', 1.0)
                if name_confidence < 0.98:
                    ranking.player_name = user_profile['player_name']
                else:
                    self._update_profile(
                        int(ranking.user_id),
                        ranking.player_name,
                        ranking.guild_tag or ""
                    )
        else:
            self._update_profile(
                int(ranking.user_id),
                ranking.player_name,
                ranking.guild_tag or ""
            )
        
        # Continue with normal save logic (without duplicate/cycle checks)
        existing = self.check_duplicate_submission(
            ranking.user_id,
            ranking.guild_id or "0",
            ranking.event_week,
            ranking.phase,
            ranking.day,
            kvk_run_id=kvk_run_id
        )
        
        if existing:
            score_changed = existing.get('score') != ranking.score
            if score_changed:
                ranking_id = self._update_ranking(existing['id'], ranking)
                return ranking_id, True, True
            else:
                return existing['id'], False, False
        else:
            ranking_id = self.save_ranking(ranking)
            return ranking_id, False, False
    
    # ------------------------------------------------------------
    # (R10) Power Bracket Calculation
    # ------------------------------------------------------------
    def _power_bracket(self, war_score: Optional[int]) -> str:
        """
        Classify player by power level based on final WAR score.
        
        Brackets:
        - Bronze: 0-250k
        - Silver: 250k-800k
        - Gold: 800k-2M
        - Diamond: 2M+
        - Unranked: No war score
        """
        if war_score is None:
            return "Unranked"
        if war_score < 250_000:
            return "Bronze"
        if war_score < 800_000:
            return "Silver"
        if war_score < 2_000_000:
            return "Gold"
        return "Diamond"
    
    def get_player_progression(self, event_week: str, guild_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get player progression data for an event week.
        
        Returns list of player records with:
        - player_name, guild
        - prep_scores (dict by day)
        - war_score
        - growth percentage
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT 
                    user_id,
                    player_name,
                    guild_tag,
                    phase,
                    day,
                    score
                FROM event_rankings
                WHERE event_week = ?
            """
            params = [event_week]
            
            if guild_id is not None:
                query += " AND guild_id = ?"
                params.append(guild_id)
            
            query += " ORDER BY user_id, phase, day"
            
            rows = conn.execute(query, params).fetchall()
            
            # Group by user_id
            players_data = {}
            for row in rows:
                user_id = row['user_id']
                if user_id not in players_data:
                    players_data[user_id] = {
                        'player_name': row['player_name'] or 'Unknown',
                        'guild': row['guild_tag'] or 'NoGuild',
                        'prep_scores': {},
                        'war_score': None
                    }
                
                if row['phase'] == 'prep':
                    day_key = row['day'] if row['day'] != 'overall' else 'overall'
                    players_data[user_id]['prep_scores'][day_key] = row['score']
                elif row['phase'] == 'war':
                    players_data[user_id]['war_score'] = row['score']
            
            # Calculate growth percentages
            result = []
            for user_id, data in players_data.items():
                prep_values = [v for k, v in data['prep_scores'].items() if k != 'overall' and v is not None]
                war_score = data['war_score']
                
                # Calculate growth
                if war_score and prep_values:
                    avg_prep = sum(prep_values) / len(prep_values)
                    growth = ((war_score - avg_prep) / avg_prep * 100) if avg_prep > 0 else 0
                else:
                    growth = 0
                
                result.append({
                    'player_name': data['player_name'],
                    'guild': data['guild'],
                    'prep_scores': data['prep_scores'],
                    'war_score': war_score,
                    'growth': round(growth, 1)
                })
            
            return result
        finally:
            self._maybe_close(conn)
    
    def get_guild_analytics(self, event_week: str, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get guild-aggregated analytics with power bracket analysis (R10).
        
        Single-guild focused: Groups players by ±10% power level for peer comparison.
        
        Returns dict of guilds with:
        - members: list of (player_name, final_score, bracket, growth)
        - total: sum of all member scores
        - brackets: count per bracket type
        """
        players = self.get_player_progression(event_week, guild_id)
        
        guilds = {}
        for p in players:
            guild = p['guild'] or 'NoGuild'
            # Use war score if available, otherwise use max prep score
            final_score = p['war_score']
            if final_score is None and p['prep_scores']:
                final_score = max(p['prep_scores'].values())
            if final_score is None:
                final_score = 0
            
            bracket = self._power_bracket(final_score if final_score > 0 else None)
            
            if guild not in guilds:
                guilds[guild] = {
                    'members': [],
                    'total': 0,
                    'brackets': {'Bronze': 0, 'Silver': 0, 'Gold': 0, 'Diamond': 0, 'Unranked': 0}
                }
            
            guilds[guild]['members'].append((p['player_name'], final_score, bracket, p['growth']))
            guilds[guild]['total'] += final_score
            guilds[guild]['brackets'][bracket] += 1
        
        return guilds
    
    def get_peer_comparison(self, user_id: str, event_week: str, guild_id: str) -> Optional[Dict[str, Any]]:
        """
        Get peer comparison for a specific user within their guild (R10B).
        
        Uses STORED POWER (not scores) to group players by ±10% power level.
        Ranks by EVENT SCORE within peer group for fair comparison.
        
        Returns:
            dict with user_stats, peer_group, percentile_rank, etc.
        """
        # Get user's stored power for this event
        user_power = self.get_power(user_id, event_week)
        if user_power is None:
            return {
                'error': 'no_power',
                'message': 'You need to submit your power using `/kvk ranking set_power <number>` first!'
            }
        
        # Get all guild players with their progression data
        players = self.get_player_progression(event_week, guild_id)
        
        # Get all power values for this event
        all_powers = self.get_all_powers(event_week, guild_id)
        
        # Find target user in player data
        user_data = None
        conn = self._get_connection()
        try:
            user_row = conn.execute(
                "SELECT player_name FROM event_rankings WHERE user_id = ? AND event_week = ? LIMIT 1",
                (user_id, event_week)
            ).fetchone()
            
            if user_row:
                target_name = user_row[0]
                for p in players:
                    if p['player_name'] == target_name:
                        user_data = p
                        break
        finally:
            self._maybe_close(conn)
        
        if not user_data:
            return {
                'error': 'no_score',
                'message': 'No event scores submitted yet. Submit rankings with `/kvk ranking submit`!'
            }
        
        # Calculate user's event score (war or max prep)
        user_score = user_data['war_score']
        if user_score is None and user_data['prep_scores']:
            user_score = max(user_data['prep_scores'].values())
        if user_score is None or user_score == 0:
            return {
                'error': 'no_score',
                'message': 'No scores submitted yet for this event'
            }
        
        # Define peer group: ±10% of user's STORED POWER
        power_min = user_power * 0.9
        power_max = user_power * 1.1
        
        # Build peer list with matching power levels
        peers = []
        for p in players:
            # Get stored power for this player
            peer_user_id = None
            conn = self._get_connection()
            try:
                peer_row = conn.execute(
                    "SELECT user_id FROM event_rankings WHERE player_name = ? AND event_week = ? LIMIT 1",
                    (p['player_name'], event_week)
                ).fetchone()
                if peer_row:
                    peer_user_id = peer_row[0]
            finally:
                self._maybe_close(conn)
            
            if not peer_user_id:
                continue
            
            peer_power = all_powers.get(peer_user_id)
            if peer_power is None:
                continue  # Skip players without power submissions
            
            # Check if within ±10% power range
            if power_min <= peer_power <= power_max:
                peer_score = p['war_score'] if p['war_score'] else (max(p['prep_scores'].values()) if p['prep_scores'] else 0)
                
                peers.append({
                    'player_name': p['player_name'],
                    'power': peer_power,
                    'score': peer_score,
                    'growth': p['growth'],
                    'prep_scores': p['prep_scores'],
                    'war_score': p['war_score']
                })
        
        if not peers:
            return {
                'error': 'no_peers',
                'message': f'No other players in your power range ({int(power_min):,} - {int(power_max):,}) have submitted both power and scores yet.'
            }
        
        # Rank by EVENT SCORE (not growth) within peer group
        peers_sorted_by_score = sorted(peers, key=lambda x: x['score'], reverse=True)
        user_rank = next((i for i, p in enumerate(peers_sorted_by_score) if p['player_name'] == user_data['player_name']), None)
        
        if user_rank is None:
            percentile = 0
        else:
            percentile = ((len(peers_sorted_by_score) - user_rank) / len(peers_sorted_by_score)) * 100
        
        # Calculate peer stats
        peer_scores = [p['score'] for p in peers]
        avg_peer_score = sum(peer_scores) / len(peer_scores) if peer_scores else 0
        
        peer_growths = [p['growth'] for p in peers]
        avg_peer_growth = sum(peer_growths) / len(peer_growths) if peer_growths else 0
        
        return {
            'user': {
                'player_name': user_data['player_name'],
                'power': user_power,  # Stored power, not derived
                'score': user_score,
                'growth': user_data['growth'],
                'prep_scores': user_data['prep_scores'],
                'war_score': user_data['war_score'],
                'bracket': self._power_bracket(user_power)
            },
            'peer_group': {
                'size': len(peers),
                'power_range': (int(power_min), int(power_max)),
                'avg_score': round(avg_peer_score),
                'avg_growth': round(avg_peer_growth, 1),
                'top_performer': peers_sorted_by_score[0] if peers_sorted_by_score else None
            },
            'percentile': round(percentile, 1),
            'rank_in_peers': user_rank + 1 if user_rank is not None else None,
            'outperformed_count': len(peers_sorted_by_score) - user_rank - 1 if user_rank is not None else 0
        }
    
    def check_duplicate_submission(
        self,
        user_id: str,
        guild_id: str,
        event_week: str,
        phase: str,
        day: Optional[int | str],
        kvk_run_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user already submitted for this event/phase/day using canonical model.
        
        Canonical uniqueness key: (user_id, event_id, phase, day)
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            event_week: Event week identifier
            phase: "prep" or "war"
            day: 1-5, "overall", or None
            kvk_run_id: Optional KVK run ID for precise matching
        
        Returns:
            Existing ranking dict if duplicate, None if no duplicate
        """
        if self.storage:
            return self.storage.check_duplicate_event_submission(
                user_id, guild_id, event_week, phase, day, kvk_run_id  # type: ignore[attr-defined]
            )
        
        conn = self._get_connection()
        self._ensure_event_ranking_columns(conn)
        
        try:
            # Convert day to string for query
            day_str = str(day) if day is not None else None
            
            if kvk_run_id is not None:
                cursor = conn.execute("""
                    SELECT * FROM event_rankings
                    WHERE user_id = ? AND guild_id = ? AND kvk_run_id = ? 
                      AND phase = ? AND day IS ?
                    LIMIT 1
                """, (user_id, guild_id, kvk_run_id, phase, day_str))
            else:
                cursor = conn.execute("""
                    SELECT * FROM event_rankings
                    WHERE user_id = ? AND guild_id = ? AND event_week = ? 
                    AND phase = ? AND day IS ?
                    LIMIT 1
                """, (user_id, guild_id, event_week, phase, day_str))
            
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
        phase: Optional[str] = None,
        day: Optional[int | str] = None,
        category: Optional[RankingCategory] = None,
        guild_tag: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get guild leaderboard using canonical phase/day model.
        
        Shows best ranking for each user based on filters.
        
        Args:
            guild_id: Discord guild ID
            event_week: Filter by event week (YYYY-WW format)
            phase: Filter by "prep" or "war"
            day: Filter by day (1-5, "overall", or None for war)
            category: Filter by category (Construction/Research/etc)
            guild_tag: Filter by in-game guild tag (e.g., "TAO")
            limit: Max results to return
        """
        if self.storage:
            return self.storage.get_guild_event_leaderboard(  # type: ignore[attr-defined]
                guild_id,
                event_week=event_week,
                phase=phase,
                day=day,
                category=category,
                guild_tag=guild_tag,
                limit=limit,
            )
        
        conn = self._get_connection()
        self._ensure_event_ranking_columns(conn)
        
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
                    phase,
                    day,
                    category,
                    MAX(submitted_at) as last_submission
                FROM event_rankings
                WHERE guild_id = ?
            """
            params: List[Any] = [guild_id]
            
            if event_week:
                query += " AND event_week = ?"
                params.append(event_week)
            
            if phase:
                query += " AND phase = ?"
                params.append(phase)
            
            if day is not None:
                query += " AND day = ?"
                params.append(str(day))
            
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
        """
        Get current event week in YYYY-WW format.
        
        Uses ScreenshotProcessor's date calculation logic directly.
        No longer delegates to GameStorageEngine (legacy removed).
        """
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
            self._maybe_close(conn)
    
    def get_submission_stats(
        self,
        guild_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get submission statistics."""
        if self.storage:
            return self.storage.get_event_submission_stats(  # type: ignore[attr-defined]
                guild_id=guild_id, days=days
            )
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
    
    def validate_event(self, guild_id: str, event_week: str) -> List[str]:
        """
        Run data integrity checks for an event.
        
        Validation checks:
        - Prep score progression (should increase or stay flat)
        - Multiple war submissions (should only have one)
        - Missing power data
        - Data consistency
        
        Returns:
            List of issue descriptions (empty if all valid)
        """
        issues = []
        conn = self._get_connection()
        
        try:
            # Fetch all rankings for this event
            rows = conn.execute("""
                SELECT user_id, username, player_name, phase, day, score, rank
                FROM event_rankings
                WHERE guild_id = ? AND event_week = ?
                ORDER BY user_id, phase, day
            """, (guild_id, event_week)).fetchall()
            
            if not rows:
                issues.append(f"No submissions found for event {event_week}")
                return issues
            
            # Group by user
            from collections import defaultdict
            user_data = defaultdict(list)
            for row in rows:
                user_id = row[0]
                user_data[user_id].append({
                    'username': row[1],
                    'player_name': row[2],
                    'phase': row[3],
                    'day': row[4],
                    'score': row[5],
                    'rank': row[6]
                })
            
            # Validate each user's submissions
            for user_id, entries in user_data.items():
                username = entries[0]['username']
                player_name = entries[0]['player_name'] or username
                
                # Extract prep and war submissions
                prep_entries = sorted(
                    [e for e in entries if e['phase'] == 'prep' and e['day'] not in [None, 'overall']],
                    key=lambda x: int(x['day']) if isinstance(x['day'], int) else 0
                )
                war_entries = [e for e in entries if e['phase'] == 'war']
                
                # Check 1: Prep score progression
                if len(prep_entries) > 1:
                    prep_scores = [e['score'] for e in prep_entries if e['score'] is not None]
                    if prep_scores and sorted(prep_scores) != prep_scores:
                        issues.append(
                            f"User {player_name}: PREP scores decrease or out of order "
                            f"({', '.join(str(s) for s in prep_scores)})"
                        )
                
                # Check 2: Multiple war submissions
                if len(war_entries) > 1:
                    issues.append(
                        f"User {player_name}: Multiple WAR submissions detected ({len(war_entries)} found)"
                    )
                
                # Check 3: Missing power data
                power = self.get_power(user_id, event_week)
                if power is None:
                    issues.append(
                        f"User {player_name}: Missing POWER data (use `/kvk ranking set_power`)"
                    )
                
                # Check 4: Score sanity checks
                for entry in entries:
                    if entry['score'] is not None:
                        if entry['score'] < 0:
                            issues.append(
                                f"User {player_name}: Negative score detected ({entry['score']})"
                            )
                        if entry['score'] > 1_000_000_000:  # 1 billion
                            issues.append(
                                f"User {player_name}: Unusually high score ({entry['score']:,})"
                            )
                    
                    if entry['rank'] is not None and entry['rank'] < 1:
                        issues.append(
                            f"User {player_name}: Invalid rank #{entry['rank']}"
                        )
            
            return issues
            
        finally:
            self._maybe_close(conn)
