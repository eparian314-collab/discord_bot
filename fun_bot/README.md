

# FunBot

FunBot is a fully self-contained Discord bot project, located in the `fun_bot` folder of the shared `discord_bot` monorepo. It is one of three independent bots (alongside LanguageBot and an upcoming third bot), each designed for separate deployment and operation.

## Project Philosophy

- **Self-contained:** FunBot does not rely on any code, configuration, or resources outside the `fun_bot` directory. Treat this folder as the root and single source of truth for all FunBot logic, dependencies, and assets.
- **Monorepo Structure:** While FunBot shares the repository with other bots, it is architected for independent deployment and development. Similar principles apply to the other bot projects in this repo.
- **Focus:** FunBot specializes in game commands, fun interactions, easter eggs, and entertainment utilities for Discord servers. It includes moderation support (admin/help) but is primarily designed for engaging, playful experiences.


## Features & Commands

FunBot offers a growing set of game and utility commands, organized into modular cogs:

- **Games & Fun:**
	- `/pokemon catch` — Spend 1 cookie to catch a random Pokémon, with unique stats and an ID in your collection. Drop luck (level/IVs) is affected by your relationship meter (mood).
	- `/pokemon explore` — Spend 3 cookies to explore for a chance at rarer Pokémon (higher chance for favourites like Snorlax, Gengar, Dragonite, Mewtwo).
	- `/pokemon fish` — Spend 1 cookie to go fishing and catch a water-type Pokémon (Squirtle line, Vaporeon, etc.).
	- `/pokemon stats` — View your high-level Pokémon stats.
	- `/pokemon collection` — View detailed info (IDs, levels, IV quality) for caught Pokémon.
	- `/pokemon train` — Train a specific Pokémon by ID to gain XP and levels (up to level 100).
	- `/pokemon evolve` — Evolve a Pokémon using a duplicate and cookies, without losing levels.
	- `/pokemon bot_battle` — Battle FunBot with one of your Pokémon (up to 2 times per day), granting XP and a small chance at free stat points.
	- `/pokemon boost_stat` — Spend free stat points on a specific stat (HP/Atk/Def/Sp.Atk/Sp.Def/Speed).
	- `/pokemon trade` — Trade Pokémon directly with another user, with a confirmation step and clear trade summary so both sides understand what is being swapped.
	- `/roll` — Roll a dice (1–6).
	- **Easter Egg Games:**
		- `/rps` — Play rock-paper-scissors with FunBot. Win cookies and affect your relationship meter.
		- `/trivia` — Answer a random trivia question for cookies and mood boosts.
		- `/weather` — Get a randomized weather report and earn cookies.
		- `/magic8` — Ask the magic 8 ball for a fun answer and cookies.
		- `/ping` and `/vibe` — Classic easter egg commands.

- **Cookies & Admin:**
	- `/cookies balance` — Check how many helper cookies you have.
	- `/admin give` — Admin-only: grant helper cookies to community members.

- **Help & Utility:**
	- `/help` — Interactive help and feature overview.
	- Automated welcome messages and onboarding.
	- Personality-driven responses and easter eggs.


## Methods & Architecture

- Modular cog system for easy extension and maintenance.
- Event-driven architecture using Discord.py's commands and app_commands.
- Role-based permissions for admin and helper features.
- Personality engine for dynamic, friendly bot responses.
- SQLite-backed storage for persistent user/game data (cookies, Pokémon, relationship meter, and future features).

### Relationship Meter & Cookie System

- Every user has a persistent relationship meter (mood index) that changes based on interactions with FunBot.
- Positive actions (winning games, answering trivia, etc.) increase your meter; negative actions (spamming, losing games) decrease it.
- The meter auto-forgives over time, trending toward neutral.
- Cookie rewards are given for playing games and interacting with FunBot. Cookies are used for Pokémon evolution and other game actions.
- Your relationship meter directly affects your luck when catching Pokémon (higher meter = better drop chances for level/IVs).
- All mood and cookie data is stored in the database and is invisible to users (background only).

### Pokémon game systems

- `/pokemon catch` and `/pokemon stats` track profile-level stats and a history of caught names.
- Battles use a simple HP-based duel system (no species, types, or IVs yet).
- The current implementation now includes:
	- Full per-Pokémon stat system (IVs, natures, proper formulas) with a level cap of 100.
	- An evolution system that uses levels, cookies, and duplicates while never lowering a Pokémon’s level on evolve.
	- Richer, type-aware battles that use real Pokémon stats and types.
	- Luck factor for Pokémon drops based on relationship meter.

For details of that design and how the current implementation will grow toward it, see:

- `fun_bot/POKEMON_DESIGN.md`

## Configuration

FunBot is configured via a `.env` file in the `fun_bot` directory. Start by copying the example:

```bash
cd fun_bot
cp .env.example .env
```

Required keys:

- `DISCORD_TOKEN` — your Discord bot token.
- `BOT_CHANNEL_ID` — one or more channel IDs (comma‑separated) where FunBot is allowed to run game/coin commands.

Optional keys:

- `BOT_PREFIX` — legacy text prefix for commands (default: `!`).
- `OWNER_IDS` — comma‑separated Discord user IDs with owner permissions.
- `OPENAI_API_KEY`, `OPENAI_PERSONALITY_MODEL` — used only if features require OpenAI.
- `TEST_GUILDS` — comma‑separated guild IDs for scoped slash‑command sync during testing.
- `FUNBOT_DB_PATH` — SQLite DB path (default: `data/funbot.sqlite3` under `fun_bot`).

FunBot loads environment variables from `.env` using `python-dotenv`. If `DISCORD_TOKEN` is missing, startup will fail with a clear error. The entry point sets `BOT_PROFILE=fun` so only fun/game features are enabled.

## Running FunBot (local dev)

Quickstart for local development:

```bash
cd fun_bot

# Create and activate a per-bot virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install FunBot dependencies
pip install -r requirements.txt

# Ensure .env is configured (DISCORD_TOKEN, BOT_CHANNEL_ID, etc.)

# Start the bot
python main.py
```

You can also run it as a module from the repo root:

```bash
python -m fun_bot.main
```

Behind the scenes, `main.py` calls `fun_bot.runner.run_fun_bot()`, which:

- Loads `.env` and builds `FunBotConfig`.
- Sets up the error engine and shared storage (`GameStorageEngine`).
- Instantiates services (`CookieManager`, `PokemonDataManager`, `PersonalityEngine`).
- Creates the Discord `Bot`, registers cogs, syncs slash commands, and starts the client.

## `ready_set_go.sh` helper script

For a more automated startup (e.g., on a server), use:

```bash
cd fun_bot/..
bash fun_bot/ready_set_go.sh --skip-tests
```

This script will:

- Create/activate a virtualenv (or use `VENV_PATH` if set).
- Install dependencies from `fun_bot/requirements.txt` (unless `SKIP_PIP_INSTALL=1`).
- Optionally run compile + pytest smoke tests.
- Start `python3 fun_bot/main.py` in a simple auto‑restart loop.

Useful environment variables:

- `VENV_PATH` — override the venv location.
- `SKIP_PIP_INSTALL=1` — skip dependency installation.
- `AUTO_GIT_PULL=1` — run `git pull` before starting.

### Persistent storage

FunBot includes a small SQLite-backed storage engine for user and game data:

- By default, data is stored in `fun_bot/data/funbot.sqlite3`.
- You can override the location with the `FUNBOT_DB_PATH` environment variable.
- When running in Docker or another container, mount this path on a host volume
  to ensure data survives container rebuilds.

Examples:

```bash
# Custom DB path on a VM / bare metal
export FUNBOT_DB_PATH=/var/lib/funbot/funbot.sqlite3

# Docker volume (excerpt)
docker run \
  -e DISCORD_TOKEN=... \
  -e FUNBOT_DB_PATH=/data/funbot.sqlite3 \
  -v funbot_data:/data \
  your-image:tag
```

## Systemd / services

For long‑running deployments on Linux, the `fun_bot/hippo_funbot.service` unit file provides an example of how to run FunBot under `systemd`. Customize paths, user, and environment to match your environment, and point ExecStart at either `python main.py` in the `fun_bot` directory or the `ready_set_go.sh` script.

---

For questions or contributions, treat the `fun_bot` folder as the boundary for all FunBot-related work. Each bot in this repo is managed and deployed independently.
