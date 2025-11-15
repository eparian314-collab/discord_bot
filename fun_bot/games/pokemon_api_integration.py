"""Local Pokémon base stat and type data.

This module deliberately keeps things simple and offline for now:
instead of calling PokeAPI, it exposes a small set of base stats for
the species used by FunBot. The design in POKEMON_DESIGN.md leaves
room to expand this into real API-backed data and caching later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class PokemonBaseStats:
    species: str
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    types: List[str]


# Minimal base stats for the starter set of species FunBot uses.
# Values are approximations of the mainline games to keep the flavour
# familiar without needing perfect accuracy.
_BASE_STATS: Dict[str, PokemonBaseStats] = {
    "bulbasaur": PokemonBaseStats(
        species="Bulbasaur",
        hp=45,
        attack=49,
        defense=49,
        special_attack=65,
        special_defense=65,
        speed=45,
        types=["grass", "poison"],
    ),
    "ivysaur": PokemonBaseStats(
        species="Ivysaur",
        hp=60,
        attack=62,
        defense=63,
        special_attack=80,
        special_defense=80,
        speed=60,
        types=["grass", "poison"],
    ),
    "venusaur": PokemonBaseStats(
        species="Venusaur",
        hp=80,
        attack=82,
        defense=83,
        special_attack=100,
        special_defense=100,
        speed=80,
        types=["grass", "poison"],
    ),
    "charmander": PokemonBaseStats(
        species="Charmander",
        hp=39,
        attack=52,
        defense=43,
        special_attack=60,
        special_defense=50,
        speed=65,
        types=["fire"],
    ),
    "charmeleon": PokemonBaseStats(
        species="Charmeleon",
        hp=58,
        attack=64,
        defense=58,
        special_attack=80,
        special_defense=65,
        speed=80,
        types=["fire"],
    ),
    "charizard": PokemonBaseStats(
        species="Charizard",
        hp=78,
        attack=84,
        defense=78,
        special_attack=109,
        special_defense=85,
        speed=100,
        types=["fire", "flying"],
    ),
    "squirtle": PokemonBaseStats(
        species="Squirtle",
        hp=44,
        attack=48,
        defense=65,
        special_attack=50,
        special_defense=64,
        speed=43,
        types=["water"],
    ),
    "wartortle": PokemonBaseStats(
        species="Wartortle",
        hp=59,
        attack=63,
        defense=80,
        special_attack=65,
        special_defense=80,
        speed=58,
        types=["water"],
    ),
    "blastoise": PokemonBaseStats(
        species="Blastoise",
        hp=79,
        attack=83,
        defense=100,
        special_attack=85,
        special_defense=105,
        speed=78,
        types=["water"],
    ),
    "pikachu": PokemonBaseStats(
        species="Pikachu",
        hp=35,
        attack=55,
        defense=40,
        special_attack=50,
        special_defense=50,
        speed=90,
        types=["electric"],
    ),
    "raichu": PokemonBaseStats(
        species="Raichu",
        hp=60,
        attack=90,
        defense=55,
        special_attack=90,
        special_defense=80,
        speed=110,
        types=["electric"],
    ),
    "eevee": PokemonBaseStats(
        species="Eevee",
        hp=55,
        attack=55,
        defense=50,
        special_attack=45,
        special_defense=65,
        speed=55,
        types=["normal"],
    ),
    "vaporeon": PokemonBaseStats(
        species="Vaporeon",
        hp=130,
        attack=65,
        defense=60,
        special_attack=110,
        special_defense=95,
        speed=65,
        types=["water"],
    ),
    "jigglypuff": PokemonBaseStats(
        species="Jigglypuff",
        hp=115,
        attack=45,
        defense=20,
        special_attack=45,
        special_defense=25,
        speed=20,
        types=["normal", "fairy"],
    ),
    "snorlax": PokemonBaseStats(
        species="Snorlax",
        hp=160,
        attack=110,
        defense=65,
        special_attack=65,
        special_defense=110,
        speed=30,
        types=["normal"],
    ),
    "gengar": PokemonBaseStats(
        species="Gengar",
        hp=60,
        attack=65,
        defense=60,
        special_attack=130,
        special_defense=75,
        speed=110,
        types=["ghost", "poison"],
    ),
    "dragonite": PokemonBaseStats(
        species="Dragonite",
        hp=91,
        attack=134,
        defense=95,
        special_attack=100,
        special_defense=100,
        speed=80,
        types=["dragon", "flying"],
    ),
    "mewtwo": PokemonBaseStats(
        species="Mewtwo",
        hp=106,
        attack=110,
        defense=90,
        special_attack=154,
        special_defense=90,
        speed=130,
        types=["psychic"],
    ),
}


def get_base_stats(species: str) -> PokemonBaseStats:
    """Return base stats for ``species`` (case-insensitive).

    If the species is unknown, fall back to a generic baseline so that
    the game remains playable even with unexpected names.
    """

    key = species.strip().lower()
    if key in _BASE_STATS:
        return _BASE_STATS[key]

    # Generic fallback roughly in line with early-game Pokémon.
    return PokemonBaseStats(
        species=species,
        hp=50,
        attack=50,
        defense=50,
        special_attack=50,
        special_defense=50,
        speed=50,
        types=["normal"],
    )


__all__ = ["PokemonBaseStats", "get_base_stats"]
