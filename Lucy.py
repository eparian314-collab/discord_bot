from __future__ import annotations

"""Convenience launcher for FunBot from the repo root.

Usage (from discord_bot repo root):

    python Lucy.py

This installs FunBot requirements (idempotently) and then delegates to
the existing FunBot entrypoint in fun_bot/main.py.
"""

import subprocess
import sys
from pathlib import Path

from fun_bot.main import main as funbot_main


def _install_requirements() -> None:
    root = Path(__file__).resolve().parent
    req = root / "fun_bot" / "requirements.txt"
    if not req.is_file():
        return
    print("[Lucy] Ensuring FunBot requirements are installed...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])


def main() -> None:
    _install_requirements()
    funbot_main()


if __name__ == "__main__":
    main()
