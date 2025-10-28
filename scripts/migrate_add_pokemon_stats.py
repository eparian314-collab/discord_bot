"""
Database Migration: Add Pokemon stat columns to pokemon table

This migration adds the missing HP, Attack, Defense, Sp.Attack, Sp.Defense, and Speed columns
to the pokemon table to support the stat system.

Run this script once to update your database schema:
    python scripts/migrate_add_pokemon_stats.py
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def migrate_pokemon_stats(db_path: str = "game_data.db"):
    """Add stat columns to pokemon table."""
    
    print(f"🔄 Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(pokemon)")
    columns = {row[1] for row in cursor.fetchall()}
    print(f"📊 Current columns: {columns}")
    
    # Columns to add
    new_columns = {
        'hp': 'INTEGER DEFAULT 0',
        'attack': 'INTEGER DEFAULT 0',
        'defense': 'INTEGER DEFAULT 0',
        'sp_attack': 'INTEGER DEFAULT 0',
        'sp_defense': 'INTEGER DEFAULT 0',
        'speed': 'INTEGER DEFAULT 0'
    }
    
    added = []
    skipped = []
    
    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            try:
                print(f"  ➕ Adding column: {col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE pokemon ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
            except sqlite3.OperationalError as e:
                print(f"  ⚠️ Warning: Could not add {col_name}: {e}")
        else:
            skipped.append(col_name)
            print(f"  ✓ Column already exists: {col_name}")
    
    conn.commit()
    
    # Verify new schema
    cursor.execute("PRAGMA table_info(pokemon)")
    new_columns_list = {row[1] for row in cursor.fetchall()}
    
    conn.close()
    
    print("\n✅ Migration complete!")
    print(f"   Added: {len(added)} columns: {added}")
    print(f"   Skipped: {len(skipped)} columns: {skipped}")
    print(f"   Final schema: {new_columns_list}")
    
    # Check if we need to populate stats for existing pokemon
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pokemon WHERE hp = 0")
    zero_hp_count = cursor.fetchone()[0]
    
    if zero_hp_count > 0:
        print(f"\n⚠️ Warning: {zero_hp_count} Pokemon have 0 HP")
        print("   Consider running a script to populate stats from PokeAPI")
    
    conn.close()


if __name__ == "__main__":
    try:
        migrate_pokemon_stats()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
