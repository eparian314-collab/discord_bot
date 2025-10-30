import asyncio
import json
from pathlib import Path
import pytest

from discord_bot.core.storage.storage_engine import StorageEngine


@pytest.mark.asyncio
async def test_json_backup_write_and_read(tmp_path: Path, monkeypatch):
    # Force DB path to an invalid location to prefer JSON fallback logic
    schema = tmp_path / "schema.sql"
    schema.write_text("-- empty schema", encoding="utf-8")

    storage = StorageEngine(db_path=tmp_path / "db.sqlite3", schema_file=str(schema))

    # Simulate DB not available by monkeypatching aiosqlite import to fail
    monkeypatch.setattr(storage, "_recover_database", lambda: asyncio.sleep(0), raising=False)

    # Perform a JSON backup write through public API
    error_payload = {"message": "unit-test", "context": "test"}
    await storage._json_backup_write("error_logs", error_payload)

    # Ensure file exists and contains the JSON line
    backup_file = tmp_path / "error_logs.jsonl"
    assert backup_file.exists()
    data = [json.loads(line) for line in backup_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert data and data[-1]["message"] == "unit-test"

