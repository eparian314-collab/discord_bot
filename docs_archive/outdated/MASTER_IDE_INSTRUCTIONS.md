# HippoBot IDE Master Instructions

Central reference for working on HippoBot inside your IDE. Use this as the “getting oriented” checklist before diving into features or debugging sessions.

## Mission & Scope
- Discord bot focused on multilingual support, community engagement, and game-style ranking for Top Heroes events.
- Core pillars: translation pipeline, event/game engines, ranking OCR workflow, admin tooling, and deployment scripts.
- Ranking system extends standard bot flow with screenshot ingestion, OCR validation, SQLite storage, and admin reports.

## Project Layout (Quick Map)
- `main.py` / `__main__.py` – entry points; load config and spin up `HippoBot`.
- `integrations/integration_loader.py` – composes engines, registers cogs, handles slash command sync.
- `cogs/` – Discord-facing behavior (`ranking_cog.py`, `admin_cog.py`, etc.).
- `core/engines/` – business logic modules:
  - `screenshot_processor.py` (OCR + extraction),
  - `ranking_storage_engine.py` (SQLite persistence),
  - translation engines, cache/error managers, KVK tracker.
- `games/` – game data stores and helper engines.
- `scripts/` – operational tooling (deployment, sync, diagnostics, migrations).
- `docs/` – detailed walkthroughs (`RANKING_SYSTEM.md`, setup checklists, admin guides).
- `data/` – runtime SQLite databases (`event_rankings.db`, `game_data.db`) created/managed automatically.
- `language_context/` – language detection, policies, maps, and translation adapters.

## Local Setup Workflow
1. **Python environment** – Use Python 3.10+ (discord.py >=2). Create a virtualenv for isolation.
2. **Dependencies** – `pip install -r requirements.txt`.
3. **OCR stack** – Install Tesseract binary (Windows installer or `choco install tesseract`; verify with `tesseract --version`). Pillow/pytesseract provided via requirements.
4. **Environment config** – Copy `.env.example` (if available) or edit `.env`; set Discord token, API keys, channel IDs (see next section).
5. **Preflight validation** – `python scripts/preflight_check.py` to confirm directories, channel config, databases, and `.env` completeness before starting the bot.
6. **Run bot** – `python main.py` (or PowerShell script `scripts/start_bot.ps1`).
7. **Slash command sync (if permissions change)** – `python scripts/sync_commands.py` or `python scripts/force_sync_commands.py`.

## Environment & Secrets
- `.env` holds tokens and channel IDs. Required keys:
  - `DISCORD_TOKEN`, `DEEPL_API_KEY`, `MY_MEMORY_API_KEY`, `OPEN_AI_API_KEY`.
  - Ranking-specific: `RANKINGS_CHANNEL_ID`, optional `MODLOG_CHANNEL_ID`, `BOT_CHANNEL_ID`, `ALLOWED_CHANNELS`.
  - Translation defaults: `SERVER_DEFAULT_LANGUAGE`, `AUTO_TRANSLATE_*`.
- Keep the ranking channel ID listed inside `ALLOWED_CHANNELS` or submissions will be rejected (preflight check enforces this).
- Never commit populated `.env`; treat secrets via IDE vault or environment manager.

## Common Local Commands
- `python scripts/preflight_check.py` – environment sanity sweep (logs to `logs/preflight.log`).
- `python scripts/validate_env.py` – strict .env validation.
- `python scripts/check_schema.py` – compare SQLite schema vs expected definitions.
- `pytest` or `pytest -m asyncio` – run automated tests (see `tests/`).
- `python scripts/sync_commands.py` – refresh slash commands (global and/or guild scoped).
- `python scripts/nuclear_sync.py` – full rebuild/sync routine (bot shutdown, git sync, dependency reinstall).
- Deployment helpers: `scripts/deploy.sh`, `scripts/push_and_deploy.ps1`, `scripts/start_production.ps1`.

## Ranking System Playbook
**Overview** – Discord users submit Top Heroes screenshots in the dedicated rankings channel. OCR extracts rank data, validates duplicates, persists to SQLite, and surfaces to admins via slash commands.

- **Submission Flow**
  1. `/games ranking submit` available only in `RANKINGS_CHANNEL_ID`.
  2. `ScreenshotProcessor` runs OCR (Tesseract) to extract stage, day, rank, score, guild tag, player name.
  3. `RankingStorageEngine` enforces uniqueness per `(user_id, guild_id, event_week, stage_type, day_number)` and logs attempts in `event_submissions`.
  4. Modlog notification optional (channel auto-detected or via `MODLOG_CHANNEL_ID`).
  5. Admins can view `/games ranking view`, `/games ranking leaderboard`, `/games ranking report`, `/games ranking stats`, `/games ranking user`.

- **Key Files**
  - `core/engines/screenshot_processor.py` – ranking dataclass, OCR helpers, validation utilities.
  - `core/engines/ranking_storage_engine.py` – persistence, duplicate detection, leaderboard queries, stats, pruning.
  - `cogs/ranking_cog.py` – slash command definitions, channel enforcement, modlog integration, admin workflows.
  - `docs/RANKING_SYSTEM.md`, `docs/RANKING_SETUP.md`, `docs/RANKING_ADMIN_COMMANDS.md`, `docs/RANKING_SETUP_CHECKLIST.md`, `docs/RANKING_WEEKLY_SYSTEM.md` – deep dives and SOPs.

- **Database**
  - Primary file: `data/event_rankings.db` (auto-created).
  - Tables: `event_rankings`, `event_submissions`; optional columns `kvk_run_id`, `is_test_run`.
  - Maintenance helpers: `RankingStorageEngine.delete_old_rankings`, `delete_old_event_weeks`.

- **Dependencies & External Services**
  - OCR: Pillow + pytesseract + Tesseract binary.
  - Discord: slash commands via discord.py 2.
  - Optional integration with `core.engines.kvk_tracker` for event context.

## Monitoring & Logs
- Runtime logs typically under `logs/`; ensure directory exists (preflight ensures).
- Ranking submissions surfaced in Discord modlog channel for audit.
- `scripts/preflight_check.py` writes to `logs/preflight.log`; check before deployments.
- SQLite databases can be inspected with DB Browser (`data/event_rankings.db`).

## Operational Scripts & Automation
- `scripts/deploy.sh` / `scripts/push_and_deploy.ps1` – deploy flows (git push + remote deploy).
- `scripts/migrate_add_pokemon_stats.py` – example migration script; follow pattern for future schema changes.
- `scripts/check_schema.py` / `scripts/check_cookies_db.py` – diagnostics for storage engines.
- `scripts/nuclear_sync.py` – clean re-sync of dependencies and git state; use cautiously (includes reinstall).

## Testing & QA Notes
- Use `tests/` suite to verify translation engines and ranking logic (expand coverage as features grow).
- For OCR, create a folder of sample screenshots to validate extraction; consider mockable interfaces for unit tests.
- Apply `/games ranking leaderboard` and `/games ranking stats` on a test guild to verify modlog + admin flows.
- When adjusting OCR patterns, validate against multiple locales and number formats to avoid false positives.

## Documentation Index
- Ranking system docs (implementation, admin, setup, weekly ops) under `docs/`.
- Translation system and general project overview: `README.md`, `docs/IMPLEMENTATION_SUMMARY.md`, `docs/QUICK_START_GUIDE.md`.
- Keep this master file updated whenever workflows change (new cogs, scripts, or environment flags).

---

**Usage Tip:** Pin this file in your IDE workspace and update it after major refactors, new deployment steps, or changes to ranking operations so contributors have a single source of truth.
