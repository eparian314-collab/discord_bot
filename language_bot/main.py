from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap_paths() -> Path:
    """Ensure the project root is available on sys.path."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root


def main() -> None:
    """Launch LanguageBot directly via its runner."""
    _bootstrap_paths()
    os.environ.setdefault("BOT_PROFILE", "language")

    from language_bot.core.error_engine import ErrorEngine

    error_engine = ErrorEngine()
    error_engine.catch_uncaught()

    # Import the package runner explicitly to avoid self-import recursion
    from language_bot.runner import run_language_bot

    run_language_bot()


if __name__ == "__main__":
    main()
