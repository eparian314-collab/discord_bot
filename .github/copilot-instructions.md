# HippoBot AI Coding Instructions

## Architecture Overview

This is a Discord translation bot with strict layered architecture enforcing dependency injection and event-driven communication.

### Core Dependencies Flow
```
config/env → logging → core engines → event bus → integration loader → cogs → discord runtime
```

**Critical Rule**: No upward imports. Each layer only depends leftward. Engines never import `discord.*` or cogs.

## Key Architectural Components

### Event-Driven Communication
- **All inter-component communication** uses `core/event_bus.py` with topics defined in `core/event_topics.py`
- **Topic naming**: `domain.action` (e.g., `translation.requested`, `engine.error`)
- **Wiring**: Only `integrations/integration_loader.py` imports both engines and cogs for dependency injection

### Engine System
- **Location**: `core/engines/*` - domain-pure services with no Discord dependencies
- **Registration**: Via `EngineRegistry` with dependency injection and lifecycle management
- **Key engines**: `ProcessingEngine`, `TranslationOrchestratorEngine`, `ContextEngine`, `PersonalityEngine`

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
- **Providers**: DeepL (primary) → MyMemory (fallback) via `TranslationOrchestratorEngine`
- **Language codes**: Normalized via `language_context/normalizer.py` and `language_map.json`

### Database & Storage
- **Game data**: SQLite via `games/storage/game_storage_engine.py` with auto-migration
- **Pattern**: Direct SQL with `sqlite3.Row` factory for dict-like access
- **Tables**: `users`, `pokemon`, `battles`, `eastereggs`, `event_reminders` with relationship tracking
- **Event reminders**: UTC-based scheduling for international Top Heroes game coordination

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
$env:DISCORD_TOKEN="your_token"
$env:OWNER_IDS="123,456"  # Optional

# Run bot
python -m discord_bot.main
```

### Testing
```bash
# Run tests (auto-discovers tests/ directory)
pytest

# Run with coverage
pytest --cov=discord_bot

# Test specific engine
pytest tests/test_processing_engine.py
```

### Database Operations
```python
# Manual migration trigger
from games.storage.game_storage_engine import GameStorageEngine
storage = GameStorageEngine("game_data.db")
storage.create_tables()

# Check schema
python check_schema.py
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
- `integrations/integration_loader.py` - Single source of truth for wiring
- `core/event_topics.py` - All event topic constants and payload contracts
- `main.py` - Entry point with preflight checks and logging setup

## Common Gotchas

1. **Import cycles**: Never import cogs from engines or vice versa - use event bus
2. **Command sync**: Commands sync globally, takes up to 1 hour to appear in all servers
3. **Engine lifecycle**: Wait for `on_dependencies_ready()` before using injected dependencies
4. **Language fallback**: DeepL → MyMemory → error (check provider logs for routing)
5. **Database threading**: SQLite connections are per-instance, safe for async usage