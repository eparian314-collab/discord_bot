"""
Run this to sanitize all .py files to UTF-8 (no BOM, no smart quotes).
Use once or include in startup sequence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent.parent

BAD_CHARS = {
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\ufeff": "",   # BOM
}


def sanitize_file(path: Path, verbose: bool = False) -> Tuple[bool, str | None]:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8", errors="replace")
        for bad, fixed in BAD_CHARS.items():
            if bad in text:
                text = text.replace(bad, fixed)
        path.write_text(text, encoding="utf-8", newline="\n")
        if verbose:
            print(f"[CLEAN] {path}")
        return True, None
    except Exception as exc:  # pylint: disable=broad-except
        error = f"{path} ({exc})"
        if verbose:
            print(f"[SKIP] {error}")
        return False, error


def run(verbose: bool = False) -> None:
    cleaned = 0
    errors: list[str] = []

    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {".venv", "__pycache__"}]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            success, error = sanitize_file(Path(root) / filename, verbose=verbose)
            if success:
                cleaned += 1
            elif error:
                errors.append(error)

    summary_prefix = "[OK]"
    print(f"{summary_prefix} Sanitized {cleaned} Python files")
    if errors:
        print(f"[WARN] Failed to sanitize {len(errors)} files")
        for error in errors:
            print(f"  - {error}")


if __name__ == "__main__":
    run(verbose=True)
