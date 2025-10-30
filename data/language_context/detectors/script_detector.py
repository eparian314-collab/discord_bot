"""
Simple script-family detection helpers used by routing heuristics.

All functions are deterministic and rely solely on Unicode code-point ranges,
so they remain safe and dependency-free.
"""

from __future__ import annotations

from typing import Optional

# Unicode blocks represented as (start, end, label)
_SCRIPT_RANGES = [
    (0x0041, 0x024F, "latin"),
    (0x0400, 0x04FF, "cyrillic"),
    (0x0370, 0x03FF, "greek"),
    (0x0590, 0x05FF, "hebrew"),
    (0x0600, 0x06FF, "arabic"),
    (0x0900, 0x097F, "devanagari"),
    (0x3040, 0x30FF, "japanese"),
    (0x4E00, 0x9FFF, "cjk"),
    (0xAC00, 0xD7AF, "hangul"),
]


def detect_script_family(text: str, *, default: str = "latin") -> str:
    """
    Return the first matching script family label for `text`.
    """
    for ch in text or "":
        code = ord(ch)
        for start, end, label in _SCRIPT_RANGES:
            if start <= code <= end:
                return label
    return default


def is_mixed_script(text: str) -> bool:
    """
    Return True when more than one script family is observed in the text.
    """
    families = set()
    for ch in text or "":
        code = ord(ch)
        for start, end, label in _SCRIPT_RANGES:
            if start <= code <= end:
                families.add(label)
                if len(families) > 1:
                    return True
                break
    return False


def primary_script(text: str) -> Optional[str]:
    """
    Convenience alias for `detect_script_family` that returns None on empty input.
    """
    if not text:
        return None
    return detect_script_family(text)
