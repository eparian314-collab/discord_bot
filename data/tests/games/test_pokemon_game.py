"""
Tests for PokemonGame engine.
"""

import pytest
from discord_bot.games.storage.game_storage_engine import GameStorageEngine
from discord_bot.core.engines.relationship_manager import RelationshipManager
from discord_bot.core.engines.cookie_manager import CookieManager
from discord_bot.games.pokemon_game import PokemonGame


@pytest.fixture
def storage():
    """Create a test storage engine with in-memory database."""
    engine = GameStorageEngine(db_path=":memory:")
    yield engine
    engine.conn.close()


@pytest.fixture
def relationship_manager(storage):
    """Create a RelationshipManager with test storage."""
    return RelationshipManager(storage)


@pytest.fixture
def cookie_manager(storage, relationship_manager):
    """Create a CookieManager with test dependencies."""
    return CookieManager(storage, relationship_manager)


@pytest.fixture
def pokemon_game(storage, cookie_manager, relationship_manager):
    """Create a PokemonGame with test dependencies."""
    return PokemonGame(storage, cookie_manager, relationship_manager)


@pytest.fixture
def pokemon_game_with_data_manager(storage, cookie_manager, relationship_manager):
    """Create a PokemonGame with explicit data_manager injection."""
    from discord_bot.games.pokemon_data_manager import PokemonDataManager
    data_manager = PokemonDataManager(cache_file="test_pokemon_cache.json")
    return PokemonGame(storage, cookie_manager, relationship_manager, data_manager=data_manager)


class TestPokemonGame:
    """Test suite for PokemonGame."""
    
    def test_initialization(self, pokemon_game):
        """Test that PokemonGame initializes correctly."""
        assert pokemon_game is not None
        assert pokemon_game.storage is not None
        assert pokemon_game.cookie_manager is not None
        assert pokemon_game.relationship_manager is not None
        assert pokemon_game.data_manager is not None  # Should auto-create
    
    def test_initialization_with_injected_data_manager(self, pokemon_game_with_data_manager):
        """Test that PokemonGame properly accepts injected data_manager."""
        assert pokemon_game_with_data_manager is not None
        assert pokemon_game_with_data_manager.data_manager is not None
        assert pokemon_game_with_data_manager.data_manager.cache_file == "test_pokemon_cache.json"
    
    def test_generate_encounter_catch(self, pokemon_game):
        """Test generating a catch encounter."""
        encounter = pokemon_game.generate_encounter('catch')
        
        assert encounter is not None
        assert encounter.species is not None
        assert encounter.level >= 1
        assert encounter.rarity in ['common', 'uncommon']
        assert 0 < encounter.catch_rate <= 1
    
    def test_generate_encounter_fish(self, pokemon_game):
        """Test generating a fish encounter."""
        encounter = pokemon_game.generate_encounter('fish')
        
        assert encounter is not None
        assert encounter.species is not None
        assert encounter.rarity in ['common', 'uncommon', 'rare']
    
    def test_generate_encounter_explore(self, pokemon_game):
        """Test generating an explore encounter."""
        encounter = pokemon_game.generate_encounter('explore')
        
        assert encounter is not None
        assert encounter.species is not None
        assert encounter.rarity in ['uncommon', 'rare', 'legendary']
    
    def test_attempt_catch_success(self, pokemon_game, relationship_manager):
        """Test successfully catching a Pokemon."""
        user_id = "test_user_catch"
        
        # Build relationship for better catch rate
        for _ in range(30):
            relationship_manager.record_interaction(user_id, 'game_action')
        
        # Generate easy encounter
        from discord_bot.games.pokemon_game import PokemonEncounter
        encounter = PokemonEncounter(species="pidgey", level=5, rarity="common", catch_rate=0.9)
        
        # Try multiple times (should succeed at least once)
        caught_any = False
        for _ in range(10):
            success, pokemon = pokemon_game.attempt_catch(user_id, encounter)
            if success and pokemon:
                caught_any = True
                assert pokemon.species == "pidgey"
                assert pokemon.level == 5
                assert pokemon.pokemon_id > 0
                break
        
        assert caught_any is True
    
    def test_catch_limit_three_per_species(self, pokemon_game, storage):
        """Test that users cannot catch more than 3 of the same species."""
        user_id = "test_user_limit"
        
        from discord_bot.games.pokemon_game import PokemonEncounter
        encounter = PokemonEncounter(species="pikachu", level=10, rarity="uncommon", catch_rate=1.0)
        
        # Catch 3 pokemon
        for i in range(3):
            success, pokemon = pokemon_game.attempt_catch(user_id, encounter)
            # May fail due to luck, but with catch_rate=1.0 should work
            if pokemon:
                assert pokemon.species == "pikachu"
        
        # Manually add 3 if needed (to ensure limit is tested)
        current_count = storage.get_pokemon_count_by_species(user_id, "pikachu")
        while current_count < 3:
            storage.add_pokemon(user_id, "pikachu", "Pikachu", "{}")
            current_count += 1
        
        # 4th catch should fail due to limit
        success, pokemon = pokemon_game.attempt_catch(user_id, encounter)
        assert success is False
        assert pokemon is None
    
    def test_train_pokemon(self, pokemon_game, storage, cookie_manager):
        """Test training a Pokemon with cookies."""
        user_id = "test_user_train"
        
        # Add a pokemon with proper stats
        pokemon_id = storage.add_pokemon(
            user_id, "charmander", "Charmander", 
            level=5, hp=20, attack=12, defense=10, 
            special_attack=14, special_defense=12, speed=15,
            iv_hp=15, iv_attack=15, iv_defense=15,
            iv_special_attack=15, iv_special_defense=15, iv_speed=15,
            nature='hardy'
        )
        
        # Give user cookies
        storage.add_cookies(user_id, 10)
        
        # Train pokemon
        success, updated = pokemon_game.train_pokemon(user_id, pokemon_id, 3)
        
        assert success is True
        assert updated is not None
        assert updated['level'] >= 5
        assert updated['experience'] > 0
    
    def test_cannot_train_without_cookies(self, pokemon_game, storage):
        """Test that training requires cookies."""
        user_id = "test_user_no_cookies"
        
        # Add a pokemon with proper stats
        pokemon_id = storage.add_pokemon(
            user_id, "bulbasaur", "Bulbasaur",
            level=5, hp=21, attack=11, defense=11,
            special_attack=14, special_defense=14, speed=11,
            iv_hp=15, iv_attack=15, iv_defense=15,
            iv_special_attack=15, iv_special_defense=15, iv_speed=15,
            nature='hardy'
        )
        
        # No cookies
        success, updated = pokemon_game.train_pokemon(user_id, pokemon_id, 1)
        
        assert success is False
        assert updated is None
    
    def test_can_evolve_requirements(self, pokemon_game, storage):
        """Test evolution requirements check."""
        user_id = "test_user_evolve_check"
        
        # Add a magikarp at level 25 (can evolve)
        pokemon_id = storage.add_pokemon(
            user_id, "magikarp", "Magikarp",
            level=25, hp=50, attack=20, defense=30,
            special_attack=25, special_defense=30, speed=40,
            iv_hp=15, iv_attack=15, iv_defense=15,
            iv_special_attack=15, iv_special_defense=15, iv_speed=15,
            nature='hardy'
        )
        
        # Cannot evolve - need duplicate (note: can_evolve returns 4 values now)
        can_evolve, evolved_form, cost, reason = pokemon_game.can_evolve(user_id, pokemon_id)
        assert can_evolve is False
        assert evolved_form == "gyarados"
        assert cost == 8  # Magikarp → Gyarados costs 8 cookies (stage 1 evolution)
        
        # Add duplicate
        storage.add_pokemon(
            user_id, "magikarp", "Magikarp2",
            level=5, hp=30, attack=15, defense=20,
            special_attack=18, special_defense=20, speed=28,
            iv_hp=15, iv_attack=15, iv_defense=15,
            iv_special_attack=15, iv_special_defense=15, iv_speed=15,
            nature='hardy'
        )
        
        # Still cannot evolve - need cookies
        can_evolve, evolved_form, cost, reason = pokemon_game.can_evolve(user_id, pokemon_id)
        assert can_evolve is False
        
        # Add cookies
        storage.add_cookies(user_id, 10)
        
        # Now can evolve
        can_evolve, evolved_form, cost, reason = pokemon_game.can_evolve(user_id, pokemon_id)
        assert can_evolve is True
    
    def test_evolve_pokemon(self, pokemon_game, storage):
        """Test evolving a Pokemon."""
        user_id = "test_user_evolve"
        
        # Add two magikarps at level 25 (can evolve)
        pokemon_id1 = storage.add_pokemon(
            user_id, "magikarp", "Magikarp1",
            level=25, hp=50, attack=20, defense=30,
            special_attack=25, special_defense=30, speed=40,
            iv_hp=15, iv_attack=15, iv_defense=15,
            iv_special_attack=15, iv_special_defense=15, iv_speed=15,
            nature='hardy'
        )
        pokemon_id2 = storage.add_pokemon(
            user_id, "magikarp", "Magikarp2",
            level=25, hp=50, attack=20, defense=30,
            special_attack=25, special_defense=30, speed=40,
            iv_hp=16, iv_attack=16, iv_defense=16,
            iv_special_attack=16, iv_special_defense=16, iv_speed=16,
            nature='hardy'
        )
        
        # Give cookies for evolution
        storage.add_cookies(user_id, 10)
        
        # Evolve
        success, evolved, error = pokemon_game.evolve_pokemon(user_id, pokemon_id1, pokemon_id2)
        
        assert success is True
        assert evolved is not None
        assert evolved['species'] == "gyarados"
        
        # Check that duplicate was consumed
        count = storage.get_pokemon_count_by_species(user_id, "magikarp")
        assert count == 0  # Both were removed (one evolved, one consumed)
    
    def test_get_user_collection(self, pokemon_game, storage):
        """Test retrieving user's Pokemon collection."""
        user_id = "test_user_collection"
        
        # Add several pokemon
        storage.add_pokemon(user_id, "pikachu", "Pika", "{}")
        storage.add_pokemon(user_id, "eevee", "Eevee", "{}")
        storage.add_pokemon(user_id, "pikachu", "Chu", "{}")
        
        # Get collection
        collection = pokemon_game.get_user_collection(user_id)
        
        assert len(collection) == 3
        species = [p['species'] for p in collection]
        assert 'pikachu' in species
        assert 'eevee' in species
    
    def test_stats_generation(self, pokemon_game):
        """Test that generated stats use PokemonDataManager correctly."""
        # Test that data manager is initialized
        assert pokemon_game.data_manager is not None
        
        # Generate stats for a Pokemon at different levels
        stats_level_5 = pokemon_game.data_manager.generate_pokemon_stats('pikachu', 5)
        stats_level_50 = pokemon_game.data_manager.generate_pokemon_stats('pikachu', 50)
        
        # Higher level should have higher stats
        assert stats_level_50['hp'] > stats_level_5['hp']
        assert stats_level_50['attack'] > stats_level_5['attack']
        
        # All stats should be positive
        for stat in ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']:
            assert stats_level_5[stat] > 0
            assert stats_level_50[stat] > 0
        
        # Should have IVs
        for iv_stat in ['iv_hp', 'iv_attack', 'iv_defense', 'iv_special_attack', 'iv_special_defense', 'iv_speed']:
            assert iv_stat in stats_level_5
            assert 0 <= stats_level_5[iv_stat] <= 31


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
