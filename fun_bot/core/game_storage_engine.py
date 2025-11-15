from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite

from .error_engine import ErrorEngine


logger = logging.getLogger(__name__)


class GameStorageEngine:
    """Async SQLite-backed storage for FunBot game/user data.

    The engine provides a small, generic API for storing arbitrary
    per-user data in JSON form, partitioned by a simple `namespace`.

    This is intentionally minimal but durable, so that future game
    systems (rankings, cookies, pokemon progress, etc.) can all share
    the same persistent store without schema churn.
    """

    def __init__(self, db_path: str) -> None:
        self._project_root = Path(__file__).resolve().parents[1]
        raw_path = Path(db_path)
        if raw_path.is_absolute():
            resolved = raw_path
        else:
            resolved = (self._project_root / raw_path).resolve()

        self._db_path = resolved
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._error_engine = ErrorEngine()

    @property
    def db_path(self) -> Path:
        return self._db_path

    async def initialize(self) -> None:
        """Open the database and ensure core tables exist.

        Safe to call multiple times; subsequent calls are no-ops.
        """

        if self._conn is not None:
            return

        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(self._db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.execute("PRAGMA foreign_keys=ON;")

            await self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id     INTEGER NOT NULL,
                    namespace   TEXT    NOT NULL,
                    key         TEXT    NOT NULL,
                    value_json  TEXT    NOT NULL,
                    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, namespace, key)
                )
                """
            )

            # Per-Pokémon records for richer game systems. This lives in
            # the same SQLite database as user_data but is managed by
            # the Pokémon data manager.
            await self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pokemon (
                    pokemon_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id            INTEGER NOT NULL,
                    species            TEXT    NOT NULL,
                    nickname           TEXT,
                    level              INTEGER NOT NULL DEFAULT 1,
                    experience         INTEGER NOT NULL DEFAULT 0,
                    hp                 INTEGER NOT NULL,
                    attack             INTEGER NOT NULL,
                    defense            INTEGER NOT NULL,
                    special_attack     INTEGER NOT NULL,
                    special_defense    INTEGER NOT NULL,
                    speed              INTEGER NOT NULL,
                    iv_hp              INTEGER NOT NULL,
                    iv_attack          INTEGER NOT NULL,
                    iv_defense         INTEGER NOT NULL,
                    iv_special_attack  INTEGER NOT NULL,
                    iv_special_defense INTEGER NOT NULL,
                    iv_speed           INTEGER NOT NULL,
                    nature             TEXT    NOT NULL,
                    types              TEXT    NOT NULL,
                    caught_date        TEXT    NOT NULL,
                    free_stat_points   INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            # In case the table was created before free_stat_points was
            # introduced, attempt to add it; ignore failures so repeated
            # initialisation stays cheap and safe.
            try:
                await self._conn.execute(
                    "ALTER TABLE pokemon ADD COLUMN free_stat_points INTEGER NOT NULL DEFAULT 0"
                )
            except Exception:
                pass

            await self._conn.commit()
            logger.info("GameStorageEngine initialised at %s", self._db_path)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._error_engine.log_exception(exc, context="GameStorageEngine.initialize")
            raise

    async def close(self) -> None:
        conn = self._conn
        if conn is None:
            return
        self._conn = None
        await conn.close()

    async def set_user_value(
        self,
        user_id: int,
        namespace: str,
        key: str,
        value: Any,
    ) -> None:
        """Store a JSON-serialisable value for a user + namespace + key."""

        if self._conn is None:
            await self.initialize()

        assert self._conn is not None  # for type checkers

        payload = json.dumps(value, separators=(",", ":"))

        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO user_data (user_id, namespace, key, value_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, namespace, key)
                DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (int(user_id), namespace, key, payload),
            )
            await self._conn.commit()

    async def get_user_value(
        self,
        user_id: int,
        namespace: str,
        key: str,
        default: Any | None = None,
    ) -> Any:
        """Fetch a stored value, returning ``default`` when missing."""

        if self._conn is None:
            await self.initialize()

        assert self._conn is not None  # for type checkers

        async with self._lock:
            cursor = await self._conn.execute(
                """
                SELECT value_json
                FROM user_data
                WHERE user_id = ? AND namespace = ? AND key = ?
                """,
                (int(user_id), namespace, key),
            )
            row = await cursor.fetchone()
            await cursor.close()

        if row is None:
            return default

        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return default

    async def get_namespace(
        self,
        user_id: int,
        namespace: str,
    ) -> Dict[str, Any]:
        """Return all key/value pairs for a user's namespace."""

        if self._conn is None:
            await self.initialize()

        assert self._conn is not None  # for type checkers

        async with self._lock:
            cursor = await self._conn.execute(
                """
                SELECT key, value_json
                FROM user_data
                WHERE user_id = ? AND namespace = ?
                """,
                (int(user_id), namespace),
            )
            rows = await cursor.fetchall()
            await cursor.close()

        result: Dict[str, Any] = {}
        for key, value_json in rows:
            try:
                result[str(key)] = json.loads(value_json)
            except json.JSONDecodeError:
                continue
        return result

    async def clear_namespace(self, user_id: int, namespace: str) -> None:
        """Remove all keys for a given user + namespace."""

        if self._conn is None:
            await self.initialize()

        assert self._conn is not None  # for type checkers

        async with self._lock:
            await self._conn.execute(
                "DELETE FROM user_data WHERE user_id = ? AND namespace = ?",
                (int(user_id), namespace),
            )
            await self._conn.commit()


__all__ = ["GameStorageEngine"]
