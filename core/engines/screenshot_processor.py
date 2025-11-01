"""
Screenshot Processing Engine for Top Heroes Rankings.

Uses OCR (Optical Character Recognition) to extract ranking data from game screenshots.
"""

from __future__ import annotations
import io
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class StageType(Enum):
    """Event stage types."""
    PREP = "Prep Stage"
    WAR = "War Stage"
    UNKNOWN = "Unknown"


class RankingCategory(Enum):
    """Event day categories."""
    CONSTRUCTION = "Construction Day"  # Day 1
    RESEARCH = "Research Day"  # Day 2
    RESOURCE_MOB = "Resource and Mob Day"  # Day 3
    HERO = "Hero Day"  # Day 4
    TROOP_TRAINING = "Troop Training Day"  # Day 5
    UNKNOWN = "Unknown"


@dataclass
class RankingData:
    """Extracted ranking data from screenshot."""
    
    # User info
    user_id: str
    username: str
    guild_tag: Optional[str]  # 3-letter guild tag (e.g., "TAO")
    
    # Event info
    event_week: str  # "YYYY-WW" format for event week tracking
    stage_type: StageType
    day_number: Optional[int]  # 1-5 for which day
    category: RankingCategory
    
    # Ranking info
    rank: int  # Overall rank position
    score: int  # Points/score
    player_name: Optional[str]  # In-game player name from screenshot
    
    # Metadata
    submitted_at: datetime
    screenshot_url: Optional[str] = None
    guild_id: Optional[str] = None
    kvk_run_id: Optional[int] = None
    is_test_run: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'guild_tag': self.guild_tag,
            'event_week': self.event_week,
            'stage_type': self.stage_type.value,
            'day_number': self.day_number,
            'category': self.category.value,
            'rank': self.rank,
            'score': self.score,
            'player_name': self.player_name,
            'submitted_at': self.submitted_at.isoformat(),
            'screenshot_url': self.screenshot_url,
            'guild_id': self.guild_id,
            'kvk_run_id': self.kvk_run_id,
            'is_test_run': int(self.is_test_run),
        }


class ScreenshotProcessor:
    """Process Top Heroes ranking screenshots to extract data."""
    
    def __init__(self):
        self.available = HAS_PIL and HAS_OCR
    
    def _get_current_event_week(self, submitted_at: Optional[datetime] = None) -> str:
        """
        Get current event week in YYYY-WW format.
        
        Events run Monday-Sunday (7 days: 5 event days + 1 war day + 1 rest).
        Week starts on Monday.
        
        Args:
            submitted_at: Optional datetime, defaults to now
            
        Returns:
            Event week string like "2025-43"
        """
        dt = submitted_at or datetime.utcnow()
        # ISO week starts on Monday (1=Monday, 7=Sunday)
        year, week, _ = dt.isocalendar()
        return f"{year}-{week:02d}"
        
    async def process_screenshot(
        self,
        image_data: bytes,
        user_id: str,
        username: str,
        guild_id: Optional[str] = None
    ) -> Optional[RankingData]:
        """
        Process a screenshot and extract ranking data.
        
        Args:
            image_data: Raw image bytes
            user_id: Discord user ID
            username: Discord username
            guild_id: Discord guild ID
            
        Returns:
            RankingData if successful, None if processing fails
        """
        if not self.available:
            raise RuntimeError("PIL or pytesseract not installed. Install with: pip install Pillow pytesseract")
        
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Extract text from image
            text = pytesseract.image_to_string(image)
            
            # Parse the extracted text
            stage_type = self._extract_stage_type(text)
            day_number = self._extract_day_number(text)
            category = self._get_category_from_day(day_number) if day_number else RankingCategory.UNKNOWN
            rank = self._extract_rank(text)
            score = self._extract_score(text)
            player_name = self._extract_player_name(text)
            guild_tag = self._extract_guild_tag(text)
            
            if rank is None or score is None:
                return None
            
            # Get current event week
            event_week = self._get_current_event_week(datetime.utcnow())
            
            return RankingData(
                user_id=user_id,
                username=username,
                guild_tag=guild_tag,
                event_week=event_week,
                stage_type=stage_type,
                day_number=day_number,
                category=category,
                rank=rank,
                score=score,
                player_name=player_name,
                submitted_at=datetime.utcnow(),
                guild_id=guild_id
            )
            
        except Exception:
            return None
    
    def _extract_stage_type(self, text: str) -> StageType:
        """Extract stage type from OCR text."""
        text_lower = text.lower()
        if 'prep stage' in text_lower:
            return StageType.PREP
        elif 'war stage' in text_lower:
            return StageType.WAR
        return StageType.UNKNOWN
    
    def _extract_day_number(self, text: str) -> Optional[int]:
        """Extract which day of the event (1-5)."""
        # Look for day indicators - buttons labeled 1-5
        for day in range(1, 6):
            # Look for patterns like "day 1", "1", etc.
            if re.search(rf'\b{day}\b', text):
                return day
        return None
    
    def _get_category_from_day(self, day_number: Optional[int]) -> RankingCategory:
        """Map day number to category."""
        category_map = {
            1: RankingCategory.CONSTRUCTION,
            2: RankingCategory.RESEARCH,
            3: RankingCategory.RESOURCE_MOB,
            4: RankingCategory.HERO,
            5: RankingCategory.TROOP_TRAINING
        }
        return category_map.get(day_number, RankingCategory.UNKNOWN)
    
    def _extract_guild_tag(self, text: str) -> Optional[str]:
        """
        Extract 3-letter guild tag from player name.
        
        Format: "#10435 [TAO] Mars" -> "TAO"
        """
        # Look for 3-letter tags in brackets or parentheses
        tag_patterns = [
            r'\[([A-Z]{3})\]',  # [TAO]
            r'\(([A-Z]{3})\)',  # (TAO)
            r'#\d+\s+([A-Z]{3})\s',  # #10435 TAO Mars
        ]
        
        for pattern in tag_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_player_name(self, text: str) -> Optional[str]:
        """
        Extract player name from screenshot.
        
        Format: "#10435 [TAO] Mars" -> "Mars"
        """
        # Look for pattern: #number [TAG] Name
        name_patterns = [
            r'#\d+\s+\[([A-Z]{3})\]\s+(\w+)',  # #10435 [TAO] Mars
            r'#\d+\s+\(([A-Z]{3})\)\s+(\w+)',  # #10435 (TAO) Mars
            r'#\d+\s+([A-Z]{3})\s+(\w+)',  # #10435 TAO Mars
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                # Return the name (last group)
                return match.group(match.lastindex)
        
        # Fallback: look for any name-like text after numbers
        fallback = re.search(r'#\d+.*?([A-Z][a-z]+)', text)
        if fallback:
            return fallback.group(1)
        
        return None
    
    def _extract_rank(self, text: str) -> Optional[int]:
        """Extract overall rank number."""
        # Look for rank patterns like "#10435" or "Rank: 10435"
        rank_patterns = [
            r'#(\d+)',
            r'rank[:\s]+(\d+)',
            r'overall[:\s]+(\d+)',
        ]
        
        for pattern in rank_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _extract_score(self, text: str) -> Optional[int]:
        """Extract score/points."""
        # Look for large numbers that represent scores
        # Scores in your screenshots are like: 28,200,103 or 87,653,088
        score_patterns = [
            r'points?[:\s]+([\d,]+)',
            r'score[:\s]+([\d,]+)',
            r'(\d{1,3}(?:,\d{3})+)',  # Numbers with commas
        ]
        
        for pattern in score_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Get the largest number (likely the score)
                scores = []
                for match in matches:
                    try:
                        score = int(match.replace(',', ''))
                        if score > 1000:  # Filter out small numbers
                            scores.append(score)
                    except ValueError:
                        continue
                
                if scores:
                    return max(scores)
        
        return None
    
    async def validate_screenshot(self, image_data: bytes) -> tuple[bool, str]:
        """
        Validate if screenshot contains ranking data.
        
        Returns:
            (is_valid, error_message)
        """
        if not self.available:
            return False, "OCR not available. Install Pillow and pytesseract."
        
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Check image size (should be reasonable)
            width, height = image.size
            if width < 100 or height < 100:
                return False, "Image too small. Please provide a clear screenshot."
            
            if width > 4000 or height > 4000:
                return False, "Image too large. Please provide a normal screenshot."
            
            # Try to extract text
            text = pytesseract.image_to_string(image)
            
            if not text or len(text.strip()) < 10:
                return False, "Could not read text from image. Please provide a clearer screenshot."
            
            # Check for ranking-related keywords
            keywords = ['rank', 'stage', 'points', 'score']
            text_lower = text.lower()
            if not any(keyword in text_lower for keyword in keywords):
                return False, "Screenshot doesn't appear to contain ranking data."
            
            return True, ""
            
        except Exception as e:
            return False, f"Error processing image: {str(e)}"
