"""
KVK Ranking Profile Cache
Player guild and name memory for auto-correction.
"""

import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime, timezone


def _ensure_player_profile_table(conn: sqlite3.Connection) -> None:
    """Create player_profile table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_profile (
            user_id TEXT PRIMARY KEY,
            server_id INTEGER,
            guild TEXT,
            player_name TEXT,
            first_seen TEXT,
            last_seen TEXT,
            name_locked BOOLEAN DEFAULT 0,
            guild_locked BOOLEAN DEFAULT 0,
            name_locked_until TEXT
        )
    """)
    conn.commit()


def upsert_player(
    conn: sqlite3.Connection,
    user_id: str,
    server_id: int,
    guild: str,
    player_name: str,
    lock_updates: Optional[Dict[str, Any]] = None
) -> None:
    """
    Insert or update player profile.
    
    Args:
        conn: Database connection
        user_id: Discord user ID
        server_id: Game server ID
        guild: Guild tag (e.g., "TAO")
        player_name: In-game player name
        lock_updates: Optional dict with 'name_locked', 'guild_locked', 'name_locked_until'
    """
    _ensure_player_profile_table(conn)
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if profile exists
    cursor = conn.execute(
        "SELECT first_seen FROM player_profile WHERE user_id = ?",
        (user_id,)
    )
    existing = cursor.fetchone()
    
    if existing:
        # Update existing
        if lock_updates:
            conn.execute("""
                UPDATE player_profile 
                SET server_id = ?, guild = ?, player_name = ?, last_seen = ?,
                    name_locked = ?, guild_locked = ?, name_locked_until = ?
                WHERE user_id = ?
            """, (
                server_id, guild, player_name, now,
                lock_updates.get('name_locked', False),
                lock_updates.get('guild_locked', False),
                lock_updates.get('name_locked_until'),
                user_id
            ))
        else:
            conn.execute("""
                UPDATE player_profile 
                SET server_id = ?, guild = ?, player_name = ?, last_seen = ?
                WHERE user_id = ?
            """, (server_id, guild, player_name, now, user_id))
    else:
        # Insert new
        conn.execute("""
            INSERT INTO player_profile 
            (user_id, server_id, guild, player_name, first_seen, last_seen, name_locked, guild_locked)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        """, (user_id, server_id, guild, player_name, now, now))
    
    conn.commit()


def get_player(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get player profile.
    
    Args:
        conn: Database connection
        user_id: Discord user ID
    
    Returns:
        Dict with player info or None if not found
    """
    _ensure_player_profile_table(conn)
    
    cursor = conn.execute("""
        SELECT 
            user_id, server_id, guild, player_name, 
            first_seen, last_seen, name_locked, guild_locked, name_locked_until
        FROM player_profile 
        WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    return {
        'user_id': row[0],
        'server_id': row[1],
        'guild': row[2],
        'player_name': row[3],
        'first_seen': row[4],
        'last_seen': row[5],
        'name_locked': bool(row[6]),
        'guild_locked': bool(row[7]),
        'name_locked_until': row[8]
    }


def is_name_lock_active(cached: Dict[str, Any]) -> bool:
    """
    Check if name lock is still active (within cooldown period).
    
    Args:
        cached: Player profile dict from get_player()
    
    Returns:
        True if name is locked and cooldown hasn't expired
    """
    if not cached.get('name_locked'):
        return False
    
    locked_until = cached.get('name_locked_until')
    if not locked_until:
        return False
    
    try:
        locked_until_dt = datetime.fromisoformat(locked_until)
        now = datetime.now(timezone.utc)
        return now < locked_until_dt
    except (ValueError, TypeError):
        return False


def prefer_cached_when_low_confidence(
    parsed: Dict[str, Any],
    cached: Optional[Dict[str, Any]],
    confidence_map: Dict[str, float]
) -> Dict[str, Any]:
    """
    Apply cached guild/name when OCR confidence is low.
    
    Args:
        parsed: Parsed ranking data
        cached: Cached player profile or None
        confidence_map: Field confidence scores
    
    Returns:
        Updated parsed dict with cached values substituted where appropriate
    """
    if not cached:
        return parsed
    
    result = parsed.copy()
    
    # Guild substitution: use cached if confidence < 0.95
    if confidence_map.get('guild', 1.0) < 0.95 and cached.get('guild'):
        result['guild'] = cached['guild']
        result['_guild_from_cache'] = True
    
    # Player name substitution: use cached if confidence < 0.98 and name differs
    parsed_name = parsed.get('player_name', '')
    cached_name = cached.get('player_name', '')
    
    if (cached_name and 
        parsed_name.lower() != cached_name.lower() and
        confidence_map.get('player_name', 1.0) < 0.98):
        
        # Check if name is locked
        if is_name_lock_active(cached):
            result['player_name'] = cached_name
            result['_name_from_cache'] = True
            result['_name_locked'] = True
        else:
            # Name differs but not locked - prompt user
            result['_name_differs'] = True
            result['_cached_name'] = cached_name
    
    return result
