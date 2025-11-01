import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from discord_bot.core.engines.screenshot_processor import RankingData, StageType, RankingCategory

class GameStorageEngine:
    def __init__(self, db_path="game_data.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        with self.conn:
            # Enhanced users table with relationship and game unlock tracking
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                total_cookies INTEGER DEFAULT 0,
                cookies_left INTEGER DEFAULT 0,
                relationship_index INTEGER DEFAULT 0,
                last_interaction TEXT,
                daily_streak INTEGER DEFAULT 0,
                game_unlocked INTEGER DEFAULT 0,
                total_interactions INTEGER DEFAULT 0,
                last_daily_check TEXT,
                aggravation_level INTEGER DEFAULT 0,
                relationship_anchor_at TEXT,
                aggravation_updated_at TEXT,
                mute_until TEXT
            );
            """)
            self._ensure_user_aux_columns()
            
            # Enhanced pokemon table with species tracking for duplicates
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pokemon (
                pokemon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                species TEXT,
                nickname TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                hp INTEGER,
                attack INTEGER,
                defense INTEGER,
                special_attack INTEGER,
                special_defense INTEGER,
                speed INTEGER,
                iv_hp INTEGER,
                iv_attack INTEGER,
                iv_defense INTEGER,
                iv_special_attack INTEGER,
                iv_special_defense INTEGER,
                iv_speed INTEGER,
                nature TEXT,
                caught_date TEXT,
                is_favorite INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            """)
            
            # Battles table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                battle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id TEXT,
                user2_id TEXT,
                winner_id TEXT,
                log TEXT,
                battle_date TEXT,
                FOREIGN KEY (user1_id) REFERENCES users(user_id),
                FOREIGN KEY (user2_id) REFERENCES users(user_id)
            );
            """)
            
            # Interaction history for relationship tracking
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                interaction_type TEXT,
                timestamp TEXT,
                cookies_earned INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            """)
            
            # Daily easter egg tracking
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_easter_egg_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                date TEXT,
                cookies_earned INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                spam_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, date)
            );
            """)

            # Admin/helper daily gift allowances
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_cookie_allowances (
                user_id TEXT PRIMARY KEY,
                last_date TEXT,
                remaining INTEGER DEFAULT 0
            );
            """)
            
            # Game statistics tracking
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS game_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                stat_type TEXT,
                stat_value INTEGER DEFAULT 0,
                last_updated TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, stat_type)
            );
            """)
            
            # Event reminders for Top Heroes coordination
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS event_reminders (
                event_id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                event_time_utc TEXT NOT NULL,
                recurrence TEXT DEFAULT 'once',
                custom_interval_hours INTEGER,
                reminder_times TEXT,
                channel_id INTEGER,
                role_to_ping INTEGER,
                created_by INTEGER,
                is_active INTEGER DEFAULT 1,
                auto_scraped INTEGER DEFAULT 0,
                source_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Event rankings for Top Heroes coordination
            self.conn.execute("""
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
            );
            """)

            # Indexes for fast ranking lookups
            self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rankings_user 
            ON event_rankings(user_id, guild_id);
            """)
            self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rankings_guild_stage 
            ON event_rankings(guild_id, stage_type, day_number);
            """)
            self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rankings_guild_tag 
            ON event_rankings(guild_tag);
            """)
            self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rankings_event_week 
            ON event_rankings(event_week, guild_id);
            """)

            # Submission log for ranking processing
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS event_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT,
                submitted_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                ranking_id INTEGER,
                FOREIGN KEY(ranking_id) REFERENCES event_rankings(id)
            );
            """)

    def _ensure_user_aux_columns(self) -> None:
        """Ensure auxiliary tracking columns exist on the users table."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "relationship_anchor_at" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN relationship_anchor_at TEXT")
        if "aggravation_updated_at" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN aggravation_updated_at TEXT")

    def add_user(self, user_id: str) -> None:
        """Initialize a new user with default values."""
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute("""
                INSERT OR IGNORE INTO users (user_id, last_interaction, last_daily_check, relationship_anchor_at) 
                VALUES (?, ?, ?, ?)
            """, (user_id, now, now, now))

    def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete user data."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_user_cookies(self, user_id: str) -> tuple[int, int]:
        """Get total and current cookies for a user."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT total_cookies, cookies_left FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return (result['total_cookies'], result['cookies_left']) if result else (0, 0)

    def update_cookies(self, user_id: str, total_cookies: Optional[int] = None, 
                      cookies_left: Optional[int] = None) -> None:
        """Update user cookie counts."""
        with self.conn:
            if total_cookies is not None and cookies_left is not None:
                self.conn.execute("""
                    UPDATE users SET total_cookies = ?, cookies_left = ? WHERE user_id = ?
                """, (total_cookies, cookies_left, user_id))
            elif total_cookies is not None:
                self.conn.execute("UPDATE users SET total_cookies = ? WHERE user_id = ?", 
                                (total_cookies, user_id))
            elif cookies_left is not None:
                self.conn.execute("UPDATE users SET cookies_left = ? WHERE user_id = ?", 
                                (cookies_left, user_id))

    def add_cookies(self, user_id: str, amount: int) -> tuple[int, int]:
        """Add cookies to user and return new totals."""
        self.add_user(user_id)
        total, current = self.get_user_cookies(user_id)
        new_total = total + amount
        new_current = current + amount
        self.update_cookies(user_id, new_total, new_current)
        return (new_total, new_current)

    def add_gift_cookies(self, user_id: str, amount: int) -> tuple[int, int]:
        """
        Add cookies that should not count toward leaderboard totals.
        Increases current balance but leaves total_cookies unchanged.
        """
        if amount <= 0:
            return self.get_user_cookies(user_id)
        self.add_user(user_id)
        total, current = self.get_user_cookies(user_id)
        new_current = current + amount
        self.update_cookies(user_id, cookies_left=new_current)
        return (total, new_current)

    def spend_cookies(self, user_id: str, amount: int) -> bool:
        """Spend cookies if user has enough. Returns True if successful."""
        _, current = self.get_user_cookies(user_id)
        if current < amount:
            return False
        self.update_cookies(user_id, cookies_left=current - amount)
        return True

    def get_admin_gift_remaining(self, user_id: str, daily_limit: int) -> int:
        """Return how many gift cookies the admin/helper has left today."""
        return self._ensure_admin_gift_record(user_id, daily_limit)

    def consume_admin_gift_allowance(self, user_id: str, amount: int, daily_limit: int) -> bool:
        """Consume from the user's daily gift allowance if possible."""
        if amount <= 0:
            return False

        remaining = self._ensure_admin_gift_record(user_id, daily_limit)
        if amount > remaining:
            return False

        new_remaining = remaining - amount
        today = datetime.utcnow().date().isoformat()
        with self.conn:
            self.conn.execute(
                """
                UPDATE admin_cookie_allowances
                SET remaining = ?, last_date = ?
                WHERE user_id = ?
                """,
                (new_remaining, today, user_id),
            )
        return True

    def _ensure_admin_gift_record(self, user_id: str, daily_limit: int) -> int:
        """Ensure an allowance record exists for today and return remaining amount."""
        today = datetime.utcnow().date().isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT last_date, remaining FROM admin_cookie_allowances WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO admin_cookie_allowances (user_id, last_date, remaining)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, today, daily_limit),
                )
            return daily_limit

        last_date = row["last_date"]
        remaining = row["remaining"]
        if last_date != today:
            with self.conn:
                self.conn.execute(
                    """
                    UPDATE admin_cookie_allowances
                    SET last_date = ?, remaining = ?
                    WHERE user_id = ?
                    """,
                    (today, daily_limit, user_id),
                )
            return daily_limit

        return remaining

    # Relationship Management
    def update_relationship(
        self,
        user_id: str,
        relationship_index: int,
        daily_streak: Optional[int] = None,
        *,
        touch_last_interaction: bool = True,
        touch_anchor: bool = True,
    ) -> None:
        """Update user's relationship index and optionally streak."""
        now = datetime.utcnow().isoformat()
        updates = ["relationship_index = ?"]
        params: list[Any] = [relationship_index]

        if daily_streak is not None:
            updates.append("daily_streak = ?")
            params.append(daily_streak)

        if touch_last_interaction:
            updates.append("last_interaction = ?")
            params.append(now)

        if touch_anchor:
            updates.append("relationship_anchor_at = ?")
            params.append(now)

        params.append(user_id)

        set_clause = ", ".join(updates)
        with self.conn:
            self.conn.execute(
                f"UPDATE users SET {set_clause} WHERE user_id = ?",
                params,
            )

    def increment_interactions(self, user_id: str, interaction_type: str, 
                              cookies_earned: int = 0) -> None:
        """Record an interaction and increment counter."""
        self.add_user(user_id)
        with self.conn:
            # Update total interactions
            self.conn.execute("""
                UPDATE users SET total_interactions = total_interactions + 1,
                last_interaction = ? WHERE user_id = ?
            """, (datetime.utcnow().isoformat(), user_id))
            
            # Log the interaction
            self.conn.execute("""
                INSERT INTO interactions (user_id, interaction_type, timestamp, cookies_earned)
                VALUES (?, ?, ?, ?)
            """, (user_id, interaction_type, datetime.utcnow().isoformat(), cookies_earned))

    def unlock_game(self, user_id: str) -> None:
        """Unlock the Pokemon game for user."""
        with self.conn:
            self.conn.execute("UPDATE users SET game_unlocked = 1 WHERE user_id = ?", (user_id,))

    def is_game_unlocked(self, user_id: str) -> bool:
        """Check if user has unlocked the game."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT game_unlocked FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return bool(result['game_unlocked']) if result else False

    # Pokemon Management
    def add_pokemon(self, user_id: str, species: str, nickname: Optional[str] = None,
                   level: int = 1, hp: int = 0, attack: int = 0, defense: int = 0,
                   special_attack: int = 0, special_defense: int = 0, speed: int = 0,
                   iv_hp: int = 0, iv_attack: int = 0, iv_defense: int = 0,
                   iv_special_attack: int = 0, iv_special_defense: int = 0, iv_speed: int = 0,
                   nature: str = 'hardy') -> Optional[int]:
        """Add a Pokemon to user's collection with full battle stats. Returns pokemon_id or None if limit reached."""
        # Check duplicate limit (max 3 of same species)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM pokemon 
            WHERE user_id = ? AND species = ?
        """, (user_id, species))
        count = cursor.fetchone()['count']
        
        if count >= 3:
            return None
        
        with self.conn:
            cursor = self.conn.execute("""
                INSERT INTO pokemon (user_id, species, nickname, level, experience,
                                   hp, attack, defense, special_attack, special_defense, speed,
                                   iv_hp, iv_attack, iv_defense, iv_special_attack, iv_special_defense, iv_speed,
                                   nature, caught_date)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, species, nickname or species, level, 
                  hp, attack, defense, special_attack, special_defense, speed,
                  iv_hp, iv_attack, iv_defense, iv_special_attack, iv_special_defense, iv_speed,
                  nature, datetime.utcnow().isoformat()))
            return cursor.lastrowid

    def get_user_pokemon(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all Pokemon owned by user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM pokemon WHERE user_id = ? ORDER BY caught_date DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_pokemon_count_by_species(self, user_id: str, species: str) -> int:
        """Get count of specific species owned by user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM pokemon 
            WHERE user_id = ? AND species = ?
        """, (user_id, species))
        return cursor.fetchone()['count']
    
    def get_pokemon_by_id(self, pokemon_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific Pokemon by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM pokemon WHERE pokemon_id = ?", (pokemon_id,))
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def update_pokemon_stats(self, pokemon_id: int, **stats) -> bool:
        """Update Pokemon stats (hp, attack, defense, etc.)."""
        valid_stats = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed',
                      'level', 'experience', 'nickname', 'is_favorite']
        
        updates = []
        values = []
        for key, value in stats.items():
            if key in valid_stats:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(pokemon_id)
        query = f"UPDATE pokemon SET {', '.join(updates)} WHERE pokemon_id = ?"
        
        with self.conn:
            cursor = self.conn.execute(query, values)
            return cursor.rowcount > 0

    def remove_pokemon(self, pokemon_id: int) -> bool:
        """Remove a Pokemon (for training/evolution). Returns True if successful."""
        with self.conn:
            cursor = self.conn.execute("DELETE FROM pokemon WHERE pokemon_id = ?", (pokemon_id,))
            return cursor.rowcount > 0

    def update_pokemon_xp(self, pokemon_id: int, xp_gain: int, max_level: int = 40) -> Optional[Dict[str, Any]]:
        """
        Add XP to Pokemon and handle leveling.
        
        Args:
            pokemon_id: Pokemon to update
            xp_gain: Amount of XP to add
            max_level: Maximum level cap (default 40)
        
        Note: This method only updates XP and level. Stats should be recalculated 
        by the caller using update_pokemon_stats() if the level changed.
        
        Returns updated Pokemon data including current stats.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT experience, level FROM pokemon WHERE pokemon_id = ?
        """, (pokemon_id,))
        result = cursor.fetchone()
        
        if not result:
            return None
        
        new_xp = result['experience'] + xp_gain
        new_level = result['level']
        
        # Simple leveling: 100 XP per level
        while new_xp >= new_level * 100 and new_level < max_level:
            new_xp -= new_level * 100
            new_level += 1
        
        # Cap at max level
        if new_level >= max_level:
            new_level = max_level
            new_xp = 0  # Clear XP at max level
        
        with self.conn:
            self.conn.execute("""
                UPDATE pokemon SET experience = ?, level = ? WHERE pokemon_id = ?
            """, (new_xp, new_level, pokemon_id))
        
        # Return full Pokemon data so caller can check if level changed
        cursor.execute("SELECT * FROM pokemon WHERE pokemon_id = ?", (pokemon_id,))
        return dict(cursor.fetchone())

    def update_daily_check(self, user_id: str) -> None:
        """Update the last daily check timestamp."""
        with self.conn:
            self.conn.execute("""
                UPDATE users SET last_daily_check = ? WHERE user_id = ?
            """, (datetime.utcnow().isoformat(), user_id))
    
    # Easter Egg Daily Tracking
    def get_daily_easter_egg_stats(self, user_id: str) -> Dict[str, int]:
        """Get today's easter egg stats for user."""
        today = datetime.utcnow().date().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT cookies_earned, attempts, spam_count 
            FROM daily_easter_egg_stats 
            WHERE user_id = ? AND date = ?
        """, (user_id, today))
        result = cursor.fetchone()
        
        if result:
            return {
                'cookies_earned': result['cookies_earned'],
                'attempts': result['attempts'],
                'spam_count': result['spam_count']
            }
        return {'cookies_earned': 0, 'attempts': 0, 'spam_count': 0}
    
    def record_easter_egg_attempt(self, user_id: str, cookies_earned: int = 0, is_spam: bool = False) -> None:
        """Record an easter egg attempt and update daily stats."""
        today = datetime.utcnow().date().isoformat()
        self.add_user(user_id)
        
        with self.conn:
            # Insert or update daily stats
            self.conn.execute("""
                INSERT INTO daily_easter_egg_stats (user_id, date, cookies_earned, attempts, spam_count)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    cookies_earned = cookies_earned + ?,
                    attempts = attempts + 1,
                    spam_count = spam_count + ?
            """, (user_id, today, cookies_earned, 1 if is_spam else 0, cookies_earned, 1 if is_spam else 0))
    
    def reset_daily_easter_egg_stats(self, user_id: str) -> None:
        """Reset daily easter egg stats (called at midnight or manually)."""
        today = datetime.utcnow().date().isoformat()
        with self.conn:
            self.conn.execute("""
                DELETE FROM daily_easter_egg_stats 
                WHERE user_id = ? AND date < ?
            """, (user_id, today))
    
    # Aggravation and Mute Tracking
    def get_aggravation_level(self, user_id: str) -> int:
        """Get user's current aggravation level."""
        record = self._get_aggravation_record(user_id)
        return record['aggravation_level'] if record else 0
    
    def increase_aggravation(self, user_id: str, amount: int = 1) -> int:
        """Increase user's aggravation level. Returns new level."""
        self.add_user(user_id)
        record = self._get_aggravation_record(user_id)
        current = record['aggravation_level'] if record else 0
        new_level = current + amount
        now = datetime.utcnow().isoformat()
        
        with self.conn:
            self.conn.execute("""
                UPDATE users
                   SET aggravation_level = ?, aggravation_updated_at = ?
                 WHERE user_id = ?
            """, (new_level, now, user_id))
        
        return new_level
    
    def reset_aggravation(self, user_id: str) -> None:
        """Reset user's aggravation level to 0."""
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute("""
                UPDATE users
                   SET aggravation_level = 0,
                       aggravation_updated_at = ?
                 WHERE user_id = ?
            """, (now, user_id))
    
    def maybe_reset_aggravation(self, user_id: str, cooldown_minutes: int) -> bool:
        """Reset aggravation if the cooldown window has passed."""
        record = self._get_aggravation_record(user_id)
        if not record:
            return False

        level = record['aggravation_level'] or 0
        if level <= 0:
            return False

        last_update_raw = record['aggravation_updated_at']
        if not last_update_raw:
            return False

        try:
            last_update = datetime.fromisoformat(last_update_raw)
        except ValueError:
            # Legacy or corrupt timestamp; reset to be safe.
            self.reset_aggravation(user_id)
            return True

        if datetime.utcnow() - last_update >= timedelta(minutes=cooldown_minutes):
            self.reset_aggravation(user_id)
            return True

        return False
    
    def _get_aggravation_record(self, user_id: str) -> Optional[sqlite3.Row]:
        """Return aggravation level and last update timestamp for a user."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT aggravation_level, aggravation_updated_at FROM users WHERE user_id = ?",
            (user_id,),
        )
        return cursor.fetchone()
    
    def set_mute_until(self, user_id: str, until_time: datetime) -> None:
        """Set when user's mute expires."""
        self.add_user(user_id)
        with self.conn:
            self.conn.execute("""
                UPDATE users SET mute_until = ? WHERE user_id = ?
            """, (until_time.isoformat(), user_id))
    
    def clear_mute(self, user_id: str) -> None:
        """Clear user's mute status."""
        with self.conn:
            self.conn.execute("""
                UPDATE users SET mute_until = NULL WHERE user_id = ?
            """, (user_id,))
    
    def is_muted(self, user_id: str) -> bool:
        """Check if user is currently muted."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT mute_until FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result or not result['mute_until']:
            return False
        
        mute_until = datetime.fromisoformat(result['mute_until'])
        now = datetime.utcnow()
        
        # If mute has expired, clear it
        if now >= mute_until:
            self.clear_mute(user_id)
            return False
        
        return True
    
    def get_mute_until(self, user_id: str) -> Optional[datetime]:
        """Get when user's mute expires."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT mute_until FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result and result['mute_until']:
            return datetime.fromisoformat(result['mute_until'])
        return None
    
    # Game Stats Tracking
    def increment_stat(self, user_id: str, stat_type: str, amount: int = 1) -> None:
        """Increment a game stat (e.g., 'pokemon_caught', 'battles_won', 'games_played')."""
        self.add_user(user_id)
        timestamp = datetime.utcnow().isoformat()
        
        with self.conn:
            self.conn.execute("""
                INSERT INTO game_stats (user_id, stat_type, stat_value, last_updated)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, stat_type) DO UPDATE SET
                    stat_value = stat_value + ?,
                    last_updated = ?
            """, (user_id, stat_type, amount, timestamp, amount, timestamp))
    
    def get_stat(self, user_id: str, stat_type: str) -> int:
        """Get a specific game stat."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT stat_value FROM game_stats 
            WHERE user_id = ? AND stat_type = ?
        """, (user_id, stat_type))
        result = cursor.fetchone()
        return result['stat_value'] if result else 0
    
    def get_all_stats(self, user_id: str) -> Dict[str, int]:
        """Get all game stats for a user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT stat_type, stat_value FROM game_stats WHERE user_id = ?
        """, (user_id,))
        return {row['stat_type']: row['stat_value'] for row in cursor.fetchall()}
    
    def get_cookie_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by total cookies earned."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT user_id, total_cookies, cookies_left
            FROM users
            WHERE total_cookies > 0
            ORDER BY total_cookies DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    # Event Reminder Storage Methods
    def store_event_reminder(self, event_data: Dict[str, Any]) -> bool:
        """Store a new event reminder."""
        try:
            import json
            with self.conn:
                self.conn.execute("""
                    INSERT INTO event_reminders (
                        event_id, guild_id, title, description, category,
                        event_time_utc, recurrence, custom_interval_hours,
                        reminder_times, channel_id, role_to_ping, created_by,
                        is_active, auto_scraped, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_data['event_id'],
                    event_data['guild_id'],
                    event_data['title'],
                    event_data.get('description', ''),
                    event_data['category'],
                    event_data['event_time_utc'],
                    event_data.get('recurrence', 'once'),
                    event_data.get('custom_interval_hours'),
                    json.dumps(event_data.get('reminder_times', [60, 15, 5])),
                    event_data.get('channel_id'),
                    event_data.get('role_to_ping'),
                    event_data.get('created_by', 0),
                    event_data.get('is_active', 1),
                    event_data.get('auto_scraped', 0),
                    event_data.get('source_url')
                ))
            return True
        except Exception:
            return False
    
    def update_event_reminder(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing event reminder."""
        try:
            import json
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key == 'reminder_times' and isinstance(value, list):
                    value = json.dumps(value)
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(event_id)
            with self.conn:
                self.conn.execute(
                    f"UPDATE event_reminders SET {', '.join(set_clauses)} WHERE event_id = ?",
                    values
                )
            return True
        except Exception:
            return False
    
    def delete_event_reminder(self, event_id: str) -> bool:
        """Delete an event reminder."""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM event_reminders WHERE event_id = ?", (event_id,))
            return True
        except Exception:
            return False
    
    def get_event_reminders(self, guild_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get event reminders, optionally filtered by guild."""
        import json
        cursor = self.conn.cursor()
        
        if guild_id is not None:
            cursor.execute("SELECT * FROM event_reminders WHERE guild_id = ?", (guild_id,))
        else:
            cursor.execute("SELECT * FROM event_reminders")
        
        results = []
        for row in cursor.fetchall():
            event = dict(row)
            # Parse JSON reminder_times
            if event.get('reminder_times'):
                try:
                    event['reminder_times'] = json.loads(event['reminder_times'])
                except Exception:
                    event['reminder_times'] = [60, 15, 5]
            results.append(event)
        
        return results

    # Event Rankings Management
    def save_event_ranking(self, ranking: RankingData) -> int:
        """Persist a ranking entry and return its row ID."""
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO event_rankings (
                    user_id, username, guild_id, guild_tag, player_name,
                    event_week, stage_type, day_number, category,
                    rank, score, submitted_at, screenshot_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                ),
            )
        return cursor.lastrowid

    def check_duplicate_event_submission(
        self,
        user_id: str,
        guild_id: str,
        event_week: str,
        stage_type: StageType,
        day_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Return existing ranking if user already submitted for the same slot."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM event_rankings
            WHERE user_id = ? AND guild_id = ? AND event_week = ?
              AND stage_type = ? AND day_number = ?
            LIMIT 1
            """,
            (user_id, guild_id, event_week, stage_type.value, day_number),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_event_ranking(
        self,
        ranking_id: int,
        rank: int,
        score: int,
        screenshot_url: Optional[str] = None,
    ) -> bool:
        """Update rank/score metadata for an existing ranking."""
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE event_rankings
                   SET rank = ?, score = ?, screenshot_url = ?, submitted_at = ?
                 WHERE id = ?
                """,
                (rank, score, screenshot_url, datetime.utcnow().isoformat(), ranking_id),
            )
        return cursor.rowcount > 0

    def get_user_event_rankings(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch most recent rankings for a user."""
        query = """
            SELECT * FROM event_rankings
             WHERE user_id = ?
        """
        params: List[Any] = [user_id]
        if guild_id:
            query += " AND guild_id = ?"
            params.append(guild_id)
        query += " ORDER BY submitted_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_guild_event_leaderboard(
        self,
        guild_id: str,
        event_week: Optional[str] = None,
        stage_type: Optional[StageType] = None,
        day_number: Optional[int] = None,
        category: Optional[RankingCategory] = None,
        guild_tag: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Summarise best rankings per user for a guild."""
        query = """
            SELECT 
                user_id,
                username,
                guild_tag,
                player_name,
                event_week,
                MIN(rank) AS best_rank,
                MAX(score) AS highest_score,
                stage_type,
                day_number,
                category,
                MAX(submitted_at) AS last_submission
            FROM event_rankings
            WHERE guild_id = ?
        """
        params: List[Any] = [guild_id]
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

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_current_event_week(self) -> str:
        """Return the current event week identifier."""
        from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor

        processor = ScreenshotProcessor()
        return processor._get_current_event_week()

    def prune_event_weeks(self, weeks_to_keep: int = 4) -> int:
        """Remove ranking data older than the specified number of weeks."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT event_week
              FROM event_rankings
             ORDER BY event_week DESC
            """
        )
        all_weeks = [row["event_week"] for row in cursor.fetchall()]
        if len(all_weeks) <= weeks_to_keep:
            return 0

        weeks_to_delete = all_weeks[weeks_to_keep:]
        placeholders = ", ".join("?" for _ in weeks_to_delete)
        with self.conn:
            cursor = self.conn.execute(
                f"""
                DELETE FROM event_rankings
                      WHERE event_week IN ({placeholders})
                """,
                weeks_to_delete,
            )
        return cursor.rowcount

    def get_event_ranking_history(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Return chronological ranking history for a user."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = """
            SELECT * FROM event_rankings
             WHERE user_id = ? AND submitted_at >= ?
        """
        params: List[Any] = [user_id, cutoff.isoformat()]
        if guild_id:
            query += " AND guild_id = ?"
            params.append(guild_id)
        query += " ORDER BY submitted_at ASC"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def log_event_submission(
        self,
        user_id: str,
        guild_id: Optional[str],
        status: str,
        error_message: Optional[str] = None,
        ranking_id: Optional[int] = None,
    ) -> None:
        """Record a submission attempt outcome."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO event_submissions (
                    user_id, guild_id, submitted_at, status, error_message, ranking_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    guild_id,
                    datetime.utcnow().isoformat(),
                    status,
                    error_message,
                    ranking_id,
                ),
            )

    def get_event_submission_stats(
        self,
        guild_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Return submission summary metrics."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = """
            SELECT
                COUNT(*) AS total_submissions,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                COUNT(DISTINCT user_id) AS unique_users
            FROM event_submissions
            WHERE submitted_at >= ?
        """
        params: List[Any] = [cutoff.isoformat()]
        if guild_id:
            query += " AND guild_id = ?"
            params.append(guild_id)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else {}

    def delete_old_event_rankings(self, days: int = 30) -> int:
        """Delete ranking entries older than the given number of days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.conn:
            cursor = self.conn.execute(
                """
                DELETE FROM event_rankings
                WHERE submitted_at < ?
                """,
                (cutoff.isoformat(),),
            )
        return cursor.rowcount
