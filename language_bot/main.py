from __future__ import annotations

import os
import sys
from pathlib import Path
from language_bot.core.error_engine import ErrorEngine


def _bootstrap_paths() -> Path:
    """Ensure the project root is available on sys.path."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root


def main() -> None:
    """
    Launch the HippoBot stack in language-only mode.

    This simply forces the ``BOT_PROFILE`` environment variable before reusing
    the existing root-level ``main`` module. All heavy lifting (config loading,
    event loop management, etc.) stays in one place.
    """
    _bootstrap_paths()
    os.environ.setdefault("BOT_PROFILE", "language")

    error_engine = ErrorEngine()
    error_engine.catch_uncaught()

    from main import main as root_main

    root_main()


if __name__ == "__main__":
    main()
