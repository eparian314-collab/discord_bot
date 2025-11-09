# HippoBot Workflow Instructions

**Project snapshot:** 2025-11-03  
HippoBot v2 is production-ready with 18 slash commands covering translation, game systems, and Top Heroes event coordination.

## Core Engineering Rules
- Use absolute imports rooted at the repository package; avoid `..` upward relative imports. The shim in `discord_bot/__init__.py` keeps legacy `discord_bot.*` paths working.
- Keep domain logic inside `core/engines/*` (and related language/game modules). Cogs manage Discord UI and delegate to engines rather than touching persistence directly.
- Cross-engine communication flows through `core/event_bus.py` with topics declared in `core/event_topics.py`.
- Instantiate engines, register command groups, and mount cogs inside `integrations/integration_loader.py`. Extend `_setup_engines` / `_mount_cogs` when wiring new services.
- Persisted state belongs in `GameStorageEngine` and the specialised reminder/storage helpers. Do not open ad-hoc SQLite connections in cogs or scripts.

## Engine & Service Map
| Component | Module | Responsibility |
| --- | --- | --- |
| `ProcessingEngine` | `core/engines/processing_engine.py` | Normalises inbound content, hands off to translation orchestrator and detectors. |
| `TranslationOrchestratorEngine` | `core/engines/translation_orchestrator.py` | Routes between DeepL, MyMemory, Google fallback, and optional OpenAI models. |
| `ContextEngine` & memories | `language_context/context_engine.py`, `context_memory.py`, `session_memory.py` | Stores per-user language preferences, conversation memory, and alias resolution. |
| `InputEngine` / `OutputEngine` | `core/engines/input_engine.py`, `core/engines/output_engine.py` | Glue between Discord events and engines; handles SOS broadcasts, cooldowns, and response formatting. |
| `PersonalityEngine` | `core/engines/personality_engine.py` | Applies persona tuning and leverages `RelationshipManager` for flavour text. |
| `CacheManager` & `GuardianErrorEngine` | `core/engines/cache_manager.py`, `core/engines/error_engine.py` | Shared TTL caches and centralised error collection / alerting. |
| Game stack | `games/storage/game_storage_engine.py`, `core/engines/cookie_manager.py`, `core/engines/relationship_manager.py`, `games/pokemon_game.py` | Cookie economy, Pokemon progression, relationship tracking, and shared SQLite connection. |
| `EventReminderEngine` | `core/engines/event_reminder_engine.py` | Stores reminder definitions, schedules notifications, and drives `/event` subcommands. |
| UI helpers | `core/engines/translation_ui_engine.py`, `core/engines/admin_ui_engine.py` | Build embeds and panels used by translation and admin cogs. |

## Command Surface (Nov 2025)
- Command surface is grouped into `/language`, `/games`, `/admin`, and `/event`. Translation and language-role commands remain top-level (`/translate`, `/language_assign`, etc.).
- Translation & language management: `/translate`, `/language_assign`, `/language_remove`, `/language_list`, `/language_sync`, SOS tools (`/sos_add`, `/sos_remove`, `/sos_list`, `/sos_clear`) powered by the input engine and role manager.
- Games & cookies: `/games pokemon ...`, `/games cookies ...`, `/games battle ...`, `/games fun ...`, plus top-level helpers `/feed`, `/hippo`, `/easteregg`, `/weather`, `/rps`, `/trivia`, `/catfact`.
- Event coordination: `/event create`, `/event list`, `/event delete`, `/event edit`, `/event cleanup`, `/event status`, and public `/events` for read-only schedules.
- Admin utilities: `/admin keyword set|link|remove|list`, moderation helpers for mute/unmute and escalation (see `cogs/admin_cog.py`).
- Channel restrictions are enforced via `core/utils.is_allowed_channel`; reminder commands respect guild-level admin/helper checks.

## Data & Persistence
- Game, cookies, relationships, reminders: `data/game_data.db` (auto-migrated on engine start).
- Cached assets: `pokemon_base_stats_cache.json`, language maps, and other helpers live in the project root or `data/`.
- Logs: `logs/hippo_bot.log` with rotation configured in `main.py`.

## Environment & Configuration
- Required `.env` keys: `DISCORD_TOKEN`, `DEEPL_API_KEY`, `MYMEMORY_API_KEY`, `MYMEMORY_USER_EMAIL`, `OWNER_IDS`, `ALLOWED_CHANNELS`, `TIMEZONE`, `LOG_LEVEL`.
- Optional / advanced: `OPENAI_API_KEY`, `OPENAI_MODEL`, `SYNC_GLOBAL_COMMANDS`, `TEST_GUILDS`, `PRIMARY_GUILD_NAME`, `CMD_PREFIX`, `GUARDIAN_SAFE_MODE`.
- Ensure `data/` exists and is writable; engines create SQLite files automatically if they do not exist.

## Operations & Diagnostics
- Start/stop: `python main.py`, or use the wrappers in `scripts/start_bot.ps1` / `scripts/start_production.ps1`.
- Preflight validation: `python scripts/preflight_check.py` verifies environment variables, directories, and database access.
- Command sync tooling: `scripts/full_sync_commands.py`, `scripts/diagnose_commands.py`, `scripts/test_group_structure.py`, and the emergency reset `scripts/nuclear_sync.py`.
- Ranking + storage utilities: `scripts/check_schema.py`, `scripts/check_cookies_db.py`, `scripts/migrate_add_pokemon_stats.py`.
- Runtime health: `scripts/runtime_diagnostic.py`, `scripts/force_sync_commands.py` for manual syncs.
- Encoding cleanup: `scripts/sanitize_encoding.py` fixes legacy mojibake in Markdown or config files.

## Documentation Sources
Live status docs: `docs/COMMAND_GROUP_FIX_SUMMARY.md`, `docs/PRODUCTION_READINESS_CHECKLIST.md`.
Historical references and setup guides now live under `docs_archive/` (e.g., translation summaries).

---

Keep this workflow prompt in sync whenever engines are introduced, command groups move, or environment expectations change so contributors always see the current project state.
