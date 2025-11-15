from __future__ import annotations

import os
import sys
from pathlib import Path
from core.error_engine import ErrorEngine


def _bootstrap_paths() -> Path:
    """Ensure project root is on sys.path for package imports."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root


def main() -> None:
    """Launch FunBot directly via its runner."""
    _bootstrap_paths()
    os.environ.setdefault("BOT_PROFILE", "fun")

    error_engine = ErrorEngine()
    error_engine.takeoff_sequence()
    error_engine.catch_uncaught()

    # Import the package runner explicitly to avoid self-import recursion
    from fun_bot.runner import run_fun_bot

    run_fun_bot()


if __name__ == "__main__":
    main()
