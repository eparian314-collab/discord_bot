from __future__ import annotations

import difflib
from typing import Iterable, List, Optional, Tuple

from .types import KVKRow


class FuzzyMatcher:
    """Apply light fuzzy matching with the guild roster to stabilize player names."""

    MATCH_THRESHOLD = 0.80

    def apply(self, rows: Iterable[KVKRow], roster: List[str]) -> Tuple[List[KVKRow], List[str]]:
        """Return rows where names may have been snapped to the roster plus summaries."""
        corrections: List[str] = []
        roster_lower = {member.lower(): member for member in roster if member}
        roster_candidates = list(roster_lower.keys())

        for row in rows:
            if not row.player_name:
                continue
            normalized = row.player_name.strip()
            if not normalized:
                continue

            best, ratio = self._find_best_match(normalized, roster_candidates)
            if best and ratio >= self.MATCH_THRESHOLD:
                canonical = roster_lower[best]
                if canonical != row.player_name:
                    corrections.append(f"Roster match: {row.player_name} -> {canonical} ({ratio:.2f})")
                    row.player_name = canonical
        return list(rows), corrections

    def _find_best_match(self, value: str, candidates: List[str]) -> Tuple[Optional[str], float]:
        if not candidates:
            return None, 0.0
        value_lower = value.lower()
        best_key: Optional[str] = None
        best_ratio = 0.0
        for candidate in candidates:
            ratio = difflib.SequenceMatcher(None, value_lower, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = candidate
        return best_key, best_ratio
