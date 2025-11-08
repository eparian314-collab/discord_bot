"""
KVK Comparison Engine

Handles power-band comparisons and rank analysis for KVK tracking.
Triggered automatically after screenshot parsing to compute ΔScore and ΔRank.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from discord_bot.core.engines.base.logging_utils import get_logger
from discord_bot.core.engines.kvk_image_parser import KVKParseResult, KVKStageType

logger = get_logger("hippo_bot.kvk_comparison")


@dataclass
class PowerBandPeer:
    """A peer player within the same power band."""
    user_id: str
    username: str
    power_level: int
    current_score: int
    current_rank: int
    score_delta: int  # Difference from reference user
    rank_delta: int   # Difference from reference user


@dataclass
class ComparisonResult:
    """Result of power band comparison analysis."""
    user_id: str
    stage_type: str
    prep_day: Optional[str]
    user_score: int
    user_rank: int
    user_power: int
    peers: List[PowerBandPeer]
    analysis_timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "stage_type": self.stage_type,
            "prep_day": self.prep_day,
            "user_score": self.user_score,
            "user_rank": self.user_rank,
            "user_power": self.user_power,
            "peers": [
                {
                    "user_id": peer.user_id,
                    "username": peer.username,
                    "power_level": peer.power_level,
                    "current_score": peer.current_score,
                    "current_rank": peer.current_rank,
                    "score_delta": peer.score_delta,
                    "rank_delta": peer.rank_delta
                }
                for peer in self.peers
            ],
            "analysis_timestamp": self.analysis_timestamp
        }


class KVKComparisonEngine:
    """
    Manages power-band comparisons for KVK tracking.
    
    Workflow:
    1. Load user power levels
    2. Identify peers within ±10% power
    3. Compute score and rank deltas
    4. Update comparison cache
    5. Generate analysis summary
    """
    
    def __init__(self, cache_folder: str = "cache", log_folder: str = "logs"):
        self.cache_folder = Path(cache_folder)
        self.log_folder = Path(log_folder)
        
        # Ensure directories exist
        self.cache_folder.mkdir(parents=True, exist_ok=True)
        self.log_folder.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.power_band_threshold = 0.10  # ±10% power difference
        
    async def trigger_comparison_update(self, parse_result: KVKParseResult) -> Optional[ComparisonResult]:
        """
        Trigger automatic comparison update after screenshot parsing.
        
        Args:
            parse_result: Result from KVK image parser
            
        Returns:
            ComparisonResult if successful, None if failed
        """
        if not parse_result.self_entry:
            logger.warning("No self entry in parse result, cannot run comparison")
            return None
            
        user_id = parse_result.metadata.get("user_id")
        if not user_id:
            logger.warning("No user_id in metadata, cannot run comparison")
            return None
            
        try:
            # Load user power level
            user_power = await self._get_user_power_level(user_id)
            if user_power is None:
                logger.warning("No power level found for user %s", user_id)
                return None
            
            # Find peers within power band
            peers = await self._find_power_band_peers(user_id, user_power)
            
            # Load current scores for all peers
            peer_scores = await self._load_peer_scores(peers, parse_result.stage_type, parse_result.prep_day)
            
            # Compute deltas
            peer_comparisons = await self._compute_peer_deltas(
                user_score=parse_result.self_entry.points,
                user_rank=parse_result.self_entry.rank,
                peer_scores=peer_scores
            )
            
            # Create comparison result
            result = ComparisonResult(
                user_id=user_id,
                stage_type=parse_result.stage_type.value,
                prep_day=str(parse_result.prep_day) if parse_result.prep_day else None,
                user_score=parse_result.self_entry.points,
                user_rank=parse_result.self_entry.rank,
                user_power=user_power,
                peers=peer_comparisons,
                analysis_timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            # Update cache
            await self._update_comparison_cache(result)
            
            # Log analysis
            await self._log_comparison_update(result)
            
            logger.info("⚔️ Comparison updated for user %s - %s day %s synced", 
                       user_id, parse_result.stage_type.value, parse_result.prep_day)
            
            return result
            
        except Exception as e:
            logger.exception("Failed to update comparison for user %s: %s", user_id, e)
            return None
    
    async def _get_user_power_level(self, user_id: str) -> Optional[int]:
        """
        Get stored power level for user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Power level if found, None otherwise
        """
        power_file = self.cache_folder / "user_power_levels.json"
        if not power_file.exists():
            logger.warning("Power levels file not found: %s", power_file)
            return None
            
        try:
            with open(power_file, "r") as f:
                power_data = json.load(f)
            
            return power_data.get(user_id)
            
        except Exception as e:
            logger.exception("Failed to load user power level: %s", e)
            return None
    
    async def _find_power_band_peers(self, user_id: str, user_power: int) -> List[Dict[str, Any]]:
        """
        Find all users within ±10% power of the reference user.
        
        Args:
            user_id: Reference user ID
            user_power: Reference user's power level
            
        Returns:
            List of peer user data
        """
        power_file = self.cache_folder / "user_power_levels.json"
        if not power_file.exists():
            return []
            
        try:
            with open(power_file, "r") as f:
                power_data = json.load(f)
            
            # Calculate power band range
            power_min = int(user_power * (1 - self.power_band_threshold))
            power_max = int(user_power * (1 + self.power_band_threshold))
            
            peers = []
            for peer_id, peer_power in power_data.items():
                if peer_id == user_id:
                    continue  # Skip self
                    
                if power_min <= peer_power <= power_max:
                    peers.append({
                        "user_id": peer_id,
                        "power_level": peer_power
                    })
            
            logger.debug("Found %d peers in power band %d-%d for user %s", 
                        len(peers), power_min, power_max, user_id)
            return peers
            
        except Exception as e:
            logger.exception("Failed to find power band peers: %s", e)
            return []
    
    async def _load_peer_scores(self, 
                              peers: List[Dict[str, Any]], 
                              stage_type: KVKStageType,
                              prep_day: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """
        Load current scores for all peers.
        
        Args:
            peers: List of peer user data
            stage_type: Current stage type
            prep_day: Current prep day
            
        Returns:
            Dictionary mapping user_id to score data
        """
        scores_file = self.cache_folder / "kvk_scores.json"
        if not scores_file.exists():
            return {}
            
        try:
            with open(scores_file, "r") as f:
                all_scores = json.load(f)
            
            peer_scores = {}
            for peer in peers:
                peer_id = peer["user_id"]
                
                if peer_id not in all_scores:
                    continue
                    
                peer_data = all_scores[peer_id]
                
                # Get score for current stage/day
                current_score = 0
                current_rank = 999999  # Default high rank
                
                stage_str = stage_type.value if hasattr(stage_type, 'value') else str(stage_type)
                
                if stage_str == "prep" and prep_day:
                    if "prep" in peer_data and str(prep_day) in peer_data["prep"]:
                        current_score = peer_data["prep"][str(prep_day)]
                elif stage_str == "war":
                    if "war" in peer_data and "war_day" in peer_data["war"]:
                        current_score = peer_data["war"]["war_day"]
                
                peer_scores[peer_id] = {
                    "score": current_score,
                    "rank": current_rank,  # We don't track ranks yet, could be enhanced
                    "power_level": peer["power_level"]
                }
            
            return peer_scores
            
        except Exception as e:
            logger.exception("Failed to load peer scores: %s", e)
            return {}
    
    async def _compute_peer_deltas(self,
                                 user_score: int,
                                 user_rank: int,
                                 peer_scores: Dict[str, Dict[str, Any]]) -> List[PowerBandPeer]:
        """
        Compute score and rank deltas for all peers.
        
        Args:
            user_score: Reference user's score
            user_rank: Reference user's rank
            peer_scores: Peer score data
            
        Returns:
            List of peer comparisons with deltas
        """
        peer_comparisons = []
        
        # Load usernames for display
        usernames = await self._load_usernames()
        
        for peer_id, peer_data in peer_scores.items():
            peer_score = peer_data["score"]
            peer_rank = peer_data["rank"]
            peer_power = peer_data["power_level"]
            
            # Calculate deltas (positive = peer is ahead)
            score_delta = peer_score - user_score
            rank_delta = user_rank - peer_rank  # Lower rank number is better
            
            peer_comparison = PowerBandPeer(
                user_id=peer_id,
                username=usernames.get(peer_id, f"User {peer_id}"),
                power_level=peer_power,
                current_score=peer_score,
                current_rank=peer_rank,
                score_delta=score_delta,
                rank_delta=rank_delta
            )
            
            peer_comparisons.append(peer_comparison)
        
        # Sort by score delta (most ahead first)
        peer_comparisons.sort(key=lambda x: x.score_delta, reverse=True)
        
        return peer_comparisons
    
    async def _load_usernames(self) -> Dict[str, str]:
        """Load cached usernames for display."""
        usernames_file = self.cache_folder / "user_names.json"
        if not usernames_file.exists():
            return {}
            
        try:
            with open(usernames_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.exception("Failed to load usernames: %s", e)
            return {}
    
    async def _update_comparison_cache(self, result: ComparisonResult) -> None:
        """
        Update comparison pairs cache.
        
        Args:
            result: Comparison result to cache
        """
        cache_file = self.cache_folder / "kvk_compare_pairs.json"
        
        try:
            # Load existing cache
            if cache_file.exists():
                with open(cache_file, "r") as f:
                    cache = json.load(f)
            else:
                cache = {}
            
            # Update cache with new result
            cache_key = f"{result.user_id}_{result.stage_type}_{result.prep_day}"
            cache[cache_key] = result.to_dict()
            
            # Save updated cache
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
            
            logger.debug("Comparison cache updated for key: %s", cache_key)
            
        except Exception as e:
            logger.exception("Failed to update comparison cache: %s", e)
    
    async def _log_comparison_update(self, result: ComparisonResult) -> None:
        """
        Log comparison update for audit trail.
        
        Args:
            result: Comparison result to log
        """
        log_file = self.log_folder / "kvk_comparison_updates.log"
        
        log_entry = {
            "timestamp": result.analysis_timestamp,
            "user_id": result.user_id,
            "stage_type": result.stage_type,
            "prep_day": result.prep_day,
            "user_score": result.user_score,
            "user_rank": result.user_rank,
            "user_power": result.user_power,
            "peers_count": len(result.peers),
            "top_peer_delta": result.peers[0].score_delta if result.peers else 0
        }
        
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.exception("Failed to log comparison update: %s", e)
    
    async def get_user_comparison(self, 
                                user_id: str, 
                                stage_type: str,
                                prep_day: Optional[str] = None) -> Optional[ComparisonResult]:
        """
        Get cached comparison result for user.
        
        Args:
            user_id: Discord user ID
            stage_type: Stage type ("prep" or "war")
            prep_day: Prep day (optional)
            
        Returns:
            ComparisonResult if found, None otherwise
        """
        cache_file = self.cache_folder / "kvk_compare_pairs.json"
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
            
            cache_key = f"{user_id}_{stage_type}_{prep_day}"
            cached_data = cache.get(cache_key)
            
            if not cached_data:
                return None
            
            # Reconstruct ComparisonResult from cached data
            peers = [
                PowerBandPeer(
                    user_id=peer["user_id"],
                    username=peer["username"],
                    power_level=peer["power_level"],
                    current_score=peer["current_score"],
                    current_rank=peer["current_rank"],
                    score_delta=peer["score_delta"],
                    rank_delta=peer["rank_delta"]
                )
                for peer in cached_data["peers"]
            ]
            
            return ComparisonResult(
                user_id=cached_data["user_id"],
                stage_type=cached_data["stage_type"],
                prep_day=cached_data["prep_day"],
                user_score=cached_data["user_score"],
                user_rank=cached_data["user_rank"],
                user_power=cached_data["user_power"],
                peers=peers,
                analysis_timestamp=cached_data["analysis_timestamp"]
            )
            
        except Exception as e:
            logger.exception("Failed to get user comparison: %s", e)
            return None
    
    async def set_user_power_level(self, user_id: str, power_level: int, username: str) -> None:
        """
        Set or update a user's power level.
        
        Args:
            user_id: Discord user ID
            power_level: User's power level
            username: User's display name
        """
        # Update power levels
        power_file = self.cache_folder / "user_power_levels.json"
        try:
            if power_file.exists():
                with open(power_file, "r") as f:
                    power_data = json.load(f)
            else:
                power_data = {}
            
            power_data[user_id] = power_level
            
            with open(power_file, "w") as f:
                json.dump(power_data, f, indent=2)
            
        except Exception as e:
            logger.exception("Failed to update user power level: %s", e)
            return
        
        # Update usernames
        usernames_file = self.cache_folder / "user_names.json"
        try:
            if usernames_file.exists():
                with open(usernames_file, "r") as f:
                    usernames = json.load(f)
            else:
                usernames = {}
            
            usernames[user_id] = username
            
            with open(usernames_file, "w") as f:
                json.dump(usernames, f, indent=2)
            
            logger.info("Updated power level for %s (%s): %d", username, user_id, power_level)
            
        except Exception as e:
            logger.exception("Failed to update username: %s", e)