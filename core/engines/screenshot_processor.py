"""
Screenshot Processing Engine for Top Heroes Rankings.

Uses OCR (Optical Character Recognition) to extract ranking data from game screenshots.
Enhanced with smart parsing for improved accuracy and confidence scoring.
"""

from __future__ import annotations
import io
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
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

try:
    from .smart_image_parser import SmartImageParser
    HAS_SMART_PARSER = True
except ImportError:
    HAS_SMART_PARSER = False

from .openai_engine import OpenAIEngine


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


@dataclass
class OCRParseResult:
    """Structured result from an OCR parsing attempt."""
    ranking_data: Optional[RankingData] = None
    error_message: Optional[str] = None
    confidence: float = 1.0  # 0.0 to 1.0
    fields_found: List[str] = field(default_factory=list)
    fields_missing: List[str] = field(default_factory=list)
    raw_ocr_text: Optional[str] = None # To store the text for analysis

    @property
    def is_successful(self) -> bool:
        return self.ranking_data is not None and not self.fields_missing


class ScreenshotProcessor:
    """Process Top Heroes ranking screenshots to extract data."""
    
    def __init__(self, use_smart_parser: bool = True, openai_engine: Optional[OpenAIEngine] = None):
        self.available = HAS_PIL and HAS_OCR
        self.use_smart_parser = use_smart_parser and HAS_SMART_PARSER
        self.openai_engine = openai_engine
        
        if self.use_smart_parser:
            self.smart_parser = SmartImageParser()
        else:
            self.smart_parser = None

    async def process_screenshot_v2(
        self,
        image_data: bytes,
        user_id: str,
        username: str,
        guild_id: Optional[str] = None
    ) -> OCRParseResult:
        """
        Process a screenshot and extract ranking data, returning a structured result.
        """
        if not self.available:
            return OCRParseResult(error_message="OCR libraries not installed.")

        try:
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image)

            if not text.strip():
                return OCRParseResult(error_message="Could not read any text from the image.", raw_ocr_text=text)

            stage_type = self._extract_stage_type(text)
            day_number = self._extract_day_number(text)
            category = self._get_category_from_day(day_number) if day_number else RankingCategory.UNKNOWN
            rank, score, player_name, guild_tag, _ = self._extract_bottom_row_data(text)

            fields_found = []
            fields_missing = []

            if rank is not None:
                fields_found.append("rank")
            else:
                fields_missing.append("rank")

            if score is not None:
                fields_found.append("score")
            else:
                fields_missing.append("score")

            if player_name:
                fields_found.append("player_name")
            if guild_tag:
                fields_found.append("guild_tag")
            if stage_type != StageType.UNKNOWN:
                fields_found.append("stage_type")
            if day_number is not None:
                fields_found.append("day_number")

            confidence = len(fields_found) / (len(fields_found) + len(fields_missing)) if (len(fields_found) + len(fields_missing)) > 0 else 0.0

            if not fields_missing:
                ranking_data = RankingData(
                    user_id=user_id,
                    username=username,
                    guild_tag=guild_tag,
                    event_week=self._get_current_event_week(datetime.utcnow()),
                    stage_type=stage_type,
                    day_number=day_number,
                    category=category,
                    rank=rank,
                    score=score,
                    player_name=player_name,
                    submitted_at=datetime.utcnow(),
                    guild_id=guild_id
                )
                return OCRParseResult(ranking_data=ranking_data, confidence=confidence, fields_found=fields_found)
            else:
                # Create partial data for correction flow
                partial_data = RankingData(
                    user_id=user_id,
                    username=username,
                    guild_tag=guild_tag,
                    event_week=self._get_current_event_week(datetime.utcnow()),
                    stage_type=stage_type,
                    day_number=day_number,
                    category=category,
                    rank=rank or 0,
                    score=score or 0,
                    player_name=player_name,
                    submitted_at=datetime.utcnow(),
                    guild_id=guild_id,
                    screenshot_url=None # URL is added later
                )
                error_msg = f"Missing fields: {', '.join(fields_missing)}"
                return OCRParseResult(
                    ranking_data=partial_data,
                    error_message=error_msg,
                    confidence=confidence,
                    fields_found=fields_found,
                    fields_missing=fields_missing,
                    raw_ocr_text=text
                )

        except Exception as e:
            return OCRParseResult(error_message=f"An unexpected error occurred: {e}", confidence=0.0)
        
    async def process_screenshot_with_ai(
        self,
        image_data: bytes,
        user_id: str,
        username: str,
        guild_id: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> OCRParseResult:
        """
        Process a screenshot using v2 method and attempt AI correction if needed.
        """
        result = await self.process_screenshot_v2(image_data, user_id, username, guild_id)
        
        # Add image_url to the ranking data if it exists
        if result.ranking_data:
            result.ranking_data.screenshot_url = image_url

        if not result.is_successful and self.openai_engine and image_url and result.ranking_data:
            if result.error_message == "Could not read any text from the image.":
                 # Try with vision model as a fallback
                prompt = f"Extract the rank, score, player_name, and guild_tag from this Top Heroes game screenshot. The user's data is in the highlighted row. Respond with a JSON object containing these fields: rank (int), score (int), player_name (string), guild_tag (string). The guild tag is a 3-letter tag in brackets."
                extracted_data = await self.openai_engine.analyze_screenshot_with_vision(image_url, prompt, ["rank", "score", "player_name", "guild_tag"])
                
                if extracted_data:
                    result.ranking_data.rank = extracted_data.get("rank", result.ranking_data.rank)
                    result.ranking_data.score = extracted_data.get("score", result.ranking_data.score)
                    result.ranking_data.player_name = extracted_data.get("player_name", result.ranking_data.player_name)
                    result.ranking_data.guild_tag = extracted_data.get("guild_tag", result.ranking_data.guild_tag)
                    
                    # Recalculate missing fields
                    fields_missing = []
                    if not result.ranking_data.rank: fields_missing.append("rank")
                    if not result.ranking_data.score: fields_missing.append("score")
                    result.fields_missing = fields_missing
                    
                    if not fields_missing:
                        result.error_message = None
                        result.confidence = 0.8 # AI assisted
                    else:
                        result.error_message = f"AI assistance failed to find all fields. Missing: {', '.join(fields_missing)}"

        return result

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
        
        The user's ranking row is always at the bottom of the visible rankings
        (highlighted row). This row contains:
        - Rank number (small, e.g., 94)
        - Kingdom ID (large, e.g., #10435)
        - Guild tag (e.g., [TAO])
        - Player name (e.g., Mars)
        - Score (large number with commas, e.g., 7,948,885)
        
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
            
            # Extract data from the bottom (user's) row
            rank, score, player_name, guild_tag, kingdom_id = self._extract_bottom_row_data(text)
            
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
        """
        Extract which day of the event (1-5).
        
        The highlighted/selected day number appears at the top.
        """
        # Look for day indicators - buttons labeled 1-5
        # The text might show numbers like "1 2 3 4 5"
        for day in range(1, 6):
            # Look for patterns indicating selected day
            if re.search(rf'\b{day}\b', text):
                return day
        return None
    
    def _extract_bottom_row_data(self, text: str) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str], Optional[str]]:
        """
        Extract data from the bottom (user's) row.
        
        Bottom row format: "94 #10435 [TAO] Mars Points: 7,948,885"
        or: "94 #10435 [TAO] Mars 7,948,885"
        
        Returns:
            (rank, score, player_name, guild_tag, kingdom_id)
        """
        # Split text into lines
        lines = text.strip().split('\n')
        
        # The user's row is typically one of the last non-empty lines
        # Look for the last line that has ranking data
        bottom_row = None
        for line in reversed(lines):
            line = line.strip()
            # Check if line contains ranking indicators (numbers and brackets)
            if re.search(r'\d+.*\[.*\].*\d', line) or re.search(r'#\d+', line):
                bottom_row = line
                break
        
        if not bottom_row:
            # Fallback to old extraction methods
            return (self._extract_rank(text), self._extract_score(text), 
                    self._extract_player_name(text), self._extract_guild_tag(text), None)
        
        # Parse the bottom row
        # Expected format: "94 #10435 [TAO] Mars 7,948,885" or similar
        
        # Extract rank (small number at start, typically 1-10000)
        rank_match = re.search(r'^(\d{1,5})\s', bottom_row)
        rank = int(rank_match.group(1)) if rank_match else None
        
        # Extract kingdom ID (large number with #, like #10435)
        kingdom_match = re.search(r'#(\d{4,6})', bottom_row)
        kingdom_id = kingdom_match.group(1) if kingdom_match else None
        
        # Extract guild tag (3 letters in brackets)
        guild_match = re.search(r'\[([A-Z]{3})\]', bottom_row)
        guild_tag = guild_match.group(1) if guild_match else None
        
        # Extract player name (text between guild tag and score)
        if guild_tag:
            # Look for name after [TAG]
            name_match = re.search(rf'\[{guild_tag}\]\s+([A-Za-z0-9_]+)', bottom_row)
            player_name = name_match.group(1) if name_match else None
        else:
            player_name = None
        
        # Extract score (large number with commas, typically at the end)
        score_match = re.search(r'([\d,]+)(?:\s|$)', bottom_row)
        if score_match:
            score_str = score_match.group(1).replace(',', '')
            try:
                score = int(score_str)
                # Validate it's a reasonable score (> 1000)
                if score < 1000:
                    score = None
            except ValueError:
                score = None
        else:
            score = None
        
        return (rank, score, player_name, guild_tag, kingdom_id)
    
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
        
        Format examples:
        - "#10435 [TAO] Mars" -> "Mars"
        - "94 [TAO] Mars 28,200,103" -> "Mars"
        
        Strategy: Look for text between guild tag and large numbers
        """
        # Try to find the pattern: number [TAG] Name score
        # The player row usually has: rank, guild_id, [guild_tag], player_name, score
        
        # Pattern 1: [TAG] followed by a name
        tag_name_pattern = r'\[([A-Z]{3})\]\s+([A-Za-z0-9_]+)'
        matches = re.findall(tag_name_pattern, text)
        if matches:
            # Return the name from the first match (assuming it's the highlighted row)
            return matches[0][1]
        
        # Pattern 2: (TAG) followed by a name
        tag_name_pattern2 = r'\(([A-Z]{3})\)\s+([A-Za-z0-9_]+)'
        matches = re.findall(tag_name_pattern2, text)
        if matches:
            return matches[0][1]
        
        return None
    
    def _extract_rank(self, text: str) -> Optional[int]:
        """
        Extract overall rank number.
        
        Looking for rank in format like "#94" or "Rank: 94"
        Filters out large numbers that are likely guild IDs (> 1000)
        """
        # Look for rank patterns
        rank_patterns = [
            r'rank[:\s]+(\d+)',
            r'position[:\s]+(\d+)',
            r'#(\d+)',  # This will match both rank and guild IDs
        ]
        
        candidates = []
        for pattern in rank_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    num = int(match)
                    # Filter: ranks are typically 1-10000, guild IDs are often larger
                    if 1 <= num <= 10000:
                        candidates.append(num)
                except ValueError:
                    continue
        
        # Return the smallest valid number (likely the actual rank)
        return min(candidates) if candidates else None
    
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
