from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from discord_bot.core.engines.screenshot_processor import RankingCategory, StageType


DAY_TO_CATEGORY: Dict[int, RankingCategory] = {
    1: RankingCategory.CONSTRUCTION,
    2: RankingCategory.RESEARCH,
    3: RankingCategory.RESOURCE_MOB,
    4: RankingCategory.HERO,
    5: RankingCategory.TROOP_TRAINING,
}


def category_from_day(day_number: Optional[int]) -> RankingCategory:
    """Map a numeric day to its ranking category."""
    if day_number is None:
        return RankingCategory.UNKNOWN
    return DAY_TO_CATEGORY.get(day_number, RankingCategory.UNKNOWN)


@dataclass
class KVKRow:
    """A parsed row candidate extracted from MMOCR output."""

    raw_line: str
    rank: Optional[int]
    score: Optional[int]
    player_name: Optional[str]
    guild_tag: Optional[str]
    confidence: float = 0.0


@dataclass
class KVKParsedResult:
    """Structured OCR result returned by the KVK OCR pipeline."""

    player_names: List[str]
    scores: List[int]
    ranks: List[int]
    stage_type: StageType
    day_number: Optional[int]
    confidence: float
    corrections_applied: List[str] = field(default_factory=list)
    fields_missing: List[str] = field(default_factory=list)
    raw_text: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """Check whether the primary fields (rank, score, player_name) are populated."""
        incomplete = {"rank", "score", "player_name"} & set(self.fields_missing)
        return not incomplete
