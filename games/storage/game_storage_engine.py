import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

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
                mute_until TEXT
            );
            """)
            
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

    def add_user(self, user_id: str) -> None:
        """Initialize a new user with default values."""
        with self.conn:
            self.conn.execute("""
                INSERT OR IGNORE INTO users (user_id, last_interaction, last_daily_check) 
                VALUES (?, ?, ?)
            """, (user_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

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

    def spend_cookies(self, user_id: str, amount: int) -> bool:
        """Spend cookies if user has enough. Returns True if successful."""
        _, current = self.get_user_cookies(user_id)
        if current < amount:
            return False
        self.update_cookies(user_id, cookies_left=current - amount)
        return True

    # Relationship Management
    def update_relationship(self, user_id: str, relationship_index: int, 
                           daily_streak: Optional[int] = None) -> None:
        """Update user's relationship index and optionally streak."""
        with self.conn:
            if daily_streak is not None:
                self.conn.execute("""
                    UPDATE users SET relationship_index = ?, daily_streak = ?, 
                    last_interaction = ? WHERE user_id = ?
                """, (relationship_index, daily_streak, datetime.utcnow().isoformat(), user_id))
            else:
                self.conn.execute("""
                    UPDATE users SET relationship_index = ?, last_interaction = ? 
                    WHERE user_id = ?
                """, (relationship_index, datetime.utcnow().isoformat(), user_id))

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
        cursor = self.conn.cursor()
        cursor.execute("SELECT aggravation_level FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result['aggravation_level'] if result else 0
    
    def increase_aggravation(self, user_id: str, amount: int = 1) -> int:
        """Increase user's aggravation level. Returns new level."""
        self.add_user(user_id)
        current = self.get_aggravation_level(user_id)
        new_level = current + amount
        
        with self.conn:
            self.conn.execute("""
                UPDATE users SET aggravation_level = ? WHERE user_id = ?
            """, (new_level, user_id))
        
        return new_level
    
    def reset_aggravation(self, user_id: str) -> None:
        """Reset user's aggravation level to 0."""
        with self.conn:
            self.conn.execute("""
                UPDATE users SET aggravation_level = 0 WHERE user_id = ?
            """, (user_id,))
    
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