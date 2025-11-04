"""
Smart Image Parser for KVK and GAR Events.

Provides intelligent, context-aware OCR with confidence scoring,
visual zone detection, and adaptive learning capabilities.
"""

from __future__ import annotations
import io
import re
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

try:
    from PIL import Image, ImageStat
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class EventType(Enum):
    """Event types detected from screenshots."""
    KVK = "Kingdom vs Kingdom"
    GAR = "Guild Arms Race"
    UNKNOWN = "Unknown"


@dataclass
class VisualZone:
    """Represents a detected region in the screenshot."""
    name: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0


@dataclass
class ParsedField:
    """Individual parsed field with confidence."""
    name: str
    value: Any
    confidence: float
    raw_text: str = ""


@dataclass
class SmartParseResult:
    """Result from smart parsing with confidence and metadata."""
    # Core data
    event_type: EventType
    stage: str
    day_number: Optional[int]
    rank: Optional[int]
    score: Optional[int]
    player_name: Optional[str]
    guild_tag: Optional[str]
    kingdom_id: Optional[str]
    
    # Confidence metrics
    overall_confidence: float
    field_confidences: Dict[str, float]
    
    # Metadata
    parsed_at: datetime
    image_hash: str
    zones_detected: List[VisualZone]
    anomalies: List[str]
    needs_review: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            'event_type': self.event_type.value,
            'zones_detected': [asdict(z) for z in self.zones_detected],
            'parsed_at': self.parsed_at.isoformat()
        }


class SmartImageParser:
    """
    Intelligent image parser with adaptive OCR and visual understanding.
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self.available = HAS_PIL and HAS_OCR
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Learning memory
        self.corrections_file = self.cache_dir / "parse_corrections.json"
        self.layout_signatures_file = self.cache_dir / "layout_signatures.json"
        self._load_learning_data()
    
    def _load_learning_data(self):
        """Load correction history and layout signatures."""
        self.corrections = []
        if self.corrections_file.exists():
            try:
                with open(self.corrections_file, 'r') as f:
                    self.corrections = json.load(f)
            except:
                pass
        
        self.layout_signatures = {}
        if self.layout_signatures_file.exists():
            try:
                with open(self.layout_signatures_file, 'r') as f:
                    self.layout_signatures = json.load(f)
            except:
                pass
    
    def _save_correction(self, image_hash: str, field: str, wrong_value: Any, correct_value: Any):
        """Log a correction for learning."""
        self.corrections.append({
            'hash': image_hash,
            'field': field,
            'wrong_value': str(wrong_value),
            'correct_value': str(correct_value),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 1000 corrections
        if len(self.corrections) > 1000:
            self.corrections = self.corrections[-1000:]
        
        try:
            with open(self.corrections_file, 'w') as f:
                json.dump(self.corrections, f, indent=2)
        except:
            pass
    
    async def parse_screenshot(
        self,
        image_data: bytes,
        user_id: str,
        username: str
    ) -> Optional[SmartParseResult]:
        """
        Intelligently parse screenshot with confidence scoring.
        
        Args:
            image_data: Raw image bytes
            user_id: Discord user ID
            username: Discord username
            
        Returns:
            SmartParseResult if successful, None if parsing fails
        """
        if not self.available:
            raise RuntimeError("PIL or pytesseract not installed")
        
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Generate image hash for tracking
            image_hash = hashlib.sha256(image_data).hexdigest()[:16]
            
            # Phase 1: Classify event type
            event_type, event_confidence = self._classify_event(image)
            
            # Phase 2: Detect visual zones
            zones = self._detect_zones(image)
            
            # Phase 3: Multi-pass OCR
            ocr_text = self._multi_pass_ocr(image, zones)
            
            # Phase 4: Extract structured data with confidence
            parsed_fields = self._extract_with_confidence(ocr_text, zones, event_type)
            
            # Phase 5: Validate and check for anomalies
            anomalies = self._detect_anomalies(parsed_fields)
            
            # Calculate overall confidence
            confidences = {f.name: f.confidence for f in parsed_fields}
            overall_confidence = sum(confidences.values()) / len(confidences) if confidences else 0.0
            
            # Build result
            result = SmartParseResult(
                event_type=event_type,
                stage=self._get_field_value(parsed_fields, 'stage', 'Unknown'),
                day_number=self._get_field_value(parsed_fields, 'day'),
                rank=self._get_field_value(parsed_fields, 'rank'),
                score=self._get_field_value(parsed_fields, 'score'),
                player_name=self._get_field_value(parsed_fields, 'player_name'),
                guild_tag=self._get_field_value(parsed_fields, 'guild_tag'),
                kingdom_id=self._get_field_value(parsed_fields, 'kingdom_id'),
                overall_confidence=overall_confidence,
                field_confidences=confidences,
                parsed_at=datetime.utcnow(),
                image_hash=image_hash,
                zones_detected=zones,
                anomalies=anomalies,
                needs_review=overall_confidence < 0.85 or len(anomalies) > 0
            )
            
            return result
            
        except Exception as e:
            print(f"Smart parsing error: {e}")
            return None
    
    def _classify_event(self, image: Image.Image) -> Tuple[EventType, float]:
        """Classify event type with confidence."""
        # Extract text from top portion (title area)
        width, height = image.size
        header = image.crop((0, 0, width, int(height * 0.2)))
        header_text = pytesseract.image_to_string(header).lower()
        
        confidence = 0.5
        event_type = EventType.UNKNOWN
        
        # KVK keywords
        kvk_keywords = ['prep stage', 'war stage', 'kingdom', 'kvk']
        kvk_matches = sum(1 for kw in kvk_keywords if kw in header_text)
        
        # GAR keywords
        gar_keywords = ['guild assault', 'tech boost', 'arms race', 'territory']
        gar_matches = sum(1 for kw in gar_keywords if kw in header_text)
        
        if kvk_matches > gar_matches:
            event_type = EventType.KVK
            confidence = min(0.95, 0.6 + (kvk_matches * 0.15))
        elif gar_matches > kvk_matches:
            event_type = EventType.GAR
            confidence = min(0.95, 0.6 + (gar_matches * 0.15))
        
        return event_type, confidence
    
    def _detect_zones(self, image: Image.Image) -> List[VisualZone]:
        """Detect visual zones dynamically."""
        width, height = image.size
        
        # Basic zone detection (can be enhanced with edge detection)
        zones = [
            VisualZone('header', 0, 0, width, int(height * 0.15)),
            VisualZone('tabs', 0, int(height * 0.08), width, int(height * 0.12)),
            VisualZone('table', 0, int(height * 0.2), width, int(height * 0.7)),
            VisualZone('bottom_row', 0, int(height * 0.85), width, int(height * 0.15))
        ]
        
        return zones
    
    def _multi_pass_ocr(self, image: Image.Image, zones: List[VisualZone]) -> Dict[str, str]:
        """Perform multi-pass OCR on different zones."""
        results = {}
        
        for zone in zones:
            # Extract zone
            zone_img = image.crop((zone.x, zone.y, zone.x + zone.width, zone.y + zone.height))
            
            # First pass: standard OCR
            text = pytesseract.image_to_string(zone_img)
            results[zone.name] = text
        
        return results
    
    def _extract_with_confidence(
        self,
        ocr_text: Dict[str, str],
        zones: List[VisualZone],
        event_type: EventType
    ) -> List[ParsedField]:
        """Extract fields with confidence scores."""
        fields = []
        
        # Get bottom row text (user's row)
        bottom_text = ocr_text.get('bottom_row', '')
        
        # Extract rank
        rank, rank_conf = self._extract_rank_with_confidence(bottom_text)
        if rank:
            fields.append(ParsedField('rank', rank, rank_conf, bottom_text))
        
        # Extract score
        score, score_conf = self._extract_score_with_confidence(bottom_text)
        if score:
            fields.append(ParsedField('score', score, score_conf, bottom_text))
        
        # Extract player name
        name, name_conf = self._extract_name_with_confidence(bottom_text)
        if name:
            fields.append(ParsedField('player_name', name, name_conf, bottom_text))
        
        # Extract guild tag
        guild, guild_conf = self._extract_guild_with_confidence(bottom_text)
        if guild:
            fields.append(ParsedField('guild_tag', guild, guild_conf, bottom_text))
        
        # Extract day from header/tabs
        header_text = ocr_text.get('header', '') + ocr_text.get('tabs', '')
        day, day_conf = self._extract_day_with_confidence(header_text)
        if day:
            fields.append(ParsedField('day', day, day_conf, header_text))
        
        # Extract stage
        stage, stage_conf = self._extract_stage_with_confidence(header_text)
        fields.append(ParsedField('stage', stage, stage_conf, header_text))
        
        return fields
    
    def _extract_rank_with_confidence(self, text: str) -> Tuple[Optional[int], float]:
        """Extract rank with confidence."""
        matches = re.findall(r'\b(\d{1,4})\b', text)
        if not matches:
            return None, 0.0
        
        # First small number is likely the rank
        for match in matches:
            num = int(match)
            if 1 <= num <= 10000:
                # Higher confidence for smaller ranks
                confidence = 0.95 if num < 1000 else 0.85
                return num, confidence
        
        return None, 0.0
    
    def _extract_score_with_confidence(self, text: str) -> Tuple[Optional[int], float]:
        """Extract score with confidence."""
        # Look for large numbers with commas
        matches = re.findall(r'([\d,]+)', text)
        scores = []
        
        for match in matches:
            try:
                score = int(match.replace(',', ''))
                if score > 10000:  # Scores are typically large
                    scores.append(score)
            except:
                continue
        
        if scores:
            # Largest number is likely the score
            score = max(scores)
            confidence = 0.9 if len(scores) == 1 else 0.8
            return score, confidence
        
        return None, 0.0
    
    def _extract_name_with_confidence(self, text: str) -> Tuple[Optional[str], float]:
        """Extract player name with confidence."""
        # Look for text between guild tag and numbers
        match = re.search(r'\[([A-Z]{3})\]\s+([A-Za-z0-9_]+)', text)
        if match:
            return match.group(2), 0.9
        
        return None, 0.0
    
    def _extract_guild_with_confidence(self, text: str) -> Tuple[Optional[str], float]:
        """Extract guild tag with confidence."""
        match = re.search(r'\[([A-Z]{3})\]', text)
        if match:
            return match.group(1), 0.95
        
        return None, 0.0
    
    def _extract_day_with_confidence(self, text: str) -> Tuple[Optional[int], float]:
        """Extract day number with confidence."""
        for day in range(1, 6):
            if re.search(rf'\b{day}\b', text):
                return day, 0.8
        
        return None, 0.0
    
    def _extract_stage_with_confidence(self, text: str) -> Tuple[str, float]:
        """Extract stage with confidence."""
        text_lower = text.lower()
        
        if 'prep stage' in text_lower:
            return 'Prep Stage', 0.95
        elif 'war stage' in text_lower:
            return 'War Stage', 0.95
        elif 'guild assault' in text_lower:
            return 'Guild Assault', 0.9
        elif 'tech boost' in text_lower:
            return 'Tech Boost', 0.9
        
        return 'Unknown', 0.3
    
    def _detect_anomalies(self, fields: List[ParsedField]) -> List[str]:
        """Detect parsing anomalies."""
        anomalies = []
        
        # Check for missing critical fields
        field_names = {f.name for f in fields}
        if 'rank' not in field_names:
            anomalies.append("Missing rank data")
        if 'score' not in field_names:
            anomalies.append("Missing score data")
        
        # Check for low confidence fields
        for field in fields:
            if field.confidence < 0.7:
                anomalies.append(f"Low confidence on {field.name}: {field.confidence:.0%}")
        
        return anomalies
    
    def _get_field_value(self, fields: List[ParsedField], name: str, default=None):
        """Get value from parsed fields."""
        for field in fields:
            if field.name == name:
                return field.value
        return default
