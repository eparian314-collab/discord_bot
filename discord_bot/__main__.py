"""
Module entry point for `python -m discord_bot`.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root() -> None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def main() -> None:
    _ensure_project_root()
    from main import main as entry_main  # noqa: WPS433 (import inside function)

    entry_main()


if __name__ == "__main__":
    main()
