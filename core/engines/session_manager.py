"""
Session Context Manager for HippoBot.

Tracks bot restart timestamps to enable cleanup of old messages
from previous deployment sessions.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from discord_bot.core.engines.base.logging_utils import get_logger

logger = get_logger("session_manager")

# Session state file location
SESSION_FILE = Path(__file__).parent.parent.parent / "data" / "session_state.json"


class SessionManager:
    """Manages bot session lifecycle and timestamp tracking."""

    def __init__(self, session_file: Optional[Path] = None):
        """Initialize session manager.
        
        Args:
            session_file: Path to session state file (defaults to data/session_state.json)
        """
        self.session_file = session_file or SESSION_FILE
        self.current_session_id: Optional[str] = None
        self.current_session_start: Optional[datetime] = None
        self.last_session_start: Optional[datetime] = None
        self.last_session_id: Optional[str] = None
        
        # Ensure data directory exists
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load previous session data
        self._load_session_data()

    def _load_session_data(self) -> None:
        """Load previous session data from file."""
        if not self.session_file.exists():
            logger.info("No previous session data found (first run)")
            return
        
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            last_start_str = data.get("last_session_start")
            if last_start_str:
                self.last_session_start = datetime.fromisoformat(last_start_str)
            
            self.last_session_id = data.get("last_session_id")
            
            logger.info(
                "Loaded previous session: %s (started %s)",
                self.last_session_id,
                self.last_session_start
            )
        
        except Exception as e:
            logger.error("Failed to load session data: %s", e)

    def _save_session_data(self) -> None:
        """Save current session data to file."""
        if not self.current_session_start:
            logger.warning("No current session to save")
            return
        
        try:
            data = {
                "last_session_start": self.current_session_start.isoformat(),
                "last_session_id": self.current_session_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Saved session data: %s", self.current_session_id)
        
        except Exception as e:
            logger.error("Failed to save session data: %s", e)

    def start_new_session(self) -> str:
        """Start a new bot session.
        
        Returns:
            str: New session ID (UUID)
        """
        # Generate new session
        self.current_session_id = str(uuid.uuid4())
        self.current_session_start = datetime.now(timezone.utc)
        
        # Save to file
        self._save_session_data()
        
        logger.info(
            "Started new session: %s at %s",
            self.current_session_id,
            self.current_session_start
        )
        
        return self.current_session_id

    def get_last_session_time(self) -> Optional[datetime]:
        """Get the start time of the previous session.
        
        Returns:
            datetime: Last session start time (UTC), or None if first run
        """
        return self.last_session_start

    def get_current_session_time(self) -> Optional[datetime]:
        """Get the start time of the current session.
        
        Returns:
            datetime: Current session start time (UTC)
        """
        return self.current_session_start

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID.
        
        Returns:
            str: Current session UUID
        """
        return self.current_session_id


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance.
    
    Returns:
        SessionManager: Global session manager
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def get_last_session_time() -> Optional[datetime]:
    """Get the start time of the previous session.
    
    Returns:
        datetime: Last session start time (UTC), or None if first run
    """
    return get_session_manager().get_last_session_time()


def update_session_start() -> str:
    """Start a new session and update timestamp.
    
    Returns:
        str: New session ID
    """
    return get_session_manager().start_new_session()


def get_current_session_id() -> Optional[str]:
    """Get the current session ID.
    
    Returns:
        str: Current session UUID
    """
    return get_session_manager().get_session_id()
