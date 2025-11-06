"""
Screenshot Processing Engine for Top Heroes Rankings.

Uses OCR (Optical Character Recognition) to extract ranking data from game screenshots.
"""

from __future__ import annotations
import io
import re
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger("hippo_bot.screenshot_processor")

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
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False


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
    PREP_OVERALL = "Prep Stage Overall"  # Overall prep aggregation
    WAR_TOTAL = "War Stage Total"  # War stage combined
    UNKNOWN = "Unknown"


@dataclass
class RankingData:
    """
    Canonical ranking data model.
    
    Schema:
        phase: "prep" or "war"
        day: 1-5 (prep days), "overall" (prep total), or None (war)
    """
    
    # User info
    user_id: str
    username: str
    guild_tag: Optional[str]  # 3-letter guild tag (e.g., "TAO")
    
    # Event info
    event_week: str  # "YYYY-WW" format for event week tracking
    phase: str  # "prep" or "war"
    day: Optional[int | str]  # 1-5, "overall", or None
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
    
    # Backward compatibility fields (deprecated)
    stage_type: Optional[StageType] = None
    day_number: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage using canonical model."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'guild_tag': self.guild_tag,
            'event_week': self.event_week,
            'phase': self.phase,  # "prep" or "war"
            'day': self.day,  # 1-5, "overall", or None
            'category': self.category.value,
            'rank': self.rank,
            'score': self.score,
            'player_name': self.player_name,
            'submitted_at': self.submitted_at.isoformat(),
            'screenshot_url': self.screenshot_url,
            'guild_id': self.guild_id,
            'kvk_run_id': self.kvk_run_id,
            'is_test_run': int(self.is_test_run),
            # Legacy fields for backward compatibility
            'stage_type': self.stage_type.value if self.stage_type else self.phase.title() + " Stage",
            'day_number': self._day_to_number(),
        }
    
    def _day_to_number(self) -> Optional[int]:
        """Convert day to legacy day_number format for backward compatibility."""
        if self.phase == "war":
            return None
        if self.day == "overall":
            return -1
        if isinstance(self.day, int):
            return self.day
        return None


class ScreenshotProcessor:
    """Process Top Heroes ranking screenshots to extract data."""
    
    def __init__(self):
        # R11 - EasyOCR lazy-loaded on first use to prevent startup memory spike
        self.available = HAS_PIL and HAS_EASYOCR
        self.reader = None  # Lazy-loaded by _ensure_reader()
        # R9 - adaptive correction memory (in-memory only for now)
        self.normalization_cache = {}
    
    def _ensure_reader(self):
        """Lazy-load EasyOCR reader on first use."""
        if self.reader is None:
            if not HAS_EASYOCR:
                raise RuntimeError("EasyOCR is required but not installed")
            try:
                self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                logger.info("EasyOCR initialized successfully with English model")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                raise
    
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
        Process a screenshot and extract ranking data using canonical model.
        
        Canonical Schema:
            phase: "prep" or "war"
            day: 1-5, "overall", or None
        
        Args:
            image_data: Raw image bytes
            user_id: Discord user ID
            username: Discord username
            guild_id: Discord guild ID
            
        Returns:
            RankingData if successful, None if processing fails
        """
        if not self.available:
            raise RuntimeError("PIL or EasyOCR not installed. Install with: pip install Pillow easyocr")
        
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # ═══════════════════════════════════════════════════════════════
            # R11 - OCR WITH CONFIDENCE EXTRACTION (EasyOCR + OpenCV)
            # ═══════════════════════════════════════════════════════════════
            # Lazy-load EasyOCR on first use
            self._ensure_reader()
            
            confidence_map = {}
            overall_confidence = 1.0
            
            if HAS_CV2:
                # Convert PIL image to OpenCV format
                img_array = np.array(image)
                img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Preprocessing pipeline: increase text clarity for game UI
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)  # Improves contrast consistently
                
                # Light adaptive thresholding to clarify UI text
                thresh = cv2.adaptiveThreshold(
                    gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    31, 2
                )
                
                # Use EasyOCR with confidence
                if self.reader:
                    try:
                        # EasyOCR with confidence values: returns [(bbox, text, confidence), ...]
                        ocr_results = self.reader.readtext(thresh, detail=1, paragraph=False)
                        
                        # Extract text and build confidence map
                        text_tokens = []
                        for (bbox, detected_text, conf) in ocr_results:
                            text_str = str(detected_text).strip()
                            conf_normalized = float(conf)  # EasyOCR returns 0-1 already
                            text_tokens.append((text_str, conf_normalized))
                            
                            # Build confidence map for key fields
                            if re.search(r'#\d+', text_str):
                                confidence_map['rank'] = max(confidence_map.get('rank', 0), conf_normalized)
                            if re.search(r'[\d,]{4,}', text_str):  # Large numbers = scores
                                confidence_map['score'] = max(confidence_map.get('score', 0), conf_normalized)
                            if re.match(r'\[([A-Z]{2,4})\]', text_str):
                                confidence_map['guild'] = max(confidence_map.get('guild', 0), conf_normalized)
                            if len(text_str) > 2 and text_str.isalpha():
                                confidence_map['player_name'] = max(confidence_map.get('player_name', 0), conf_normalized)
                        
                        # Combine all text
                        text = " ".join([t[0] for t in text_tokens])
                        
                        # Calculate overall confidence
                        if confidence_map:
                            overall_confidence = sum(confidence_map.values()) / len(confidence_map)
                        else:
                            overall_confidence = 0.5  # Low confidence if no key fields detected
                        
                        logger.debug(f"EasyOCR confidence: overall={overall_confidence:.2f}, map={confidence_map}")
                    except Exception as e:
                        logger.error(f"EasyOCR failed: {e}")
                        raise
                else:
                    raise RuntimeError("EasyOCR reader not initialized")
            else:
                raise RuntimeError("OpenCV (cv2) is required for OCR preprocessing")
            
            # Determine phase and day using canonical logic
            phase, day = self._determine_phase_and_day(text, image)
            category = self._get_category_from_day(day, phase)
            rank = self._extract_rank(text)
            score = self._extract_score(text)
            
            # ------------------------------------------------------------
            # R9 - Score Stability Normalization
            # ------------------------------------------------------------
            if score is not None:
                raw_score = str(score)
                
                # 1) Remove common thousands-separator formatting
                raw_score = raw_score.replace(",", "").replace(".", "").replace(" ", "")
                
                # 2) Fix OCR digit substitution errors (O→0, I→1, l→1, B→8, S→5)
                substitutions = {
                    "O": "0", "o": "0",
                    "I": "1", "l": "1",
                    "B": "8",
                    "S": "5"
                }
                for bad, good in substitutions.items():
                    raw_score = raw_score.replace(bad, good)
                
                # 3) Strip leading non-digits and trailing non-digits safely
                while raw_score and not raw_score[0].isdigit():
                    raw_score = raw_score[1:]
                while raw_score and not raw_score[-1].isdigit():
                    raw_score = raw_score[:-1]
                
                # 4) Convert safely to int (default to None if invalid)
                try:
                    score = int(raw_score)
                except Exception:
                    score = None
            
            player_name = self._extract_player_name(text)
            guild_tag = self._extract_guild_tag(text)
            
            # R9 - adaptive text normalization
            if player_name and ("player_name", player_name) in self.normalization_cache:
                player_name = self.normalization_cache[("player_name", player_name)]
            if guild_tag and ("guild", guild_tag) in self.normalization_cache:
                guild_tag = self.normalization_cache[("guild", guild_tag)]
            
            if rank is None or score is None:
                return None
            
            # Get current event week
            event_week = self._get_current_event_week(datetime.utcnow())
            
            # Convert phase to StageType for backward compatibility
            stage_type = StageType.PREP if phase == "prep" else StageType.WAR
            
            # Create ranking data
            ranking = RankingData(
                user_id=user_id,
                username=username,
                guild_tag=guild_tag,
                event_week=event_week,
                phase=phase,  # Canonical: "prep" or "war"
                day=day,  # Canonical: 1-5, "overall", or None
                category=category,
                rank=rank,
                score=score,
                player_name=player_name,
                submitted_at=datetime.utcnow(),
                guild_id=guild_id,
                stage_type=stage_type,  # Legacy compatibility
            )
            
            # R11 - Attach confidence metadata for UI validation flow
            ranking.confidence = overall_confidence
            ranking.confidence_map = confidence_map
            
            # Apply learned corrections from OCR training engine if available
            ranking = self._apply_training_corrections(ranking)
            
            return ranking
            
        except Exception:
            return None
    
    def parse_ranking_screenshot(
        self,
        image_data: bytes,
        user_id: str,
        username: str,
        guild_id: Optional[str] = None,
        event_week: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        LOCKED PARSING FUNCTION: Extracts ranking data from screenshot using visual anchors.
        
        Parsing Rules:
        1) Phase Detection:
           - "Prep Stage" highlighted → phase="prep"
           - "War Stage" highlighted → phase="war"
           
        2) Day Detection (prep only):
           - Day tab 1-5 highlighted → day = that number
           - Grid/overview icon highlighted → day="overall"
           - If phase="war" → day=None always
           
        3) Player Entry Parsing (bottom-most row):
           Format: "#10435 [TAO] Mars"
           - server_id = digits after '#'
           - guild_tag = text inside brackets []
           - player_name = remainder after guild tag
           
           Format: "Points: 25,200,103"
           - score = digits (commas removed)
        
        Returns:
            {
                "server_id": int,
                "guild": str,
                "player_name": str,
                "score": int,
                "phase": "prep" or "war",
                "day": int or "overall" or None
            }
            or None if parsing fails
        """
        if not HAS_PIL or not HAS_EASYOCR:
            return None
        
        # Lazy-load EasyOCR on first use
        self._ensure_reader()
            
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # ═══════════════════════════════════════════════════════════════
            # OCR PREPROCESSING WITH OPENCV (R8+ Enhancement)
            # ═══════════════════════════════════════════════════════════════
            if HAS_CV2:
                # Convert PIL image to OpenCV format
                img_array = np.array(image)
                img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Preprocessing pipeline: increase text clarity for game UI
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)  # Improves contrast consistently
                
                # Light adaptive thresholding to clarify UI text
                thresh = cv2.adaptiveThreshold(
                    gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    31, 2
                )
                
                # Use EasyOCR to extract text
                ocr_results = self.reader.readtext(thresh, detail=0, paragraph=False)
                text = " ".join(ocr_results)
            else:
                # No preprocessing available
                ocr_results = self.reader.readtext(np.array(image), detail=0, paragraph=False)
                text = " ".join(ocr_results)
            text_lower = text.lower()
            
            # ═══════════════════════════════════════════════════════
            # PHASE DETECTION: Use explicit highlighted stage markers
            # ═══════════════════════════════════════════════════════
            phase = self._extract_phase_from_highlight(text_lower)
            
            # ═══════════════════════════════════════════════════════
            # DAY DETECTION: Parse highlighted tab (prep only)
            # ═══════════════════════════════════════════════════════
            day = self._extract_day_from_highlight(text_lower, phase)
            
            # ═══════════════════════════════════════════════════════
            # PLAYER ENTRY PARSING: Bottom-most row format
            # ═══════════════════════════════════════════════════════
            player_entry = self._parse_player_entry(text)
            if not player_entry:
                return None
            
            return {
                "server_id": player_entry["server_id"],
                "guild": player_entry["guild_tag"],
                "player_name": player_entry["player_name"],
                "score": player_entry["score"],
                "phase": phase,
                "day": day,
                "rank": player_entry.get("rank"),  # Optional
            }
            
        except Exception as e:
            logger.error(f"Screenshot parsing failed: {e}")
            return None
    
    def _extract_phase_from_highlight(self, text_lower: str) -> str:
        """
        Extract phase using visual anchor detection.
        
        Rules:
        - "prep stage" + nearby highlight markers → "prep"
        - "war stage" + nearby highlight markers → "war"
        - Presence of day selector (multiple day tabs) → "prep"
        - Fallback → "war"
        """
        # Look for explicit stage markers with highlight context
        prep_patterns = [
            r'prep\s+stage.*?(?:highlighted|selected|active)',
            r'(?:highlighted|selected|active).*?prep\s+stage',
            r'preparation\s+(?:phase|stage)',
        ]
        
        war_patterns = [
            r'war\s+stage.*?(?:highlighted|selected|active)',
            r'(?:highlighted|selected|active).*?war\s+stage',
        ]
        
        for pattern in prep_patterns:
            if re.search(pattern, text_lower):
                return "prep"
        
        for pattern in war_patterns:
            if re.search(pattern, text_lower):
                return "war"
        
        # Fallback: detect day selector UI (indicates prep)
        if self._has_day_selector_ui(text_lower):
            return "prep"
        
        # Default to war (consolidated view)
        return "war"
    
    def _extract_day_from_highlight(self, text_lower: str, phase: str) -> Optional[int | str]:
        """
        Extract highlighted day tab (prep phase only).
        
        Rules:
        - If phase="war" → return None immediately
        - Look for "day 1-5" + highlight context → return int
        - Look for "overall" or grid icon → return "overall"
        - Fallback → return 1 (assume day 1)
        """
        if phase == "war":
            return None
        
        # Pattern for highlighted day tabs
        day_highlight_patterns = [
            r'(?:day\s*(\d)).*?(?:highlighted|selected|active)',
            r'(?:highlighted|selected|active).*?(?:day\s*(\d))',
        ]
        
        for pattern in day_highlight_patterns:
            match = re.search(pattern, text_lower)
            if match:
                day_num = int(match.group(1))
                if 1 <= day_num <= 5:
                    return day_num
        
        # Check for "overall" / "all" / grid view
        overall_patterns = [
            r'overall.*?(?:highlighted|selected|active)',
            r'(?:highlighted|selected|active).*?overall',
            r'(?:all|total).*?(?:highlighted|selected|active)',
        ]
        
        for pattern in overall_patterns:
            if re.search(pattern, text_lower):
                return "overall"
        
        # Explicit day mentions without highlight context
        for day_num in range(1, 6):
            if re.search(rf'\bday\s*{day_num}\b', text_lower):
                return day_num
        
        if re.search(r'\boverall\b', text_lower):
            return "overall"
        
        # Fallback: assume day 1
        return 1
    
    def _has_day_selector_ui(self, text_lower: str) -> bool:
        """Detect if screenshot shows day selector (multiple day tabs = prep phase)."""
        day_mentions = sum(1 for i in range(1, 6) if f'day {i}' in text_lower or f'day{i}' in text_lower)
        overall_mention = 'overall' in text_lower
        return day_mentions >= 3 or (day_mentions >= 2 and overall_mention)
    
    def _parse_player_entry(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse player entry from bottom-most row.
        
        Expected formats:
        "#10435 [TAO] Mars"
        "Points: 25,200,103"
        
        Returns:
            {
                "server_id": int,
                "guild_tag": str,
                "player_name": str,
                "score": int,
                "rank": int (optional)
            }
        """
        # Pattern: #<server_id> [<guild>] <player_name>
        player_pattern = r'#(\d+)\s+\[([A-Z]{2,4})\]\s+([^\n]+)'
        player_match = re.search(player_pattern, text, re.IGNORECASE)
        
        if not player_match:
            return None
        
        server_id = int(player_match.group(1))
        guild_tag = player_match.group(2).strip().upper()
        player_name = player_match.group(3).strip()
        
        # Pattern: Points: <score>
        score_pattern = r'points?:?\s*([\d,]+)'
        score_match = re.search(score_pattern, text, re.IGNORECASE)
        
        if not score_match:
            return None
        
        score_str = score_match.group(1).replace(',', '')
        score = int(score_str)
        
        # Optional: Extract rank (position number)
        rank_pattern = r'(?:^|\s)(\d+)(?:\s|$)'
        rank = None
        rank_match = re.search(rank_pattern, text)
        if rank_match:
            try:
                rank = int(rank_match.group(1))
            except ValueError:
                pass
        
        return {
            "server_id": server_id,
            "guild_tag": guild_tag,
            "player_name": player_name,
            "score": score,
            "rank": rank,
        }
    
    def _determine_phase_and_day(self, text: str, image: Image.Image) -> tuple[str, Optional[int | str]]:
        """
        DEPRECATED: Use parse_ranking_screenshot() instead.
        Kept for backward compatibility.
        """
        text_lower = text.lower()
        phase = self._extract_phase_from_highlight(text_lower)
        day = self._extract_day_from_highlight(text_lower, phase)
        return phase, day
    
    def _detect_day_selector(self, text_lower: str) -> bool:
        """Detect if screenshot shows day selector UI (indicates PREP phase)."""
        day_indicators = ['day 1', 'day 2', 'day 3', 'day 4', 'day 5', 'overall']
        detected_count = sum(1 for indicator in day_indicators if indicator in text_lower)
        # If we see 3+ day indicators, it's a day selector UI
        return detected_count >= 3
    
    def _extract_highlighted_day(self, text_lower: str) -> str:
        """Extract the highlighted day from prep stage UI."""
        # Look for patterns indicating a highlighted/selected day
        highlight_patterns = [
            r'(?:selected|highlighted|active|current).*?(day\s*\d|overall)',
            r'(day\s*\d|overall).*?(?:selected|highlighted|active|current)',
        ]
        
        for pattern in highlight_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).strip()
        
        # Fallback: look for isolated day mentions
        for day_num in range(1, 6):
            if f'day {day_num}' in text_lower or f'day{day_num}' in text_lower:
                return f'day {day_num}'
        
        if 'overall' in text_lower:
            return 'overall'
        
        return ''
    
    def _extract_stage_type(self, text: str) -> StageType:
        """
        Extract stage type from OCR text.
        
        Detection rules:
        - 'prep' or 'preparation' keyword → PREP
        - 'war' keyword → WAR
        - Multiple day tabs visible → PREP
        - No day selector → WAR
        """
        text_lower = text.lower()
        
        # Direct keyword match
        if 'prep' in text_lower or 'preparation' in text_lower:
            return StageType.PREP
        elif 'war' in text_lower:
            return StageType.WAR
        
        # Check for day selector UI (indicates PREP)
        day_indicators = ['day 1', 'day 2', 'day 3', 'day 4', 'day 5', 'overall']
        if sum(1 for indicator in day_indicators if indicator in text_lower) >= 3:
            return StageType.PREP
        
        return StageType.UNKNOWN
    
    def _extract_day_number(self, text: str) -> Optional[int]:
        """
        Extract which day of the event (1-5) or detect 'overall'.
        
        Returns:
        - 1-5: Specific prep day
        - -1: Overall prep aggregation
        - None: Not detected or not applicable (WAR stage)
        """
        text_lower = text.lower()
        
        # Check for "Overall" indicator first
        if 'overall' in text_lower:
            return -1  # Special value for overall prep
        
        # Look for highlighted day in day selector UI
        # Priority order: try to find explicit highlight markers
        highlight_patterns = [
            r'(?:selected|highlighted|active).*?day\s*(\d)',
            r'day\s*(\d).*?(?:selected|highlighted|active)',
        ]
        
        for pattern in highlight_patterns:
            match = re.search(pattern, text_lower)
            if match:
                day = int(match.group(1))
                if 1 <= day <= 5:
                    return day
        
        # Fallback: look for isolated day numbers (less reliable)
        for day in range(1, 6):
            # Only match if surrounded by word boundaries to avoid false positives
            if re.search(rf'\bday\s*{day}\b', text_lower):
                return day
        
        return None
    
    def _get_category_from_day(self, day: Optional[int | str], phase: str) -> RankingCategory:
        """
        Map day to category using canonical model.
        
        Args:
            day: 1-5, "overall", or None
            phase: "prep" or "war"
        
        Returns:
            Appropriate RankingCategory
        """
        if phase == "war":
            return RankingCategory.WAR_TOTAL
        
        if day == "overall":
            return RankingCategory.PREP_OVERALL
        
        category_map = {
            1: RankingCategory.CONSTRUCTION,
            2: RankingCategory.RESEARCH,
            3: RankingCategory.RESOURCE_MOB,
            4: RankingCategory.HERO,
            5: RankingCategory.TROOP_TRAINING,
        }
        return category_map.get(day, RankingCategory.UNKNOWN) if isinstance(day, int) else RankingCategory.UNKNOWN
    
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
            return False, "OCR not available. Install Pillow and EasyOCR."
        
        # Lazy-load EasyOCR on first use
        self._ensure_reader()
        
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Check image size (should be reasonable)
            width, height = image.size
            if width < 100 or height < 100:
                return False, "Image too small. Please provide a clear screenshot."
            
            if width > 4000 or height > 4000:
                return False, "Image too large. Please provide a normal screenshot."
            
            # ═══════════════════════════════════════════════════════════════
            # OCR PREPROCESSING WITH OPENCV (R8+ Enhancement)
            # ═══════════════════════════════════════════════════════════════
            if HAS_CV2:
                # Convert PIL image to OpenCV format
                img_array = np.array(image)
                img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Preprocessing pipeline: increase text clarity for game UI
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)  # Improves contrast consistently
                
                # Light adaptive thresholding to clarify UI text
                thresh = cv2.adaptiveThreshold(
                    gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    31, 2
                )
                
                # Use EasyOCR to extract text
                ocr_results = self.reader.readtext(thresh, detail=0, paragraph=False)
                text = " ".join(ocr_results)
            else:
                # No preprocessing available
                ocr_results = self.reader.readtext(np.array(image), detail=0, paragraph=False)
                text = " ".join(ocr_results)
            
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
    
    def _apply_training_corrections(self, ranking: RankingData) -> RankingData:
        """
        Apply learned corrections from OCR training engine if available.
        
        This method is called after OCR processing to apply any learned
        correction patterns from the interactive training system.
        """
        # Check if training corrections are available
        # This will be populated by the OCR training engine
        if not hasattr(self, 'training_corrections'):
            return ranking
        
        corrections = getattr(self, 'training_corrections', None)
        if corrections and hasattr(corrections, 'apply_learned_corrections'):
            try:
                ranking = corrections.apply_learned_corrections(ranking)
                logger.debug("Applied training corrections to OCR results")
            except Exception as e:
                logger.error("Failed to apply training corrections: %s", e)
        
        return ranking
    
    def set_training_engine(self, training_engine) -> None:
        """Set the OCR training engine for applying learned corrections."""
        self.training_corrections = training_engine
        logger.info("OCR training engine connected to screenshot processor")
