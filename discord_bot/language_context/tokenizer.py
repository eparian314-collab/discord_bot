"""
Lightweight accessors for the shared language-context tokenizer.

This module exposes a `tokenize` helper that reuses the default tokenizer
from `language_context.normalizer` without forcing callers to instantiate
the full `Normalizer` class.
"""

from __future__ import annotations

from typing import List

from .normalizer import Token, default_tokenizer

__all__ = ["Token", "tokenize", "default_tokenizer"]


def tokenize(text: str) -> List[Token]:
    """Tokenize `text` using the shared default tokenizer implementation."""
    return default_tokenizer(text)


