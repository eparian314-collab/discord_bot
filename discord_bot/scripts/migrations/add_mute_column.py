"""
Database Migration: Add mute_until and aggravation_level columns to users table.

This migration adds spam protection columns that were missing from the schema.
"""
import sqlite3
from pathlib import Path


def migrate():
    """Add mute_until and aggravation_level columns to users table."""
    db_path = Path("data/game_data.db")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        print("The database will be created automatically when the bot starts.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    changes_made = False
    
    # Add mute_until column if it doesn't exist
    if 'mute_until' not in columns:
        print("Adding 'mute_until' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN mute_until TEXT")
        changes_made = True
        print("✅ Added 'mute_until' column")
    else:
        print("✓ 'mute_until' column already exists")
    
    # Add aggravation_level column if it doesn't exist
    if 'aggravation_level' not in columns:
        print("Adding 'aggravation_level' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN aggravation_level INTEGER DEFAULT 0")
        changes_made = True
        print("✅ Added 'aggravation_level' column")
    else:
        print("✓ 'aggravation_level' column already exists")
    
    if changes_made:
        conn.commit()
        print("\n✅ Migration completed successfully!")
    else:
        print("\n✓ No migration needed - all columns present")
    
    conn.close()


if __name__ == "__main__":
    print("🔧 Running database migration: add_mute_column")
    print("=" * 60)
    migrate()
