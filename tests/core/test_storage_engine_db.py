import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from discord_bot.core.storage.storage_engine import StorageEngine


@pytest.mark.asyncio
async def test_execute_and_fetch_roundtrip(tmp_path: Path):
    db_path = tmp_path / "storage.db"
    schema = tmp_path / "schema.sql"
    schema.write_text(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            severity TEXT,
            context TEXT,
            message TEXT
        );
        """,
        encoding="utf-8",
    )

    storage = StorageEngine(db_path=db_path, schema_file=str(schema))
    await storage.initialize()

    entry = {
        "timestamp": "2024-10-26T12:00:00",
        "severity": "INFO",
        "context": "test",
        "message": "roundtrip",
    }

    await storage.insert_log_entry(entry)

    rows = await storage.fetch(
        "SELECT timestamp, severity, context, message FROM logs WHERE context = ?",
        ("test",),
    )

    assert rows is not None and len(rows) == 1
    assert rows[0][3] == "roundtrip"


@pytest.mark.asyncio
async def test_execute_handles_query_failure_and_returns_false(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "storage.db"
    storage = StorageEngine(db_path=db_path, schema_file="")

    async def broken_execute(*args, **kwargs):
        raise RuntimeError("boom")

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def commit(self):
            return None

    monkeypatch.setattr(
        "discord_bot.core.storage.storage_engine.aiosqlite.connect",
        lambda path: FakeConnection(),
    )

    result = await storage.execute("INSERT INTO logs VALUES (1)", commit=True)
    assert result is False


