# FunBot Pokémon Game Design

This document captures the design for FunBot's Pokémon systems and how
they relate to the current implementation. It is intentionally more
ambitious than the code that exists today so you can grow into it over
time.

---

## Relationship Meter & Cookie System (v1)

FunBot now includes a persistent relationship meter (mood index) for each user:

- The meter increases with positive interactions (winning games, answering trivia, etc.) and decreases with negative actions (spamming, losing games).
- The meter auto-forgives over time, trending toward neutral.
- Cookie rewards are given for playing games and interacting with FunBot. Cookies are used for Pokémon evolution and other game actions.
- The relationship meter directly affects Pokémon drop luck: higher meter increases the chance for better level and IVs when catching Pokémon.
- All mood and cookie data is stored in the database and is invisible to users (background only).

### Easter Egg Games

FunBot now offers several fun game commands that reward cookies and affect the relationship meter:
- `/rps` — Rock-paper-scissors
- `/trivia` — Trivia questions
- `/weather` — Randomized weather report
- `/magic8` — Magic 8 ball
- `/ping` and `/vibe` — Classic easter egg commands

These games are designed to encourage interaction and reward users with cookies and improved Pokémon drop luck.

---

## 1. Current Implementation (v0)

Right now FunBot ships a lightweight Pokémon experience:

- `/pokemon catch`  
  - Picks a random Pokémon name from a small pool.  
  - Records that name and increments your overall Pokémon stats.
- `/pokemon stats`  
  - Shows how many Pokémon you’ve caught, battle counts, and a history
    of caught names.
- Battles (`/battle …`)  
  - Use a simple HP‑based duel system defined in `fun_bot/games/battle_system.py`
    (no species, types, or IVs yet).

All Pokémon data is stored through `GameStorageEngine` as JSON in
`fun_bot/data/funbot.sqlite3`. There is **no per‑Pokémon row** yet:
the current system tracks profile‑level stats only.

The sections below describe the **planned** evolution, stat and battle
systems for a richer Pokémon game (v1+).

---

## 2. Stat System (planned)

Target: a full per‑Pokémon stat model with IVs, natures and proper
stat formulas, ready for a richer battle engine.

### 2.1 Level Cap

- `MAX_POKEMON_LEVEL = 100`
- Pokémon cannot exceed level 100.  
- XP gain stops at max level; XP is cleared when clamping to 100.

On evolution:

- Level and XP are **never reduced**. Evolving preserves the exact
  current level and XP; Pokémon never “level down” when evolving.

### 2.2 Per‑Pokémon Records

Instead of only profile JSON, each Pokémon owned by a user will be
stored with its own ID and stats (schema expressed conceptually here):

```sql
pokemon_id INTEGER PRIMARY KEY,
user_id INTEGER NOT NULL,
species TEXT NOT NULL,
nickname TEXT,
level INTEGER DEFAULT 1,
experience INTEGER DEFAULT 0,

-- Actual stats (recalculated on level up / evolution)
hp INTEGER,
attack INTEGER,
defense INTEGER,
special_attack INTEGER,
special_defense INTEGER,
speed INTEGER,

-- Individual values (fixed per Pokémon, 0–31)
iv_hp INTEGER,
iv_attack INTEGER,
iv_defense INTEGER,
iv_special_attack INTEGER,
iv_special_defense INTEGER,
iv_speed INTEGER,

nature TEXT,
types TEXT,
caught_date TEXT
```

In this repo, that storage will be layered on top of `GameStorageEngine`
using either a dedicated table or a per‑user Pokémon collection stored
as JSON.

### 2.3 IVs and Natures

**Individual Values (IVs):**

- Range: 0–31 per stat (HP / Atk / Def / SpA / SpD / Spe).
- Generation: triangular distribution to bias toward the middle:

  ```python
  int(random.triangular(0, 31, 15))
  ```

- Total IV range: 0–186; “perfect” 186/186 Pokémon are very rare.

**Nature system:**

- 25 natures, matching the mainline games.
- Neutral natures: Hardy, Docile, Bashful, Quirky, Serious.
- Others apply ±10% to a pair of stats (e.g. Adamant: +Atk, ‑SpA).
- HP is never modified by nature.

### 2.4 Stat Formulas

Using the standard Pokémon formulas:

```python
# HP
hp = floor(((2 * base_hp + iv_hp) * level) / 100) + level + 10

# Other stats
stat = floor(((2 * base_stat + iv_stat) * level) / 100) + 5
stat = apply_nature_modifier(stat, nature, stat_name)
```

Base stats and types come from a local cache (and optionally PokeAPI)
described below.

### 2.5 Base Stat Data / API

Planned behaviour:

- Fetch base stats and types from `https://pokeapi.co/api/v2/pokemon/{species}`.
- Cache responses in a JSON file next to the game code (e.g.
  `pokemon_base_stats_cache.json`).
- Use built‑in fallback stats for common species if the API is slow or
  unreachable (Pikachu, Eevee, starters, a few favourites).

Key helper concepts:

- `PokemonBaseStats` dataclass with species, 6 base stats, and types.
- `generate_ivs()`, `calculate_stat()`, `apply_nature_modifier()`.

### 2.6 Capture and Training Flow

When a Pokémon is **caught**:
- The user's relationship meter (mood) is checked in the background.
- Higher meter increases the chance for a higher starting level and better IVs.
- Level, IVs, and nature are generated, base stats are fetched, and stats are calculated.
- A full Pokémon record is persisted, returning its `pokemon_id`.

When a Pokémon is **trained**:

- Add XP, respecting `MAX_POKEMON_LEVEL = 100`.
- If the level increases, recalculate all 6 stats using:
  - same IVs
  - same nature
  - same species
  - new level

On **evolution**:

- Keep level and XP exactly the same (no level loss).
- Keep IVs and nature exactly the same.
- Swap in new base stats and types for the evolved species.
- Recalculate stats using the same formulas.

---

## 3. Evolution System (planned)

Target: a level‑ and cookie‑gated evolution system that uses duplicates
and respects official chains while staying simple in UX.

### 3.1 Core Rules

- Level cap: 100.
- 3‑stage chains:
  - Stage 1 → Stage 2 at level 15.
  - Stage 2 → Stage 3 at level 25.
- 2‑stage chains:
  - Stage 1 → Final at level 25.
- Special evolutions:
  - Level requirement 40 (can be raised later if desired).

Additional requirements:

- Pokémon must meet the minimum level.
- Player must own a **duplicate** of the same species to consume.
- Player must pay a cookie cost based on evolution tier.
- Pokémon game must be “unlocked” for the user.

### 3.2 Evolution Costs (cookies)

Indicative cookie ranges:

- 3‑stage chains:
  - Stage 1 → 2: 2–6 cookies.
  - Stage 2 → 3: 4–10 cookies.
- 2‑stage chains:
  - Stage 1 → Final: 4–8 cookies.
- Special (level 40+):
  - Stage 1 → Final: 8–10 cookies.

Exact numbers are defined in an `EVOLUTIONS` mapping.

### 3.3 Evolution Mapping

Conceptual structure:

```python
EVOLUTIONS = {
    "charmander": ("charmeleon", 15, 5, 1),
    "charmeleon": ("charizard", 25, 8, 2),
    # species: (evolved_form, min_level, cookie_cost, stage)
}
```

### 3.4 Evolution API (planned)

- `can_evolve(user_id, pokemon_id)`  
  Returns `(can_evolve, evolution_name, cookie_cost, reason)` after
  checking:
  - species is evolvable
  - level requirement
  - cookie balance
  - duplicate availability

- `evolve_pokemon(user_id, pokemon_id, duplicate_id)`  
  Performs the evolution, consuming cookies and the duplicate, and
  returns `(success, evolved_pokemon_data, error_message)`.

On success:

- Old Pokémon entry is replaced with the evolved species.
- Duplicate entry is removed.
- Level and XP unchanged.
- IVs, nature, nickname, and owner ID are preserved.
- Stats and types are recalculated.

### 3.5 UX and IDs

Pokémon are selected by numeric ID:

- `/collection` lists your Pokémon, showing:
  - `pokemon_id`
  - species, level, IV quality, evolution status.
- `/evolve pokemon_id:<id> duplicate_id:<id>` uses those IDs.

Future convenience:

- Optional shortcut like `/evolve species:<name>` which auto‑selects the
  “best IV” main Pokémon and a duplicate to consume.

---

## 4. Battle System (current + future)

### 4.1 Current Battles

The existing `BattleCog` and `games/battle_system.py` implement a
simple HP‑only duel:

- Each player has a flat `MAX_HP` pool (100 HP).
- A small set of moves (strike, heavy_strike, heal).
- No Pokémon species, types, IVs, natures, or level scaling yet.

This is intentionally light so the rest of the bot stays fast and
low‑maintenance.

### 4.2 Target Battle Design

The long‑term design is a more authentic Pokémon battle system:

- Single‑Pokémon, turn‑based battles to start (1v1).
- Speed stat determines who moves first; ties broken randomly.
- Official‑style damage formula:

  ```python
  level_factor = (2 * attacker_level / 5) + 2
  damage = (level_factor * move_power * attack_stat) / defense_stat
  damage = (damage / 50) + 2
  damage *= type_effectiveness_multiplier
  if move.type in attacker.types:
      damage *= 1.5  # STAB
  if critical_hit:
      damage *= 1.5
  damage *= random.uniform(0.85, 1.0)
  damage = max(1, int(damage))
  ```

- Type effectiveness:
  - 18‑type chart, including dual‑type stacking.
  - Super‑effective (2×), not very effective (0.5×), immune (0×).
- Physical vs. special moves:
  - Physical: Attack vs Defense.
  - Special: Sp.Atk vs. Sp.Def.
- Accuracy and critical hits:
  - Each move has an accuracy rating.
  - ~6.25% crit rate (1/16) for baseline.

### 4.3 Battle Commands (planned)

Examples of the planned UX:

- `/battle @user` – challenge another user; cost cookies; auto‑select
  each player’s best Pokémon.
- `/battle_move <slot>` – choose one of 4 moves during your turn.
- `/battle_status` – view HP bars, current turn, and move details.
- `/battle_forfeit` – concede the match.

Rewards:

- XP and cookie rewards for the winner based on level differences.
- No penalties beyond losing the battle.

---

## 5. Collection & IV Display (planned)

To make the system intuitive and satisfying:

- `/collection` will:
  - List each Pokémon with ID, species, level, nature, and IV quality.
  - Compute an IV percentage:

    ```python
    total_ivs = (
        iv_hp + iv_attack + iv_defense +
        iv_special_attack + iv_special_defense + iv_speed
    )
    iv_percentage = (total_ivs / 186) * 100
    ```

  - Map to a simple rating:
    - ≥ 90%: `★★★ Perfect`
    - ≥ 75%: `★★ Excellent`
    - ≥ 50%: `★ Good`
    - else: `Average`

This makes it easy to see which Pokémon to evolve or bring into battle.

---

## 6. Roadmap Summary

Implemented today:

- `/pokemon catch` now creates a full per‑Pokémon record with:
  - random level (1–10), IVs, and nature
  - stats calculated from local base stats + IVs + nature
  - a unique numeric ID for each Pokémon
- `/pokemon stats` still shows high‑level profile stats.
- `/pokemon collection` lists your caught Pokémon with IDs, levels and IV quality.
- `/pokemon train` applies XP to a specific Pokémon ID using a simple 100‑XP‑per‑level curve, up to level 100,
  and recalculates stats when levels increase.
- `/pokemon evolve` supports a small set of starter evolutions (Bulbasaur/Charmander/Squirtle/Pikachu/Eevee lines)
  using duplicate consumption and cookie costs, while preserving level and XP.
- `/pokemon bot_battle` lets you battle FunBot up to twice per day with one of your Pokémon; battles grant XP and
  have a small chance to award a free stat point for that Pokémon.
- `/pokemon boost_stat` spends free stat points to permanently increase a chosen stat by 1 (HP, Attack, Defense,
  Special Attack, Special Defense, or Speed).
- Lightweight HP‑based battles still exist and are unchanged.

Planned next steps:

- Expand evolution chains beyond the starter examples.
- Integrate battle rewards with the XP system.
- Richer battles that use species, types and stats.

This document is the source of truth for how the Pokémon system should
feel as it grows. The code in `fun_bot/games` and `fun_bot/cogs` will
incrementally move further toward this design.

**Latest additions:**
- Relationship meter and cookie system are now fully integrated.
- Pokémon drop luck is affected by user mood.
- New easter egg games reward cookies and affect mood.

---

## 7. Trading System

Users can now trade Pokémon directly with each other using the `/pokemon trade` command:

- To initiate a trade, a user uses `/pokemon trade @otheruser pokemon_id:<id>` to request a trade with another user, specifying the Pokémon ID they wish to offer.
- The other user receives a trade request and can respond with their own offer (selecting a Pokémon ID from their collection).
- The original user is shown both offers in an embedded selection screen and has the final decision to approve or decline the trade.
- All trade interactions are handled via Discord embedded messages and selection screens for clarity and security.
- When approved, the Pokémon are swapped between users, preserving all stats, level, IVs, and natures.
- Trades are logged and may be subject to cooldowns or limits to prevent abuse.
- This system encourages community interaction and collection building.

This feature is now implemented and available for users to trade Pokémon with each other.
