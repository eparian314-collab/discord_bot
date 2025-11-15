from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..core.game_storage_engine import GameStorageEngine
from .pokemon_api_integration import PokemonBaseStats, get_base_stats


POKEMON_NAMESPACE = "pokemon"
POKEMON_PROFILE_KEY = "profile"

# Long-term cap for the Pokémon system. Training and battle rewards
# must respect this value; evolution never reduces level.
MAX_POKEMON_LEVEL = 100

# Basic evolution mapping for the starter species FunBot currently
# supports. Each entry is:
#   species -> (evolved_species, min_level, cookie_cost, stage)
EVOLUTIONS: Dict[str, Tuple[str, int, int, int]] = {
    # 3-stage starters
    "bulbasaur": ("Ivysaur", 15, 5, 1),
    "ivysaur": ("Venusaur", 25, 8, 2),
    "charmander": ("Charmeleon", 15, 5, 1),
    "charmeleon": ("Charizard", 25, 8, 2),
    "squirtle": ("Wartortle", 15, 5, 1),
    "wartortle": ("Blastoise", 25, 8, 2),
    # 2-stage examples
    "pikachu": ("Raichu", 25, 6, 1),
    "eevee": ("Vaporeon", 25, 7, 1),
}


@dataclass(slots=True)
class PokemonStats:
    """High-level per-user Pokémon profile stats."""

    caught: int = 0
    battles: int = 0
    wins: int = 0
    losses: int = 0
    caught_names: List[str] | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PokemonStats":
        return cls(
            caught=int(data.get("caught", 0) or 0),
            battles=int(data.get("battles", 0) or 0),
            wins=int(data.get("wins", 0) or 0),
            losses=int(data.get("losses", 0) or 0),
            caught_names=list(data.get("caught_names", []) or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if payload.get("caught_names") is None:
            payload["caught_names"] = []
        return payload


@dataclass(slots=True)
class PokemonIVs:
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int


@dataclass(slots=True)
class PokemonRecord:
    pokemon_id: int
    user_id: int
    species: str
    nickname: Optional[str]
    level: int
    experience: int
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    iv_hp: int
    iv_attack: int
    iv_defense: int
    iv_special_attack: int
    iv_special_defense: int
    iv_speed: int
    nature: str
    types: List[str]
    caught_date: str
    free_stat_points: int = 0

    def total_ivs(self) -> int:
        return (
            self.iv_hp
            + self.iv_attack
            + self.iv_defense
            + self.iv_special_attack
            + self.iv_special_defense
            + self.iv_speed
        )

    def iv_percentage(self) -> float:
        return (self.total_ivs() / 186.0) * 100.0

    def iv_quality_label(self) -> str:
        pct = self.iv_percentage()
        if pct >= 90.0:
            return "★★★ Perfect"
        if pct >= 75.0:
            return "★★ Excellent"
        if pct >= 50.0:
            return "★ Good"
        return "Average"


class PokemonDataManager:
    """Persisted Pokémon profile stats and per-Pokémon records."""

    def __init__(self, storage: GameStorageEngine) -> None:
        self._storage = storage

    async def update_pokemon_owner(self, pokemon_id: int, new_user_id: int) -> bool:
        """Update the owner of a Pokémon by ID."""

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]
        async with self._storage._lock:  # type: ignore[attr-defined]
            await self._storage._conn.execute(  # type: ignore[attr-defined]
                "UPDATE pokemon SET user_id = ? WHERE pokemon_id = ?",
                (int(new_user_id), int(pokemon_id)),
            )
            await self._storage._conn.commit()  # type: ignore[attr-defined]
        return True

    # ------------------------------------------------------------------
    # Profile-level stats (backwards compatible with existing commands).
    # ------------------------------------------------------------------

    async def get_stats(self, user_id: int) -> PokemonStats:
        raw = await self._storage.get_user_value(
            user_id=user_id,
            namespace=POKEMON_NAMESPACE,
            key=POKEMON_PROFILE_KEY,
            default={
                "caught": 0,
                "battles": 0,
                "wins": 0,
                "losses": 0,
                "caught_names": [],
            },
        )
        try:
            return PokemonStats.from_dict(raw)  # type: ignore[arg-type]
        except Exception:
            return PokemonStats()

    async def _save_profile(self, user_id: int, stats: PokemonStats) -> PokemonStats:
        await self._storage.set_user_value(
            user_id=user_id,
            namespace=POKEMON_NAMESPACE,
            key=POKEMON_PROFILE_KEY,
            value=stats.to_dict(),
        )
        return stats

    async def record_catch(self, user_id: int, pokemon_name: str) -> PokemonStats:
        """Update profile stats for a new catch.

        Per-Pokémon records are handled separately; this method keeps the
        behaviour expected by existing commands.
        """

        stats = await self.get_stats(user_id)
        stats.caught += 1
        if stats.caught_names is None:
            stats.caught_names = []
        stats.caught_names.append(pokemon_name)
        return await self._save_profile(user_id, stats)

    async def record_battle(self, user_id: int, won: bool) -> PokemonStats:
        stats = await self.get_stats(user_id)
        stats.battles += 1
        if won:
            stats.wins += 1
        else:
            stats.losses += 1
        return await self._save_profile(user_id, stats)

    async def reset_profile(self, user_id: int) -> PokemonStats:
        stats = PokemonStats()
        return await self._save_profile(user_id, stats)

    # ------------------------------------------------------------------
    # Daily bot battle limits (simple per-user counter).
    # ------------------------------------------------------------------

    async def get_daily_bot_battles(self, user_id: int) -> Tuple[str, int]:
        """Return (today_yyyymmdd, count) for bot battles."""

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw = await self._storage.get_user_value(
            user_id=user_id,
            namespace=POKEMON_NAMESPACE,
            key="bot_battle_daily",
            default={"date": today, "count": 0},
        )
        try:
            date = str(raw.get("date", today))  # type: ignore[arg-type]
            count = int(raw.get("count", 0))  # type: ignore[arg-type]
        except Exception:
            date, count = today, 0
        if date != today:
            date, count = today, 0
        return date, max(count, 0)

    async def increment_daily_bot_battles(self, user_id: int) -> Tuple[str, int]:
        """Increment the daily bot battle counter and return (date, new_count)."""

        today, count = await self.get_daily_bot_battles(user_id)
        count += 1
        await self._storage.set_user_value(
            user_id=user_id,
            namespace=POKEMON_NAMESPACE,
            key="bot_battle_daily",
            value={"date": today, "count": count},
        )
        return today, count

    # ------------------------------------------------------------------
    # Per-Pokémon collection and stat system (v1).
    # ------------------------------------------------------------------

    async def create_caught_pokemon(self, user_id: int, species: str) -> PokemonRecord:
        """Create a new Pokémon for a catch event with randomised stats.

        - Random starting level (1–10).
        - Random IVs (0–31, triangular distribution).
        - Random nature.
        - Stats calculated from base stats, IVs, level and nature.
        """

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]

        base = get_base_stats(species)
        # --- Mood meter luck factor ---
        from fun_bot.core.relationship_meter import RelationshipMeter
        meter = RelationshipMeter(self._storage)
        mood = await meter.get_meter(user_id)
        # Luck factor: positive mood increases chance for higher level and better IVs
        luck_bonus = max(0, mood)  # Only positive mood helps
        # Level: add up to +luck_bonus (max 10)
        base_level = random.randint(1, 10)
        level = min(base_level + luck_bonus, MAX_POKEMON_LEVEL)
        # IVs: add up to +luck_bonus to each IV (max 31)
        base_ivs = self._generate_ivs()
        ivs = type(base_ivs)(
            hp=min(base_ivs.hp + random.randint(0, luck_bonus), 31),
            attack=min(base_ivs.attack + random.randint(0, luck_bonus), 31),
            defense=min(base_ivs.defense + random.randint(0, luck_bonus), 31),
            special_attack=min(base_ivs.special_attack + random.randint(0, luck_bonus), 31),
            special_defense=min(base_ivs.special_defense + random.randint(0, luck_bonus), 31),
            speed=min(base_ivs.speed + random.randint(0, luck_bonus), 31),
        )
        nature = self._random_nature()
        stats = self._calculate_all_stats(base, ivs, level, nature)

        caught_date = datetime.now(timezone.utc).isoformat()
        types_str = ",".join(base.types)

        async with self._storage._lock:  # type: ignore[attr-defined]
            cursor = await self._storage._conn.execute(  # type: ignore[attr-defined]
                """
                INSERT INTO pokemon (
                    user_id,
                    species,
                    nickname,
                    level,
                    experience,
                    hp,
                    attack,
                    defense,
                    special_attack,
                    special_defense,
                    speed,
                    iv_hp,
                    iv_attack,
                    iv_defense,
                    iv_special_attack,
                    iv_special_defense,
                    iv_speed,
                    nature,
                    types,
                    caught_date
                ) VALUES (
                    ?, ?, NULL, ?, 0,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?,
                    ?
                )
                """,
                (
                    int(user_id),
                    base.species,
                    level,
                    stats["hp"],
                    stats["attack"],
                    stats["defense"],
                    stats["special_attack"],
                    stats["special_defense"],
                    stats["speed"],
                    ivs.hp,
                    ivs.attack,
                    ivs.defense,
                    ivs.special_attack,
                    ivs.special_defense,
                    ivs.speed,
                    nature,
                    types_str,
                    caught_date,
                ),
            )
            await self._storage._conn.commit()  # type: ignore[attr-defined]
            pokemon_id = cursor.lastrowid or 0
            await cursor.close()

        return PokemonRecord(
            pokemon_id=int(pokemon_id),
            user_id=int(user_id),
            species=base.species,
            nickname=None,
            level=level,
            experience=0,
            hp=stats["hp"],
            attack=stats["attack"],
            defense=stats["defense"],
            special_attack=stats["special_attack"],
            special_defense=stats["special_defense"],
            speed=stats["speed"],
            iv_hp=ivs.hp,
            iv_attack=ivs.attack,
            iv_defense=ivs.defense,
            iv_special_attack=ivs.special_attack,
            iv_special_defense=ivs.special_defense,
            iv_speed=ivs.speed,
            nature=nature,
            types=base.types,
            caught_date=caught_date,
            free_stat_points=0,
        )

    async def list_pokemon(self, user_id: int) -> List[PokemonRecord]:
        """Return all Pokémon owned by ``user_id``."""

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]

        async with self._storage._lock:  # type: ignore[attr-defined]
            cursor = await self._storage._conn.execute(  # type: ignore[attr-defined]
                """
                SELECT
                    pokemon_id,
                    user_id,
                    species,
                    nickname,
                    level,
                    experience,
                    hp,
                    attack,
                    defense,
                    special_attack,
                    special_defense,
                    speed,
                    iv_hp,
                    iv_attack,
                    iv_defense,
                    iv_special_attack,
                    iv_special_defense,
                    iv_speed,
                    nature,
                    types,
                    caught_date,
                    free_stat_points
                FROM pokemon
                WHERE user_id = ?
                ORDER BY pokemon_id ASC
                """,
                (int(user_id),),
            )
            rows = await cursor.fetchall()
            await cursor.close()

        records: List[PokemonRecord] = []
        for row in rows:
            types = str(row[20] or "").split(",") if row[20] else []
            records.append(
                PokemonRecord(
                    pokemon_id=int(row[0]),
                    user_id=int(row[1]),
                    species=str(row[2]),
                    nickname=row[3],
                    level=int(row[4]),
                    experience=int(row[5]),
                    hp=int(row[6]),
                    attack=int(row[7]),
                    defense=int(row[8]),
                    special_attack=int(row[9]),
                    special_defense=int(row[10]),
                    speed=int(row[11]),
                    iv_hp=int(row[12]),
                    iv_attack=int(row[13]),
                    iv_defense=int(row[14]),
                    iv_special_attack=int(row[15]),
                    iv_special_defense=int(row[16]),
                    iv_speed=int(row[17]),
                    nature=str(row[18]),
                    types=[t for t in types if t],
                    caught_date=str(row[21]),
                    free_stat_points=int(row[22]) if len(row) > 22 else 0,
                )
            )
        return records

    async def get_pokemon(
        self, user_id: int, pokemon_id: int
    ) -> Optional[PokemonRecord]:
        """Fetch a single Pokémon owned by a user."""

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]

        async with self._storage._lock:  # type: ignore[attr-defined]
            cursor = await self._storage._conn.execute(  # type: ignore[attr-defined]
                """
                SELECT
                    pokemon_id,
                    user_id,
                    species,
                    nickname,
                    level,
                    experience,
                    hp,
                    attack,
                    defense,
                    special_attack,
                    special_defense,
                    speed,
                    iv_hp,
                    iv_attack,
                    iv_defense,
                    iv_special_attack,
                    iv_special_defense,
                    iv_speed,
                    nature,
                    types,
                    caught_date,
                    free_stat_points
                FROM pokemon
                WHERE user_id = ? AND pokemon_id = ?
                """,
                (int(user_id), int(pokemon_id)),
            )
            row = await cursor.fetchone()
            await cursor.close()

        if row is None:
            return None

        types = str(row[20] or "").split(",") if row[20] else []
        return PokemonRecord(
            pokemon_id=int(row[0]),
            user_id=int(row[1]),
            species=str(row[2]),
            nickname=row[3],
            level=int(row[4]),
            experience=int(row[5]),
            hp=int(row[6]),
            attack=int(row[7]),
            defense=int(row[8]),
            special_attack=int(row[9]),
            special_defense=int(row[10]),
            speed=int(row[11]),
            iv_hp=int(row[12]),
            iv_attack=int(row[13]),
            iv_defense=int(row[14]),
            iv_special_attack=int(row[15]),
            iv_special_defense=int(row[16]),
            iv_speed=int(row[17]),
            nature=str(row[18]),
            types=[t for t in types if t],
            caught_date=str(row[21]),
            free_stat_points=int(row[22]) if len(row) > 22 else 0,
        )

    async def train_pokemon(
        self,
        user_id: int,
        pokemon_id: int,
        xp_gain: int,
    ) -> Optional[Tuple[PokemonRecord, int, int]]:
        """Apply training XP to a Pokémon and recalculate stats on level up.

        Returns ``(updated_record, old_level, new_level)`` or ``None`` if
        the Pokémon does not exist or is owned by another user.
        """

        record = await self.get_pokemon(user_id, pokemon_id)
        if record is None:
            return None

        old_level = record.level
        old_xp = record.experience
        new_level, new_xp = self._apply_experience(
            level=record.level,
            experience=record.experience,
            xp_gain=xp_gain,
        )

        # If nothing changed (including at max level), avoid extra writes.
        if new_level == old_level and new_xp == old_xp:
            return record, old_level, new_level

        base = get_base_stats(record.species)
        ivs = PokemonIVs(
            hp=record.iv_hp,
            attack=record.iv_attack,
            defense=record.iv_defense,
            special_attack=record.iv_special_attack,
            special_defense=record.iv_special_defense,
            speed=record.iv_speed,
        )
        stats = self._calculate_all_stats(base, ivs, new_level, record.nature)

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]

        async with self._storage._lock:  # type: ignore[attr-defined]
            await self._storage._conn.execute(  # type: ignore[attr-defined]
                """
                UPDATE pokemon
                SET
                    level = ?,
                    experience = ?,
                    hp = ?,
                    attack = ?,
                    defense = ?,
                    special_attack = ?,
                    special_defense = ?,
                    speed = ?
                WHERE pokemon_id = ? AND user_id = ?
                """,
                (
                    new_level,
                    new_xp,
                    stats["hp"],
                    stats["attack"],
                    stats["defense"],
                    stats["special_attack"],
                    stats["special_defense"],
                    stats["speed"],
                    pokemon_id,
                    user_id,
                ),
            )
            await self._storage._conn.commit()  # type: ignore[attr-defined]

        # Re-read the updated record so callers see current values.
        updated = await self.get_pokemon(user_id, pokemon_id)
        assert updated is not None
        return updated, old_level, updated.level

    async def add_free_stat_points(
        self,
        user_id: int,
        pokemon_id: int,
        amount: int,
    ) -> Optional[PokemonRecord]:
        """Increment free stat points for a Pokémon."""

        record = await self.get_pokemon(user_id, pokemon_id)
        if record is None:
            return None

        delta = max(int(amount), 0)
        if delta == 0:
            return record

        new_points = record.free_stat_points + delta

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]
        async with self._storage._lock:  # type: ignore[attr-defined]
            await self._storage._conn.execute(  # type: ignore[attr-defined]
                "UPDATE pokemon SET free_stat_points = ? WHERE pokemon_id = ? AND user_id = ?",
                (new_points, pokemon_id, user_id),
            )
            await self._storage._conn.commit()  # type: ignore[attr-defined]

        updated = await self.get_pokemon(user_id, pokemon_id)
        return updated

    async def boost_stat_with_point(
        self,
        user_id: int,
        pokemon_id: int,
        stat_name: str,
    ) -> Optional[PokemonRecord]:
        """Spend one free stat point to boost a specific stat by 1."""

        record = await self.get_pokemon(user_id, pokemon_id)
        if record is None or record.free_stat_points <= 0:
            return None

        field_map = {
            "hp": "hp",
            "attack": "attack",
            "defense": "defense",
            "special_attack": "special_attack",
            "special_defense": "special_defense",
            "speed": "speed",
        }
        field = field_map.get(stat_name.lower())
        if field is None:
            return None

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]

        async with self._storage._lock:  # type: ignore[attr-defined]
            await self._storage._conn.execute(  # type: ignore[attr-defined]
                f"""
                UPDATE pokemon
                SET {field} = {field} + 1,
                    free_stat_points = free_stat_points - 1
                WHERE pokemon_id = ? AND user_id = ? AND free_stat_points > 0
                """,
                (pokemon_id, user_id),
            )
            await self._storage._conn.commit()  # type: ignore[attr-defined]

        updated = await self.get_pokemon(user_id, pokemon_id)
        return updated

    def get_evolution_info(
        self,
        species: str,
    ) -> Optional[Tuple[str, int, int, int]]:
        """Return evolution info for a species, if any.

        Returns ``(evolved_species, min_level, cookie_cost, stage)``.
        """

        key = species.strip().lower()
        return EVOLUTIONS.get(key)

    async def evolve_pokemon(
        self,
        user_id: int,
        pokemon_id: int,
        duplicate_id: int,
        evolved_species: str,
    ) -> Optional[PokemonRecord]:
        """Perform an evolution in the database.

        - Keeps level and XP exactly the same (no level loss).
        - Keeps IVs, nature and nickname.
        - Recalculates stats using the evolved species' base stats.
        - Deletes the duplicate Pokémon row.
        """

        if pokemon_id == duplicate_id:
            return None

        main = await self.get_pokemon(user_id, pokemon_id)
        duplicate = await self.get_pokemon(user_id, duplicate_id)
        if main is None or duplicate is None:
            return None

        if main.user_id != user_id or duplicate.user_id != user_id:
            return None

        if duplicate.species.lower() != main.species.lower():
            return None

        base = get_base_stats(evolved_species)
        level = main.level  # no level loss
        ivs = PokemonIVs(
            hp=main.iv_hp,
            attack=main.iv_attack,
            defense=main.iv_defense,
            special_attack=main.iv_special_attack,
            special_defense=main.iv_special_defense,
            speed=main.iv_speed,
        )
        stats = self._calculate_all_stats(base, ivs, level, main.nature)
        types_str = ",".join(base.types)

        await self._storage.initialize()
        assert self._storage._conn is not None  # type: ignore[attr-defined]

        async with self._storage._lock:  # type: ignore[attr-defined]
            # Update main Pokémon to the evolved form.
            await self._storage._conn.execute(  # type: ignore[attr-defined]
                """
                UPDATE pokemon
                SET
                    species = ?,
                    hp = ?,
                    attack = ?,
                    defense = ?,
                    special_attack = ?,
                    special_defense = ?,
                    speed = ?,
                    types = ?
                WHERE pokemon_id = ? AND user_id = ?
                """,
                (
                    base.species,
                    stats["hp"],
                    stats["attack"],
                    stats["defense"],
                    stats["special_attack"],
                    stats["special_defense"],
                    stats["speed"],
                    types_str,
                    pokemon_id,
                    user_id,
                ),
            )

            # Delete the duplicate used as evolution fuel.
            await self._storage._conn.execute(  # type: ignore[attr-defined]
                "DELETE FROM pokemon WHERE pokemon_id = ? AND user_id = ?",
                (duplicate_id, user_id),
            )

            await self._storage._conn.commit()  # type: ignore[attr-defined]

        updated = await self.get_pokemon(user_id, pokemon_id)
        return updated

    # ------------------------------------------------------------------
    # Internal stat helpers
    # ------------------------------------------------------------------

    def _generate_ivs(self) -> PokemonIVs:
        """Generate a set of IVs biased toward the middle of the range."""

        def roll() -> int:
            return int(random.triangular(0, 31, 15))

        return PokemonIVs(
            hp=roll(),
            attack=roll(),
            defense=roll(),
            special_attack=roll(),
            special_defense=roll(),
            speed=roll(),
        )

    def _calculate_all_stats(
        self,
        base: PokemonBaseStats,
        ivs: PokemonIVs,
        level: int,
        nature: str,
    ) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        stats["hp"] = self._calculate_stat(base.hp, ivs.hp, level, is_hp=True)
        stats["attack"] = self._apply_nature(
            self._calculate_stat(base.attack, ivs.attack, level, is_hp=False),
            nature,
            "attack",
        )
        stats["defense"] = self._apply_nature(
            self._calculate_stat(base.defense, ivs.defense, level, is_hp=False),
            nature,
            "defense",
        )
        stats["special_attack"] = self._apply_nature(
            self._calculate_stat(
                base.special_attack, ivs.special_attack, level, is_hp=False
            ),
            nature,
            "special_attack",
        )
        stats["special_defense"] = self._apply_nature(
            self._calculate_stat(
                base.special_defense, ivs.special_defense, level, is_hp=False
            ),
            nature,
            "special_defense",
        )
        stats["speed"] = self._apply_nature(
            self._calculate_stat(base.speed, ivs.speed, level, is_hp=False),
            nature,
            "speed",
        )
        return stats

    @staticmethod
    def _calculate_stat(base: int, iv: int, level: int, *, is_hp: bool) -> int:
        level = max(1, min(int(level), MAX_POKEMON_LEVEL))
        base = max(1, int(base))
        iv = max(0, min(int(iv), 31))
        if is_hp:
            # HP formula
            return int(((2 * base + iv) * level) / 100) + level + 10
        # Other stats
        return int(((2 * base + iv) * level) / 100) + 5

    @staticmethod
    def _apply_experience(
        level: int,
        experience: int,
        xp_gain: int,
    ) -> Tuple[int, int]:
        """Apply XP gain, respecting MAX_POKEMON_LEVEL.

        Uses a simple 100 XP per level curve and clears XP at max level.
        """

        level = max(1, min(int(level), MAX_POKEMON_LEVEL))
        experience = max(0, int(experience))
        xp_gain = max(0, int(xp_gain))

        while xp_gain > 0 and level < MAX_POKEMON_LEVEL:
            needed = 100 - experience
            if xp_gain >= needed:
                xp_gain -= needed
                level += 1
                experience = 0
            else:
                experience += xp_gain
                xp_gain = 0

        if level >= MAX_POKEMON_LEVEL:
            level = MAX_POKEMON_LEVEL
            experience = 0

        return level, experience

    def _apply_nature(self, value: int, nature: str, stat_name: str) -> int:
        inc, dec = self._nature_modifiers().get(nature.lower(), (None, None))
        if stat_name == "hp":
            return value
        if inc == stat_name:
            return int(value * 1.1)
        if dec == stat_name:
            return int(value * 0.9)
        return value

    def _random_nature(self) -> str:
        names = list(self._nature_modifiers().keys())
        return random.choice(names)

    @staticmethod
    def _nature_modifiers() -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Return mapping of nature -> (increased_stat, decreased_stat)."""

        return {
            # Neutral natures (no modifiers)
            "hardy": (None, None),
            "docile": (None, None),
            "bashful": (None, None),
            "quirky": (None, None),
            "serious": (None, None),
            # Attack up
            "lonely": ("attack", "defense"),
            "adamant": ("attack", "special_attack"),
            "naughty": ("attack", "special_defense"),
            "brave": ("attack", "speed"),
            # Defense up
            "bold": ("defense", "attack"),
            "impish": ("defense", "special_attack"),
            "lax": ("defense", "special_defense"),
            "relaxed": ("defense", "speed"),
            # Sp. Atk up
            "modest": ("special_attack", "attack"),
            "mild": ("special_attack", "defense"),
            "rash": ("special_attack", "special_defense"),
            "quiet": ("special_attack", "speed"),
            # Sp. Def up
            "calm": ("special_defense", "attack"),
            "gentle": ("special_defense", "defense"),
            "careful": ("special_defense", "special_attack"),
            "sassy": ("special_defense", "speed"),
            # Speed up
            "timid": ("speed", "attack"),
            "hasty": ("speed", "defense"),
            "jolly": ("speed", "special_attack"),
            "naive": ("speed", "special_defense"),
        }


__all__ = [
    "PokemonStats",
    "PokemonIVs",
    "PokemonRecord",
    "PokemonDataManager",
    "MAX_POKEMON_LEVEL",
]
