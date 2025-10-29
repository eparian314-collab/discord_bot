"""
Tests for Battle System.
"""

import pytest
from discord_bot.games.battle_system import (
    BattlePokemon, Move, MoveCategory, BattleState, BattleEngine, TypeEffectiveness,
    create_battle, get_active_battle, end_battle, _active_battles
)


class TestTypeEffectiveness:
    """Test type effectiveness calculations."""
    
    def test_super_effective(self):
        """Test super effective matchups (2x damage)."""
        # Water vs Fire
        assert TypeEffectiveness.get_multiplier("water", ["fire"]) == 2.0
        
        # Electric vs Water
        assert TypeEffectiveness.get_multiplier("electric", ["water"]) == 2.0
        
        # Grass vs Water
        assert TypeEffectiveness.get_multiplier("grass", ["water"]) == 2.0
        
        # Fire vs Grass
        assert TypeEffectiveness.get_multiplier("fire", ["grass"]) == 2.0
    
    def test_not_very_effective(self):
        """Test not very effective matchups (0.5x damage)."""
        # Water vs Grass
        assert TypeEffectiveness.get_multiplier("water", ["grass"]) == 0.5
        
        # Fire vs Water
        assert TypeEffectiveness.get_multiplier("fire", ["water"]) == 0.5
        
        # Electric vs Electric
        assert TypeEffectiveness.get_multiplier("electric", ["electric"]) == 0.5
    
    def test_immune(self):
        """Test immunity (0x damage)."""
        # Normal vs Ghost
        assert TypeEffectiveness.get_multiplier("normal", ["ghost"]) == 0
        
        # Electric vs Ground
        assert TypeEffectiveness.get_multiplier("electric", ["ground"]) == 0
        
        # Ground vs Flying
        assert TypeEffectiveness.get_multiplier("ground", ["flying"]) == 0
    
    def test_normal_effectiveness(self):
        """Test normal effectiveness (1x damage)."""
        # Normal vs Normal
        assert TypeEffectiveness.get_multiplier("normal", ["normal"]) == 1.0
        
        # Fire vs Flying (1x)
        assert TypeEffectiveness.get_multiplier("fire", ["flying"]) == 1.0
    
    def test_dual_type_multipliers(self):
        """Test dual-type Pokemon effectiveness."""
        # Electric vs Water/Flying (both weak to electric = 4x)
        # Note: Implementation multiplies both weaknesses
        result = TypeEffectiveness.get_multiplier("electric", ["water", "flying"])
        assert result == 4.0
        
        # Fire vs Grass/Bug (2x * 2x = 4x)
        result = TypeEffectiveness.get_multiplier("fire", ["grass", "bug"])
        assert result == 4.0
    
    def test_effectiveness_text(self):
        """Test effectiveness description text."""
        assert TypeEffectiveness.get_effectiveness_text(2.0) == "super"
        assert TypeEffectiveness.get_effectiveness_text(4.0) == "super"
        assert TypeEffectiveness.get_effectiveness_text(0.5) == "not_very"
        assert TypeEffectiveness.get_effectiveness_text(0.25) == "not_very"
        assert TypeEffectiveness.get_effectiveness_text(0) == "immune"
        assert TypeEffectiveness.get_effectiveness_text(1.0) == "normal"


class TestBattlePokemon:
    """Test BattlePokemon dataclass."""
    
    def test_battle_pokemon_creation(self):
        """Test creating a BattlePokemon."""
        moves = [
            Move("Tackle", "normal", MoveCategory.PHYSICAL, 40, 100, 35, "A normal type attack"),
            Move("Ember", "fire", MoveCategory.SPECIAL, 40, 100, 25, "A small flame attack")
        ]
        
        pokemon = BattlePokemon(
            pokemon_id=1,
            user_id="test_user",
            species="charmander",
            nickname="Char",
            level=5,
            max_hp=20,
            current_hp=20,
            attack=12,
            defense=10,
            special_attack=14,
            special_defense=12,
            speed=15,
            types=["fire"],
            moves=moves
        )
        
        assert pokemon.species == "charmander"
        assert pokemon.level == 5
        assert pokemon.max_hp == 20
        assert pokemon.current_hp == 20
        assert len(pokemon.moves) == 2
        assert pokemon.is_fainted is False
    
    def test_display_name_with_nickname(self):
        """Test display name uses nickname when provided."""
        pokemon = BattlePokemon(
            pokemon_id=1, user_id="u1", species="pikachu", nickname="Sparky",
            level=10, max_hp=30, current_hp=30, attack=15, defense=10,
            special_attack=12, special_defense=10, speed=20,
            types=["electric"], moves=[]
        )
        
        assert pokemon.display_name == "Sparky"
    
    def test_display_name_without_nickname(self):
        """Test display name uses species when no nickname."""
        pokemon = BattlePokemon(
            pokemon_id=1, user_id="u1", species="pikachu", nickname=None,
            level=10, max_hp=30, current_hp=30, attack=15, defense=10,
            special_attack=12, special_defense=10, speed=20,
            types=["electric"], moves=[]
        )
        
        assert pokemon.display_name == "Pikachu"
    
    def test_hp_percentage(self):
        """Test HP percentage calculation."""
        pokemon = BattlePokemon(
            pokemon_id=1, user_id="u1", species="bulbasaur", nickname=None,
            level=5, max_hp=20, current_hp=10, attack=10, defense=10,
            special_attack=10, special_defense=10, speed=10,
            types=["grass", "poison"], moves=[]
        )
        
        assert pokemon.hp_percentage == 50.0
        
        pokemon.current_hp = 20
        assert pokemon.hp_percentage == 100.0
        
        pokemon.current_hp = 0
        assert pokemon.hp_percentage == 0.0


class TestBattleState:
    """Test BattleState management."""
    
    def test_battle_state_creation(self):
        """Test creating a battle state."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = BattleState("u1", "u2", p1, p2)
        
        assert battle.challenger_id == "u1"
        assert battle.opponent_id == "u2"
        assert battle.turn_number == 0
        assert battle.is_finished is False
        assert battle.winner_id is None
    
    def test_turn_order_by_speed(self):
        """Test that faster Pokemon goes first."""
        # Pikachu has speed 20, Charmander has speed 18
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = BattleState("u1", "u2", p1, p2)
        
        # Pikachu (challenger) should go first
        assert battle.current_turn_user_id == "u1"
    
    def test_get_pokemon_by_user(self):
        """Test retrieving Pokemon by user ID."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = BattleState("u1", "u2", p1, p2)
        
        assert battle.get_pokemon_by_user("u1").species == "pikachu"
        assert battle.get_pokemon_by_user("u2").species == "charmander"
    
    def test_get_opponent_pokemon(self):
        """Test retrieving opponent's Pokemon."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = BattleState("u1", "u2", p1, p2)
        
        assert battle.get_opponent_pokemon("u1").species == "charmander"
        assert battle.get_opponent_pokemon("u2").species == "pikachu"
    
    def test_switch_turn(self):
        """Test turn switching."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = BattleState("u1", "u2", p1, p2)
        
        first_turn = battle.current_turn_user_id
        battle.switch_turn()
        second_turn = battle.current_turn_user_id
        
        assert first_turn != second_turn


class TestBattleEngine:
    """Test battle calculations and logic."""
    
    def test_calculate_damage_basic(self):
        """Test basic damage calculation."""
        attacker = BattlePokemon(
            1, "u1", "charmander", "Char", 10, 30, 30, 20, 15, 18, 15, 20,
            ["fire"], [Move("Tackle", "normal", MoveCategory.PHYSICAL, 40, 100, 35)]
        )
        defender = BattlePokemon(
            2, "u2", "bulbasaur", "Bulb", 10, 30, 30, 18, 20, 16, 20, 18,
            ["grass", "poison"], []
        )
        
        move = Move("Tackle", "normal", MoveCategory.PHYSICAL, 40, 100, 35)
        damage, type_mult, is_crit = BattleEngine.calculate_damage(attacker, defender, move)
        
        # Damage should be positive
        assert damage > 0
        
        # Normal type vs Grass/Poison is 1x effectiveness
        assert type_mult == 1.0
    
    def test_calculate_damage_with_stab(self):
        """Test STAB bonus (Same Type Attack Bonus)."""
        # Fire Pokemon using Fire move
        attacker = BattlePokemon(
            1, "u1", "charmander", "Char", 10, 30, 30, 20, 15, 18, 15, 20,
            ["fire"], [Move("Ember", "fire", MoveCategory.SPECIAL, 40, 100, 25)]
        )
        defender = BattlePokemon(
            2, "u2", "bulbasaur", "Bulb", 10, 30, 30, 18, 20, 16, 20, 18,
            ["grass", "poison"], []
        )
        
        move_with_stab = Move("Ember", "fire", MoveCategory.SPECIAL, 40, 100, 25)
        damage_stab, _, _ = BattleEngine.calculate_damage(attacker, defender, move_with_stab)
        
        # Fire vs Grass is super effective (2x) + STAB (1.5x)
        # Damage should be significant
        assert damage_stab > 5
    
    def test_calculate_damage_type_effectiveness(self):
        """Test type effectiveness in damage calculation."""
        attacker = BattlePokemon(
            1, "u1", "squirtle", "Squirt", 10, 30, 30, 18, 20, 16, 20, 18,
            ["water"], [Move("Water Gun", "water", MoveCategory.SPECIAL, 40, 100, 25)]
        )
        defender = BattlePokemon(
            2, "u2", "charmander", "Char", 10, 30, 30, 20, 15, 18, 15, 20,
            ["fire"], []
        )
        
        move = Move("Water Gun", "water", MoveCategory.SPECIAL, 40, 100, 25)
        damage, type_mult, is_crit = BattleEngine.calculate_damage(attacker, defender, move)
        
        # Water vs Fire is super effective
        assert type_mult == 2.0
        assert damage > 10
    
    def test_execute_turn(self):
        """Test executing a battle turn."""
        attacker = BattlePokemon(
            1, "u1", "pikachu", "Pika", 10, 30, 30, 18, 15, 16, 15, 25,
            ["electric"],
            [Move("Tackle", "normal", MoveCategory.PHYSICAL, 40, 100, 35), Move("Thunder Shock", "electric", MoveCategory.SPECIAL, 40, 100, 30)]
        )
        defender = BattlePokemon(
            2, "u2", "squirtle", "Squirt", 10, 35, 35, 16, 20, 14, 20, 18,
            ["water"], []
        )
        
        initial_hp = defender.current_hp
        turn_result = BattleEngine.execute_turn(attacker, defender, 1)  # Use Thunder Shock
        
        # Defender should take damage
        assert defender.current_hp < initial_hp
        
        # Turn result should have correct data
        assert turn_result.attacker_name == "Pika"
        assert turn_result.defender_name == "Squirt"
        assert turn_result.move_used == "Thunder Shock"
        assert turn_result.damage_dealt > 0
        assert turn_result.effectiveness == "super"  # Electric vs Water
    
    def test_execute_turn_causes_faint(self):
        """Test that turn execution can cause fainting."""
        attacker = BattlePokemon(
            1, "u1", "machamp", "Mach", 40, 100, 100, 80, 50, 60, 50, 60,
            ["fighting"], [Move("Karate Chop", "fighting", MoveCategory.PHYSICAL, 100, 100, 25)]
        )
        defender = BattlePokemon(
            2, "u2", "pidgey", "Pidg", 5, 5, 5, 10, 10, 10, 10, 15,
            ["normal", "flying"], []
        )
        
        turn_result = BattleEngine.execute_turn(attacker, defender, 0)
        
        # Defender should be fainted
        assert defender.current_hp == 0
        assert defender.is_fainted is True
        assert turn_result.defender_fainted is True
    
    def test_move_index_out_of_bounds(self):
        """Test that invalid move index defaults to first move."""
        attacker = BattlePokemon(
            1, "u1", "pikachu", "Pika", 10, 30, 30, 18, 15, 16, 15, 25,
            ["electric"], [Move("Tackle", "normal", MoveCategory.PHYSICAL, 40, 100, 35)]
        )
        defender = BattlePokemon(
            2, "u2", "squirtle", "Squirt", 10, 35, 35, 16, 20, 14, 20, 18,
            ["water"], []
        )
        
        # Try to use move index 5 (out of bounds)
        turn_result = BattleEngine.execute_turn(attacker, defender, 5)
        
        # Should use first move (Tackle)
        assert turn_result.move_used == "Tackle"
    
    def test_calculate_xp_reward(self):
        """Test XP reward calculation."""
        # Winner is lower level - should get more XP
        xp_low_wins = BattleEngine.calculate_xp_reward(10, 30)
        assert xp_low_wins > 100
        
        # Winner is higher level - should get less XP
        xp_high_wins = BattleEngine.calculate_xp_reward(30, 10)
        assert xp_high_wins > 0
        assert xp_high_wins < xp_low_wins
        
        # Same level
        xp_equal = BattleEngine.calculate_xp_reward(20, 20)
        assert xp_equal > 0
    
    def test_calculate_cookie_reward(self):
        """Test cookie reward calculation."""
        # Winner is lower level - more cookies
        cookies_low = BattleEngine.calculate_cookie_reward(10, 30)
        assert cookies_low >= 3
        
        # Winner is higher level - fewer cookies
        cookies_high = BattleEngine.calculate_cookie_reward(30, 10)
        assert cookies_high >= 1
        
        # Same level
        cookies_equal = BattleEngine.calculate_cookie_reward(20, 20)
        assert cookies_equal >= 2
    
    def test_assign_moves_to_pokemon(self):
        """Test move assignment based on Pokemon type and level."""
        # Fire type Pokemon
        fire_pokemon_data = {
            'species': 'charmander',
            'types': ['fire'],
            'level': 5
        }
        moves = BattleEngine.assign_moves_to_pokemon(fire_pokemon_data, 5)
        
        # Should have at least tackle and ember
        assert len(moves) >= 2
        move_names = [m.name for m in moves]
        assert "Tackle" in move_names
        assert "Ember" in move_names
    
    def test_assign_moves_high_level(self):
        """Test that higher level Pokemon get more moves."""
        water_pokemon_data = {
            'species': 'squirtle',
            'types': ['water'],
            'level': 25
        }
        moves = BattleEngine.assign_moves_to_pokemon(water_pokemon_data, 25)
        
        # Should have multiple moves including higher level ones
        assert len(moves) >= 2


class TestBattleManagement:
    """Test battle creation and management."""
    
    def setup_method(self):
        """Clear active battles before each test."""
        _active_battles.clear()
    
    def test_create_battle(self):
        """Test creating a new battle."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = create_battle("u1", "u2", p1, p2)
        
        assert battle is not None
        assert battle.challenger_id == "u1"
        assert battle.opponent_id == "u2"
        
        # Both users should have active battles
        assert get_active_battle("u1") is not None
        assert get_active_battle("u2") is not None
    
    def test_get_active_battle(self):
        """Test retrieving active battle."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = create_battle("u1", "u2", p1, p2)
        
        retrieved_battle = get_active_battle("u1")
        assert retrieved_battle is battle
    
    def test_get_active_battle_none(self):
        """Test retrieving active battle when none exists."""
        assert get_active_battle("nonexistent_user") is None
    
    def test_end_battle(self):
        """Test ending a battle."""
        p1 = BattlePokemon(1, "u1", "pikachu", "Pika", 10, 30, 30, 15, 10, 12, 10, 20, ["electric"], [])
        p2 = BattlePokemon(2, "u2", "charmander", "Char", 10, 25, 25, 14, 11, 13, 11, 18, ["fire"], [])
        
        battle = create_battle("u1", "u2", p1, p2)
        end_battle(battle)
        
        # Both users should no longer have active battles
        assert get_active_battle("u1") is None
        assert get_active_battle("u2") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
