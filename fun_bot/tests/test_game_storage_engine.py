from __future__ import annotations

from pathlib import Path
import sys
from pathlib import Path

import pytest


# Ensure the repository root is on sys.path so that the
# `fun_bot` package can be imported regardless of the
# current working directory when pytest is invoked.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fun_bot.core.game_storage_engine import GameStorageEngine


@pytest.mark.asyncio
async def test_set_and_get_round_trips(tmp_path: Path) -> None:
    db_file = tmp_path / "test_storage.sqlite3"
    engine = GameStorageEngine(str(db_file))

    await engine.initialize()
    try:
        user_id = 123456789
        namespace = "test_namespace"
        key = "test_key"
        payload = {"wins": 5, "losses": 2, "streak": 3}

        await engine.set_user_value(user_id, namespace, key, payload)
        loaded = await engine.get_user_value(user_id, namespace, key)

        assert loaded == payload
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_get_missing_returns_default(tmp_path: Path) -> None:
    db_file = tmp_path / "test_storage.sqlite3"
    engine = GameStorageEngine(str(db_file))

    await engine.initialize()
    try:
        default = {"wins": 0}
        result = await engine.get_user_value(999, "missing", "missing", default=default)
        assert result == default
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_namespace_round_trip(tmp_path: Path) -> None:
    db_file = tmp_path / "test_storage.sqlite3"
    engine = GameStorageEngine(str(db_file))

    await engine.initialize()
    try:
        user_id = 42
        namespace = "pokemon"

        await engine.set_user_value(user_id, namespace, "pokedex", {"seen": [1, 4, 7]})
        await engine.set_user_value(user_id, namespace, "team", ["pikachu", "charizard"])

        data = await engine.get_namespace(user_id, namespace)

        assert "pokedex" in data
        assert "team" in data
        assert data["pokedex"]["seen"] == [1, 4, 7]
        assert data["team"] == ["pikachu", "charizard"]

        await engine.clear_namespace(user_id, namespace)
        cleared = await engine.get_namespace(user_id, namespace)
        assert cleared == {}
    finally:
        await engine.close()
