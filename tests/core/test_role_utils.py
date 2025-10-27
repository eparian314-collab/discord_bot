"""
Tests for role utility functions.
"""
import os
from unittest.mock import MagicMock

import pytest

from discord_bot.core.utils.role_utils import (
    get_helper_role_id,
    has_helper_role,
    is_admin_or_helper,
    is_bot_owner,
    is_server_owner,
)


def test_get_helper_role_id_when_set(monkeypatch):
    """Test getting helper role ID from environment."""
    monkeypatch.setenv("HELPER_ROLE_ID", "123456789")
    assert get_helper_role_id() == 123456789


def test_get_helper_role_id_when_not_set(monkeypatch):
    """Test getting helper role ID when not configured."""
    monkeypatch.delenv("HELPER_ROLE_ID", raising=False)
    assert get_helper_role_id() is None


def test_get_helper_role_id_when_invalid(monkeypatch):
    """Test getting helper role ID with invalid value."""
    monkeypatch.setenv("HELPER_ROLE_ID", "not_a_number")
    assert get_helper_role_id() is None


def test_is_server_owner_true():
    """Test server owner check returns True for owner."""
    user = MagicMock()
    user.id = 12345
    
    guild = MagicMock()
    guild.owner_id = 12345
    
    assert is_server_owner(user, guild) is True


def test_is_server_owner_false():
    """Test server owner check returns False for non-owner."""
    user = MagicMock()
    user.id = 12345
    
    guild = MagicMock()
    guild.owner_id = 99999
    
    assert is_server_owner(user, guild) is False


def test_is_bot_owner_true(monkeypatch):
    """Test bot owner check returns True for configured owner."""
    monkeypatch.setenv("OWNER_IDS", "111,222,333")
    
    user = MagicMock()
    user.id = 222
    
    assert is_bot_owner(user) is True


def test_is_bot_owner_false(monkeypatch):
    """Test bot owner check returns False for non-owner."""
    monkeypatch.setenv("OWNER_IDS", "111,222,333")
    
    user = MagicMock()
    user.id = 999
    
    assert is_bot_owner(user) is False


def test_is_bot_owner_not_configured(monkeypatch):
    """Test bot owner check when OWNER_IDS not set."""
    monkeypatch.delenv("OWNER_IDS", raising=False)
    
    user = MagicMock()
    user.id = 123
    
    assert is_bot_owner(user) is False


def test_has_helper_role_true(monkeypatch):
    """Test helper role check returns True when user has role."""
    monkeypatch.setenv("HELPER_ROLE_ID", "777")
    
    role1 = MagicMock()
    role1.id = 666
    
    role2 = MagicMock()
    role2.id = 777
    
    user = MagicMock()
    user.roles = [role1, role2]
    
    assert has_helper_role(user) is True


def test_has_helper_role_false(monkeypatch):
    """Test helper role check returns False when user doesn't have role."""
    monkeypatch.setenv("HELPER_ROLE_ID", "777")
    
    role1 = MagicMock()
    role1.id = 666
    
    user = MagicMock()
    user.roles = [role1]
    
    assert has_helper_role(user) is False


def test_has_helper_role_not_configured(monkeypatch):
    """Test helper role check when role not configured."""
    monkeypatch.delenv("HELPER_ROLE_ID", raising=False)
    
    user = MagicMock()
    user.roles = []
    
    assert has_helper_role(user) is False


def test_is_admin_or_helper_server_owner(monkeypatch):
    """Test admin/helper check for server owner."""
    monkeypatch.delenv("OWNER_IDS", raising=False)
    monkeypatch.delenv("HELPER_ROLE_ID", raising=False)
    
    user = MagicMock()
    user.id = 12345
    user.roles = []
    
    guild = MagicMock()
    guild.owner_id = 12345
    
    assert is_admin_or_helper(user, guild) is True


def test_is_admin_or_helper_bot_owner(monkeypatch):
    """Test admin/helper check for bot owner."""
    monkeypatch.setenv("OWNER_IDS", "12345")
    monkeypatch.delenv("HELPER_ROLE_ID", raising=False)
    
    user = MagicMock()
    user.id = 12345
    user.roles = []
    
    guild = MagicMock()
    guild.owner_id = 99999
    
    assert is_admin_or_helper(user, guild) is True


def test_is_admin_or_helper_has_helper_role(monkeypatch):
    """Test admin/helper check for user with helper role."""
    monkeypatch.delenv("OWNER_IDS", raising=False)
    monkeypatch.setenv("HELPER_ROLE_ID", "777")
    
    role = MagicMock()
    role.id = 777
    
    user = MagicMock()
    user.id = 12345
    user.roles = [role]
    
    guild = MagicMock()
    guild.owner_id = 99999
    
    assert is_admin_or_helper(user, guild) is True


def test_is_admin_or_helper_regular_user(monkeypatch):
    """Test admin/helper check for regular user."""
    monkeypatch.delenv("OWNER_IDS", raising=False)
    monkeypatch.setenv("HELPER_ROLE_ID", "777")
    
    role = MagicMock()
    role.id = 666
    
    user = MagicMock()
    user.id = 12345
    user.roles = [role]
    
    guild = MagicMock()
    guild.owner_id = 99999
    
    assert is_admin_or_helper(user, guild) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
