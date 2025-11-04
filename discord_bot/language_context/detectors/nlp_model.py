"""
Lightweight NLP processor for translation pipeline.

Responsibilities:
- normalize unicode and quotes
- collapse excessive whitespace while preserving paragraphs
- prevent accidental pings in Discord output (zero-width-space after @ and for @everyone/@here)
- safe trimming to provider-friendly length limits
- light postprocessing (trim trailing spaces, normalize punctuation spacing)
- stateless and concurrency-safe (no per-call shared mutation)

This processor is intentionally conservative: it prepares text for translation and
cleans translation output for display. It does NOT call external services or
perform any I/O. Inject into your TranslationOrchestrator as `nlp_processor`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Tuple, Optional


DEFAULT_MAX_INPUT_CHARS = 4000  # conservative default, adjust per provider limits


class NLPProcessor:
    def __init__(self, *, max_input_chars: int = DEFAULT_MAX_INPUT_CHARS) -> None:
        self.max_input_chars = int(max_input_chars or DEFAULT_MAX_INPUT_CHARS)

        # precompiled regexes for speed
        self._re_multispace = re.compile(r"[ \t]{2,}")
        self._re_multine = re.compile(r"\n{3,}")
        self._re_mention = re.compile(r"@(?P<name>everyone|here)\b", flags=re.IGNORECASE)
        self._re_at = re.compile(r"@")  # generic '@' occurrences
        self._re_curly_quotes = re.compile(r"[""„‟«»❝❞❮❯]")
        self._re_single_curly = re.compile(r"[''‚‛❛❜]")
        self._re_backticks = re.compile(r"`{3,}")  # triple or more backticks
        self._re_leading_trailing_ws = re.compile(r"^\s+|\s+$")
        self._re_space_before_punct = re.compile(r"\s+([,.:;!?%])")
        self._re_multidots = re.compile(r"\.{3,}")

    def preprocess(self, text: Optional[str]) -> str:
        """
        Prepare text before sending to translation providers.

        - Normalizes unicode (NFKC)
        - Converts curly quotes to straight quotes
        - Collapses excessive spaces and newlines while preserving paragraphs
        - Prevents accidental Discord pings (@everyone, @here, and generic @) by inserting
          a zero-width space after '@'
        - Protects long sequences of backticks by converting them to a safe marker
        - Trims to max_input_chars, preferring to cut at a newline boundary when possible
        """
        if not text:
            return ""

        t = str(text)

        # Unicode normalization
        t = unicodedata.normalize("NFKC", t)

        # Convert common curly quotes to straight equivalents
        t = self._re_curly_quotes.sub('"', t)
        t = self._re_single_curly.sub("'", t)

        # Normalize ellipses to three dots
        t = self._re_multidots.sub("...", t)

        # Collapse multiple spaces but keep single newlines/paragraph breaks
        t = self._re_multispace.sub(" ", t)
        t = self._re_multine.sub("\n\n", t)

        # Strip leading/trailing whitespace
        t = self._re_leading_trailing_ws.sub("", t)

        # Protect Discord mass-mentions explicitly
        t = self._re_mention.sub(lambda m: "@\u200b" + m.group("name"), t)

        # Insert zero-width space after any remaining '@' to reduce chance of mention
        # This will also affect email addresses; we keep it because translations shouldn't trigger pings.
        t = self._re_at.sub("@\u200b", t)

        # Protect long sequences of backticks by reducing to exactly three to avoid provider confusion
        # This helps keep code blocks stable across translations.
        t = self._re_backticks.sub("```", t)

        # Trim safely to max chars. Prefer to trim at last newline before limit so sentences/blocks are preserved.
        if len(t) > self.max_input_chars:
            # try to cut at last double newline within limit for better chunking
            cut_point = t.rfind("\n\n", 0, self.max_input_chars)
            if cut_point == -1:
                cut_point = self.max_input_chars
            t = t[:cut_point].rstrip() + "\n\n..."  # indicate truncation

        return t

    def postprocess(self, text: Optional[str]) -> str:
        """
        Clean translated output before display.

        - Normalize unicode again
        - Remove zero-width spaces used to prevent pings (so display looks natural)
        - Normalize spacing before punctuation
        - Collapse excessive newlines to a maximum of two
        - Ensure code fences remain triple-backticks
        """
        if not text:
            return ""

        t = str(text)

        # Unicode normalize
        t = unicodedata.normalize("NFKC", t)

        # Remove zero-width spaces we added to prevent accidental pings (U+200B)
        t = t.replace("\u200b", "")

        # Normalize space before punctuation (e.g., "hello  ," -> "hello,")
        t = self._re_space_before_punct.sub(r"\1", t)

        # Restore triple backticks sequences (collapse excessive)
        t = self._re_backticks.sub("```", t)

        # Trim leading/trailing whitespace
        t = self._re_leading_trailing_ws.sub("", t)

        # Collapse excessive newlines
        t = self._re_multine.sub("\n\n", t)

        return t

    def split_into_chunks(self, text: Optional[str], *, max_size: Optional[int] = None) -> Tuple[str, ...]:
        """
        Utility: split text into chunked segments not exceeding max_size.
        Returns a tuple of chunks. Default max_size uses self.max_input_chars.

        Splitting tries to preserve paragraph boundaries.
        """
        if not text:
            return tuple()

        t = str(text)
        max_size = int(max_size or self.max_input_chars)
        if len(t) <= max_size:
            return (t,)

        parts = []
        start = 0
        while start < len(t):
            end = min(start + max_size, len(t))
            if end < len(t):
                # attempt to cut at last paragraph/newline within the window
                cut = t.rfind("\n\n", start, end)
                if cut <= start:
                    cut = t.rfind("\n", start, end)
                if cut <= start:
                    cut = end
            else:
                cut = end
            parts.append(t[start:cut].rstrip())
            start = cut
        return tuple(parts)

