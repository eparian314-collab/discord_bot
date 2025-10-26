"""
Asynchronous storage engine with self-healing SQLite support and JSON fallback.

Key features:
 - Async API using `aiosqlite`
 - Automatic schema loading from `schema.sql` (optional)
 - Graceful fallback to JSON log/backup when SQLite is unavailable
 - Self-recovery attempts when corruption is detected
 - Optional integration with ErrorEngine for structured logging
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, Union

import aiosqlite

try:
    import aiofiles  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    aiofiles = None  # type: ignore

try:
    from core.engines.error_engine import get_error_engine
except Exception:  # pragma: no cover - optional dependency
    get_error_engine = None


class StorageEngine:
    """
    Unified asynchronous persistence layer.

    Parameters:
        db_path: path to SQLite database file.
        json_backup: line-delimited JSON fallback file.
        schema_file: optional SQL schema to bootstrap the database.
    """

    def __init__(
        self,
        *,
        db_path: str = "data/database.db",
        json_backup: str = "data/storage_backup.json",
        schema_file: str = "data/schema.sql",
    ) -> None:
        self.db_path = db_path
        self.json_backup = json_backup
        self.schema_file = schema_file
        self._lock = asyncio.Lock()
        self._error_engine = get_error_engine() if get_error_engine else None

        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """Ensure database exists and schema is present."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute("PRAGMA synchronous=NORMAL;")
                await self._apply_schema(db)
        except Exception as exc:
            await self._log_internal(exc, "StorageEngine.initialize")
            await self._recover_database()

    async def _apply_schema(self, db: aiosqlite.Connection) -> None:
        if not self.schema_file or not Path(self.schema_file).exists():
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT,
                    message TEXT,
                    traceback TEXT,
                    timestamp TEXT,
                    context TEXT
                )
                """
            )
            await db.commit()
            return

        try:
            if aiofiles is not None:
                async with aiofiles.open(self.schema_file, "r", encoding="utf-8") as fh:  # type: ignore[attr-defined]
                    sql = await fh.read()
            else:
                sql = await asyncio.to_thread(Path(self.schema_file).read_text, encoding="utf-8")
            await db.executescript(sql)
            await db.commit()
        except Exception as exc:  # pragma: no cover - schema errors should be logged
            await self._log_internal(exc, "StorageEngine._apply_schema")

    # ------------------------------------------------------------------
    # Core query helpers
    # ------------------------------------------------------------------
    async def execute(
        self,
        query: str,
        params: Optional[Union[Sequence[Any], Tuple[Any, ...]]] = None,
        *,
        commit: bool = True,
    ) -> bool:
        """Execute a write query with automatic recovery on failure."""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("PRAGMA foreign_keys=ON;")
                    await db.execute(query, params or ())
                    if commit:
                        await db.commit()
                return True
            except aiosqlite.Error as exc:
                await self._log_internal(exc, "StorageEngine.execute")
                await self._recover_database()
                return False
            except Exception as exc:
                await self._log_internal(exc, "StorageEngine.execute:unexpected")
                return False

    async def fetch(
        self,
        query: str,
        params: Optional[Union[Sequence[Any], Tuple[Any, ...]]] = None,
    ) -> Optional[list]:
        """Execute a read query. Falls back to JSON snapshot for specific tables."""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(query, params or ())
                    rows = await cursor.fetchall()
                    await cursor.close()
                    return rows
            except aiosqlite.Error as exc:
                await self._log_internal(exc, "StorageEngine.fetch")
                return await self._json_fallback_fetch()
            except Exception as exc:
                await self._log_internal(exc, "StorageEngine.fetch:unexpected")
                return None

    # ------------------------------------------------------------------
    # JSON fallback utilities
    # ------------------------------------------------------------------
    async def _json_fallback_fetch(self) -> list:
        """Return records from the JSON backup (best effort)."""
        if not Path(self.json_backup).exists():
            return []
        try:
            return await asyncio.to_thread(self._read_json_lines)
        except Exception as exc:
            await self._log_internal(exc, "StorageEngine._json_fallback_fetch")
            return []

    def _read_json_lines(self) -> list:
        records: list = []
        with Path(self.json_backup).open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    async def _json_backup_write(self, table: str, data: Dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "table": table,
            "record": data,
        }
        try:
            backup_path = Path(self.json_backup)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._append_json_line, backup_path, payload)
        except Exception as exc:
            await self._log_internal(exc, "StorageEngine._json_backup_write")

    def _append_json_line(self, backup_path: Path, payload: Dict[str, Any]) -> None:
        with backup_path.open("a", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
            fh.write("\n")

    # ------------------------------------------------------------------
    # Higher-level helpers
    # ------------------------------------------------------------------
    async def insert_error_log(self, error_info: Dict[str, Any]) -> None:
        query = """
            INSERT INTO error_logs (error_type, message, traceback, timestamp, context)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            error_info.get("type", "Unknown"),
            error_info.get("message", ""),
            error_info.get("traceback", ""),
            error_info.get("timestamp", datetime.utcnow().isoformat()),
            error_info.get("context", "Unknown"),
        )
        if not await self.execute(query, params):
            await self._json_backup_write("error_logs", error_info)

    async def insert_log_entry(self, entry: Dict[str, Any]) -> None:
        query = """
            INSERT INTO logs (timestamp, severity, context, message)
            VALUES (?, ?, ?, ?)
        """
        params = (
            entry.get("timestamp", datetime.utcnow().isoformat()),
            entry.get("severity", "INFO"),
            entry.get("context", "General"),
            entry.get("message", ""),
        )
        if not await self.execute(query, params):
            await self._json_backup_write("logs", entry)

    # ------------------------------------------------------------------
    # Health + recovery
    # ------------------------------------------------------------------
    async def ping(self) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1;")
            return True
        except Exception:
            return False

    async def _recover_database(self) -> None:
        try:
            db_path = Path(self.db_path)
            if not db_path.exists():
                await self.initialize()
                return

            backup = db_path.with_suffix(".bak")
            if backup.exists():
                backup.unlink(missing_ok=True)
            db_path.rename(backup)
            await self.initialize()
            backup.unlink(missing_ok=True)
        except Exception as exc:
            await self._log_internal(exc, "StorageEngine._recover_database")

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    async def _log_internal(self, exc: Exception, context: str) -> None:
        if not self._error_engine or not hasattr(self._error_engine, "log_error"):
            # Fall back to stderr logging
            print(f"[StorageEngine] {context}: {exc}")
            return
        try:
            maybe = self._error_engine.log_error(exc, context=context)
            if asyncio.iscoroutine(maybe):
                await maybe
        except Exception:
            print(f"[StorageEngine] error_engine.log_error failed during {context}: {exc}")
