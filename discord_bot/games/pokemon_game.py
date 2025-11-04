"""
PokemonGame - Core game logic for Pokemon capture, training, and evolution.

Features:
- Random Pokemon encounters with rarity system
- Max 3 of same species per user
- Training with cookies (luck-based XP)
- Evolution system using duplicates + cookies
- Battle system (PvP and PvE)
- Proper stat generation with IVs and natures
- API integration for accurate Pokemon data
"""

from __future__ import annotations

import random
import json
from typing import Optional, Dict, List, Tuple, TYPE_CHECKING, Any
from collections import defaultdict
from dataclasses import dataclass

from discord_bot.games.pokemon_data_manager import PokemonDataManager

if TYPE_CHECKING:
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine
    from discord_bot.core.engines.cookie_manager import CookieManager
    from discord_bot.core.engines.relationship_manager import RelationshipManager


@dataclass
class PokemonEncounter:
    """Represents a wild Pokemon encounter."""
    species: str
    level: int
    rarity: str  # common, uncommon, rare, legendary
    catch_rate: float  # 0.0 to 1.0


@dataclass
class Pokemon:
    """Represents a captured Pokemon with full battle stats."""
    pokemon_id: int
    species: str
    nickname: str
    level: int
    experience: int
    nature: str
    # Actual stats
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    # IVs
    iv_hp: int
    iv_attack: int
    iv_defense: int
    iv_special_attack: int
    iv_special_defense: int
    iv_speed: int
    is_favorite: bool = False
    types: List[str] = None
    
    def __post_init__(self):
        if self.types is None:
            self.types = []


class PokemonGame:
    """
    Main Pokemon game engine.
    
    Mechanics:
    - Catch: Random common/uncommon encounters
    - Fish: Water-type Pokemon encounters
    - Explore: Chance for rare/legendary Pokemon
    - Train: Spend cookies for XP (luck-based)
    - Evolve: Use duplicate + cookies to evolve
    """
    
    # Pokemon pools by encounter type
    CATCH_POOL = [
        # Common Pokemon (70% chance)
        ("pidgey", "common"), ("rattata", "common"), ("caterpie", "common"),
        ("weedle", "common"), ("spearow", "common"), ("ekans", "common"),
        # Uncommon Pokemon (30% chance)
        ("pikachu", "uncommon"), ("eevee", "uncommon"), ("meowth", "uncommon"),
        ("psyduck", "uncommon"), ("growlithe", "uncommon"), ("vulpix", "uncommon"),
    ]
    
    FISH_POOL = [
        # Common water types (60% chance)
        ("magikarp", "common"), ("goldeen", "common"), ("tentacool", "common"),
        ("poliwag", "common"), ("horsea", "common"),
        # Uncommon water types (30% chance)
        ("squirtle", "uncommon"), ("psyduck", "uncommon"), ("staryu", "uncommon"),
        ("krabby", "uncommon"),
        # Rare water types (10% chance)
        ("lapras", "rare"), ("vaporeon", "rare"), ("gyarados", "rare"),
    ]
    
    EXPLORE_POOL = [
        # Uncommon (50% chance)
        ("charmander", "uncommon"), ("bulbasaur", "uncommon"), ("squirtle", "uncommon"),
        ("pikachu", "uncommon"), ("eevee", "uncommon"), ("dratini", "uncommon"),
        # Rare (35% chance)
        ("dragonair", "rare"), ("lapras", "rare"), ("snorlax", "rare"),
        ("gyarados", "rare"), ("arcanine", "rare"),
        # Legendary (15% chance)
        ("articuno", "legendary"), ("zapdos", "legendary"), ("moltres", "legendary"),
        ("mewtwo", "legendary"), ("dragonite", "legendary"),
    ]
    
    # Rarity weights and catch rates
    RARITY_WEIGHTS = {
        'common': 70,
        'uncommon': 20,
        'rare': 8,
        'legendary': 2
    }
    
    BASE_CATCH_RATES = {
        'common': 0.70,
        'uncommon': 0.50,
        'rare': 0.30,
        'legendary': 0.10
    }
    
    # Maximum Pokemon level
    MAX_POKEMON_LEVEL = 40
    
    # Evolution chains with level requirements
    # Format: species: (evolved_form, min_level, cookie_cost, stage)
    # stage: 1 = basic, 2 = second stage, 3 = final stage
    EVOLUTIONS = {
        # 3-stage evolution chains (levels 15, 25)
        'bulbasaur': ('ivysaur', 15, 5, 1),
        'ivysaur': ('venusaur', 25, 8, 2),
        'charmander': ('charmeleon', 15, 5, 1),
        'charmeleon': ('charizard', 25, 8, 2),
        'squirtle': ('wartortle', 15, 5, 1),
        'wartortle': ('blastoise', 25, 8, 2),
        'caterpie': ('metapod', 15, 2, 1),
        'metapod': ('butterfree', 25, 4, 2),
        'weedle': ('kakuna', 15, 2, 1),
        'kakuna': ('beedrill', 25, 4, 2),
        'pidgey': ('pidgeotto', 15, 3, 1),
        'pidgeotto': ('pidgeot', 25, 6, 2),
        'dratini': ('dragonair', 15, 6, 1),
        'dragonair': ('dragonite', 25, 10, 2),
        'larvitar': ('pupitar', 15, 6, 1),
        'pupitar': ('tyranitar', 25, 10, 2),
        'beldum': ('metang', 15, 6, 1),
        'metang': ('metagross', 25, 10, 2),
        
        # 2-stage evolution chains (level 25)
        'pikachu': ('raichu', 25, 6, 1),
        'magikarp': ('gyarados', 25, 8, 1),
        'eevee': ('vaporeon', 25, 7, 1),  # Simplified - one evolution path
        'abra': ('kadabra', 25, 5, 1),
        'machop': ('machoke', 25, 5, 1),
        'gastly': ('haunter', 25, 5, 1),
        'geodude': ('graveler', 25, 5, 1),
        'ponyta': ('rapidash', 25, 5, 1),
        'slowpoke': ('slowbro', 25, 5, 1),
        'magnemite': ('magneton', 25, 5, 1),
        'onix': ('steelix', 25, 6, 1),
        'drowzee': ('hypno', 25, 4, 1),
        'cubone': ('marowak', 25, 4, 1),
        'horsea': ('seadra', 25, 5, 1),
        'goldeen': ('seaking', 25, 4, 1),
        'staryu': ('starmie', 25, 5, 1),
        'magby': ('magmar', 25, 5, 1),
        'elekid': ('electabuzz', 25, 5, 1),
        
        # Pokemon that max out at level 40 with special evolution
        'scyther': ('scizor', 40, 10, 1),
        'porygon': ('porygon2', 40, 8, 1),
        'feebas': ('milotic', 40, 10, 1),
    }
    
    def __init__(self, storage: GameStorageEngine, cookie_manager: CookieManager, 
                 relationship_manager: RelationshipManager,
                 data_manager: Optional[PokemonDataManager] = None):
        self.storage = storage
        self.cookie_manager = cookie_manager
        self.relationship_manager = relationship_manager
        # Allow optional injection for testing, create default if not provided
        self.data_manager = data_manager if data_manager is not None else PokemonDataManager()
    
    def generate_encounter(self, encounter_type: str = 'catch') -> PokemonEncounter:
        """
        Generate a random Pokemon encounter based on type.
        
        Args:
            encounter_type: 'catch', 'fish', or 'explore'
        
        Returns:
            PokemonEncounter object
        """
        # Select pool
        if encounter_type == 'fish':
            pool = self.FISH_POOL
        elif encounter_type == 'explore':
            pool = self.EXPLORE_POOL
        else:
            pool = self.CATCH_POOL
        
        # Weight by rarity
        species_list = []
        weights = []
        
        for species, rarity in pool:
            species_list.append((species, rarity))
            weights.append(self.RARITY_WEIGHTS[rarity])
        
        # Random selection
        species, rarity = random.choices(species_list, weights=weights, k=1)[0]
        
        # Generate level (1-20 for common, up to 50 for legendary)
        level_ranges = {
            'common': (1, 10),
            'uncommon': (5, 20),
            'rare': (15, 35),
            'legendary': (30, 50)
        }
        min_lvl, max_lvl = level_ranges[rarity]
        level = random.randint(min_lvl, max_lvl)
        
        catch_rate = self.BASE_CATCH_RATES[rarity]
        
        return PokemonEncounter(species, level, rarity, catch_rate)
    
    def attempt_catch(self, user_id: str, encounter: PokemonEncounter) -> Tuple[bool, Optional[Pokemon]]:
        """
        Attempt to catch a Pokemon with properly generated stats.
        
        Args:
            user_id: User attempting catch
            encounter: The Pokemon encounter
        
        Returns:
            (success, Pokemon or None)
        """
        # Check if user already has 3 of this species
        count = self.storage.get_pokemon_count_by_species(user_id, encounter.species)
        if count >= 3:
            return (False, None)  # Limit reached
        
        # Calculate catch success with luck modifier
        luck = self.relationship_manager.get_luck_modifier(user_id)
        adjusted_rate = min(0.95, encounter.catch_rate * luck)  # Cap at 95%
        
        if random.random() > adjusted_rate:
            return (False, None)  # Failed to catch
        
        # Generate complete Pokemon stats using data manager
        pokemon_data = self.data_manager.generate_pokemon_stats(
            encounter.species, 
            encounter.level
        )
        
        # Add to storage with full stats
        pokemon_id = self.storage.add_pokemon(
            user_id=user_id,
            species=encounter.species,
            nickname=encounter.species.capitalize(),
            level=encounter.level,
            hp=pokemon_data['hp'],
            attack=pokemon_data['attack'],
            defense=pokemon_data['defense'],
            special_attack=pokemon_data['special_attack'],
            special_defense=pokemon_data['special_defense'],
            speed=pokemon_data['speed'],
            iv_hp=pokemon_data['iv_hp'],
            iv_attack=pokemon_data['iv_attack'],
            iv_defense=pokemon_data['iv_defense'],
            iv_special_attack=pokemon_data['iv_special_attack'],
            iv_special_defense=pokemon_data['iv_special_defense'],
            iv_speed=pokemon_data['iv_speed'],
            nature=pokemon_data['nature']
        )
        
        if pokemon_id is None:
            return (False, None)  # Storage error
        
        # Create Pokemon object
        pokemon = Pokemon(
            pokemon_id=pokemon_id,
            species=encounter.species,
            nickname=encounter.species.capitalize(),
            level=encounter.level,
            experience=0,
            nature=pokemon_data['nature'],
            hp=pokemon_data['hp'],
            attack=pokemon_data['attack'],
            defense=pokemon_data['defense'],
            special_attack=pokemon_data['special_attack'],
            special_defense=pokemon_data['special_defense'],
            speed=pokemon_data['speed'],
            iv_hp=pokemon_data['iv_hp'],
            iv_attack=pokemon_data['iv_attack'],
            iv_defense=pokemon_data['iv_defense'],
            iv_special_attack=pokemon_data['iv_special_attack'],
            iv_special_defense=pokemon_data['iv_special_defense'],
            iv_speed=pokemon_data['iv_speed'],
            types=pokemon_data['types']
        )
        
        return (True, pokemon)
    
    def train_pokemon(self, user_id: str, pokemon_id: int, cookies_spent: int) -> Tuple[bool, Optional[Dict]]:
        """
        Train a Pokemon with cookies for XP.
        Recalculates stats when Pokemon levels up.
        
        Args:
            user_id: User training
            pokemon_id: Pokemon to train
            cookies_spent: Number of cookies to spend
        
        Returns:
            (success, updated_pokemon_data or None)
        """
        # Check if user can afford
        if not self.cookie_manager.can_afford(user_id, 'train'):
            return (False, None)
        
        # Get Pokemon's current level
        pokemon_before = self.storage.get_pokemon_by_id(pokemon_id)
        if not pokemon_before:
            return (False, None)
        
        old_level = pokemon_before['level']
        
        # Spend cookies (1 cookie per training action)
        success, _ = self.cookie_manager.spend_stamina(user_id, 'train')
        if not success:
            return (False, None)
        
        # Calculate XP based on luck
        xp_gained = self.cookie_manager.calculate_training_xp(user_id, cookies_spent)
        
        # Update Pokemon XP and level
        updated_pokemon = self.storage.update_pokemon_xp(pokemon_id, xp_gained)
        
        if not updated_pokemon:
            return (False, None)
        
        # If Pokemon leveled up, recalculate stats
        new_level = updated_pokemon['level']
        if new_level > old_level:
            new_stats = self.recalculate_stats_on_level(updated_pokemon)
            if new_stats:
                # Update stats in storage
                self.storage.update_pokemon_stats(pokemon_id, **new_stats)
                # Get fresh data
                updated_pokemon = self.storage.get_pokemon_by_id(pokemon_id)
        
        return (True, updated_pokemon)

    def _resolve_evolution_targets(
        self, user_id: str, pokemon_id: int
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Determine the primary Pokemon to evolve and available duplicates.

        Returns:
            (main_pokemon, duplicate_pokemon_list)
        """
        target = self.storage.get_pokemon_by_id(pokemon_id)
        if not target:
            return None, []

        species = target['species'].lower()
        user_pokemon = self.storage.get_user_pokemon(user_id)

        species_group = [
            poke for poke in user_pokemon if poke['species'].lower() == species
        ]

        if not species_group:
            return None, []

        species_group.sort(key=lambda p: ((p.get('caught_date') or ''), p['pokemon_id']))
        main_pokemon = species_group[0]
        duplicates = [p for p in species_group if p['pokemon_id'] != main_pokemon['pokemon_id']]
        return main_pokemon, duplicates
    
    def can_evolve(self, user_id: str, pokemon_id: int) -> Tuple[bool, Optional[str], int, Optional[str]]:
        """
        Check if a Pokemon can evolve.
        
        Returns:
            (can_evolve, evolution_name or None, cookie_cost, reason_if_cannot)
        """
        target_pokemon, duplicates = self._resolve_evolution_targets(user_id, pokemon_id)

        if not target_pokemon:
            return (False, None, 0, "Pokemon not found")
        
        species = target_pokemon['species'].lower()
        current_level = target_pokemon.get('level', 1)
        
        # Check if species can evolve
        if species not in self.EVOLUTIONS:
            return (False, None, 0, f"{species.title()} cannot evolve")
        
        evolved_form, min_level, cookie_cost, stage = self.EVOLUTIONS[species]
        
        # Check level requirement
        if current_level < min_level:
            return (False, evolved_form, cookie_cost, 
                    f"{species.title()} needs to reach level {min_level} to evolve (currently level {current_level})")
        
        # Check if user has enough cookies
        if not self.cookie_manager.can_afford(user_id, 'evolve'):
            return (False, evolved_form, cookie_cost,
                    f"Not enough cookies (need {cookie_cost} cookies to evolve)")
        
        # Check if user has a duplicate to consume
        if not duplicates:
            return (False, evolved_form, cookie_cost,
                    f"Need a duplicate {species.title()} to evolve")
        
        return (True, evolved_form, cookie_cost, None)

    def get_evolution_candidates(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return a summary of Pokemon that could evolve along with their IDs.
        """
        candidates: List[Dict[str, Any]] = []
        user_pokemon = self.storage.get_user_pokemon(user_id)
        species_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for poke in user_pokemon:
            species_groups[poke['species'].lower()].append(poke)

        for species, pokes in species_groups.items():
            if species not in self.EVOLUTIONS or len(pokes) < 2:
                continue

            pokes.sort(key=lambda p: ((p.get('caught_date') or ''), p['pokemon_id']))
            main = pokes[0]
            duplicates = [p for p in pokes if p['pokemon_id'] != main['pokemon_id']]

            can_evolve, evolved_form, cost, reason = self.can_evolve(user_id, main['pokemon_id'])
            candidates.append(
                {
                    "species": species,
                    "main_id": main['pokemon_id'],
                    "main_level": main.get('level', 1),
                    "next_form": evolved_form,
                    "cookie_cost": cost,
                    "ready": can_evolve,
                    "reason": reason,
                    "duplicate_ids": [p['pokemon_id'] for p in duplicates],
                }
            )

        return sorted(candidates, key=lambda c: c["species"])

    def evolve_pokemon(
        self,
        user_id: str,
        pokemon_id: int,
        duplicate_id: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Evolve a Pokemon using a duplicate and cookies.
        Maintains IVs and nature from original Pokemon.
        
        Args:
            user_id: User evolving
            pokemon_id: Pokemon to evolve
            duplicate_id: Duplicate Pokemon to consume (optional - auto-selects newest)
        
        Returns:
            (success, evolved_pokemon_data or None, error_message or None)
        """
        target_pokemon, duplicates = self._resolve_evolution_targets(user_id, pokemon_id)

        if not target_pokemon:
            return (False, None, "Pokemon not found")

        primary_id = target_pokemon['pokemon_id']

        can_evolve_result = self.can_evolve(user_id, primary_id)
        can_evolve, evolved_form, cookie_cost, reason = can_evolve_result
        
        if not can_evolve or not evolved_form:
            return (False, None, reason)

        if duplicate_id:
            duplicate = next((p for p in duplicates if p['pokemon_id'] == duplicate_id), None)
            if not duplicate:
                return (False, None, "Duplicate Pokemon not found")
        else:
            if not duplicates:
                return (False, None, "Need a duplicate to evolve")
            duplicate = duplicates[-1]  # newest capture becomes the sacrifice
        
        # Spend cookies
        success, _ = self.cookie_manager.spend_stamina(user_id, 'evolve')
        if not success:
            return (False, None, "Failed to spend cookies")
        
        # Remove duplicate
        if not self.storage.remove_pokemon(duplicate['pokemon_id']):
            return (False, None, "Failed to consume duplicate Pokemon")
        
        # Keep current level (no level boost)
        current_level = target_pokemon['level']
        
        # Cap at max level
        if current_level > self.MAX_POKEMON_LEVEL:
            current_level = self.MAX_POKEMON_LEVEL
        
        # Maintain IVs and nature from original Pokemon
        nature = target_pokemon.get('nature', 'hardy')
        
        # Generate new stats for evolved form
        pokemon_data = self.data_manager.generate_pokemon_stats(
            evolved_form,
            current_level,
            nature=nature
        )
        
        # Override IVs to keep the original Pokemon's IVs
        # (Evolution doesn't change IVs, just base stats)
        pokemon_data['iv_hp'] = target_pokemon['iv_hp']
        pokemon_data['iv_attack'] = target_pokemon['iv_attack']
        pokemon_data['iv_defense'] = target_pokemon['iv_defense']
        pokemon_data['iv_special_attack'] = target_pokemon['iv_special_attack']
        pokemon_data['iv_special_defense'] = target_pokemon['iv_special_defense']
        pokemon_data['iv_speed'] = target_pokemon['iv_speed']
        
        # Recalculate stats with original IVs and new base stats
        base_stats = self.data_manager.get_base_stats(evolved_form)
        if base_stats:
            pokemon_data['hp'] = self.data_manager.calculate_stat(
                base_stats.hp, pokemon_data['iv_hp'], current_level, is_hp=True
            )
            pokemon_data['attack'] = self.data_manager.calculate_stat(
                base_stats.attack, pokemon_data['iv_attack'], current_level
            )
            pokemon_data['defense'] = self.data_manager.calculate_stat(
                base_stats.defense, pokemon_data['iv_defense'], current_level
            )
            pokemon_data['special_attack'] = self.data_manager.calculate_stat(
                base_stats.special_attack, pokemon_data['iv_special_attack'], current_level
            )
            pokemon_data['special_defense'] = self.data_manager.calculate_stat(
                base_stats.special_defense, pokemon_data['iv_special_defense'], current_level
            )
            pokemon_data['speed'] = self.data_manager.calculate_stat(
                base_stats.speed, pokemon_data['iv_speed'], current_level
            )
            
            # Apply nature modifiers
            for stat_name in ['attack', 'defense', 'special_attack', 'special_defense', 'speed']:
                pokemon_data[stat_name] = self.data_manager.apply_nature_modifier(
                    pokemon_data[stat_name], stat_name, nature
                )
        
        # Remove old Pokemon
        self.storage.remove_pokemon(primary_id)
        
        # Add evolved Pokemon with maintained IVs
        new_pokemon_id = self.storage.add_pokemon(
            user_id=user_id,
            species=evolved_form,
            nickname=target_pokemon.get('nickname', evolved_form.capitalize()),
            level=current_level,
            hp=pokemon_data['hp'],
            attack=pokemon_data['attack'],
            defense=pokemon_data['defense'],
            special_attack=pokemon_data['special_attack'],
            special_defense=pokemon_data['special_defense'],
            speed=pokemon_data['speed'],
            iv_hp=pokemon_data['iv_hp'],
            iv_attack=pokemon_data['iv_attack'],
            iv_defense=pokemon_data['iv_defense'],
            iv_special_attack=pokemon_data['iv_special_attack'],
            iv_special_defense=pokemon_data['iv_special_defense'],
            iv_speed=pokemon_data['iv_speed'],
            nature=nature
        )
        
        if new_pokemon_id:
            evolved_data = self.storage.get_pokemon_by_id(new_pokemon_id)
            if evolved_data is not None:
                evolved_data['consumed_duplicate_id'] = duplicate['pokemon_id']
                evolved_data['consumed_duplicate_nickname'] = duplicate.get('nickname')
            return (True, evolved_data, None)
        
        return (False, None, "Failed to create evolved Pokemon")
    
    def get_user_collection(self, user_id: str) -> List[Dict]:
        """Get user's Pokemon collection with full stats."""
        pokemon_list = self.storage.get_user_pokemon(user_id)
        
        # All stats are now stored as columns, no JSON parsing needed
        # But we can add calculated fields like IV percentage
        for pokemon in pokemon_list:
            # Calculate IV percentage
            if all(key in pokemon for key in ['iv_hp', 'iv_attack', 'iv_defense', 
                                              'iv_special_attack', 'iv_special_defense', 'iv_speed']):
                total_ivs = (pokemon['iv_hp'] + pokemon['iv_attack'] + pokemon['iv_defense'] + 
                           pokemon['iv_special_attack'] + pokemon['iv_special_defense'] + pokemon['iv_speed'])
                pokemon['iv_percentage'] = round((total_ivs / 186) * 100, 1)  # 186 = 31*6
                
                # Add quality rating
                pokemon['iv_quality'] = self._get_iv_quality(pokemon['iv_percentage'])
        
        return pokemon_list
    
    def _get_iv_quality(self, iv_percentage: float) -> str:
        """Get quality description for IV percentage."""
        if iv_percentage >= 90:
            return "Perfect"
        elif iv_percentage >= 80:
            return "Excellent"
        elif iv_percentage >= 65:
            return "Great"
        elif iv_percentage >= 50:
            return "Good"
        elif iv_percentage >= 35:
            return "Average"
        elif iv_percentage >= 20:
            return "Below Average"
        else:
            return "Poor"
    
    def recalculate_stats_on_level(self, pokemon_data: Dict) -> Dict[str, int]:
        """
        Recalculate Pokemon stats when leveling up.
        Uses stored IVs and nature to maintain consistency.
        """
        level = pokemon_data['level']
        species = pokemon_data['species']
        nature = pokemon_data.get('nature', 'hardy')
        
        # Get base stats
        base_stats = self.data_manager.get_base_stats(species)
        if not base_stats:
            return {}
        
        # Recalculate using stored IVs
        new_stats = {}
        new_stats['hp'] = self.data_manager.calculate_stat(
            base_stats.hp, pokemon_data['iv_hp'], level, is_hp=True
        )
        new_stats['attack'] = self.data_manager.calculate_stat(
            base_stats.attack, pokemon_data['iv_attack'], level
        )
        new_stats['defense'] = self.data_manager.calculate_stat(
            base_stats.defense, pokemon_data['iv_defense'], level
        )
        new_stats['special_attack'] = self.data_manager.calculate_stat(
            base_stats.special_attack, pokemon_data['iv_special_attack'], level
        )
        new_stats['special_defense'] = self.data_manager.calculate_stat(
            base_stats.special_defense, pokemon_data['iv_special_defense'], level
        )
        new_stats['speed'] = self.data_manager.calculate_stat(
            base_stats.speed, pokemon_data['iv_speed'], level
        )
        
        # Apply nature modifiers (except HP)
        for stat_name in ['attack', 'defense', 'special_attack', 'special_defense', 'speed']:
            new_stats[stat_name] = self.data_manager.apply_nature_modifier(
                new_stats[stat_name], stat_name, nature
            )
        
        return new_stats


