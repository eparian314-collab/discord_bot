from __future__ import annotations

from typing import Iterable, Optional

from .types import KVKRow


class Optimizer:
    """Pick the strongest candidate row based on completeness and confidence."""

    def select_best(self, rows: Iterable[KVKRow]) -> Optional[KVKRow]:
        best: Optional[KVKRow] = None
        best_score = -1.0
        for row in rows:
            if row is None:
                continue
            tier = row.confidence
            if row.rank and row.score and row.player_name:
                tier += 0.3
            if tier > best_score:
                best = row
                best_score = tier
        return best
