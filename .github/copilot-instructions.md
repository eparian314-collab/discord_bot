# HippoBot AI Coding Instructions

## Architecture Overview

HippoBot is a multilingual Discord bot combining translation, game features, and event tracking for international gaming communities. Built with strict layered architecture enforcing dependency injection and event-driven communication.

### Core Dependencies Flow
```
config/env → logging → core engines → event bus → integration loader → cogs → discord runtime
```

**Critical Rule**: No upward imports. Each layer only depends leftward. Engines never import `discord.*` or cogs.

### Project Structure - CRITICAL
```
discord_bot/           # Symlink directory for module packaging
├── cogs -> ../cogs
├── core -> ../core
├── games -> ../games
├── integrations -> ../integrations
├── language_context -> ../language_context
├── __init__.py
└── __main__.py
```
- **Run with**: `python main.py` (NOT `python -m discord_bot.main`)
- Symlinks allow clean imports while maintaining flat source structure
- Both `main.py` and `discord_bot/__main__.py` exist; production uses `main.py`

## Key Architectural Components

### Event-Driven Communication
- **All inter-component communication** uses `core/event_bus.py` with topics defined in `core/event_topics.py`
- **Topic naming**: `domain.action` (e.g., `translation.requested`, `engine.error`)
- **Wiring**: Only `discord_bot/integrations/integration_loader.py` imports both engines and cogs for dependency injection

### Engine System
- **Location**: `core/engines/*` - domain-pure services with no Discord dependencies
- **Registration**: Via `EngineRegistry` with dependency injection and lifecycle management
- **Key engines**: `ProcessingEngine`, `TranslationOrchestratorEngine`, `ContextEngine`, `PersonalityEngine`, `KVKTrackerEngine`, `RankingStorageEngine`, `ScreenshotProcessor`

### Cogs (Discord Interface)
- **Location**: `cogs/*` - thin adapters that parse Discord inputs and call engines
- **Pattern**: Receive engines via injection in `setup_*` functions, not constructor
- **Example**: `cogs/translation_cog.py` gets `TranslationUIEngine` injected

## Development Patterns

### UI Organization & Command Groups
- **Layered structure**: Commands organized into logical groups for better UX
  - `language.*` - All language/communication tools (translate, roles, sos)
  - `games.*` - Pokemon, battles, cookies, fun activities
  - `admin.*` - Administrative and help commands
- **Shared groups**: Use `core/ui_groups.py` to define command group hierarchy and avoid circular imports
- **Pattern**: `/language translate text`, `/language roles assign`, `/games pokemon catch`

### Translation Stack
- **Jobs**: Use `TranslationJob` dataclass from `language_context/translation_job.py`
- **Providers**: DeepL (primary) → MyMemory → Google Translate (fallback chain) via `TranslationOrchestratorEngine`
- **Language codes**: Normalized via `language_context/normalizer.py` and `language_map.json`

### Ranking & OCR System
- **Screenshot processing**: `core/engines/screenshot_processor.py` uses Tesseract OCR for Top Heroes event rankings
- **Storage**: `core/engines/ranking_storage_engine.py` (SQLite: `data/event_rankings.db`)
- **Visual parsing**: KVK (Kingdom vs Kingdom) visual comparison via `kvk_parser_engine.py` and `kvk_visual_manager.py`
- **Pattern**: Upload screenshot → OCR extraction → validation → storage → leaderboard generation

### Database & Storage
- **Game data**: SQLite via `games/storage/game_storage_engine.py` with auto-migration
- **Pattern**: Direct SQL with `sqlite3.Row` factory for dict-like access
- **Tables**: `users`, `pokemon`, `battles`, `eastereggs`, `event_reminders`, `event_rankings`, `event_submissions`
- **Event reminders**: UTC-based scheduling for international Top Heroes game coordination
- **Ranking data**: Unique constraint per `(user_id, guild_id, event_week, stage_type, day_number)`

### Session Management & Cleanup
- **Session tracking**: `core/engines/session_manager.py` tracks bot restart sessions
- **Message cleanup**: `core/engines/cleanup_engine.py` deletes old bot messages on restart
- **Pattern**: Load previous session timestamp → delete messages since then → start new session
- **Safety**: Never deletes pinned messages or user messages, only bot's own ephemeral content

### Error Handling
- **Guardian pattern**: `GuardianErrorEngine` collects errors and emits via `ENGINE_ERROR` topic
- **Safe mode**: Registry can disable/enable plugins on repeated failures
- **Logging**: Use `get_logger("module_name")` from `core/engines/base/logging_utils.py`

## Critical Commands

### Setup & Run
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment (see .env.example)
export DISCORD_TOKEN="your_token"
export OWNER_IDS="123,456"  # Optional

# Run bot locally
python main.py

# Run tests (auto-discovers tests/ directory)
pytest

# Run with coverage
pytest --cov=discord_bot
```

### Production Deployment (EC2/Linux)
```bash
# One-time setup - creates systemd service, cron health checks, log rotation
./scripts/production_setup.sh

# Service management
sudo systemctl status discord_bot    # Check status
sudo systemctl restart discord_bot   # Restart
sudo systemctl stop discord_bot      # Stop
sudo journalctl -u discord_bot -f    # Live logs

# Health monitoring
tail -f logs/health_check.log        # Automated health checks (every 5 min)
tail -f logs/systemd.log             # Bot output
tail -f logs/critical_alerts.log     # Critical issues

# Environment validation
python3 scripts/check_env.py              # Validate .env completeness
python3 scripts/test_module_integrity.py  # Test all imports
```

### Database Operations
```bash
# Check schema integrity
python scripts/check_schema.py

# Manual migration (if needed)
python -c "from games.storage.game_storage_engine import GameStorageEngine; GameStorageEngine('data/game_data.db').create_tables()"
```

## Project-Specific Conventions

### Module Structure
- **Engines**: Pure domain logic, async methods, dependency injection via registry
- **Adapters**: External service wrappers in `language_context/translators/*`
- **Context**: Language detection/normalization in `language_context/*`
- **Integration**: Single point of dependency wiring in `integrations/`
- **UI Groups**: Shared command group definitions in `core/ui_groups.py` for organized slash commands

### Configuration Patterns
- **Environment-first**: Use `os.getenv()` with defaults in `load_config()`
- **Secrets masking**: Use `_mask()` utility for logging sensitive values
- **JSON injection**: Optional `CONFIG_JSON` file overlay for complex configs

### Testing Patterns
- **Async support**: All tests use `pytest-asyncio` with `asyncio_mode = auto`
- **Fixtures**: Minimal setup in `tests/conftest.py`
- **Engine testing**: Mock event bus and registry dependencies

## Key Files for Understanding

- `ARCHITECTURE.md` - Complete dependency flow and anti-cycle rules
- `OPERATIONS.md` - Startup checklist and event topic catalog  
- `TOP_HEROES_EVENT_SYSTEM.md` - Event reminder system for game coordination
- `RANKING_SYSTEM.md` - Screenshot OCR workflow and ranking storage
- `integrations/integration_loader.py` - Single source of truth for wiring
- `core/event_topics.py` - All event topic constants and payload contracts
- `main.py` - Entry point with preflight checks and logging setup
- `docs/PRODUCTION_READY.md` - Production deployment and management guide

## Common Gotchas

1. **Import cycles**: Never import cogs from engines or vice versa - use event bus
2. **Command sync**: Commands sync globally, takes up to 1 hour to appear in all servers
3. **Engine lifecycle**: Wait for `on_dependencies_ready()` before using injected dependencies
4. **Language fallback**: DeepL → MyMemory → Google Translate (check provider logs for routing)
5. **Database threading**: SQLite connections are per-instance, safe for async usage
6. **Integration loader fixes**: When fixing `integration_loader.py`, always edit `discord_bot/integrations/integration_loader.py` (the symlinked version), not the root copy
7. **Production entry point**: Use `python main.py`, not `python -m discord_bot.main` - systemd service configured for direct execution