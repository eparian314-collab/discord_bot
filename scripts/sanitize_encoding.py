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


def sanitize_file(path: str, verbose: bool = False) -> tuple[bool, str | None]:
    """
    Sanitize a single file.
    
    Returns:
        (success, error_message) tuple
    """
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

        if verbose:
            print(f"[CLEAN] {path}")
        
        return (True, None)

    except Exception as e:
        error = f"{path} ({e})"
        if verbose:
            print(f"[SKIP] {error}")
        return (False, error)


def run(verbose: bool = False):
    """
    Sanitize all Python files in the project.
    
    Args:
        verbose: If True, print each file processed. If False, only show summary.
    """
    cleaned = 0
    errors = []
    
    for root, dirs, files in os.walk(ROOT):
        # Skip virtual environments and other generated directories
        dirs[:] = [d for d in dirs if d not in {".venv", "__pycache__"}]
        for file in files:
            if file.endswith(".py"):
                success, error = sanitize_file(os.path.join(root, file), verbose=verbose)
                if success:
                    cleaned += 1
                else:
                    errors.append(error)
    
    # Always show summary
    if not verbose:
        print(f"✓ Sanitized {cleaned} Python files")
        if errors:
            print(f"⚠ Failed to sanitize {len(errors)} files")
            for error in errors:
                print(f"  - {error}")


if __name__ == "__main__":
    # When run directly, show all files (verbose mode)
    run(verbose=True)
