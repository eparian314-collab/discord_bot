"""
Run this to sanitize all .py files to UTF-8 (no BOM, no smart quotes).
Use once or include in startup sequence.
"""

from __future__ import annotations
import os
import re

ROOT = os.path.dirname(os.path.dirname(__file__))  # points to /discord_bot_v2/discord_bot

BAD_CHARS = {
    "\u2013": "-",  # � en dash
    "\u2014": "-",  # � em dash
    "\u2018": "'",  # � left single quote
    "\u2019": "'",  # � right single quote
    "\u201c": '"',  # � left double quote
    "\u201d": '"',  # � right double quote
    "\ufeff": "",   # BOM
}


def sanitize_file(path: str):
    try:
        with open(path, "rb") as f:
            raw = f.read()

        # Remove BOM if present
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]

        text = raw.decode("utf-8", errors="replace")

        # Replace smart quotes & invalid chars
        for bad, fixed in BAD_CHARS.items():
            if bad in text:
                text = text.replace(bad, fixed)

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

        print(f"[CLEAN] {path}")

    except Exception as e:
        print(f"[SKIP] {path} ({e})")


def run():
    for root, dirs, files in os.walk(ROOT):
        # Skip virtual environments and other generated directories
        dirs[:] = [d for d in dirs if d not in {".venv", "__pycache__"}]
        for file in files:
            if file.endswith(".py"):
                sanitize_file(os.path.join(root, file))


if __name__ == "__main__":
    run()
