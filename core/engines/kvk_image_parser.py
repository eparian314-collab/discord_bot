"""
KVK Image Parser Engine

Visual-aware screenshot parser for Top Heroes KVK rankings.
Parses daily KVK ranking screenshots using visual cues to determine
prep/war stage, prep day (1–5 or overall), and identify the submitting
user's own score row for accurate personal tracking.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from PIL import Image, ImageEnhance, ImageFilter
    import cv2
    import numpy as np
    HAS_CV2 = True
    HAS_PIL = True
except ImportError:
    HAS_CV2 = False
    HAS_PIL = False

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

from discord_bot.core.engines.base.logging_utils import get_logger

logger = get_logger("hippo_bot.kvk_image_parser")


class KVKStageType(Enum):
    """KVK stage types detected from UI elements."""
    PREP = "prep"
    WAR = "war"
    UNKNOWN = "unknown"


@dataclass
class KVKLeaderboardEntry:
    """Single leaderboard entry from screenshot."""
    rank: int
    player_name: str
    kingdom_id: Optional[int]
    points: int
    is_self: bool = False
    guild_tag: Optional[str] = None


@dataclass
class KVKParseResult:
    """Complete parse result from KVK screenshot."""
    stage_type: KVKStageType
    prep_day: Optional[Union[int, str]]  # 1-5 or "overall"
    kingdom_id: Optional[int]
    entries: List[KVKLeaderboardEntry]
    self_entry: Optional[KVKLeaderboardEntry]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "stage_type": self.stage_type.value,
            "prep_day": self.prep_day,
            "kingdom_id": self.kingdom_id,
            "entries": [asdict(entry) for entry in self.entries],
            "self_entry": asdict(self.self_entry) if self.self_entry else None,
            "metadata": self.metadata
        }


class KVKImageParser:
    """
    Visual-aware parser for KVK ranking screenshots.
    
    Phases:
    1. Stage & Day Detection - UI element recognition
    2. Row Parsing - Leaderboard extraction
    3. Self-Score Identification - Visual highlighting detection
    4. Data Validation - Ensure detected context matches UI cues
    """
    
    def __init__(self, 
                 upload_folder: str = "uploads/screenshots",
                 log_folder: str = "logs",
                 cache_folder: str = "cache"):
        self.upload_folder = Path(upload_folder)
        self.log_folder = Path(log_folder)
        self.cache_folder = Path(cache_folder)
        self.available = HAS_PIL and HAS_OCR and HAS_CV2
        
        # Ensure directories exist
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.log_folder.mkdir(parents=True, exist_ok=True)
        self.cache_folder.mkdir(parents=True, exist_ok=True)
        
        # Pattern configurations for visual detection
        self.stage_patterns = {
            KVKStageType.PREP: [
                r"prep\s+stage",
                r"preparation\s+stage", 
                r"prep\s+day",
                # Look for specific UI button text patterns
                r"day\s+[1-5]",
                r"overall"
            ],
            KVKStageType.WAR: [
                r"war\s+stage",
                r"battle\s+stage",
                r"war\s+day"
            ]
        }
        
        # Day detection patterns
        self.day_patterns = {
            1: [r"day\s*1", r"\b1\b"],
            2: [r"day\s*2", r"\b2\b"],
            3: [r"day\s*3", r"\b3\b"],
            4: [r"day\s*4", r"\b4\b"],
            5: [r"day\s*5", r"\b5\b"],
            "overall": [r"overall", r"total", r"all\s+days", r"summary"]
        }
        
        # Score patterns for point extraction
        self.score_patterns = [
            r"(\d{1,3}(?:,\d{3})+)",  # Comma-separated numbers
            r"(\d{7,})",              # Large numbers without commas
            r"points?[:\s]+([\d,]+)", # "points: 1,234,567"
            r"score[:\s]+([\d,]+)"    # "score: 1,234,567"
        ]
        
        # Kingdom ID patterns
        self.kingdom_patterns = [
            r"#(\d{4,6})",            # #10435
            r"kingdom[:\s]+(\d{4,6})", # Kingdom: 10435
            r"k(\d{4,6})"             # K10435
        ]
        
    async def parse_screenshot(self,
                             image_data: bytes,
                             user_id: str,
                             username: str,
                             filename: Optional[str] = None) -> Optional[KVKParseResult]:
        """
        Parse KVK ranking screenshot and extract all data.
        
        Args:
            image_data: Raw image bytes
            user_id: Discord user ID submitting the screenshot
            username: Discord username
            filename: Optional filename for logging
            
        Returns:
            KVKParseResult if successful, None if parsing fails
        """
        if not self.available:
            logger.error("Required dependencies not available: PIL, cv2, pytesseract")
            return None
            
        try:
            timestamp = datetime.now(timezone.utc)
            
            # Load and preprocess image
            image = Image.open(io.BytesIO(image_data))
            processed_image = await self._preprocess_image(image)
            
            # Extract text using OCR
            ocr_text = await self._extract_text(processed_image)
            if not ocr_text:
                logger.warning("No text extracted from screenshot")
                return None
            
            # Debug: Log the OCR output
            logger.info(f"OCR extracted text:\n{ocr_text[:500]}")  # First 500 chars
            
            # Phase 1: Stage & Day Detection
            stage_type = await self._detect_stage_type(ocr_text, processed_image)
            prep_day = await self._detect_prep_day(ocr_text, processed_image)
            logger.info(f"Detected stage={stage_type}, prep_day={prep_day}")
            
            # Phase 2: Row Parsing - Extract leaderboard entries with context
            entries = await self._parse_leaderboard_rows(ocr_text, processed_image, stage_type, prep_day)
            if not entries:
                logger.warning("No leaderboard entries found")
                logger.debug(f"Full OCR text for debugging:\n{ocr_text}")
                return None
            
            # Phase 3: Self-Score Identification
            self_entry = await self._identify_self_entry(entries, processed_image, username)
            
            # Extract kingdom ID from any row
            kingdom_id = await self._extract_kingdom_id(ocr_text)
            
            # Create parse result
            result = KVKParseResult(
                stage_type=stage_type,
                prep_day=prep_day,
                kingdom_id=kingdom_id,
                entries=entries,
                self_entry=self_entry,
                metadata={
                    "parser_version": "1.0",
                    "user_id": user_id,
                    "username": username,
                    "filename": filename,
                    "timestamp": timestamp.isoformat(),
                    "ocr_text_length": len(ocr_text),
                    "entries_count": len(entries)
                }
            )
            
            # Phase 4: Data Validation
            await self._validate_parse_result(result)
            
            # Log successful parse
            await self._log_parse_success(result, filename)
            
            return result
            
        except Exception as e:
            logger.exception("Failed to parse KVK screenshot: %s", e)
            await self._log_parse_error(str(e), filename, user_id)
            return None
    
    async def validate_screenshot(self, image_data: bytes) -> tuple[bool, str]:
        """
        Validate if screenshot contains KVK ranking data.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            (is_valid, error_message)
        """
        if not self.available:
            return False, "OCR not available. Install Pillow, cv2, and pytesseract."
        
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Check image size (should be reasonable)
            width, height = image.size
            if width < 100 or height < 100:
                return False, "Image too small. Please provide a clear screenshot."
            
            if width > 4000 or height > 4000:
                return False, "Image too large. Please provide a normal screenshot."
            
            # Try to extract text
            text = await self._extract_text(image)
            
            if not text or len(text.strip()) < 10:
                return False, "Could not read text from image. Please provide a clearer screenshot."
            
            # Check for KVK-related keywords
            keywords = ['rank', 'stage', 'points', 'score', 'prep', 'war', 'kingdom']
            text_lower = text.lower()
            if not any(keyword in text_lower for keyword in keywords):
                return False, "Screenshot doesn't appear to contain KVK ranking data."
            
            return True, ""
            
        except Exception as e:
            return False, f"Error processing image: {str(e)}"
    
    async def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR results.
        
        Args:
            image: PIL Image object
            
        Returns:
            Preprocessed PIL Image
        """
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhance contrast for better text recognition
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        return image
    
    async def _extract_text(self, image: Image.Image) -> str:
        """
        Extract text from image using OCR.
        
        Args:
            image: PIL Image object
            
        Returns:
            Extracted text string
        """
        try:
            # Use different OCR configurations for better results
            configs = [
                '--psm 6',  # Uniform block of text
                '--psm 4',  # Single column of text
                '--psm 11', # Sparse text
                '--psm 13'  # Raw line
            ]
            
            best_text = ""
            for config in configs:
                try:
                    text = pytesseract.image_to_string(image, config=config)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
                except:
                    continue
            
            return best_text.strip()
            
        except Exception as e:
            logger.warning("OCR extraction failed: %s", e)
            return ""
    
    async def _detect_stage_type(self, ocr_text: str, image: Image.Image) -> KVKStageType:
        """
        Detect whether screenshot shows Prep Stage or War Stage.
        
        Args:
            ocr_text: OCR extracted text
            image: PIL Image object
            
        Returns:
            Detected stage type
        """
        text_lower = ocr_text.lower()
        
        # Check for stage type patterns
        for stage_type, patterns in self.stage_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    logger.debug("Detected stage type %s with pattern: %s", stage_type.value, pattern)
                    return stage_type
        
        # Default to prep if we find day numbers
        if any(re.search(rf"\b{day}\b", text_lower) for day in range(1, 6)):
            logger.debug("Defaulting to prep stage due to day numbers")
            return KVKStageType.PREP
        
        logger.warning("Could not detect stage type, defaulting to unknown")
        return KVKStageType.UNKNOWN
    
    async def _detect_prep_day(self, ocr_text: str, image: Image.Image) -> Optional[Union[int, str]]:
        """
        Detect which prep day (1-5) or "overall" is shown.
        
        Args:
            ocr_text: OCR extracted text
            image: PIL Image object
            
        Returns:
            Day number (1-5) or "overall" string, or None
        """
        text_lower = ocr_text.lower()
        
        # Check for specific day patterns
        for day, patterns in self.day_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    logger.debug("Detected prep day %s with pattern: %s", day, pattern)
                    return day
        
        logger.warning("Could not detect prep day")
        return None
    
    async def _parse_leaderboard_rows(self, ocr_text: str, image: Image.Image, stage_type: Optional[KVKStageType] = None, prep_day: Optional[int] = None) -> List[KVKLeaderboardEntry]:
        """
        Parse leaderboard rows from OCR text with context awareness.
        
        Args:
            ocr_text: OCR extracted text
            image: PIL Image object
            stage_type: Detected stage (PREP or WAR) for context
            prep_day: Detected prep day (1-5) for smart filtering
            
        Returns:
            List of leaderboard entries
        """
        entries = []
        lines = ocr_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to parse each line as a leaderboard entry
            entry = await self._parse_single_row(line)
            if entry:
                entries.append(entry)
        
        # Fallback: If no entries found, try simpler bottom-row extraction with context
        if not entries:
            logger.debug(f"No entries found with full parser, trying context-aware simple extraction [stage={stage_type}, day={prep_day}]")
            bottom_entry = await self._parse_bottom_row_simple(ocr_text, stage_type, prep_day)
            if bottom_entry:
                entries.append(bottom_entry)
        
        # Sort by rank
        entries.sort(key=lambda x: x.rank)
        
        logger.debug("Parsed %d leaderboard entries", len(entries))
        return entries
    
    async def _parse_bottom_row_simple(self, ocr_text: str, stage_type: Optional[KVKStageType] = None, prep_day: Optional[int] = None) -> Optional[KVKLeaderboardEntry]:
        """
        Simple fallback parser for bottom (user's) row with context-aware filtering.
        
        Expected format: "94 #10435 [TAO] Mars 7,948,885"
        
        Args:
            ocr_text: Full OCR text from screenshot
            stage_type: Detected stage (PREP or WAR) for smart filtering
            prep_day: Detected prep day (1-5) for eliminating day numbers from parsing
        
        Returns:
            Single entry for the user's row
        """
        try:
            lines = ocr_text.strip().split('\n')
            logger.info(f"Simple parser processing {len(lines)} lines")
            
            # Build context-aware exclusion list
            excluded_numbers = set()
            if prep_day is not None:
                excluded_numbers.add(prep_day)
                logger.info(f"Excluding prep day {prep_day} from rank candidates")
            
            # Try last few lines for the bottom row
            last_lines = lines[-5:] if len(lines) >= 5 else lines
            logger.info(f"Checking last {len(last_lines)} lines: {last_lines}")
            
            for line in reversed(last_lines):
                line = line.strip()
                if not line:
                    continue
                
                logger.debug(f"Analyzing line: '{line}'")
                
                # Extract all numbers from the line for context-aware filtering
                all_numbers = re.findall(r'\d+', line.replace(',', ''))
                
                # Look for pattern: small_number #large_number [TAG] name large_score
                # Extract rank (small number, 1-10000)
                rank_match = re.search(r'^(\d{1,5})\s', line)
                if not rank_match:
                    continue
                
                rank = int(rank_match.group(1))
                
                # Context-aware filtering
                if rank > 10000:  # Skip if too large (probably kingdom ID)
                    logger.debug(f"Skipping {rank} - too large for rank")
                    continue
                    
                if rank in excluded_numbers:
                    logger.debug(f"Skipping {rank} - matches prep day {prep_day}")
                    continue
                
                # Extract kingdom ID
                kingdom_match = re.search(r'#(\d{4,6})', line)
                kingdom_id = int(kingdom_match.group(1)) if kingdom_match else None
                
                # Validate kingdom ID is not the same as rank
                if kingdom_id and kingdom_id == rank:
                    logger.debug(f"Skipping - kingdom ID {kingdom_id} matches rank {rank}")
                    continue
                
                # Extract guild tag
                guild_match = re.search(r'\[([A-Z]{3})\]', line)
                guild_tag = guild_match.group(1) if guild_match else None
                
                # Extract player name (after guild tag or after kingdom)
                if guild_tag:
                    name_match = re.search(rf'\[{guild_tag}\]\s+([A-Za-z0-9_]+)', line)
                    player_name = name_match.group(1) if name_match else "Unknown"
                else:
                    # Try to find name after kingdom ID
                    if kingdom_id:
                        name_match = re.search(rf'#{kingdom_id}\s+([A-Za-z0-9_]+)', line)
                        player_name = name_match.group(1) if name_match else "Unknown"
                    else:
                        player_name = "Unknown"
                
                # Extract score (large number with commas at end)
                score_matches = re.findall(r'([\d,]+)', line)
                points = 0
                for score_str in reversed(score_matches):
                    try:
                        score_val = int(score_str.replace(',', ''))
                        # Score must be larger than both rank and kingdom ID
                        if score_val > 10000 and score_val not in excluded_numbers:
                            if kingdom_id is None or score_val != kingdom_id:
                                points = score_val
                                break
                    except:
                        continue
                
                if points > 0:
                    logger.info(f"Context-aware parser found: rank={rank}, kingdom={kingdom_id}, tag={guild_tag}, name={player_name}, score={points} [stage={stage_type}, day={prep_day}]")
                    return KVKLeaderboardEntry(
                        rank=rank,
                        player_name=player_name,
                        kingdom_id=kingdom_id,
                        points=points,
                        guild_tag=guild_tag,
                        is_self=True  # Bottom row is always the user
                    )
            
            return None
            
        except Exception as e:
            logger.debug(f"Simple parser failed: {e}")
            return None
    
    async def _parse_single_row(self, line: str) -> Optional[KVKLeaderboardEntry]:
        """
        Parse a single leaderboard row.
        
        Expected formats:
        - "1 カッサー #10435 14,422,335"
        - "94 [TAO] Mars #10435 7,948,885"
        - "2 camy 14,342,747"
        
        Args:
            line: Single line of text
            
        Returns:
            KVKLeaderboardEntry if parsed successfully, None otherwise
        """
        try:
            # Pattern to match: rank, optional guild tag, player name, optional kingdom, score
            patterns = [
                # Pattern 1: rank name #kingdom score
                r"^(\d+)\s+([^\d#]+?)\s*#(\d+)\s+([\d,]+)$",
                # Pattern 2: rank [tag] name #kingdom score  
                r"^(\d+)\s+\[([A-Z]{3})\]\s+([^\d#]+?)\s*#(\d+)\s+([\d,]+)$",
                # Pattern 3: rank name score (no kingdom)
                r"^(\d+)\s+([^\d]+?)\s+([\d,]+)$",
                # Pattern 4: rank [tag] name score (no kingdom)
                r"^(\d+)\s+\[([A-Z]{3})\]\s+([^\d]+?)\s+([\d,]+)$"
            ]
            
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    groups = match.groups()
                    
                    if len(groups) == 4:  # rank, name, kingdom, score
                        rank = int(groups[0])
                        player_name = groups[1].strip()
                        kingdom_id = int(groups[2]) if groups[2] else None
                        points = int(groups[3].replace(',', ''))
                        guild_tag = None
                    elif len(groups) == 5:  # rank, tag, name, kingdom, score
                        rank = int(groups[0])
                        guild_tag = groups[1]
                        player_name = groups[2].strip()
                        kingdom_id = int(groups[3]) if groups[3] else None
                        points = int(groups[4].replace(',', ''))
                    else:  # rank, name, score (or rank, tag, name, score)
                        rank = int(groups[0])
                        if len(groups) == 4:  # has guild tag
                            guild_tag = groups[1]
                            player_name = groups[2].strip()
                            points = int(groups[3].replace(',', ''))
                        else:  # no guild tag
                            guild_tag = None
                            player_name = groups[1].strip()
                            points = int(groups[2].replace(',', ''))
                        kingdom_id = None
                    
                    return KVKLeaderboardEntry(
                        rank=rank,
                        player_name=player_name,
                        kingdom_id=kingdom_id,
                        points=points,
                        guild_tag=guild_tag
                    )
            
            return None
            
        except (ValueError, IndexError) as e:
            logger.debug("Failed to parse line '%s': %s", line, e)
            return None
    
    async def _identify_self_entry(self, 
                                 entries: List[KVKLeaderboardEntry],
                                 image: Image.Image,
                                 username: str) -> Optional[KVKLeaderboardEntry]:
        """
        Identify which entry belongs to the submitting user.
        
        This would ideally use visual highlighting detection,
        but for now we'll use name matching as a fallback.
        
        Args:
            entries: List of parsed entries
            image: PIL Image object
            username: Discord username for fallback matching
            
        Returns:
            The user's own entry if found
        """
        # TODO: Implement visual highlighting detection using CV2
        # For now, try to match by player name patterns
        
        # Try exact username match first
        for entry in entries:
            if entry.player_name.lower() == username.lower():
                entry.is_self = True
                logger.debug("Found self entry by exact username match: %s", entry.player_name)
                return entry
        
        # Try partial matches
        username_lower = username.lower()
        for entry in entries:
            if username_lower in entry.player_name.lower() or entry.player_name.lower() in username_lower:
                entry.is_self = True
                logger.debug("Found self entry by partial username match: %s", entry.player_name)
                return entry
        
        logger.warning("Could not identify self entry for username: %s", username)
        return None
    
    async def _extract_kingdom_id(self, ocr_text: str) -> Optional[int]:
        """
        Extract kingdom ID from OCR text.
        
        Args:
            ocr_text: OCR extracted text
            
        Returns:
            Kingdom ID if found
        """
        for pattern in self.kingdom_patterns:
            match = re.search(pattern, ocr_text, re.IGNORECASE)
            if match:
                try:
                    kingdom_id = int(match.group(1))
                    logger.debug("Extracted kingdom ID: %d", kingdom_id)
                    return kingdom_id
                except ValueError:
                    continue
        
        logger.warning("Could not extract kingdom ID")
        return None
    
    async def _validate_parse_result(self, result: KVKParseResult) -> None:
        """
        Validate parsed result for consistency.
        
        Args:
            result: Parse result to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Validate stage type
        if result.stage_type == KVKStageType.UNKNOWN:
            logger.warning("Stage type is unknown")
        
        # Validate prep day for prep stage
        if result.stage_type == KVKStageType.PREP:
            if result.prep_day is None:
                logger.warning("Prep day not detected for prep stage")
            elif isinstance(result.prep_day, int) and not (1 <= result.prep_day <= 5):
                logger.warning("Invalid prep day number: %s", result.prep_day)
            elif isinstance(result.prep_day, str) and result.prep_day != "overall":
                logger.warning("Invalid prep day string: %s", result.prep_day)
        
        # Validate entries
        if not result.entries:
            raise ValueError("No leaderboard entries found")
        
        # Validate self entry
        if not result.self_entry:
            logger.warning("Self entry not identified")
        
        # Validate kingdom ID
        if not result.kingdom_id:
            logger.warning("Kingdom ID not extracted")
        
        logger.debug("Parse result validation completed")
    
    async def _log_parse_success(self, result: KVKParseResult, filename: Optional[str]) -> None:
        """Log successful parse to verification log."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "filename": filename,
            "stage_type": result.stage_type.value,
            "prep_day": result.prep_day,
            "kingdom_id": result.kingdom_id,
            "entries_count": len(result.entries),
            "self_entry_found": result.self_entry is not None,
            "user_id": result.metadata.get("user_id"),
            "username": result.metadata.get("username")
        }
        
        # Write to verification log
        log_file = self.log_folder / "kvk_verification.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        logger.info("✅ Screenshot parsed and validated successfully")
    
    async def _log_parse_error(self, error: str, filename: Optional[str], user_id: str) -> None:
        """Log parse error to verification log."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "filename": filename,
            "error": error,
            "user_id": user_id
        }
        
        # Write to verification log
        log_file = self.log_folder / "kvk_verification.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        logger.error("❌ Screenshot parsing failed: %s", error)
    
    async def save_leaderboard_snapshot(self, result: KVKParseResult) -> str:
        """
        Save full parsed leaderboard to logs for analytics.
        
        Args:
            result: Parse result to save
            
        Returns:
            Path to saved snapshot file
        """
        # Create filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        kingdom_str = f"kingdom_{result.kingdom_id}" if result.kingdom_id else "kingdom_unknown"
        day_str = f"day_{result.prep_day}" if result.prep_day else "day_unknown"
        filename = f"{kingdom_str}_{day_str}_{timestamp}.json"
        
        # Ensure leaderboards directory exists
        leaderboards_dir = self.log_folder / "parsed_leaderboards"
        leaderboards_dir.mkdir(exist_ok=True)
        
        # Save snapshot
        snapshot_path = leaderboards_dir / filename
        with open(snapshot_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        logger.info("📊 Leaderboard snapshot saved: %s", filename)
        return str(snapshot_path)
    
    async def update_user_score(self, result: KVKParseResult) -> bool:
        """
        Update the submitting user's score record.
        
        Args:
            result: Parse result containing self entry
            
        Returns:
            True if update was successful
        """
        if not result.self_entry:
            logger.warning("No self entry found, cannot update user score")
            return False
        
        try:
            # Load existing scores
            scores_file = self.cache_folder / "kvk_scores.json"
            if scores_file.exists():
                with open(scores_file, "r") as f:
                    kvk_scores = json.load(f)
            else:
                kvk_scores = {}
            
            # Get user data
            user_id = result.metadata.get("user_id")
            if not user_id:
                logger.warning("No user_id in metadata, cannot update score")
                return False
            
            # Initialize user data if needed
            if user_id not in kvk_scores:
                kvk_scores[user_id] = {"prep": {}, "war": {}}
            
            # Update score based on stage type
            if result.stage_type == KVKStageType.PREP:
                if result.prep_day:
                    kvk_scores[user_id]["prep"][str(result.prep_day)] = result.self_entry.points
            elif result.stage_type == KVKStageType.WAR:
                kvk_scores[user_id]["war_day"] = result.self_entry.points
            
            # Save updated scores
            with open(scores_file, "w") as f:
                json.dump(kvk_scores, f, indent=2)
            
            # Log update
            update_log = self.log_folder / "kvk_self_updates.log"
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "stage_type": result.stage_type.value,
                "prep_day": result.prep_day,
                "points": result.self_entry.points,
                "rank": result.self_entry.rank
            }
            with open(update_log, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            logger.info("💾 User score updated: %s points for %s day %s", 
                       result.self_entry.points, result.stage_type.value, result.prep_day)
            return True
            
        except Exception as e:
            logger.exception("Failed to update user score: %s", e)
            return False