# Architecture Improvement: PokemonDataManager Dependency Injection

## Summary
Refactored the PokemonDataManager from a global singleton pattern to proper dependency injection through the IntegrationLoader.

## Changes Made

### 1. **pokemon_game.py**
- **Before**: Called `get_pokemon_data_manager()` directly in `__init__`
- **After**: Accepts `data_manager` as an optional constructor parameter
- **Benefit**: 
  - Testable with mock data managers
  - No hidden global dependencies
  - Can configure different cache files per instance

```python
# Old code:
def __init__(self, storage, cookie_manager, relationship_manager):
    self.data_manager = get_pokemon_data_manager()

# New code:
def __init__(self, storage, cookie_manager, relationship_manager, 
             data_manager: Optional[PokemonDataManager] = None):
    self.data_manager = data_manager if data_manager is not None else PokemonDataManager()
```

### 2. **integration_loader.py**
- **Added**: PokemonDataManager creation and management
- **Added**: Registry injection for pokemon_data_manager
- **Added**: Bot attribute exposure for easy access
- **Benefit**: Single source of truth for all game dependencies

```python
# Added to __init__:
from discord_bot.games.pokemon_data_manager import PokemonDataManager
self.pokemon_data_manager = PokemonDataManager(cache_file="pokemon_base_stats_cache.json")

# Updated PokemonGame initialization:
self.pokemon_game = PokemonGame(
    storage=self.game_storage,
    cookie_manager=self.cookie_manager,
    relationship_manager=self.relationship_manager,
    data_manager=self.pokemon_data_manager  # <-- Injected!
)

# Added registry injection:
self.registry.inject("pokemon_data_manager", self.pokemon_data_manager)

# Added bot attribute:
mapping["pokemon_data_manager"] = self.pokemon_data_manager
```

### 3. **pokemon_data_manager.py**
- **Deprecated**: `get_pokemon_data_manager()` function (kept for backwards compatibility)
- **Added**: Clear deprecation warning in docstring
- **Benefit**: Clear migration path for any legacy code

```python
# DEPRECATED: Singleton pattern - kept for backwards compatibility only
# Use dependency injection via integration_loader instead
def get_pokemon_data_manager() -> PokemonDataManager:
    """DEPRECATED: Get or create the singleton Pokemon data manager..."""
```

### 4. **test_pokemon_game.py**
- **Added**: New fixture `pokemon_game_with_data_manager` for testing injection
- **Added**: Test case `test_initialization_with_injected_data_manager`
- **Benefit**: Verifies the dependency injection works correctly

## Benefits

### 🎯 **Improved Architecture**
- ✅ Explicit dependencies instead of hidden globals
- ✅ Single responsibility: IntegrationLoader manages all dependencies
- ✅ Consistent with other engine initialization patterns

### 🧪 **Better Testability**
- ✅ Can inject mock/fake PokemonDataManager for testing
- ✅ No singleton state pollution between tests
- ✅ Can test with different cache configurations

### 📦 **Configurable**
- ✅ Cache file path now configurable through IntegrationLoader
- ✅ Can create multiple instances with different configurations
- ✅ No risk of singleton conflicts

### 🔄 **Backwards Compatible**
- ✅ Old `get_pokemon_data_manager()` still works
- ✅ Tests pass without modification (optional parameter)
- ✅ Clear deprecation path for future cleanup

## Migration Guide

### For New Code
```python
# Get it from the bot instance (injected by IntegrationLoader)
data_manager = bot.pokemon_data_manager

# Or receive it via dependency injection
def my_function(pokemon_game: PokemonGame):
    # pokemon_game already has data_manager injected
    stats = pokemon_game.data_manager.get_base_stats("pikachu")
```

### For Tests
```python
@pytest.fixture
def pokemon_game(storage, cookie_manager, relationship_manager):
    # Option 1: Let it auto-create (backwards compatible)
    return PokemonGame(storage, cookie_manager, relationship_manager)
    
    # Option 2: Inject a test data manager
    test_data_manager = PokemonDataManager(cache_file=":memory:")
    return PokemonGame(storage, cookie_manager, relationship_manager, 
                      data_manager=test_data_manager)
```

## Files Modified
- `games/pokemon_game.py` - Added data_manager parameter
- `integrations/integration_loader.py` - Added PokemonDataManager management
- `games/pokemon_data_manager.py` - Deprecated singleton function
- `tests/games/test_pokemon_game.py` - Added injection tests

## No Breaking Changes
All existing code continues to work because:
1. The `data_manager` parameter is optional with a default
2. The deprecated singleton function still exists
3. Tests don't need modification

## Future Improvements
- Remove deprecated `get_pokemon_data_manager()` in next major version
- Make cache file path configurable via config.json
- Consider adding cache clearing commands for admins
