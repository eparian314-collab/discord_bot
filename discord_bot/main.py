"""
Package-level entry point shim for legacy invocations.

Historically the bot was started with ``python -m discord_bot.main``.
The core startup logic now lives in the repository root ``main.py``.
This module simply proxies the call so both entry points remain valid.
"""
from __future__ import annotations

from pathlib import Path
import importlib
import sys


def _load_root_main():
    """
    Import the top-level ``main`` module dynamically.

    Avoids circular imports by inserting the project root into ``sys.path`` on demand.
    """
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return importlib.import_module("main")


def main() -> None:
    """Delegate execution to the root ``main.main`` function."""
    root_main_module = _load_root_main()
    if hasattr(root_main_module, "main"):
        root_main_module.main()
    else:
        raise RuntimeError("Root main module does not expose a main() function")


if __name__ == "__main__":
    main()
