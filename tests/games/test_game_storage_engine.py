import pytest
from discord_bot.games.storage.game_storage_engine import GameStorageEngine

@pytest.fixture
def storage_engine():
    # Use an in-memory SQLite database for testing
    engine = GameStorageEngine(db_path=":memory:")
    return engine

def test_create_tables(storage_engine):
    # Ensure tables are created without errors
    cursor = storage_engine.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "users" in tables
    assert "pokemon" in tables
    assert "battles" in tables

def test_add_user(storage_engine):
    user_id = "12345"
    storage_engine.add_user(user_id)

    cursor = storage_engine.conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    assert user is not None
    assert user[0] == user_id
    assert user[1] == 0  # total_cookies
    assert user[2] == 0  # cookies_left

def test_update_cookies(storage_engine):
    user_id = "12345"
    storage_engine.add_user(user_id)

    # Update cookies
    storage_engine.update_cookies(user_id, total_cookies=10, cookies_left=5)

    cursor = storage_engine.conn.cursor()
    cursor.execute("SELECT total_cookies, cookies_left FROM users WHERE user_id = ?", (user_id,))
    cookies = cursor.fetchone()
    assert tuple(cookies) == (10, 5)

def test_get_user_cookies(storage_engine):
    user_id = "12345"
    storage_engine.add_user(user_id)

    # Update cookies
    storage_engine.update_cookies(user_id, total_cookies=10, cookies_left=5)

    # Retrieve cookies
    cookies = storage_engine.get_user_cookies(user_id)
    assert cookies == (10, 5)

    # Test for non-existent user
    cookies = storage_engine.get_user_cookies("nonexistent")
    assert cookies == (0, 0)