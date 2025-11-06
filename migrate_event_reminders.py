"""
One-time migration script to ensure event_reminders table exists.
Run this to create the missing event_reminders table.
"""
import sqlite3
import sys
from pathlib import Path

# Ensure we're in the project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from discord_bot.games.storage.game_storage_engine import GameStorageEngine

def migrate_event_reminders():
    """Create the event_reminders table if it doesn't exist."""
    print("🔧 Event Reminders Table Migration")
    print("=" * 60)
    
    # Initialize storage engine (will auto-create tables)
    storage = GameStorageEngine("game_data.db")
    
    # Verify the table was created
    conn = sqlite3.connect("game_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_reminders'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        print("✅ event_reminders table created successfully")
        print("\n📋 Schema:")
        cursor.execute("PRAGMA table_info(event_reminders)")
        for row in cursor.fetchall():
            col_id, name, col_type, not_null, default, pk = row
            pk_marker = " [PRIMARY KEY]" if pk else ""
            nullable = "" if not_null else " NULL"
            default_val = f" DEFAULT {default}" if default else ""
            print(f"  • {name}: {col_type}{pk_marker}{nullable}{default_val}")
    else:
        print("❌ Failed to create event_reminders table")
        conn.close()
        return False
    
    conn.close()
    print("\n✅ Migration complete!")
    return True

if __name__ == "__main__":
    success = migrate_event_reminders()
    sys.exit(0 if success else 1)
