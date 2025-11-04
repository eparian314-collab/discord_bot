"""
Database Migration: Fix Pokemon table schema and ensure all required columns exist.

This migration adds missing columns to the pokemon table for HP/stats tracking.
"""
import sqlite3
from pathlib import Path


def migrate():
    """Add missing columns to pokemon table for battle stats."""
    db_path = Path("data/game_data.db")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        print("The database will be created automatically when the bot starts.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if pokemon table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pokemon'")
    if not cursor.fetchone():
        print("❌ Pokemon table does not exist yet")
        conn.close()
        return
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(pokemon)")
    columns = [col[1] for col in cursor.fetchall()]
    
    changes_made = False
    
    # Define all the columns that should exist with their types and defaults
    required_columns = [
        ('hp', 'INTEGER', 'DEFAULT 100'),
        ('max_hp', 'INTEGER', 'DEFAULT 100'),
        ('attack', 'INTEGER', 'DEFAULT 50'),
        ('defense', 'INTEGER', 'DEFAULT 50'),
        ('sp_attack', 'INTEGER', 'DEFAULT 50'),
        ('sp_defense', 'INTEGER', 'DEFAULT 50'),
        ('speed', 'INTEGER', 'DEFAULT 50'),
    ]
    
    for col_name, col_type, col_default in required_columns:
        if col_name not in columns:
            print(f"Adding '{col_name}' column to pokemon table...")
            cursor.execute(f"ALTER TABLE pokemon ADD COLUMN {col_name} {col_type} {col_default}")
            changes_made = True
            print(f"✅ Added '{col_name}' column")
        else:
            print(f"✓ '{col_name}' column already exists")
    
    if changes_made:
        conn.commit()
        print("\n✅ Pokemon table migration completed successfully!")
    else:
        print("\n✓ No migration needed - all columns present")
    
    conn.close()


if __name__ == "__main__":
    print("🔧 Running database migration: fix_pokemon_schema")
    print("=" * 60)
    migrate()
