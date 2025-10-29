"""
Pokemon Battle System - Turn-based combat matching official Pokemon game mechanics.

Features:
- Turn-based combat with speed determining turn order
- Type effectiveness (super effective, not very effective, immune)
- Physical and special attack/defense split
- Critical hits
- Move power and accuracy
- Status effects (future enhancement)
- Battle rewards (XP and cookies)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from enum import Enum

if TYPE_CHECKING:
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class MoveType(Enum):
    """Pokemon types."""
    NORMAL = "normal"
    FIRE = "fire"
    WATER = "water"
    GRASS = "grass"
    ELECTRIC = "electric"
    ICE = "ice"
    FIGHTING = "fighting"
    POISON = "poison"
    GROUND = "ground"
    FLYING = "flying"
    PSYCHIC = "psychic"
    BUG = "bug"
    ROCK = "rock"
    GHOST = "ghost"
    DRAGON = "dragon"
    DARK = "dark"
    STEEL = "steel"
    FAIRY = "fairy"


class MoveCategory(Enum):
    """Move damage category."""
    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"


@dataclass
class Move:
    """Represents a Pokemon move."""
    name: str
    type: str
    category: MoveCategory
    power: int
    accuracy: int  # 0-100
    pp: int
    description: str = ""


@dataclass
class BattlePokemon:
    """Pokemon state during battle."""
    pokemon_id: int
    user_id: str
    species: str
    nickname: str
    level: int
    
    # Stats
    max_hp: int
    current_hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    
    # Battle info
    types: List[str]
    moves: List[Move]
    
    # Status
    is_fainted: bool = False
    
    @property
    def display_name(self) -> str:
        """Get display name for battle."""
        return self.nickname if self.nickname else self.species.capitalize()
    
    @property
    def hp_percentage(self) -> float:
        """Get HP percentage."""
        return (self.current_hp / self.max_hp) * 100 if self.max_hp > 0 else 0


@dataclass
class BattleAction:
    """Represents a battle action."""
    user_id: str
    action_type: str  # "move", "switch", "forfeit"
    move_index: Optional[int] = None
    target_pokemon_id: Optional[int] = None


@dataclass
class BattleTurn:
    """Results of a battle turn."""
    attacker_name: str
    defender_name: str
    move_used: str
    damage_dealt: int
    effectiveness: str  # "normal", "super", "not_very", "immune"
    is_critical: bool
    defender_fainted: bool
    message: str


class BattleState:
    """Manages the state of an ongoing battle."""
    
    def __init__(self, challenger_id: str, opponent_id: str,
                 challenger_pokemon: BattlePokemon, opponent_pokemon: BattlePokemon):
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.challenger_pokemon = challenger_pokemon
        self.opponent_pokemon = opponent_pokemon
        self.turn_number = 0
        self.battle_log: List[BattleTurn] = []
        self.is_finished = False
        self.winner_id: Optional[str] = None
        
        # Determine first turn based on speed
        if challenger_pokemon.speed >= opponent_pokemon.speed:
            self.current_turn_user_id = challenger_id
        else:
            self.current_turn_user_id = opponent_id
    
    def get_pokemon_by_user(self, user_id: str) -> BattlePokemon:
        """Get Pokemon belonging to a user."""
        if user_id == self.challenger_id:
            return self.challenger_pokemon
        return self.opponent_pokemon
    
    def get_opponent_pokemon(self, user_id: str) -> BattlePokemon:
        """Get opponent's Pokemon."""
        if user_id == self.challenger_id:
            return self.opponent_pokemon
        return self.challenger_pokemon
    
    def get_opponent_id(self, user_id: str) -> str:
        """Get opponent's user ID."""
        return self.opponent_id if user_id == self.challenger_id else self.challenger_id
    
    def switch_turn(self):
        """Switch to the other player's turn."""
        self.current_turn_user_id = self.get_opponent_id(self.current_turn_user_id)
        self.turn_number += 1


class TypeEffectiveness:
    """Type effectiveness chart for Pokemon battles."""
    
    # Type effectiveness multipliers: attacking_type -> {defending_type: multiplier}
    CHART = {
        "normal": {"rock": 0.5, "ghost": 0, "steel": 0.5},
        "fire": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 2, "bug": 2, "rock": 0.5, "dragon": 0.5, "steel": 2},
        "water": {"fire": 2, "water": 0.5, "grass": 0.5, "ground": 2, "rock": 2, "dragon": 0.5},
        "grass": {"fire": 0.5, "water": 2, "grass": 0.5, "poison": 0.5, "ground": 2, "flying": 0.5, "bug": 0.5, "rock": 2, "dragon": 0.5, "steel": 0.5},
        "electric": {"water": 2, "electric": 0.5, "grass": 0.5, "ground": 0, "flying": 2, "dragon": 0.5},
        "ice": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 0.5, "ground": 2, "flying": 2, "dragon": 2, "steel": 0.5},
        "fighting": {"normal": 2, "ice": 2, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2, "ghost": 0, "dark": 2, "steel": 2, "fairy": 0.5},
        "poison": {"grass": 2, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0, "fairy": 2},
        "ground": {"fire": 2, "electric": 2, "grass": 0.5, "poison": 2, "flying": 0, "bug": 0.5, "rock": 2, "steel": 2},
        "flying": {"electric": 0.5, "grass": 2, "fighting": 2, "bug": 2, "rock": 0.5, "steel": 0.5},
        "psychic": {"fighting": 2, "poison": 2, "psychic": 0.5, "dark": 0, "steel": 0.5},
        "bug": {"fire": 0.5, "grass": 2, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2, "ghost": 0.5, "dark": 2, "steel": 0.5, "fairy": 0.5},
        "rock": {"fire": 2, "ice": 2, "fighting": 0.5, "ground": 0.5, "flying": 2, "bug": 2, "steel": 0.5},
        "ghost": {"normal": 0, "psychic": 2, "ghost": 2, "dark": 0.5},
        "dragon": {"dragon": 2, "steel": 0.5, "fairy": 0},
        "dark": {"fighting": 0.5, "psychic": 2, "ghost": 2, "dark": 0.5, "fairy": 0.5},
        "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2, "rock": 2, "steel": 0.5, "fairy": 2},
        "fairy": {"fire": 0.5, "fighting": 2, "poison": 0.5, "dragon": 2, "dark": 2, "steel": 0.5},
    }
    
    @classmethod
    def get_multiplier(cls, attack_type: str, defender_types: List[str]) -> float:
        """
        Calculate type effectiveness multiplier.
        
        Args:
            attack_type: Type of the attacking move
            defender_types: List of defender's types
        
        Returns:
            Multiplier (0, 0.5, 1, 2, or 4 for dual-type)
        """
        multiplier = 1.0
        attack_type = attack_type.lower()
        
        for def_type in defender_types:
            def_type = def_type.lower()
            type_chart = cls.CHART.get(attack_type, {})
            multiplier *= type_chart.get(def_type, 1.0)
        
        return multiplier
    
    @classmethod
    def get_effectiveness_text(cls, multiplier: float) -> str:
        """Get text description of effectiveness."""
        if multiplier == 0:
            return "immune"
        elif multiplier < 1:
            return "not_very"
        elif multiplier > 1:
            return "super"
        return "normal"


class BattleEngine:
    """Handles battle calculations and logic."""
    
    # Move database (simplified - in production this would be much larger)
    MOVES_DB = {
        "tackle": Move("Tackle", "normal", MoveCategory.PHYSICAL, 40, 100, 35),
        "scratch": Move("Scratch", "normal", MoveCategory.PHYSICAL, 40, 100, 35),
        "pound": Move("Pound", "normal", MoveCategory.PHYSICAL, 40, 100, 35),
        "quick_attack": Move("Quick Attack", "normal", MoveCategory.PHYSICAL, 40, 100, 30),
        
        "ember": Move("Ember", "fire", MoveCategory.SPECIAL, 40, 100, 25),
        "flamethrower": Move("Flamethrower", "fire", MoveCategory.SPECIAL, 90, 100, 15),
        "fire_blast": Move("Fire Blast", "fire", MoveCategory.SPECIAL, 110, 85, 5),
        
        "water_gun": Move("Water Gun", "water", MoveCategory.SPECIAL, 40, 100, 25),
        "bubble_beam": Move("Bubble Beam", "water", MoveCategory.SPECIAL, 65, 100, 20),
        "hydro_pump": Move("Hydro Pump", "water", MoveCategory.SPECIAL, 110, 80, 5),
        
        "vine_whip": Move("Vine Whip", "grass", MoveCategory.PHYSICAL, 45, 100, 25),
        "razor_leaf": Move("Razor Leaf", "grass", MoveCategory.PHYSICAL, 55, 95, 25),
        "solar_beam": Move("Solar Beam", "grass", MoveCategory.SPECIAL, 120, 100, 10),
        
        "thunder_shock": Move("Thunder Shock", "electric", MoveCategory.SPECIAL, 40, 100, 30),
        "thunderbolt": Move("Thunderbolt", "electric", MoveCategory.SPECIAL, 90, 100, 15),
        "thunder": Move("Thunder", "electric", MoveCategory.SPECIAL, 110, 70, 10),
        
        "bite": Move("Bite", "dark", MoveCategory.PHYSICAL, 60, 100, 25),
        "dragon_rage": Move("Dragon Rage", "dragon", MoveCategory.SPECIAL, 40, 100, 10),
        "psychic": Move("Psychic", "psychic", MoveCategory.SPECIAL, 90, 100, 10),
    }
    
    @classmethod
    def assign_moves_to_pokemon(cls, pokemon_data: Dict, level: int) -> List[Move]:
        """
        Assign appropriate moves based on Pokemon species and level.
        Simplified - uses type-based moves.
        """
        moves = []
        types = pokemon_data.get('types', [])
        
        if not types:
            types = ['normal']
        
        # Always include a basic normal move
        moves.append(cls.MOVES_DB["tackle"])
        
        # Add type-specific moves based on level
        primary_type = types[0].lower() if types else 'normal'
        
        # Level 1-15: Basic moves
        if primary_type == "fire":
            moves.append(cls.MOVES_DB["ember"])
            if level >= 10:
                moves.append(cls.MOVES_DB["flamethrower"])
        elif primary_type == "water":
            moves.append(cls.MOVES_DB["water_gun"])
            if level >= 10:
                moves.append(cls.MOVES_DB["bubble_beam"])
        elif primary_type == "grass":
            moves.append(cls.MOVES_DB["vine_whip"])
            if level >= 10:
                moves.append(cls.MOVES_DB["razor_leaf"])
        elif primary_type == "electric":
            moves.append(cls.MOVES_DB["thunder_shock"])
            if level >= 10:
                moves.append(cls.MOVES_DB["thunderbolt"])
        elif primary_type == "dragon":
            moves.append(cls.MOVES_DB["dragon_rage"])
        elif primary_type == "dark":
            moves.append(cls.MOVES_DB["bite"])
        elif primary_type == "psychic":
            moves.append(cls.MOVES_DB["psychic"])
        
        # Add secondary type move if dual-type and high level
        if len(types) > 1 and level >= 20:
            secondary_type = types[1].lower()
            if secondary_type == "flying":
                moves.append(cls.MOVES_DB["quick_attack"])
        
        # Ensure at least 2 moves, max 4
        while len(moves) < 2:
            moves.append(cls.MOVES_DB["scratch"])
        
        return moves[:4]
    
    @classmethod
    def calculate_damage(cls, attacker: BattlePokemon, defender: BattlePokemon, 
                        move: Move) -> Tuple[int, float, bool]:
        """
        Calculate damage using Pokemon formula.
        
        Returns:
            (damage, type_effectiveness_multiplier, is_critical)
        """
        # Check accuracy
        if random.randint(1, 100) > move.accuracy:
            return (0, 1.0, False)
        
        # Status moves don't deal damage
        if move.category == MoveCategory.STATUS:
            return (0, 1.0, False)
        
        # Determine attack and defense stats
        if move.category == MoveCategory.PHYSICAL:
            attack_stat = attacker.attack
            defense_stat = defender.defense
        else:  # SPECIAL
            attack_stat = attacker.special_attack
            defense_stat = defender.special_defense
        
        # Base damage calculation (Pokemon formula)
        level_factor = (2 * attacker.level / 5) + 2
        damage = (level_factor * move.power * attack_stat) / defense_stat
        damage = (damage / 50) + 2
        
        # Type effectiveness
        type_multiplier = TypeEffectiveness.get_multiplier(move.type, defender.types)
        damage *= type_multiplier
        
        # STAB (Same Type Attack Bonus) - 1.5x if move type matches Pokemon type
        attacker_types = [t.lower() for t in attacker.types]
        if move.type.lower() in attacker_types:
            damage *= 1.5
        
        # Critical hit (6.25% chance)
        is_critical = random.random() < 0.0625
        if is_critical:
            damage *= 1.5
        
        # Random factor (85-100%)
        damage *= random.uniform(0.85, 1.0)
        
        # Minimum 1 damage if hit lands
        damage = max(1, int(damage))
        
        return (damage, type_multiplier, is_critical)
    
    @classmethod
    def execute_turn(cls, attacker: BattlePokemon, defender: BattlePokemon, 
                    move_index: int) -> BattleTurn:
        """
        Execute a battle turn.
        
        Args:
            attacker: Pokemon using the move
            defender: Pokemon receiving the move
            move_index: Index of move to use (0-3)
        
        Returns:
            BattleTurn with results
        """
        if move_index < 0 or move_index >= len(attacker.moves):
            move_index = 0
        
        move = attacker.moves[move_index]
        damage, type_mult, is_crit = cls.calculate_damage(attacker, defender, move)
        
        # Apply damage
        defender.current_hp = max(0, defender.current_hp - damage)
        defender_fainted = defender.current_hp == 0
        if defender_fainted:
            defender.is_fainted = True
        
        # Build message
        effectiveness = TypeEffectiveness.get_effectiveness_text(type_mult)
        
        if damage == 0:
            message = f"{attacker.display_name}'s {move.name} missed!"
        else:
            message = f"{attacker.display_name} used {move.name}!"
            if is_crit:
                message += " Critical hit!"
            if effectiveness == "super":
                message += " It's super effective!"
            elif effectiveness == "not_very":
                message += " It's not very effective..."
            elif effectiveness == "immune":
                message += " It doesn't affect the foe..."
        
        return BattleTurn(
            attacker_name=attacker.display_name,
            defender_name=defender.display_name,
            move_used=move.name,
            damage_dealt=damage,
            effectiveness=effectiveness,
            is_critical=is_crit,
            defender_fainted=defender_fainted,
            message=message
        )
    
    @classmethod
    def calculate_xp_reward(cls, winner_level: int, loser_level: int) -> int:
        """Calculate XP reward for battle winner."""
        # Base XP scales with opponent level
        base_xp = loser_level * 50
        
        # Level difference modifier
        level_diff = loser_level - winner_level
        if level_diff > 0:
            # Bonus for beating higher level
            base_xp += level_diff * 10
        
        return max(50, base_xp)
    
    @classmethod
    def calculate_cookie_reward(cls, winner_level: int, loser_level: int) -> int:
        """Calculate cookie reward for battle winner."""
        # Base 2-4 cookies
        base_cookies = random.randint(2, 4)
        
        # Bonus for beating higher level opponent
        level_diff = loser_level - winner_level
        if level_diff >= 5:
            base_cookies += 2
        elif level_diff >= 10:
            base_cookies += 5
        
        return base_cookies


# Global battle manager to track active battles
_active_battles: Dict[str, BattleState] = {}


def get_active_battle(user_id: str) -> Optional[BattleState]:
    """Get active battle for a user."""
    return _active_battles.get(user_id)


def create_battle(challenger_id: str, opponent_id: str,
                 challenger_pokemon: BattlePokemon, opponent_pokemon: BattlePokemon) -> BattleState:
    """Create a new battle."""
    battle = BattleState(challenger_id, opponent_id, challenger_pokemon, opponent_pokemon)
    _active_battles[challenger_id] = battle
    _active_battles[opponent_id] = battle
    return battle


def end_battle(battle: BattleState):
    """End a battle and clean up."""
    _active_battles.pop(battle.challenger_id, None)
    _active_battles.pop(battle.opponent_id, None)
    battle.is_finished = True
