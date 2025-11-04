"""
KVK Visual Manager

Orchestrates the complete KVK visual parsing workflow:
1. Image parsing and validation
2. User score synchronization
3. Leaderboard snapshot storage
4. Comparison engine triggering
5. Verification and logging
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from discord_bot.core.engines.base.logging_utils import get_logger
from discord_bot.core.engines.kvk_image_parser import KVKImageParser, KVKParseResult
from discord_bot.core.engines.kvk_comparison_engine import KVKComparisonEngine, ComparisonResult

logger = get_logger("hippo_bot.kvk_visual_manager")


class KVKVisualManager:
    """
    Main orchestrator for KVK visual parsing system.
    
    Implements the complete workflow from image input to comparison updates.
    """
    
    def __init__(self, 
                 upload_folder: str = "uploads/screenshots",
                 log_folder: str = "logs",
                 cache_folder: str = "cache"):
        self.upload_folder = upload_folder
        self.log_folder = log_folder
        self.cache_folder = cache_folder
        
        # Initialize engines
        self.image_parser = KVKImageParser(upload_folder, log_folder, cache_folder)
        self.comparison_engine = KVKComparisonEngine(cache_folder, log_folder)
        
        # Ensure directories exist
        Path(upload_folder).mkdir(parents=True, exist_ok=True)
        Path(log_folder).mkdir(parents=True, exist_ok=True)
        Path(cache_folder).mkdir(parents=True, exist_ok=True)
        
        logger.info("📸 Visual Parsing System Active")
    
    async def process_kvk_screenshot(self,
                                   image_data: bytes,
                                   user_id: str,
                                   username: str,
                                   filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete KVK screenshot processing workflow.
        
        Args:
            image_data: Raw image bytes
            user_id: Discord user ID
            username: Discord username  
            filename: Optional filename for logging
            
        Returns:
            Dictionary with processing results and status
        """
        workflow_start = datetime.now(timezone.utc)
        
        try:
            logger.info("🔄 Starting KVK screenshot processing for user %s", username)
            
            # Phase 1: Parse screenshot
            logger.debug("Phase 1: Parsing screenshot...")
            parse_result = await self.image_parser.parse_screenshot(
                image_data, user_id, username, filename
            )
            
            if not parse_result:
                return {
                    "success": False,
                    "error": "Failed to parse screenshot",
                    "phase": "parsing"
                }
            
            # Phase 2: Save leaderboard snapshot
            logger.debug("Phase 2: Saving leaderboard snapshot...")
            snapshot_path = await self.image_parser.save_leaderboard_snapshot(parse_result)
            
            # Phase 3: Update user score
            logger.debug("Phase 3: Updating user score...")
            score_updated = await self.image_parser.update_user_score(parse_result)
            
            # Phase 4: Trigger comparison engine
            logger.debug("Phase 4: Triggering comparison engine...")
            comparison_result = await self.comparison_engine.trigger_comparison_update(parse_result)
            
            # Phase 5: Generate success summary
            workflow_end = datetime.now(timezone.utc)
            processing_time = (workflow_end - workflow_start).total_seconds()
            
            success_summary = {
                "success": True,
                "processing_time_seconds": processing_time,
                "parse_result": {
                    "stage_type": parse_result.stage_type.value,
                    "prep_day": parse_result.prep_day,
                    "kingdom_id": parse_result.kingdom_id,
                    "entries_count": len(parse_result.entries),
                    "self_entry_found": parse_result.self_entry is not None
                },
                "score_updated": score_updated,
                "snapshot_path": snapshot_path,
                "comparison_updated": comparison_result is not None,
                "timestamp": workflow_end.isoformat()
            }
            
            # Add self score info if available
            if parse_result.self_entry:
                success_summary["self_score"] = {
                    "rank": parse_result.self_entry.rank,
                    "points": parse_result.self_entry.points,
                    "player_name": parse_result.self_entry.player_name,
                    "guild_tag": parse_result.self_entry.guild_tag
                }
            
            # Add comparison summary if available
            if comparison_result:
                success_summary["comparison"] = {
                    "peer_count": len(comparison_result.peers),
                    "user_power": comparison_result.user_power,
                    "top_peer_ahead_by": comparison_result.peers[0].score_delta if comparison_result.peers else 0
                }
            
            logger.info("✅ KVK screenshot processing completed successfully in %.2fs", processing_time)
            
            # Announce completion
            await self._announce_processing_complete(parse_result, comparison_result)
            
            return success_summary
            
        except Exception as e:
            logger.exception("❌ KVK screenshot processing failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "phase": "workflow"
            }
    
    async def _announce_processing_complete(self,
                                          parse_result: KVKParseResult,
                                          comparison_result: Optional[ComparisonResult]) -> None:
        """
        Announce processing completion.
        
        Args:
            parse_result: Parse result from image processing
            comparison_result: Comparison result if available
        """
        stage_desc = f"{parse_result.stage_type.value} stage"
        day_desc = f"day {parse_result.prep_day}" if parse_result.prep_day else "unknown day"
        
        announcement = f"⚔️ Comparison updated for @{parse_result.metadata.get('username', 'User')} — {stage_desc} {day_desc} synced."
        
        logger.info(announcement)
    
    async def validate_screenshot_requirements(self, image_data: bytes) -> Dict[str, Any]:
        """
        Validate screenshot before processing.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Validation result dictionary
        """
        try:
            is_valid, error_message = await self.image_parser.validate_screenshot(image_data)
            
            return {
                "valid": is_valid,
                "error": error_message if not is_valid else None,
                "requirements_met": is_valid
            }
            
        except Exception as e:
            logger.exception("Screenshot validation failed: %s", e)
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}",
                "requirements_met": False
            }
    
    async def get_user_comparison_status(self,
                                       user_id: str,
                                       stage_type: str = "prep",
                                       prep_day: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get current comparison status for a user.
        
        Args:
            user_id: Discord user ID
            stage_type: Stage type ("prep" or "war")
            prep_day: Prep day (optional)
            
        Returns:
            Comparison status dictionary or None
        """
        try:
            comparison = await self.comparison_engine.get_user_comparison(
                user_id, stage_type, prep_day
            )
            
            if not comparison:
                return None
            
            return {
                "user_score": comparison.user_score,
                "user_rank": comparison.user_rank,
                "user_power": comparison.user_power,
                "peer_count": len(comparison.peers),
                "ahead_of": len([p for p in comparison.peers if p.score_delta < 0]),
                "behind": len([p for p in comparison.peers if p.score_delta > 0]),
                "last_updated": comparison.analysis_timestamp,
                "top_performer": {
                    "username": comparison.peers[0].username,
                    "score_delta": comparison.peers[0].score_delta
                } if comparison.peers else None
            }
            
        except Exception as e:
            logger.exception("Failed to get user comparison status: %s", e)
            return None
    
    async def set_user_power_level(self, user_id: str, power_level: int, username: str) -> bool:
        """
        Set or update a user's power level for comparison tracking.
        
        Args:
            user_id: Discord user ID
            power_level: User's power level
            username: User's display name
            
        Returns:
            True if successful
        """
        try:
            await self.comparison_engine.set_user_power_level(user_id, power_level, username)
            logger.info("Power level set for %s: %d", username, power_level)
            return True
        except Exception as e:
            logger.exception("Failed to set power level for %s: %s", username, e)
            return False
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get overall system status and diagnostics.
        
        Returns:
            System status dictionary
        """
        try:
            # Check if required dependencies are available
            dependencies_ok = self.image_parser.available
            
            # Check if directories exist
            directories_ok = all([
                Path(self.upload_folder).exists(),
                Path(self.log_folder).exists(),
                Path(self.cache_folder).exists()
            ])
            
            # Count cached data
            cache_files = {
                "kvk_scores": (Path(self.cache_folder) / "kvk_scores.json").exists(),
                "power_levels": (Path(self.cache_folder) / "user_power_levels.json").exists(),
                "comparisons": (Path(self.cache_folder) / "kvk_compare_pairs.json").exists(),
                "usernames": (Path(self.cache_folder) / "user_names.json").exists()
            }
            
            return {
                "system_active": dependencies_ok and directories_ok,
                "dependencies_available": dependencies_ok,
                "directories_ready": directories_ok,
                "cache_files": cache_files,
                "upload_folder": str(self.upload_folder),
                "log_folder": str(self.log_folder),
                "cache_folder": str(self.cache_folder),
                "status_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.exception("Failed to get system status: %s", e)
            return {
                "system_active": False,
                "error": str(e),
                "status_timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """
        Clean up old logs and snapshots.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Cleanup summary
        """
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            cleaned_files = {
                "snapshots": 0,
                "logs": 0,
                "total_mb_freed": 0
            }
            
            # Clean old leaderboard snapshots
            snapshots_dir = Path(self.log_folder) / "parsed_leaderboards"
            if snapshots_dir.exists():
                for file_path in snapshots_dir.glob("*.json"):
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        file_path.unlink()
                        cleaned_files["snapshots"] += 1
                        cleaned_files["total_mb_freed"] += size_mb
            
            # Clean old log files (could be enhanced to clean specific log entries)
            # For now, just report what would be cleaned
            
            logger.info("Cleanup completed: %d snapshots removed, %.2f MB freed", 
                       cleaned_files["snapshots"], cleaned_files["total_mb_freed"])
            
            return cleaned_files
            
        except Exception as e:
            logger.exception("Cleanup failed: %s", e)
            return {"error": str(e)}


# Factory function for easy integration
async def create_kvk_visual_manager(**kwargs) -> KVKVisualManager:
    """
    Create and initialize KVK Visual Manager.
    
    Returns:
        Configured KVKVisualManager instance
    """
    manager = KVKVisualManager(**kwargs)
    
    # Verify system is ready
    status = await manager.get_system_status()
    if not status.get("system_active", False):
        logger.warning("KVK Visual Manager created but system not fully active: %s", status)
    
    return manager