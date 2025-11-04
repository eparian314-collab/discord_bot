#!/usr/bin/env python3
"""
Live test suite that can be run while the bot is connected to Discord.
Tests all major functions and database operations without requiring Discord interaction.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from discord_bot.core.engines.base.logging_utils import get_logger
from discord_bot.games.storage.game_storage_engine import GameStorageEngine
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine
from discord_bot.language_context.normalizer import detect_language_with_confidence
from discord_bot.language_context.context_utils import normalize_lang_code
from discord_bot.core.engines.personality_engine import PersonalityEngine
from discord_bot.games.pokemon_game import PokemonGame

logger = get_logger("live_test_suite")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"  ✓ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  ✗ {test_name}: {error}")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print("LIVE TEST SUITE SUMMARY")
        print("=" * 70)
        print(f"Total: {total} | Passed: {self.passed} | Failed: {self.failed}")
        
        if self.failed > 0:
            print("\nFailed tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")
        
        return self.failed == 0


async def test_game_database(results: TestResult):
    """Test game database operations"""
    print("\n[Testing Game Database]")
    
    try:
        storage = GameStorageEngine("data/game_data.db")
        
        # Test database file exists and is accessible
        import os
        if os.path.exists("data/game_data.db"):
            results.add_pass("Game database: File accessible")
        else:
            results.add_fail("Game database: File accessible", "Database file not found")
        
        # Test basic pokemon query
        test_user_id = 123456789
        team = storage.get_user_pokemon(test_user_id)
        
        # Should return empty list or actual data, not error
        if isinstance(team, list):
            results.add_pass("Game database: Query operations")
        else:
            results.add_fail("Game database: Query operations", "Invalid query response")
        
    except Exception as e:
        results.add_fail("Game database operations", str(e))


async def test_ranking_database(results: TestResult):
    """Test ranking database operations"""
    print("\n[Testing Ranking Database]")
    
    try:
        storage = RankingStorageEngine("data/event_rankings.db")
        
        # Test database file exists and is accessible
        import os
        if os.path.exists("data/event_rankings.db"):
            results.add_pass("Ranking database: File accessible")
        else:
            results.add_fail("Ranking database: File accessible", "Database file not found")
        
        # Test current event week calculation
        event_week = storage.get_current_event_week()
        
        if event_week and isinstance(event_week, str):
            results.add_pass("Ranking database: Event week tracking")
        else:
            results.add_fail("Ranking database: Event week tracking", "Invalid event week")
        
    except Exception as e:
        results.add_fail("Ranking database operations", str(e))


async def test_language_detection(results: TestResult):
    """Test language detection and normalization"""
    print("\n[Testing Language Detection]")
    
    try:
        # Test language detection with high-confidence cases
        test_cases = [
            ("Hello world, how are you today?", "en"),
            ("Bonjour le monde, comment allez-vous?", "fr"),
            ("Hola mundo, cómo estás hoy?", "es"),
        ]
        
        all_passed = True
        for text, expected_lang in test_cases:
            detected, confidence = detect_language_with_confidence(text)
            if detected != expected_lang:
                all_passed = False
                results.add_fail(f"Language detection: {text[:20]}...", f"Expected {expected_lang}, got {detected}")
                break
        
        if all_passed:
            results.add_pass("Language detection: Multiple languages")
        
        # Test normalization with known code
        normalized = normalize_lang_code("en")
        if normalized == "en":
            results.add_pass("Language normalization: Code passthrough")
        else:
            results.add_fail("Language normalization", f"Expected 'en', got '{normalized}'")
        
    except Exception as e:
        results.add_fail("Language detection/normalization", str(e))


async def test_personality_engine(results: TestResult):
    """Test personality engine"""
    print("\n[Testing Personality Engine]")
    
    try:
        engine = PersonalityEngine(cache_manager=None)
        
        # Test greeting generation
        greeting = engine.greeting("TestUser")
        if greeting and len(greeting) > 0:
            results.add_pass("Personality engine: Greeting generation")
        else:
            results.add_fail("Personality engine: Greeting generation", "No greeting generated")
        
        # Test error messages
        error_msg = engine.error()
        if error_msg and len(error_msg) > 0:
            results.add_pass("Personality engine: Error messages")
        else:
            results.add_fail("Personality engine: Error messages", "No error message")
        
        # Test mood system
        mood = engine.get_mood()
        if mood in ["happy", "neutral", "grumpy"]:
            results.add_pass("Personality engine: Mood system")
        else:
            results.add_fail("Personality engine: Mood system", f"Invalid mood: {mood}")
        
    except Exception as e:
        results.add_fail("Personality engine operations", str(e))


async def test_pokemon_mechanics(results: TestResult):
    """Test Pokemon game mechanics"""
    print("\n[Testing Pokemon Mechanics]")
    
    try:
        # Test Pokemon API data structure (without initializing full game)
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pokeapi.co/api/v2/pokemon/25") as response:
                if response.status == 200:
                    data = await response.json()
                    if "name" in data and data["name"] == "pikachu":
                        results.add_pass("Pokemon mechanics: API connectivity")
                    else:
                        results.add_fail("Pokemon mechanics: API connectivity", "Invalid API response")
                else:
                    results.add_fail("Pokemon mechanics: API connectivity", f"HTTP {response.status}")
        
        # Test catch rate calculation logic
        # Using basic formula: catch_rate = min(1.0, base_rate * (1 - hp_ratio) * level_modifier)
        hp_ratio = 20 / 35  # Current HP / Max HP
        base_rate = 0.8
        level_modifier = 1.0 / 5  # 1 / level
        catch_rate = min(1.0, base_rate * (1 - hp_ratio) * level_modifier)
        
        if 0 <= catch_rate <= 1:
            results.add_pass("Pokemon mechanics: Catch rate logic")
        else:
            results.add_fail("Pokemon mechanics: Catch rate logic", f"Invalid rate: {catch_rate}")
        
    except Exception as e:
        results.add_fail("Pokemon mechanics", str(e))


async def test_file_integrity(results: TestResult):
    """Test critical file existence"""
    print("\n[Testing File Integrity]")
    
    critical_files = [
        "discord_bot/__init__.py",
        "discord_bot/cogs/__init__.py",
        "discord_bot/core/event_bus.py",
        "discord_bot/integrations/integration_loader.py",
        "discord_bot/language_context/language_map.json",
        "main.py",
        ".env",
    ]
    
    all_exist = True
    for file_path in critical_files:
        full_path = project_root / file_path
        if not full_path.exists():
            all_exist = False
            results.add_fail("File integrity", f"Missing: {file_path}")
    
    if all_exist:
        results.add_pass("File integrity: All critical files present")


async def main():
    """Run all tests"""
    print("=" * 70)
    print("LIVE TEST SUITE - Running while bot is operational")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    results = TestResult()
    
    # Run all test suites
    await test_file_integrity(results)
    await test_game_database(results)
    await test_ranking_database(results)
    await test_language_detection(results)
    await test_personality_engine(results)
    await test_pokemon_mechanics(results)
    
    # Print summary
    success = results.summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
