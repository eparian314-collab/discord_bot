---
applyTo: '**'
---
# HippoBot IDE Master Instructions

Central reference for working on HippoBot inside your IDE. Review this before diving into new features or debugging sessions.

## Mission & Scope
- Discord bot focused on multilingual support, community engagement, and Top Heroes event coordination.
- Core pillars: translation pipeline, event/game engines, reminder automation, admin tooling, and deployment scripts.
- Event system extends the bot with persistent schedules, cleanup helpers, and `/event` slash commands.

## Project Layout (Quick Map)
- `main.py` / `__main__.py` – entry points; load config and spin up `HippoBot`.
- `integrations/integration_loader.py` – composes engines, registers cogs, handles slash command sync and post-setup hooks.
- `cogs/` – Discord-facing behaviour (`admin_cog.py`, `event_management_cog.py`, `translation_cog.py`, `game_cog.py`, etc.).
- `core/engines/` – business logic modules:
  - translation engines, cache/error managers, reminder engine, role/cookie managers.
  - event delegates (`event_reminder_engine.py`, `session_manager.py`, `cleanup_engine.py`).
- `games/` – game data stores and helper engines.
- `scripts/` – operational tooling (deployment, sync, diagnostics, migrations).
- `docs/` – detailed walkthroughs (event automation, translation, deployment checklists).
- `data/` – runtime SQLite database (`game_data.db`) created/managed automatically.
- `language_context/` – language detection, policies, maps, and translation adapters.

## Local Setup Workflow
1. **Python environment** – Use Python 3.10+ (discord.py >=2). Create a virtualenv for isolation.
2. **Dependencies** – `pip install -r requirements.txt`.
3. **Environment config** – Copy `.env.example` (if available) or edit `.env`; set Discord token, API keys, owner IDs, allowed channels.
4. **Preflight validation** – `python scripts/preflight_check.py` to confirm directories, channel config, databases, and `.env` completeness before starting the bot.
5. **Run bot** – `python main.py` (or `scripts/start_bot.ps1` on Windows).
6. **Slash command sync (if permissions change)** – `python scripts/force_sync_commands.py`.

## Message Cleanup System
**Overview** – Bot automatically cleans up its old messages from previous sessions on startup to keep channels tidy.

- Each restart records a session UUID + timestamp (`data/session_state.json`).
- Cleanup removes historical bot messages while respecting pins, `DO NOT DELETE` tags, and configurable channel skip lists.
- Manual command: `/admin cleanup [limit]` (1–500 messages) for the current channel.
- Key knobs (in `.env`):
  ```
  CLEANUP_ENABLED=true
  CLEANUP_SKIP_RECENT_MINUTES=30
  CLEANUP_LIMIT_PER_CHANNEL=200
  CLEANUP_RATE_DELAY=0.5
  ```
- Core files: `core/engines/session_manager.py`, `core/engines/cleanup_engine.py`, integration wiring inside `integration_loader.py`, command handler inside `cogs/admin_cog.py`.

## Environment & Secrets
- `.env` holds tokens and channel IDs. Required keys:
  - `DISCORD_TOKEN`, `DEEPL_API_KEY`, `MYMEMORY_API_KEY`, `OWNER_IDS`, `ALLOWED_CHANNELS`, `BOT_CHANNEL_ID`, `TIMEZONE`, `LOG_LEVEL`.
- Optional helpers: `OPENAI_API_KEY`, `PRIMARY_GUILD_NAME`, `CMD_PREFIX`, `GUARDIAN_SAFE_MODE`.
- Keep event-related channels (`BOT_CHANNEL_ID`, helper channels listed in `ALLOWED_CHANNELS`) accurate or reminder commands will fail validation.
- Never commit `.env`; use your IDE secret storage or OS keychain.

## Common Local Commands
- `python scripts/preflight_check.py` – environment sanity sweep (logs to `logs/preflight.log`).
- `python scripts/validate_env.py` – strict .env validation.
- `python scripts/check_schema.py` – compare SQLite schema vs expected definitions.
- `pytest` – run automated tests (see `tests/`).
- `python scripts/force_sync_commands.py` – refresh slash commands (guild scoped).
- Deployment helpers: `scripts/deploy.sh`, `scripts/push_and_deploy.ps1`.

## Event Management Playbook
**Overview** – Discord admins schedule and curate Top Heroes events via `/event` group commands. Reminders persist in SQLite and run through the `EventReminderEngine`.

- **Key Commands**
  - `/event create` – schedule a reminder with title, UTC time, category, recurrence, reminder offsets.
  - `/event list` – show upcoming events for the guild.
  - `/event edit` – adjust title/time/recurrence.
  - `/event delete` – remove one or more events.
  - `/event cleanup` – prune stale or duplicate reminders (especially after tests).
  - `/events` – public read-only list for members.

- **Submission Flow**
  1. Slash command payload validated inside `EventManagementCog`.
  2. Persistence handled by `games/storage/game_storage_engine.py` (shared `GameStorageEngine` instance).
  3. Scheduler tasks spawned in `EventReminderEngine` (per-channel reminders + optional DMs).
  4. `/bot status` summarises pending reminders + next occurrence.

- **Key Files**
  - `core/engines/event_reminder_engine.py` – reminder storage, scheduler, Discord dispatch.
  - `cogs/event_management_cog.py` – slash command definitions, permission checks, embed builders.
  - `games/storage/game_storage_engine.py` – reminder tables and helper queries.
  - `docs/EVENT_COMMANDS.md` – end-user guide for `/event` workflow.

## Monitoring & Logs
- Runtime logs live under `logs/`; ensure directory exists (preflight creates it).
- `logs/preflight.log` captures environment drift each time `scripts/preflight_check.py` runs.
- For reminder debugging, toggle `EVENT_REMINDER_DEBUG=1` (see engine docstring) to log scheduling decisions.
- SQLite (`data/game_data.db`) can be inspected with DB Browser when diagnosing reminder state.

## Operational Scripts & Automation
- `scripts/deploy.sh` / `scripts/push_and_deploy.ps1` – deploy flows (git push + remote deploy).
- `scripts/check_schema.py` / `scripts/check_cookies_db.py` – diagnostics for storage engines.
- `scripts/nuclear_sync.py` – clean re-sync of dependencies and git state; use cautiously (includes reinstall).
- `scripts/diagnostics/command_registry_diagnostic.py` – current slash command tree dump.
- `scripts/diagnostics/fix_duplicate_commands.py` – clears guild/global command caches when Discord is out of sync.

## Testing & QA Notes
- Use `pytest` to cover admin, language, and reminder flows (see `tests/cogs/test_admin_cog.py`, `tests/engines/test_event_reminder_engine.py`).
- For event scheduling QA, exercise `/event create`, `/event list`, `/event delete`, and `/event cleanup` on a test guild.
- When adjusting recurrence logic, add cases to `tests/engines/test_event_reminder_engine.py` to guard against regressions.

## Documentation Index
- Event workflows: `docs/EVENT_COMMANDS.md`, `docs/PRODUCTION_READINESS_CHECKLIST.md`.
- Translation/architecture overview: `README.md`, `docs/IMPLEMENTATION_SUMMARY.md`, `docs/QUICK_START_GUIDE.md`.
- Deployment + ops: `RUNBOOK.md`, `docs/COMMAND_GROUP_FIX_SUMMARY.md`.
- Keep this master file updated whenever workflows change (new cogs, scripts, or environment flags).

---

**Tip:** Pin this file in your IDE workspace and update it after major refactors, new deployment steps, or changes to `/event` flows so contributors always have a current source of truth.
