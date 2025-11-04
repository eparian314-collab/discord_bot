"""
Lightweight helpers for stripping noisy characters from user input.

These functions are pure and dependency-free so they can be reused by detectors,
routers, or preprocessing pipelines without dragging in heavy NLP libraries.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

# Basic emoji range (covers emoticons, transport symbols, pictographs).
_EMOJI_RE = re.compile(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001FAFF]+", flags=re.UNICODE)

# Zero-width and other invisible formatting characters that often appear in Discord text.
_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\uFEFF]")

# Discord custom emoji markup <:name:id> or <a:name:id>.
_CUSTOM_EMOJI_RE = re.compile(r"<a?:\w+:\d+>")

# Common URL pattern used for lightweight URL stripping when desired.
_URL_RE = re.compile(r"https?://\S+|www\.\S+", flags=re.IGNORECASE)

# Collapses runs of whitespace into a single space.
_WHITESPACE_RE = re.compile(r"\s+")


def remove_emojis(text: str) -> str:
    """Remove standard Unicode emoji characters."""
    return _EMOJI_RE.sub("", text or "")


def remove_custom_emojis(text: str) -> str:
    """Strip Discord-specific custom emoji tags."""
    return _CUSTOM_EMOJI_RE.sub("", text or "")


def remove_zero_width(text: str) -> str:
    """Remove zero-width or non-printing characters frequently used for spam."""
    return _ZERO_WIDTH_RE.sub("", text or "")


def remove_urls(text: str) -> str:
    """Optionally strip obvious URLs from text."""
    return _URL_RE.sub("", text or "")


def collapse_whitespace(text: str) -> str:
    """Collapse consecutive whitespace into single spaces and trim the ends."""
    return _WHITESPACE_RE.sub(" ", text or "").strip()


def strip_noise(
    text: str,
    *,
    drop_urls: bool = False,
    extra_filters: Iterable[Callable[[str], str]] = (),
) -> str:
    """
    Apply the default noise filters in a fixed order.

    Parameters:
        text: Input string to clean.
        drop_urls: If True, URLs are removed in addition to emoji/zero-width cleanup.
        extra_filters: Optional iterable of callables to run after the built-in filters.
    """
    cleaned = text or ""
    cleaned = remove_custom_emojis(cleaned)
    cleaned = remove_emojis(cleaned)
    cleaned = remove_zero_width(cleaned)
    if drop_urls:
        cleaned = remove_urls(cleaned)
    cleaned = collapse_whitespace(cleaned)
    for fn in extra_filters:
        try:
            cleaned = fn(cleaned)
        except Exception:
            # Ignore custom filter failures so noise removal remains best-effort.
            continue
    return cleaned


