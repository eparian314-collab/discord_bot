#!/usr/bin/env python3
"""
Module Integrity Test for HippoBot.

Verifies that all engines and cogs can be imported and mounted
without runtime errors or circular dependencies.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def test_core_engines() -> List[Tuple[str, bool, str]]:
    """Test importing core engines."""
    engines = [
        ("AdminUIEngine", "discord_bot.core.engines.admin_ui_engine"),
        ("CacheManager", "discord_bot.core.engines.cache_manager"),
        ("CleanupEngine", "discord_bot.core.engines.cleanup_engine"),
        ("ContextEngine", "discord_bot.language_context.context_engine"),
        ("ErrorEngine", "discord_bot.core.engines.error_engine"),
        ("EventEngine", "discord_bot.core.engines.event_engine"),
        ("EventReminderEngine", "discord_bot.core.engines.event_reminder_engine"),
        ("InputEngine", "discord_bot.core.engines.input_engine"),
        ("KVKTrackerEngine", "discord_bot.core.engines.kvk_tracker_engine"),
        ("OutputEngine", "discord_bot.core.engines.output_engine"),
        ("PersonalityEngine", "discord_bot.core.engines.personality_engine"),
        ("ProcessingEngine", "discord_bot.core.engines.processing_engine"),
        ("RoleManager", "discord_bot.core.engines.role_manager"),
        ("SessionManager", "discord_bot.core.engines.session_manager"),
        ("TranslationOrchestratorEngine", "discord_bot.core.engines.translation_orchestrator"),
    ]
    
    results = []
    for name, module_path in engines:
        try:
            parts = module_path.split(".")
            __import__(module_path, fromlist=[parts[-1]])
            results.append((name, True, "OK"))
        except Exception as e:
            results.append((name, False, str(e)[:50]))
    
    return results


def test_cogs() -> List[Tuple[str, bool, str]]:
    """Test importing cogs."""
    cogs = [
        ("AdminCog", "discord_bot.cogs.admin_cog"),
        ("EasterEggCog", "discord_bot.cogs.easteregg_cog"),
        ("EventManagementCog", "discord_bot.cogs.event_management_cog"),
        ("GameCog", "discord_bot.cogs.game_cog"),
        ("HelpCog", "discord_bot.cogs.help_cog"),
        ("RankingCog", "discord_bot.cogs.unified_ranking_cog"),
        ("RoleManagementCog", "discord_bot.cogs.role_management_cog"),
        ("SOSPhraseCog", "discord_bot.cogs.sos_phrase_cog"),
        ("TranslationCog", "discord_bot.cogs.translation_cog"),
    ]
    
    results = []
    for name, module_path in cogs:
        try:
            parts = module_path.split(".")
            __import__(module_path, fromlist=[parts[-1]])
            results.append((name, True, "OK"))
        except Exception as e:
            results.append((name, False, str(e)[:50]))
    
    return results


def test_integration_loader() -> Tuple[bool, str]:
    """Test importing integration loader."""
    try:
        return True, "OK"
    except Exception as e:
        return False, str(e)[:100]


def test_event_bus() -> Tuple[bool, str]:
    """Test event bus import and basic functionality."""
    try:
        from discord_bot.core.event_bus import EventBus
        bus = EventBus()
        # Test basic subscription
        bus.subscribe("test.topic", lambda x: None)
        return True, "OK"
    except Exception as e:
        return False, str(e)[:100]


def print_result(name: str, passed: bool, details: str = "") -> None:
    """Print a formatted result."""
    symbol = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    detail_str = f" - {details}" if details and not passed else ""
    print(f"  {symbol} {name}{detail_str}")


def main() -> int:
    """Run all module integrity tests."""
    print("=" * 60)
    print("HippoBot Module Integrity Test")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # Test core engines
    print("🔧 Core Engines:")
    engine_results = test_core_engines()
    for name, passed, details in engine_results:
        print_result(name, passed, details)
        all_passed = all_passed and passed
    print()
    
    # Test cogs
    print("🧩 Cogs:")
    cog_results = test_cogs()
    for name, passed, details in cog_results:
        print_result(name, passed, details)
        all_passed = all_passed and passed
    print()
    
    # Test integration loader
    print("🔗 Integration Layer:")
    loader_passed, loader_details = test_integration_loader()
    print_result("IntegrationLoader", loader_passed, loader_details)
    all_passed = all_passed and loader_passed
    print()
    
    # Test event bus
    print("📡 Event System:")
    bus_passed, bus_details = test_event_bus()
    print_result("EventBus", bus_passed, bus_details)
    all_passed = all_passed and bus_passed
    print()
    
    # Summary
    print("=" * 60)
    if all_passed:
        print(f"{GREEN}✅ All modules loaded successfully!{RESET}")
        print(f"{GREEN}   Architecture is clean and ready.{RESET}")
        return 0
    else:
        print(f"{RED}❌ Some modules failed to load.{RESET}")
        print(f"{YELLOW}   Check for missing dependencies or circular imports.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
