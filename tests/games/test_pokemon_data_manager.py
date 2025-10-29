"""
Tests for Pokemon Data Manager - IV system, stat calculations, natures.
"""

import pytest
from unittest.mock import patch, Mock
from discord_bot.games.pokemon_data_manager import (
    PokemonDataManager, PokemonBaseStats, PokemonIVs, NATURES
)


class TestPokemonIVs:
    """Test IV generation and validation."""
    
    def test_generate_ivs_range(self):
        """Test that generated IVs are in valid range (0-31)."""
        manager = PokemonDataManager()
        
        # Generate IVs many times to test distribution
        for _ in range(100):
            ivs = manager.generate_ivs()
            
            assert 0 <= ivs.hp <= 31
            assert 0 <= ivs.attack <= 31
            assert 0 <= ivs.defense <= 31
            assert 0 <= ivs.special_attack <= 31
            assert 0 <= ivs.special_defense <= 31
            assert 0 <= ivs.speed <= 31
    
    def test_generate_ivs_triangular_distribution(self):
        """Test that IVs favor middle values (triangular distribution)."""
        manager = PokemonDataManager()
        
        # Generate many IVs and check average is near 15 (mode)
        iv_sums = []
        for _ in range(200):
            ivs = manager.generate_ivs()
            total = ivs.hp + ivs.attack + ivs.defense + ivs.special_attack + ivs.special_defense + ivs.speed
            iv_sums.append(total)
        
        average_total = sum(iv_sums) / len(iv_sums)
        
        # Expected average for triangular(0, 31, 15) is (0+31+15)/3 = 15.33 per stat
        # Total for 6 stats: ~92
        # Allow reasonable variance (80-104)
        assert 80 <= average_total <= 104
    
    def test_generate_ivs_variation(self):
        """Test that IVs are not all the same."""
        manager = PokemonDataManager()
        
        ivs_list = [manager.generate_ivs() for _ in range(10)]
        
        # Check that not all IV sets are identical
        unique_iv_sets = set()
        for ivs in ivs_list:
            iv_tuple = (ivs.hp, ivs.attack, ivs.defense, ivs.special_attack, ivs.special_defense, ivs.speed)
            unique_iv_sets.add(iv_tuple)
        
        # Should have multiple unique sets
        assert len(unique_iv_sets) > 1


class TestNatureModifiers:
    """Test nature effects on stats."""
    
    def test_nature_neutral(self):
        """Test that neutral natures don't modify stats."""
        manager = PokemonDataManager()
        
        base_stat = 100
        
        # Hardy is neutral
        modified = manager.apply_nature_modifier(base_stat, 'attack', 'hardy')
        assert modified == base_stat
    
    def test_nature_positive_modifier(self):
        """Test that natures increase favored stats by 10%."""
        manager = PokemonDataManager()
        
        base_stat = 100
        
        # Adamant: +Attack
        modified = manager.apply_nature_modifier(base_stat, 'attack', 'adamant')
        assert modified == 110
        
        # Jolly: +Speed
        modified = manager.apply_nature_modifier(base_stat, 'speed', 'jolly')
        assert modified == 110
    
    def test_nature_negative_modifier(self):
        """Test that natures decrease hindered stats by 10%."""
        manager = PokemonDataManager()
        
        base_stat = 100
        
        # Adamant: -Special Attack
        modified = manager.apply_nature_modifier(base_stat, 'special_attack', 'adamant')
        assert modified == 90
        
        # Jolly: -Special Attack
        modified = manager.apply_nature_modifier(base_stat, 'special_attack', 'jolly')
        assert modified == 90
    
    def test_nature_no_effect_on_unaffected_stats(self):
        """Test that natures don't affect neutral stats."""
        manager = PokemonDataManager()
        
        base_stat = 100
        
        # Adamant: +Attack -Special Attack, should not affect Defense
        modified = manager.apply_nature_modifier(base_stat, 'defense', 'adamant')
        assert modified == base_stat
    
    def test_all_natures_exist(self):
        """Test that all 23 natures are defined."""
        assert len(NATURES) == 23
        
        # Check some key natures
        assert 'hardy' in NATURES
        assert 'adamant' in NATURES
        assert 'jolly' in NATURES
        assert 'modest' in NATURES
        assert 'timid' in NATURES


class TestStatCalculation:
    """Test Pokemon stat formulas."""
    
    def test_calculate_stat_hp(self):
        """Test HP stat calculation (different formula)."""
        manager = PokemonDataManager()
        
        # HP Formula: floor(((2 * base + IV) * level) / 100) + level + 10
        base_stat = 45
        iv = 15
        level = 10
        
        expected = int(((2 * base_stat + iv) * level) / 100) + level + 10
        calculated = manager.calculate_stat(base_stat, iv, level, is_hp=True)
        
        assert calculated == expected
    
    def test_calculate_stat_regular(self):
        """Test regular stat calculation (Attack, Defense, etc.)."""
        manager = PokemonDataManager()
        
        # Regular Formula: floor(((2 * base + IV) * level) / 100) + 5
        base_stat = 55
        iv = 20
        level = 15
        
        expected = int(((2 * base_stat + iv) * level) / 100) + 5
        calculated = manager.calculate_stat(base_stat, iv, level, is_hp=False)
        
        assert calculated == expected
    
    def test_stat_scaling_with_level(self):
        """Test that stats increase with level."""
        manager = PokemonDataManager()
        
        base_stat = 50
        iv = 15
        
        stat_level_5 = manager.calculate_stat(base_stat, iv, 5)
        stat_level_25 = manager.calculate_stat(base_stat, iv, 25)
        stat_level_50 = manager.calculate_stat(base_stat, iv, 50)
        
        # Higher level should always give higher stat
        assert stat_level_5 < stat_level_25 < stat_level_50
    
    def test_stat_iv_impact(self):
        """Test that higher IVs give higher stats."""
        manager = PokemonDataManager()
        
        base_stat = 50
        level = 20
        
        stat_iv_0 = manager.calculate_stat(base_stat, 0, level)
        stat_iv_15 = manager.calculate_stat(base_stat, 15, level)
        stat_iv_31 = manager.calculate_stat(base_stat, 31, level)
        
        # Higher IV should give higher stat
        assert stat_iv_0 < stat_iv_15 < stat_iv_31


class TestPokemonDataManager:
    """Test Pokemon data manager functionality."""
    
    def test_initialization(self):
        """Test that manager initializes correctly."""
        manager = PokemonDataManager()
        
        assert manager is not None
        assert hasattr(manager, 'base_stats_cache')
    
    @patch('requests.get')
    def test_fetch_from_pokeapi_success(self, mock_get):
        """Test fetching Pokemon data from PokeAPI."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'stats': [
                {'base_stat': 45, 'stat': {'name': 'hp'}},
                {'base_stat': 49, 'stat': {'name': 'attack'}},
                {'base_stat': 49, 'stat': {'name': 'defense'}},
                {'base_stat': 65, 'stat': {'name': 'special-attack'}},
                {'base_stat': 65, 'stat': {'name': 'special-defense'}},
                {'base_stat': 45, 'stat': {'name': 'speed'}}
            ],
            'types': [{'type': {'name': 'grass'}}, {'type': {'name': 'poison'}}]
        }
        mock_get.return_value = mock_response
        
        manager = PokemonDataManager()
        base_stats = manager._fetch_from_pokeapi('bulbasaur')
        
        assert base_stats is not None
        assert base_stats.hp == 45
        assert base_stats.attack == 49
        assert base_stats.defense == 49
        assert base_stats.special_attack == 65
        assert base_stats.special_defense == 65
        assert base_stats.speed == 45
        assert 'grass' in base_stats.types
        assert 'poison' in base_stats.types
    
    @patch('requests.get')
    def test_fetch_from_pokeapi_failure(self, mock_get):
        """Test fallback when PokeAPI fails."""
        # Mock API failure
        mock_get.side_effect = Exception("API Error")
        
        manager = PokemonDataManager()
        base_stats = manager.get_base_stats('pikachu')
        
        # Should return fallback stats
        assert base_stats is not None
        assert base_stats.hp > 0
        assert base_stats.attack > 0
    
    def test_cache_behavior(self):
        """Test that base stats are cached."""
        manager = PokemonDataManager()
        
        # First call should fetch and cache
        stats1 = manager.get_base_stats('pikachu')
        
        # Second call should use cache
        stats2 = manager.get_base_stats('pikachu')
        
        # Should return same object (cached)
        assert stats1 == stats2
    
    def test_generate_pokemon_stats_complete(self):
        """Test generating complete Pokemon stats."""
        manager = PokemonDataManager()
        
        species = 'charmander'
        level = 10
        nature = 'adamant'
        
        stats = manager.generate_pokemon_stats(species, level, nature)
        
        # Should have all required fields
        assert 'hp' in stats
        assert 'attack' in stats
        assert 'defense' in stats
        assert 'special_attack' in stats
        assert 'special_defense' in stats
        assert 'speed' in stats
        assert 'iv_hp' in stats
        assert 'iv_attack' in stats
        assert 'iv_defense' in stats
        assert 'iv_special_attack' in stats
        assert 'iv_special_defense' in stats
        assert 'iv_speed' in stats
        assert 'nature' in stats
        assert 'types' in stats
        
        # Nature should be set
        assert stats['nature'] == nature
        
        # All stats should be positive
        assert stats['hp'] > 0
        assert stats['attack'] > 0
        assert stats['defense'] > 0
        assert stats['special_attack'] > 0
        assert stats['special_defense'] > 0
        assert stats['speed'] > 0
        
        # IVs should be in range
        assert 0 <= stats['iv_hp'] <= 31
        assert 0 <= stats['iv_attack'] <= 31
        assert 0 <= stats['iv_defense'] <= 31
        assert 0 <= stats['iv_special_attack'] <= 31
        assert 0 <= stats['iv_special_defense'] <= 31
        assert 0 <= stats['iv_speed'] <= 31
    
    def test_generate_pokemon_stats_nature_effect(self):
        """Test that natures affect generated stats."""
        manager = PokemonDataManager()
        
        species = 'pikachu'
        level = 20
        
        # Generate multiple times and check that nature affects stats
        # Note: Without seed_ivs, we can't guarantee exact comparisons
        # so we test that natures produce different distributions
        stats_adamant_list = [manager.generate_pokemon_stats(species, level, 'adamant') for _ in range(10)]
        stats_modest_list = [manager.generate_pokemon_stats(species, level, 'modest') for _ in range(10)]
        
        # Adamant: +Attack, -Special Attack
        # Modest: +Special Attack, -Attack
        # On average, Adamant should have higher Attack and Modest should have higher Special Attack
        avg_adamant_attack = sum(s['attack'] for s in stats_adamant_list) / len(stats_adamant_list)
        avg_modest_attack = sum(s['attack'] for s in stats_modest_list) / len(stats_modest_list)
        
        avg_adamant_sp_atk = sum(s['special_attack'] for s in stats_adamant_list) / len(stats_adamant_list)
        avg_modest_sp_atk = sum(s['special_attack'] for s in stats_modest_list) / len(stats_modest_list)
        
        # Adamant should have higher attack than Modest
        assert avg_adamant_attack > avg_modest_attack
        
        # Modest should have higher special attack than Adamant
        assert avg_modest_sp_atk > avg_adamant_sp_atk
    
    def test_generate_pokemon_stats_level_scaling(self):
        """Test that stats scale with level."""
        manager = PokemonDataManager()
        
        species = 'squirtle'
        nature = 'hardy'
        
        # Generate multiple times at each level and check averages
        stats_low_list = [manager.generate_pokemon_stats(species, 5, nature) for _ in range(10)]
        stats_high_list = [manager.generate_pokemon_stats(species, 30, nature) for _ in range(10)]
        
        # Average stats should be higher at higher level
        avg_low_hp = sum(s['hp'] for s in stats_low_list) / len(stats_low_list)
        avg_high_hp = sum(s['hp'] for s in stats_high_list) / len(stats_high_list)
        
        avg_low_attack = sum(s['attack'] for s in stats_low_list) / len(stats_low_list)
        avg_high_attack = sum(s['attack'] for s in stats_high_list) / len(stats_high_list)
        
        # Higher level should have higher stats
        assert avg_high_hp > avg_low_hp
        assert avg_high_attack > avg_low_attack


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_stat_calculation_level_1(self):
        """Test stat calculation at minimum level."""
        manager = PokemonDataManager()
        
        base_stat = 50
        iv = 15
        
        stat_hp = manager.calculate_stat(base_stat, iv, 1, is_hp=True)
        stat_regular = manager.calculate_stat(base_stat, iv, 1, is_hp=False)
        
        # Should still be positive even at level 1
        assert stat_hp > 0
        assert stat_regular > 0
    
    def test_stat_calculation_level_100(self):
        """Test stat calculation at maximum level."""
        manager = PokemonDataManager()
        
        base_stat = 100
        iv = 31
        
        stat_hp = manager.calculate_stat(base_stat, iv, 100, is_hp=True)
        stat_regular = manager.calculate_stat(base_stat, iv, 100, is_hp=False)
        
        # Should be large but reasonable
        assert stat_hp > 200
        assert stat_regular > 100
    
    def test_stat_calculation_zero_iv(self):
        """Test stat calculation with 0 IV."""
        manager = PokemonDataManager()
        
        base_stat = 50
        level = 20
        
        stat = manager.calculate_stat(base_stat, 0, level)
        
        # Should still be positive
        assert stat > 0
    
    def test_stat_calculation_max_iv(self):
        """Test stat calculation with 31 IV."""
        manager = PokemonDataManager()
        
        base_stat = 50
        level = 20
        
        stat = manager.calculate_stat(base_stat, 31, level)
        
        # Should be higher than 0 IV
        stat_zero_iv = manager.calculate_stat(base_stat, 0, level)
        assert stat > stat_zero_iv
    
    def test_nature_on_zero_stat(self):
        """Test that nature modifiers work on edge case stats."""
        manager = PokemonDataManager()
        
        # Very low stat
        modified = manager.apply_nature_modifier(1, 'attack', 'adamant')
        
        # Should apply modifier correctly (1 * 1.1 = 1.1 → 1)
        assert modified >= 1
    
    def test_unknown_nature_fallback(self):
        """Test that unknown natures are treated as neutral."""
        manager = PokemonDataManager()
        
        base_stat = 100
        
        # Unknown nature should not modify stat
        modified = manager.apply_nature_modifier(base_stat, 'attack', 'unknown_nature')
        assert modified == base_stat


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
