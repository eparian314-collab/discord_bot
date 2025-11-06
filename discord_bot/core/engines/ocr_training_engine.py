"""
OCR Training Engine - Interactive learning system for screenshot processing.

This engine processes sample screenshots on startup, compares OCR results with
ground truth provided by the bot owner, and builds smart normalization patterns
for improved accuracy.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import discord

from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor, RankingData

logger = logging.getLogger("hippo_bot.ocr_training")


@dataclass
class OcrGroundTruth:
    """Ground truth values provided by owner for training."""
    server_id: int
    guild_tag: str
    player_name: str
    score: int
    phase: str  # "prep" or "war"
    day: Optional[int | str]  # 1-5, "overall", or None
    rank: int
    
    # Original OCR output for comparison
    ocr_server_id: Optional[int] = None
    ocr_guild_tag: Optional[str] = None
    ocr_player_name: Optional[str] = None
    ocr_score: Optional[int] = None
    ocr_phase: Optional[str] = None
    ocr_day: Optional[int | str] = None
    ocr_rank: Optional[int] = None
    
    screenshot_filename: str = ""
    timestamp: str = ""


@dataclass
class CorrectionPattern:
    """Learned correction pattern for OCR normalization."""
    field_name: str  # "guild_tag", "player_name", "score", etc.
    ocr_value: str  # What OCR detected
    correct_value: str  # What it should be
    frequency: int = 1  # How many times this correction was applied
    confidence: float = 1.0  # Confidence in this correction


class OcrTrainingEngine:
    """
    Interactive OCR training system.
    
    On startup:
    1. Scans logs/screenshots for training images
    2. Processes each through OCR pipeline
    3. DMs owner with results and asks for corrections
    4. Builds normalization patterns from corrections
    5. Applies learned patterns to future OCR results
    """
    
    def __init__(
        self,
        processor: ScreenshotProcessor,
        training_data_path: str = "data/ocr_training.json",
        screenshots_dir: str = "logs/screenshots"
    ):
        self.processor = processor
        self.training_data_path = Path(training_data_path)
        self.screenshots_dir = Path(screenshots_dir)
        self.corrections: List[OcrGroundTruth] = []
        self.patterns: Dict[str, List[CorrectionPattern]] = {}
        self._load_training_data()
    
    def _load_training_data(self):
        """Load existing training data from disk."""
        if not self.training_data_path.exists():
            logger.info("No existing OCR training data found")
            return
        
        try:
            with open(self.training_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.corrections = [
                    OcrGroundTruth(**item) for item in data.get('corrections', [])
                ]
                
                # Rebuild patterns from corrections
                self._build_patterns_from_corrections()
                
                logger.info(
                    "Loaded %d OCR corrections and %d patterns from training data",
                    len(self.corrections),
                    sum(len(patterns) for patterns in self.patterns.values())
                )
        except Exception as e:
            logger.error("Failed to load OCR training data: %s", e)
    
    def _save_training_data(self):
        """Save training data to disk."""
        try:
            self.training_data_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'corrections': [asdict(c) for c in self.corrections],
                'patterns': {
                    field: [asdict(p) for p in patterns]
                    for field, patterns in self.patterns.items()
                },
                'last_updated': datetime.utcnow().isoformat(),
            }
            
            with open(self.training_data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("Saved OCR training data with %d corrections", len(self.corrections))
        except Exception as e:
            logger.error("Failed to save OCR training data: %s", e)
    
    def _build_patterns_from_corrections(self):
        """Build correction patterns from accumulated ground truth data."""
        self.patterns.clear()
        
        for correction in self.corrections:
            # Compare each field and build correction patterns
            fields = [
                ('guild_tag', correction.ocr_guild_tag, correction.guild_tag),
                ('player_name', correction.ocr_player_name, correction.player_name),
                ('phase', correction.ocr_phase, correction.phase),
            ]
            
            for field_name, ocr_val, correct_val in fields:
                if ocr_val is None or correct_val is None:
                    continue
                if str(ocr_val) == str(correct_val):
                    continue  # No correction needed
                
                # Add or update pattern
                if field_name not in self.patterns:
                    self.patterns[field_name] = []
                
                # Check if pattern already exists
                existing = next(
                    (p for p in self.patterns[field_name] 
                     if p.ocr_value == str(ocr_val) and p.correct_value == str(correct_val)),
                    None
                )
                
                if existing:
                    existing.frequency += 1
                else:
                    self.patterns[field_name].append(
                        CorrectionPattern(
                            field_name=field_name,
                            ocr_value=str(ocr_val),
                            correct_value=str(correct_val),
                        )
                    )
        
        logger.info("Built %d correction patterns from training data", 
                   sum(len(patterns) for patterns in self.patterns.values()))
    
    async def run_training_session(self, bot: discord.Client, owner_id: int):
        """
        Run interactive training session on startup.
        
        Args:
            bot: Discord bot instance
            owner_id: Discord user ID of bot owner
        """
        if not self.screenshots_dir.exists():
            logger.warning("Screenshots directory not found: %s", self.screenshots_dir)
            return
        
        # Get all image files
        image_files = list(self.screenshots_dir.glob("*.png")) + \
                     list(self.screenshots_dir.glob("*.jpg")) + \
                     list(self.screenshots_dir.glob("*.jpeg"))
        
        if not image_files:
            logger.info("No training screenshots found in %s", self.screenshots_dir)
            return
        
        logger.info("Found %d training screenshots, starting interactive session", len(image_files))
        
        # Get owner user
        try:
            owner = await bot.fetch_user(owner_id)
        except Exception as e:
            logger.error("Could not fetch owner user %s: %s", owner_id, e)
            return
        
        # Send initial message
        try:
            await owner.send(
                "🤖 **OCR Training Session Started**\n\n"
                f"I found {len(image_files)} screenshot(s) in `logs/screenshots`.\n"
                "I'll process each one and ask you to verify or correct the extracted values.\n\n"
                "This will help me learn and improve screenshot parsing accuracy!"
            )
        except Exception as e:
            logger.error("Could not send DM to owner: %s", e)
            return
        
        # Process each screenshot
        for idx, image_path in enumerate(image_files, 1):
            try:
                await self._process_training_image(bot, owner, image_path, idx, len(image_files))
                # Small delay between images to avoid rate limits
                await asyncio.sleep(2)
            except Exception as e:
                logger.error("Error processing training image %s: %s", image_path.name, e)
                try:
                    await owner.send(f"❌ Error processing `{image_path.name}`: {e}")
                except:
                    pass
        
        # Save accumulated training data
        self._save_training_data()
        
        # Send completion message
        try:
            await owner.send(
                f"✅ **Training Session Complete**\n\n"
                f"Processed: {len(image_files)} screenshot(s)\n"
                f"Total corrections: {len(self.corrections)}\n"
                f"Learned patterns: {sum(len(p) for p in self.patterns.values())}\n\n"
                "These corrections will be applied automatically to future submissions!"
            )
        except:
            pass
        
        logger.info("OCR training session completed successfully")
    
    async def _process_training_image(
        self,
        bot: discord.Client,
        owner: discord.User,
        image_path: Path,
        current: int,
        total: int
    ):
        """Process a single training image and collect ground truth."""
        logger.info("Processing training image %d/%d: %s", current, total, image_path.name)
        
        # Read image data
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Process through OCR pipeline
        parsed = await self.processor.process_screenshot(
            image_data,
            user_id=str(owner.id),
            username=owner.name,
            guild_id=None
        )
        
        # Send results to owner for verification
        embed = discord.Embed(
            title=f"🔍 Training Screenshot {current}/{total}",
            description=f"**File:** `{image_path.name}`\n\n"
                       "Please review the OCR results below and provide corrections:",
            color=discord.Color.blue()
        )
        
        if parsed:
            embed.add_field(
                name="📊 OCR Extracted Values",
                value=(
                    f"**Server ID:** {getattr(parsed, 'server_id', 'N/A')}\n"
                    f"**Guild Tag:** {parsed.guild_tag or 'N/A'}\n"
                    f"**Player Name:** {parsed.player_name or 'N/A'}\n"
                    f"**Score:** {parsed.score:,} pts\n"
                    f"**Phase:** {parsed.phase}\n"
                    f"**Day:** {parsed.day if parsed.day is not None else 'N/A'}\n"
                    f"**Rank:** #{parsed.rank:,}\n"
                ),
                inline=False
            )
            
            # Add confidence scores if available
            if hasattr(parsed, 'confidence_map') and parsed.confidence_map:
                conf_text = "\n".join(
                    f"{k}: {v:.1%}" for k, v in parsed.confidence_map.items()
                )
                embed.add_field(
                    name="🎯 OCR Confidence",
                    value=conf_text or "N/A",
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ OCR Failed",
                value="Could not extract ranking data from this screenshot.",
                inline=False
            )
        
        embed.add_field(
            name="✏️ How to Respond",
            value=(
                "Reply with the **correct values** in this format:\n"
                "```\n"
                "server_id: 10435\n"
                "guild: TAO\n"
                "player: Mars\n"
                "score: 25200103\n"
                "phase: prep\n"
                "day: 3\n"
                "rank: 94\n"
                "```\n"
                "Or reply **\"skip\"** to skip this image."
            ),
            inline=False
        )
        
        # Send embed with screenshot attachment
        try:
            with open(image_path, 'rb') as f:
                file = discord.File(f, filename=image_path.name)
                await owner.send(embed=embed, file=file)
        except Exception as e:
            logger.error("Could not send training embed: %s", e)
            return
        
        # Wait for owner response
        def check(m: discord.Message) -> bool:
            return m.author.id == owner.id and isinstance(m.channel, discord.DMChannel)
        
        try:
            response = await bot.wait_for('message', check=check, timeout=300.0)  # 5 minute timeout
        except asyncio.TimeoutError:
            await owner.send("⏱️ Timeout - skipping this image")
            return
        
        # Parse response
        response_text = response.content.strip().lower()
        
        if response_text == "skip":
            await owner.send("⏭️ Skipped")
            return
        
        # Parse ground truth from response
        try:
            ground_truth = self._parse_ground_truth_response(response.content, parsed)
            ground_truth.screenshot_filename = image_path.name
            ground_truth.timestamp = datetime.utcnow().isoformat()
            
            # Store correction
            self.corrections.append(ground_truth)
            
            # Update patterns
            self._build_patterns_from_corrections()
            
            await owner.send(
                "✅ **Correction Saved**\n"
                f"This will help improve future OCR accuracy for similar screenshots."
            )
            
            logger.info("Saved ground truth correction for %s", image_path.name)
            
        except ValueError as e:
            await owner.send(f"❌ Could not parse response: {e}\nPlease try again with the correct format.")
            # Retry
            await self._process_training_image(bot, owner, image_path, current, total)
    
    def _parse_ground_truth_response(
        self,
        response_text: str,
        parsed: Optional[RankingData]
    ) -> OcrGroundTruth:
        """Parse ground truth values from owner's response."""
        lines = response_text.strip().split('\n')
        values = {}
        
        for line in lines:
            line = line.strip()
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            values[key] = value
        
        # Extract required fields
        try:
            server_id = int(values.get('server_id', values.get('server', 0)))
            guild_tag = values.get('guild', values.get('guild_tag', '')).upper()
            player_name = values.get('player', values.get('player_name', ''))
            score = int(values.get('score', '0').replace(',', '').replace(' ', ''))
            phase = values.get('phase', 'prep').lower()
            rank = int(values.get('rank', '0').replace(',', '').replace(' ', ''))
            
            # Parse day (can be int or "overall")
            day_str = values.get('day', '1')
            if day_str.lower() in ['overall', 'all', 'total']:
                day = "overall"
            elif day_str.lower() in ['none', 'null', 'n/a']:
                day = None
            else:
                day = int(day_str)
            
        except (ValueError, KeyError) as e:
            raise ValueError(f"Missing or invalid field: {e}")
        
        # Create ground truth with OCR values for comparison
        return OcrGroundTruth(
            server_id=server_id,
            guild_tag=guild_tag,
            player_name=player_name,
            score=score,
            phase=phase,
            day=day,
            rank=rank,
            ocr_server_id=getattr(parsed, 'server_id', None) if parsed else None,
            ocr_guild_tag=parsed.guild_tag if parsed else None,
            ocr_player_name=parsed.player_name if parsed else None,
            ocr_score=parsed.score if parsed else None,
            ocr_phase=parsed.phase if parsed else None,
            ocr_day=parsed.day if parsed else None,
            ocr_rank=parsed.rank if parsed else None,
        )
    
    def apply_learned_corrections(self, ranking: RankingData) -> RankingData:
        """
        Apply learned correction patterns to OCR results.
        
        Args:
            ranking: OCR-extracted ranking data
            
        Returns:
            Corrected ranking data
        """
        if not self.patterns:
            return ranking  # No corrections to apply
        
        corrections_applied = []
        
        # Apply guild_tag corrections
        if ranking.guild_tag and 'guild_tag' in self.patterns:
            for pattern in self.patterns['guild_tag']:
                if ranking.guild_tag == pattern.ocr_value:
                    ranking.guild_tag = pattern.correct_value
                    corrections_applied.append(f"guild_tag: {pattern.ocr_value} → {pattern.correct_value}")
                    break
        
        # Apply player_name corrections
        if ranking.player_name and 'player_name' in self.patterns:
            for pattern in self.patterns['player_name']:
                if ranking.player_name == pattern.ocr_value:
                    ranking.player_name = pattern.correct_value
                    corrections_applied.append(f"player_name: {pattern.ocr_value} → {pattern.correct_value}")
                    break
        
        # Apply phase corrections
        if ranking.phase and 'phase' in self.patterns:
            for pattern in self.patterns['phase']:
                if ranking.phase == pattern.ocr_value:
                    ranking.phase = pattern.correct_value
                    corrections_applied.append(f"phase: {pattern.ocr_value} → {pattern.correct_value}")
                    break
        
        if corrections_applied:
            logger.info("Applied %d learned corrections: %s", len(corrections_applied), corrections_applied)
        
        return ranking
