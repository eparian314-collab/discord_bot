"""
PokemonDataManager - Manages Pokemon base stats, API integration, and IV system.

Features:
- Fetches Pokemon data from PokeAPI
- Caches base stats for performance
- Generates Individual Values (IVs) with balanced normal distribution
- Calculates actual stats using Pokemon formulas
- Applies nature modifiers
- Supports multiple data sources with fallbacks
"""

from __future__ import annotations

import random
import json
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict

import requests


@dataclass
class PokemonBaseStats:
    """Base stats for a Pokemon species (from API)."""
    species: str
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    types: list[str]
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PokemonIVs:
    """Individual Values (0-31) that add variation to each Pokemon."""
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    
    def to_dict(self) -> dict:
        return asdict(self)


# Pokemon Natures that modify stats
NATURES = {
    'hardy': {},  # Neutral
    'lonely': {'attack': 1.1, 'defense': 0.9},
    'brave': {'attack': 1.1, 'speed': 0.9},
    'adamant': {'attack': 1.1, 'special_attack': 0.9},
    'naughty': {'attack': 1.1, 'special_defense': 0.9},
    'bold': {'defense': 1.1, 'attack': 0.9},
    'relaxed': {'defense': 1.1, 'speed': 0.9},
    'impish': {'defense': 1.1, 'special_attack': 0.9},
    'lax': {'defense': 1.1, 'special_defense': 0.9},
    'timid': {'speed': 1.1, 'attack': 0.9},
    'hasty': {'speed': 1.1, 'defense': 0.9},
    'jolly': {'speed': 1.1, 'special_attack': 0.9},
    'naive': {'speed': 1.1, 'special_defense': 0.9},
    'modest': {'special_attack': 1.1, 'attack': 0.9},
    'mild': {'special_attack': 1.1, 'defense': 0.9},
    'quiet': {'special_attack': 1.1, 'speed': 0.9},
    'bashful': {},  # Neutral
    'rash': {'special_attack': 1.1, 'special_defense': 0.9},
    'calm': {'special_defense': 1.1, 'attack': 0.9},
    'gentle': {'special_defense': 1.1, 'defense': 0.9},
    'sassy': {'special_defense': 1.1, 'speed': 0.9},
    'careful': {'special_defense': 1.1, 'special_attack': 0.9},
    'quirky': {},  # Neutral
}


class PokemonDataManager:
    """
    Manages Pokemon data from APIs and generates battle-ready stats.
    
    Features:
    - API integration with caching
    - Balanced IV generation (normal distribution favoring average)
    - Proper stat calculation using Pokemon formulas
    - Nature modifiers
    """
    
    POKEAPI_BASE = "https://pokeapi.co/api/v2/"
    
    def __init__(self, cache_file: str = "pokemon_base_stats_cache.json"):
        self.cache_file = cache_file
        self.base_stats_cache: Dict[str, PokemonBaseStats] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cached base stats from file."""
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                for species, stats_dict in data.items():
                    self.base_stats_cache[species] = PokemonBaseStats(**stats_dict)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    def _save_cache(self) -> None:
        """Save base stats cache to file."""
        try:
            data = {species: stats.to_dict() for species, stats in self.base_stats_cache.items()}
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def get_base_stats(self, species: str) -> Optional[PokemonBaseStats]:
        """
        Get base stats for a Pokemon species.
        First checks cache, then fetches from API if needed.
        """
        species = species.lower()
        
        # Check cache
        if species in self.base_stats_cache:
            return self.base_stats_cache[species]
        
        # Fetch from API
        base_stats = self._fetch_from_pokeapi(species)
        
        if base_stats:
            # Cache it
            self.base_stats_cache[species] = base_stats
            self._save_cache()
            return base_stats
        
        # Fallback to default stats if API fails
        return self._get_fallback_stats(species)
    
    def _fetch_from_pokeapi(self, species: str) -> Optional[PokemonBaseStats]:
        """Fetch Pokemon data from PokeAPI."""
        try:
            response = requests.get(f"{self.POKEAPI_BASE}pokemon/{species}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Extract base stats
                stats_dict = {}
                for stat in data['stats']:
                    stat_name = stat['stat']['name']
                    # Map API names to our names
                    if stat_name == 'hp':
                        stats_dict['hp'] = stat['base_stat']
                    elif stat_name == 'attack':
                        stats_dict['attack'] = stat['base_stat']
                    elif stat_name == 'defense':
                        stats_dict['defense'] = stat['base_stat']
                    elif stat_name == 'special-attack':
                        stats_dict['special_attack'] = stat['base_stat']
                    elif stat_name == 'special-defense':
                        stats_dict['special_defense'] = stat['base_stat']
                    elif stat_name == 'speed':
                        stats_dict['speed'] = stat['base_stat']
                
                # Extract types
                types = [t['type']['name'] for t in data['types']]
                
                return PokemonBaseStats(
                    species=species,
                    types=types,
                    **stats_dict
                )
        except Exception as e:
            print(f"Error fetching Pokemon data for {species}: {e}")
            return None
    
    def _get_fallback_stats(self, species: str) -> PokemonBaseStats:
        """
        Fallback stats for common Pokemon if API fails.
        These are reasonable estimates for common species.
        """
        # Common Pokemon fallback stats
        fallback_data = {
            'pikachu': {'hp': 35, 'attack': 55, 'defense': 40, 'special_attack': 50, 'special_defense': 50, 'speed': 90, 'types': ['electric']},
            'charmander': {'hp': 39, 'attack': 52, 'defense': 43, 'special_attack': 60, 'special_defense': 50, 'speed': 65, 'types': ['fire']},
            'bulbasaur': {'hp': 45, 'attack': 49, 'defense': 49, 'special_attack': 65, 'special_defense': 65, 'speed': 45, 'types': ['grass', 'poison']},
            'squirtle': {'hp': 44, 'attack': 48, 'defense': 65, 'special_attack': 50, 'special_defense': 64, 'speed': 43, 'types': ['water']},
            'eevee': {'hp': 55, 'attack': 55, 'defense': 50, 'special_attack': 45, 'special_defense': 65, 'speed': 55, 'types': ['normal']},
            'magikarp': {'hp': 20, 'attack': 10, 'defense': 55, 'special_attack': 15, 'special_defense': 20, 'speed': 80, 'types': ['water']},
            'dratini': {'hp': 41, 'attack': 64, 'defense': 45, 'special_attack': 50, 'special_defense': 50, 'speed': 50, 'types': ['dragon']},
            'mewtwo': {'hp': 106, 'attack': 110, 'defense': 90, 'special_attack': 154, 'special_defense': 90, 'speed': 130, 'types': ['psychic']},
        }
        
        if species in fallback_data:
            return PokemonBaseStats(species=species, **fallback_data[species])
        
        # Generic fallback for unknown Pokemon
        return PokemonBaseStats(
            species=species,
            hp=50,
            attack=50,
            defense=50,
            special_attack=50,
            special_defense=50,
            speed=50,
            types=['normal']
        )
    
    def generate_ivs(self) -> PokemonIVs:
        """
        Generate Individual Values (IVs) with balanced distribution.
        Uses normal distribution centered at 15 (out of 31) with ±5% variance.
        This makes average stats most common, with rare high/low rolls.
        """
        def generate_single_iv() -> int:
            # Use triangular distribution for balanced randomness
            # Mode is at 15 (middle), range 0-31
            # This naturally creates bell curve favoring average
            value = random.triangular(0, 31, 15)
            return int(round(value))
        
        return PokemonIVs(
            hp=generate_single_iv(),
            attack=generate_single_iv(),
            defense=generate_single_iv(),
            special_attack=generate_single_iv(),
            special_defense=generate_single_iv(),
            speed=generate_single_iv()
        )
    
    def calculate_stat(self, base: int, iv: int, level: int, is_hp: bool = False) -> int:
        """
        Calculate actual stat using Pokemon formula.
        
        Formula:
        HP = floor(((2 * Base + IV) * Level) / 100) + Level + 10
        Other = floor(((2 * Base + IV) * Level) / 100) + 5
        """
        if is_hp:
            return int(((2 * base + iv) * level) / 100) + level + 10
        else:
            return int(((2 * base + iv) * level) / 100) + 5
    
    def apply_nature_modifier(self, stat_value: int, stat_name: str, nature: str) -> int:
        """Apply nature modifier to a stat (10% boost or reduction)."""
        nature_mods = NATURES.get(nature, {})
        modifier = nature_mods.get(stat_name, 1.0)
        return int(stat_value * modifier)
    
    def generate_pokemon_stats(self, species: str, level: int, nature: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate complete Pokemon stats for a caught Pokemon.
        
        Returns dict with:
        - All base stats
        - IVs
        - Calculated actual stats
        - Nature
        - Types
        """
        # Get base stats
        base_stats = self.get_base_stats(species)
        if not base_stats:
            base_stats = self._get_fallback_stats(species)
        
        # Generate IVs
        ivs = self.generate_ivs()
        
        # Choose nature (random if not specified)
        if nature is None:
            nature = random.choice(list(NATURES.keys()))
        
        # Calculate actual stats
        hp = self.calculate_stat(base_stats.hp, ivs.hp, level, is_hp=True)
        attack = self.calculate_stat(base_stats.attack, ivs.attack, level)
        defense = self.calculate_stat(base_stats.defense, ivs.defense, level)
        special_attack = self.calculate_stat(base_stats.special_attack, ivs.special_attack, level)
        special_defense = self.calculate_stat(base_stats.special_defense, ivs.special_defense, level)
        speed = self.calculate_stat(base_stats.speed, ivs.speed, level)
        
        # Apply nature modifiers (except HP)
        attack = self.apply_nature_modifier(attack, 'attack', nature)
        defense = self.apply_nature_modifier(defense, 'defense', nature)
        special_attack = self.apply_nature_modifier(special_attack, 'special_attack', nature)
        special_defense = self.apply_nature_modifier(special_defense, 'special_defense', nature)
        speed = self.apply_nature_modifier(speed, 'speed', nature)
        
        return {
            'species': species,
            'level': level,
            'nature': nature,
            'types': base_stats.types,
            # Actual stats
            'hp': hp,
            'attack': attack,
            'defense': defense,
            'special_attack': special_attack,
            'special_defense': special_defense,
            'speed': speed,
            # IVs (for future breeding/reference)
            'iv_hp': ivs.hp,
            'iv_attack': ivs.attack,
            'iv_defense': ivs.defense,
            'iv_special_attack': ivs.special_attack,
            'iv_special_defense': ivs.special_defense,
            'iv_speed': ivs.speed,
            # Base stats (for reference)
            'base_hp': base_stats.hp,
            'base_attack': base_stats.attack,
            'base_defense': base_stats.defense,
            'base_special_attack': base_stats.special_attack,
            'base_special_defense': base_stats.special_defense,
            'base_speed': base_stats.speed,
        }
    
    def get_stat_quality(self, iv: int) -> str:
        """Get quality description for an IV value."""
        if iv >= 28:
            return "Perfect"
        elif iv >= 24:
            return "Excellent"
        elif iv >= 20:
            return "Great"
        elif iv >= 15:
            return "Good"
        elif iv >= 10:
            return "Average"
        elif iv >= 5:
            return "Below Average"
        else:
            return "Poor"
    
    def calculate_iv_percentage(self, ivs: PokemonIVs) -> float:
        """Calculate overall IV percentage (0-100%)."""
        total = ivs.hp + ivs.attack + ivs.defense + ivs.special_attack + ivs.special_defense + ivs.speed
        max_total = 31 * 6  # Max possible
        return (total / max_total) * 100


# DEPRECATED: Singleton pattern - kept for backwards compatibility only
# Use dependency injection via integration_loader instead
_pokemon_data_manager: Optional[PokemonDataManager] = None


def get_pokemon_data_manager() -> PokemonDataManager:
    """
    DEPRECATED: Get or create the singleton Pokemon data manager.
    
    This function is kept for backwards compatibility only.
    New code should receive PokemonDataManager via dependency injection
    from the integration_loader.
    """
    global _pokemon_data_manager
    if _pokemon_data_manager is None:
        _pokemon_data_manager = PokemonDataManager()
    return _pokemon_data_manager
