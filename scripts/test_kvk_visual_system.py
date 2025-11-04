"""
Test script for KVK Image Parser

Tests the visual parsing system with mock data to validate functionality.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.engines.kvk_image_parser import KVKImageParser, KVKStageType
from core.engines.kvk_comparison_engine import KVKComparisonEngine
from core.engines.kvk_visual_manager import KVKVisualManager


async def test_kvk_visual_system():
    """Test the complete KVK visual parsing system."""
    print("🔍 Testing KVK Visual Parsing System")
    print("=" * 50)
    
    # Create test directories
    test_upload_folder = "test_uploads"
    test_log_folder = "test_logs"
    test_cache_folder = "test_cache"
    
    for folder in [test_upload_folder, test_log_folder, test_cache_folder]:
        Path(folder).mkdir(exist_ok=True)
    
    # Initialize the visual manager
    print("📦 Initializing KVK Visual Manager...")
    visual_manager = KVKVisualManager(
        upload_folder=test_upload_folder,
        log_folder=test_log_folder,
        cache_folder=test_cache_folder
    )
    
    # Check system status
    print("\n🔧 Checking system status...")
    status = await visual_manager.get_system_status()
    print(f"System active: {status.get('system_active', False)}")
    print(f"Dependencies available: {status.get('dependencies_available', False)}")
    print(f"Directories ready: {status.get('directories_ready', False)}")
    
    if not status.get('system_active', False):
        print("⚠️ System not fully active. Some dependencies may be missing.")
        print("Install with: pip install Pillow pytesseract opencv-python")
        print("Also ensure Tesseract binary is installed on your system.")
    
    # Test power level setting
    print("\n⚡ Testing power level management...")
    test_user_id = "123456789"
    test_username = "TestUser"
    test_power = 25000000  # 25M power
    
    success = await visual_manager.set_user_power_level(test_user_id, test_power, test_username)
    print(f"Power level set: {success}")
    
    # Create mock peers for comparison testing
    print("\n👥 Setting up mock peer data...")
    comparison_engine = visual_manager.comparison_engine
    
    # Add some mock peers with similar power levels
    mock_peers = [
        ("user_001", "PlayerOne", 24000000, test_username),
        ("user_002", "PlayerTwo", 26000000, test_username),
        ("user_003", "PlayerThree", 23500000, test_username),
        ("user_004", "PlayerFour", 27000000, test_username),
    ]
    
    for user_id, username, power, _ in mock_peers:
        await comparison_engine.set_user_power_level(user_id, power, username)
    
    print(f"Added {len(mock_peers)} mock peers for testing")
    
    # Test mock KVK scores
    print("\n📊 Setting up mock KVK scores...")
    mock_scores = {
        test_user_id: {
            "prep": {"1": 5000000, "2": 8000000, "3": 12000000},
            "war": {"war_day": 20000000}
        },
        "user_001": {
            "prep": {"1": 4800000, "2": 7500000, "3": 11500000},
            "war": {"war_day": 19000000}
        },
        "user_002": {
            "prep": {"1": 5200000, "2": 8500000, "3": 13000000},
            "war": {"war_day": 22000000}
        },
        "user_003": {
            "prep": {"1": 4600000, "2": 7200000, "3": 11000000},
            "war": {"war_day": 18500000}
        },
        "user_004": {
            "prep": {"1": 5500000, "2": 9000000, "3": 14000000},
            "war": {"war_day": 24000000}
        }
    }
    
    # Write mock scores to cache
    scores_file = Path(test_cache_folder) / "kvk_scores.json"
    with open(scores_file, "w") as f:
        json.dump(mock_scores, f, indent=2)
    
    print("Mock KVK scores saved to cache")
    
    # Test comparison status
    print("\n📈 Testing comparison status...")
    prep_status = await visual_manager.get_user_comparison_status(test_user_id, "prep", "3")
    if prep_status:
        print(f"Prep Day 3 Status:")
        print(f"  Score: {prep_status['user_score']:,}")
        print(f"  Power: {prep_status['user_power']:,}")
        print(f"  Peers: {prep_status['peer_count']}")
        print(f"  Ahead of: {prep_status['ahead_of']}/{prep_status['peer_count']}")
    else:
        print("No prep comparison status found")
    
    # Test image validation (with dummy data since we don't have real images)
    print("\n🖼️ Testing image validation...")
    try:
        # Create a small dummy image for testing
        from PIL import Image
        import io
        
        # Create a small test image
        test_image = Image.new('RGB', (100, 100), color='white')
        img_buffer = io.BytesIO()
        test_image.save(img_buffer, format='PNG')
        dummy_image_data = img_buffer.getvalue()
        
        validation = await visual_manager.validate_screenshot_requirements(dummy_image_data)
        print(f"Image validation result: {validation}")
        
    except Exception as e:
        print(f"Image validation test skipped (dependencies not available): {e}")
    
    # Test cleanup
    print("\n🧹 Testing cleanup...")
    cleanup_result = await visual_manager.cleanup_old_data(days_to_keep=1)
    print(f"Cleanup result: {cleanup_result}")
    
    # Final system status
    print("\n📋 Final system status...")
    final_status = await visual_manager.get_system_status()
    cache_files = final_status.get("cache_files", {})
    active_files = [name for name, exists in cache_files.items() if exists]
    print(f"Active cache files: {active_files}")
    
    print("\n✅ KVK Visual System test completed!")
    print(f"Check test folders for generated files:")
    print(f"  - {test_cache_folder}/")
    print(f"  - {test_log_folder}/")
    print(f"  - {test_upload_folder}/")


async def test_mock_parse_result():
    """Test creating and processing a mock parse result."""
    print("\n🎯 Testing mock parse result creation...")
    
    from core.engines.kvk_image_parser import KVKParseResult, KVKLeaderboardEntry, KVKStageType
    
    # Create mock leaderboard entries
    mock_entries = [
        KVKLeaderboardEntry(rank=1, player_name="TopPlayer", kingdom_id=10435, points=28200103, guild_tag="TOP"),
        KVKLeaderboardEntry(rank=2, player_name="SecondPlace", kingdom_id=10435, points=25100000, guild_tag="SEC"),
        KVKLeaderboardEntry(rank=94, player_name="TestUser", kingdom_id=10435, points=7948885, guild_tag="TAO", is_self=True),
        KVKLeaderboardEntry(rank=150, player_name="LowerRank", kingdom_id=10435, points=5200000, guild_tag="LOW"),
    ]
    
    # Create mock parse result
    mock_result = KVKParseResult(
        stage_type=KVKStageType.PREP,
        prep_day=3,
        kingdom_id=10435,
        entries=mock_entries,
        self_entry=mock_entries[2],  # TestUser entry
        metadata={
            "parser_version": "1.0",
            "user_id": "123456789",
            "username": "TestUser",
            "filename": "mock_screenshot.png",
            "timestamp": datetime.now().isoformat(),
            "ocr_text_length": 500,
            "entries_count": len(mock_entries)
        }
    )
    
    print(f"Created mock parse result:")
    print(f"  Stage: {mock_result.stage_type.value}")
    print(f"  Day: {mock_result.prep_day}")
    print(f"  Kingdom: #{mock_result.kingdom_id}")
    print(f"  Entries: {len(mock_result.entries)}")
    print(f"  Self entry found: {mock_result.self_entry is not None}")
    
    if mock_result.self_entry:
        print(f"  Self score: Rank #{mock_result.self_entry.rank:,} • {mock_result.self_entry.points:,} pts")
    
    return mock_result


if __name__ == "__main__":
    try:
        asyncio.run(test_kvk_visual_system())
        asyncio.run(test_mock_parse_result())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()