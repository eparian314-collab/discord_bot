"""
Database migration to align the `pokemon` table with the latest stat schema.

The updated game logic expects the following columns to exist:
    - `special_attack` / `special_defense` instead of the legacy
      `sp_attack` / `sp_defense`.
    - Individual value (IV) columns for each stat.
    - A `nature` column for personality effects.

This migration is idempotent and safe to run multiple times.

Usage:
    python -m discord_bot.scripts.migrate_add_pokemon_stats
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


DB_DEFAULT_PATH = Path("data") / "game_data.db"
TABLE_NAME = "pokemon"


def fetch_columns(cursor: sqlite3.Cursor, table: str) -> List[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def rename_column(cursor: sqlite3.Cursor, table: str, old: str, new: str) -> bool:
    columns = set(fetch_columns(cursor, table))
    if new in columns or old not in columns:
        return False
    cursor.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")
    return True


def ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> bool:
    columns = set(fetch_columns(cursor, table))
    if column in columns:
        return False
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    return True


def resolve_stat(stats: Dict[str, object], keys: Iterable[str]) -> Optional[int]:
    for key in keys:
        value = stats.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def backfill_from_legacy_stats(conn: sqlite3.Connection, columns_present: Set[str]) -> int:
    """
    Older schemas stored stats JSON in the `stats` column.
    Attempt to hydrate the new stat columns from that payload if it exists.
    """
    if "stats" not in columns_present:
        return 0

    cursor = conn.cursor()
    rows = cursor.execute(
        f"SELECT pokemon_id, stats FROM {TABLE_NAME} "
        "WHERE stats IS NOT NULL AND stats != ''"
    ).fetchall()

    if not rows:
        return 0

    updated = 0
    for pokemon_id, stats_payload in rows:
        if not stats_payload:
            continue

        try:
            stats = json.loads(stats_payload)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(stats, dict):
            continue

        update_values: Dict[str, Optional[int]] = {
            "hp": resolve_stat(stats, ["hp", "HP", "max_hp"]),
            "attack": resolve_stat(stats, ["attack", "Attack"]),
            "defense": resolve_stat(stats, ["defense", "Defense"]),
            "special_attack": resolve_stat(stats, ["special_attack", "sp_attack", "specialAttack"]),
            "special_defense": resolve_stat(stats, ["special_defense", "sp_defense", "specialDefense"]),
            "speed": resolve_stat(stats, ["speed", "Speed"]),
        }

        assignments = []
        params: List[int] = []
        for column, value in update_values.items():
            if column not in columns_present or value is None:
                continue
            assignments.append(f"{column} = ?")
            params.append(value)

        if not assignments:
            continue

        params.append(pokemon_id)
        cursor.execute(
            f"UPDATE {TABLE_NAME} SET {', '.join(assignments)} WHERE pokemon_id = ?",
            params,
        )
        updated += 1

    conn.commit()
    return updated


def migrate_pokemon_stats(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Start the bot once to create it, "
            "then rerun this migration."
        )

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,),
        )
        if not cursor.fetchone():
            raise RuntimeError(
                f"Table '{TABLE_NAME}' does not exist yet. "
                "Launch the bot to initialise the schema before running the migration."
            )

        print(f"Migrating table '{TABLE_NAME}' in database {db_path}")
        original_columns = set(fetch_columns(cursor, TABLE_NAME))
        print(f"Existing columns: {sorted(original_columns)}")

        changes: List[str] = []

        if rename_column(cursor, TABLE_NAME, "sp_attack", "special_attack"):
            changes.append("Renamed sp_attack -> special_attack")
        if rename_column(cursor, TABLE_NAME, "sp_defense", "special_defense"):
            changes.append("Renamed sp_defense -> special_defense")

        required_columns = {
            "special_attack": "INTEGER DEFAULT 0",
            "special_defense": "INTEGER DEFAULT 0",
            "iv_hp": "INTEGER DEFAULT 0",
            "iv_attack": "INTEGER DEFAULT 0",
            "iv_defense": "INTEGER DEFAULT 0",
            "iv_special_attack": "INTEGER DEFAULT 0",
            "iv_special_defense": "INTEGER DEFAULT 0",
            "iv_speed": "INTEGER DEFAULT 0",
            "nature": "TEXT DEFAULT 'hardy'",
        }

        for column, definition in required_columns.items():
            if ensure_column(cursor, TABLE_NAME, column, definition):
                changes.append(f"Added column {column}")

        conn.commit()

        final_columns = set(fetch_columns(cursor, TABLE_NAME))
        hydrated_rows = backfill_from_legacy_stats(conn, final_columns)
        if hydrated_rows:
            changes.append(f"Hydrated stats from legacy JSON for {hydrated_rows} rows")

        if changes:
            print("Migration actions performed:")
            for entry in changes:
                print(f" - {entry}")
        else:
            print("No schema changes were required. Table already up to date.")

        print(f"Final columns: {sorted(final_columns)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Align the pokemon table with the latest stat schema."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_DEFAULT_PATH,
        help="Path to the game SQLite database (default: data/game_data.db)",
    )
    args = parser.parse_args()

    migrate_pokemon_stats(args.db_path)


if __name__ == "__main__":
    main()
