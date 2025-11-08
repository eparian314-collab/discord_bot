from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

from discord_bot.core.engines.screenshot_processor import StageType

from .types import KVKRow


class PostProcessor:
    """Normalize MMOCR output into structured lines and structured rows."""

    def extract_lines(self, raw_blocks: Sequence[str]) -> List[str]:
        """Clean raw text blocks and preserve line breaks that look like rows."""
        lines: List[str] = []
        for block in raw_blocks:
            cleaned = self._clean_line(block)
            if not cleaned:
                continue
            # Split on forced line breaks inside the block
            for piece in cleaned.splitlines():
                piece = piece.strip()
                if piece:
                    lines.append(piece)
        return lines

    def parse_rows(self, lines: Iterable[str]) -> List[KVKRow]:
        """Try to pull rank, score, and player data out of candidate lines."""
        rows: List[KVKRow] = []
        for line in lines:
            rank = self._parse_rank(line)
            score = self._parse_score(line)
            player_name = self._parse_player_name(line)
            guild_tag = self._parse_guild_tag(line)
            confidence = self._calc_confidence(rank, score, player_name)
            rows.append(KVKRow(
                raw_line=line,
                rank=rank,
                score=score,
                player_name=player_name,
                guild_tag=guild_tag,
                confidence=confidence,
            ))
        return rows

    def extract_stage_and_day(self, raw_text: str) -> tuple[StageType, Optional[int]]:
        """Heuristic stage/day extractor shared with ranking submissions."""
        text_lower = raw_text.lower()
        if "prep" in text_lower:
            stage = StageType.PREP
        elif "war" in text_lower:
            stage = StageType.WAR
        else:
            stage = StageType.UNKNOWN

        day = self._find_day_number(text_lower)
        return stage, day

    def _clean_line(self, line: str) -> str:
        """Remove zero-width spaces and collapse extra whitespace."""
        result = line.replace("\u200b", " ").replace("\ufeff", " ").strip()
        result = re.sub(r"[^\x00-\x7F]+", " ", result)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def _parse_rank(self, text: str) -> Optional[int]:
        """Find the leading rank in the string."""
        patterns = [r"rank[:\s]+(\d{1,5})", r"#(\d{1,5})", r"^\s*(\d{1,5})\b"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = int(match.group(1))
                except ValueError:
                    continue
                if 1 <= value <= 10000:
                    return value
        return None

    def _parse_score(self, text: str) -> Optional[int]:
        """Find a large score value with separators."""
        patterns = [
            r"score[:\s]+([\d,\.]+)",
            r"points[:\s]+([\d,\.]+)",
            r"([\d\.]{2,}[,\.\s]\d{3,})",
            r"(\d{1,3}(?:,\d{3})+)"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for candidate in matches:
                digits = re.sub(r"[^\d]", "", candidate)
                if len(digits) < 4:
                    continue
                try:
                    return int(digits)
                except ValueError:
                    continue
        return None

    def _parse_player_name(self, text: str) -> Optional[str]:
        """Attempt to locate the highlighted player name near the guild tag."""
        if match := re.search(r"\[([A-Z]{3})\]\s*([A-Za-z0-9_ ]+)", text):
            return match.group(2).strip()
        if match := re.search(r"\(([A-Z]{3})\)\s*([A-Za-z0-9_ ]+)", text):
            return match.group(2).strip()
        parts = text.split()
        if len(parts) >= 2 and parts[-1].isdigit() is False:
            return parts[-1].strip()
        return None

    def _parse_guild_tag(self, text: str) -> Optional[str]:
        if match := re.search(r"\[([A-Z]{3})\]", text):
            return match.group(1)
        if match := re.search(r"\(([A-Z]{3})\)", text):
            return match.group(1)
        return None

    def _calc_confidence(self, rank: Optional[int], score: Optional[int], player_name: Optional[str]) -> float:
        present = sum(1 for value in (rank, score, player_name) if value)
        return min(1.0, present / 3 + 0.1)

    def _find_day_number(self, text_lower: str) -> Optional[int]:
        if match := re.search(r"day\s*[:#\s-]*(\d)", text_lower):
            return int(match.group(1))
        candidates = [int(num) for num in re.findall(r"\b([1-5])\b", text_lower)]
        return candidates[-1] if candidates else None
