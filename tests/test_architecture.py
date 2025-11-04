"""
Quick test to validate the PokemonDataManager dependency injection architecture.
Run with: python -m discord_bot.test_architecture
"""

from discord_bot.games.pokemon_data_manager import PokemonDataManager
from discord_bot.games.pokemon_game import PokemonGame
from discord_bot.games.storage.game_storage_engine import GameStorageEngine
from discord_bot.core.engines.relationship_manager import RelationshipManager
from discord_bot.core.engines.cookie_manager import CookieManager

def test_architecture():
    """Test that dependency injection works correctly."""
    print("Testing PokemonDataManager dependency injection...")
    
    # Create dependencies
    storage = GameStorageEngine(db_path=":memory:")
    relationship_manager = RelationshipManager(storage=storage)
    cookie_manager = CookieManager(storage=storage, relationship_manager=relationship_manager)
    
    # Test 1: PokemonGame with default data_manager
    print("✓ Test 1: Creating PokemonGame with default data_manager")
    game1 = PokemonGame(
        storage=storage,
        cookie_manager=cookie_manager,
        relationship_manager=relationship_manager
    )
    assert game1.data_manager is not None
    print(f"  - data_manager created: {type(game1.data_manager).__name__}")
    print(f"  - cache_file: {game1.data_manager.cache_file}")
    
    # Test 2: PokemonGame with injected data_manager
    print("\n✓ Test 2: Creating PokemonGame with injected data_manager")
    custom_data_manager = PokemonDataManager(cache_file="custom_cache.json")
    game2 = PokemonGame(
        storage=storage,
        cookie_manager=cookie_manager,
        relationship_manager=relationship_manager,
        data_manager=custom_data_manager
    )
    assert game2.data_manager is custom_data_manager
    print(f"  - data_manager injected: {type(game2.data_manager).__name__}")
    print(f"  - cache_file: {game2.data_manager.cache_file}")
    
    # Test 3: Verify they're different instances
    print("\n✓ Test 3: Verifying independence")
    assert game1.data_manager is not game2.data_manager
    print("  - game1 and game2 have independent data_managers")
    
    print("\n🎉 All architecture tests passed!")
    print("✅ Dependency injection is working correctly")
    print("✅ No singleton conflicts")
    print("✅ PokemonDataManager can be properly injected and configured")

if __name__ == "__main__":
    test_architecture()


