"""
Tests for message cleanup system.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from discord_bot.core.engines.session_manager import SessionManager
from discord_bot.core.engines.cleanup_engine import CleanupEngine


class TestSessionManager:
    """Tests for SessionManager."""

    def test_session_manager_init(self, tmp_path):
        """Test session manager initialization."""
        session_file = tmp_path / "session_test.json"
        manager = SessionManager(session_file=session_file)
        
        assert manager.session_file == session_file
        assert manager.current_session_id is None
        assert manager.current_session_start is None
        assert manager.last_session_start is None

    def test_start_new_session(self, tmp_path):
        """Test starting a new session."""
        session_file = tmp_path / "session_test.json"
        manager = SessionManager(session_file=session_file)
        
        # Start first session
        session_id = manager.start_new_session()
        
        assert session_id is not None
        assert manager.current_session_id == session_id
        assert manager.current_session_start is not None
        assert session_file.exists()

    def test_session_persistence(self, tmp_path):
        """Test that session data persists across instances."""
        session_file = tmp_path / "session_test.json"
        
        # First instance
        manager1 = SessionManager(session_file=session_file)
        session_id1 = manager1.start_new_session()
        start_time1 = manager1.current_session_start
        
        # Second instance (simulates restart)
        manager2 = SessionManager(session_file=session_file)
        
        assert manager2.last_session_start == start_time1
        assert manager2.last_session_id == session_id1

    def test_get_last_session_time_first_run(self, tmp_path):
        """Test get_last_session_time on first run."""
        session_file = tmp_path / "session_test.json"
        manager = SessionManager(session_file=session_file)
        
        assert manager.get_last_session_time() is None


class TestCleanupEngine:
    """Tests for CleanupEngine."""

    def test_cleanup_engine_init(self):
        """Test cleanup engine initialization."""
        engine = CleanupEngine()
        
        assert engine.config["enabled"] is True
        assert engine.config["skip_recent_minutes"] == 30
        assert "messages_deleted" in engine.stats

    def test_should_preserve_pinned_message(self):
        """Test that pinned messages are preserved."""
        engine = CleanupEngine()
        
        message = MagicMock()
        message.pinned = True
        message.content = ""
        message.reactions = []
        message.created_at = datetime.now(timezone.utc)
        
        should_preserve, reason = engine._should_preserve_message(message)
        
        assert should_preserve is True
        assert reason == "pinned"

    def test_should_preserve_keyword_message(self):
        """Test that messages with preserve keywords are kept."""
        engine = CleanupEngine()
        
        message = MagicMock()
        message.pinned = False
        message.content = "DO NOT DELETE this message"
        message.reactions = []
        message.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        should_preserve, reason = engine._should_preserve_message(message)
        
        assert should_preserve is True
        assert "keyword" in reason

    def test_should_preserve_recent_message(self):
        """Test that recent messages are preserved."""
        engine = CleanupEngine(config={"skip_recent_minutes": 30})
        
        message = MagicMock()
        message.pinned = False
        message.content = "Normal message"
        message.reactions = []
        message.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        should_preserve, reason = engine._should_preserve_message(message)
        
        assert should_preserve is True
        assert reason == "too_recent"

    def test_should_not_preserve_old_message(self):
        """Test that old messages are not preserved."""
        engine = CleanupEngine(config={"skip_recent_minutes": 30})
        
        message = MagicMock()
        message.pinned = False
        message.content = "Old message"
        message.reactions = []
        message.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        
        should_preserve, reason = engine._should_preserve_message(message)
        
        assert should_preserve is False
        assert reason == ""

    def test_should_skip_blocklisted_channel(self):
        """Test that blocklisted channels are skipped."""
        engine = CleanupEngine(config={"skip_channels": ["bot-logs", "announcements"]})
        
        channel = MagicMock()
        channel.name = "bot-logs"
        channel.guild.me = MagicMock()
        permissions = MagicMock()
        permissions.read_message_history = True
        permissions.manage_messages = True
        channel.permissions_for.return_value = permissions
        
        should_skip, reason = engine._should_skip_channel(channel)
        
        assert should_skip is True
        assert "blocklist" in reason

    def test_should_skip_no_permissions(self):
        """Test that channels without permissions are skipped."""
        engine = CleanupEngine()
        
        channel = MagicMock()
        channel.name = "general"
        channel.guild.me = MagicMock()
        permissions = MagicMock()
        permissions.read_message_history = False
        permissions.manage_messages = True
        channel.permissions_for.return_value = permissions
        
        should_skip, reason = engine._should_skip_channel(channel)
        
        assert should_skip is True
        assert "permission" in reason

    @pytest.mark.asyncio
    async def test_cleanup_channel(self):
        """Test cleanup of a single channel."""
        engine = CleanupEngine(config={"rate_limit_delay": 0})
        
        # Mock channel and messages
        channel = MagicMock()
        channel.name = "test-channel"
        
        bot_user = MagicMock()
        bot_user.id = 123456
        
        # Create mock messages
        messages = []
        for i in range(5):
            msg = MagicMock()
            msg.id = i
            msg.author.id = bot_user.id
            msg.pinned = False
            msg.content = f"Message {i}"
            msg.reactions = []
            msg.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
            msg.delete = AsyncMock()
            messages.append(msg)
        
        # Mock history
        async def mock_history(limit=None, after=None):
            for msg in messages:
                yield msg
        
        channel.history = mock_history
        
        # Run cleanup
        deleted = await engine.cleanup_channel(channel, bot_user)
        
        assert deleted == 5
        for msg in messages:
            msg.delete.assert_called_once()


class TestCleanupIntegration:
    """Integration tests for cleanup system."""

    def test_session_and_cleanup_workflow(self, tmp_path):
        """Test complete workflow: session tracking -> cleanup."""
        session_file = tmp_path / "session_test.json"
        
        # Simulate first bot run
        manager1 = SessionManager(session_file=session_file)
        session1_id = manager1.start_new_session()
        session1_time = manager1.get_current_session_time()
        
        # Simulate bot restart
        manager2 = SessionManager(session_file=session_file)
        last_session_time = manager2.get_last_session_time()
        
        # Verify last session matches first session
        assert last_session_time == session1_time
        
        # Start new session
        session2_id = manager2.start_new_session()
        
        # Verify session IDs are different
        assert session1_id != session2_id
