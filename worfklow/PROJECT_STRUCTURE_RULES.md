# HippoBot Project Structure & Coding Standards

> **Purpose**: Ensure consistent file placement, import patterns, and code organization across all development sessions.

---

## 📁 Directory Structure & File Placement Rules

### **Root Directory** (`/`)
**ONLY Essential Files Allowed:**
- `main.py` - Primary bot entry point
- `__main__.py` - Module entry point
- `README.md` - Project documentation
- `requirements.txt` - Python dependencies
- `pytest.ini` - Test configuration
- `.env`, `.env.example` - Environment config (never commit .env)
- `.gitignore`, `.gitattributes` - Git config

**❌ NEVER place in root:**
- Scripts, utilities, or tools
- Documentation files (*.md except README.md)
- Database files
- Project/IDE files
- Diagnostic scripts

---

### **Core Bot Code** (`discord_bot/`)

#### `discord_bot/cogs/`
**Discord command groups and UI interaction**
- **Pattern**: `{feature}_cog.py`
- **Examples**: `translation_cog.py`, `ranking_cog.py`, `event_management_cog.py`
- **Rules**:
  - Thin adapters only - parse Discord inputs, call engines
  - NO business logic in cogs
  - Receive engines via dependency injection in `setup_*` functions
  - Use shared command groups from `core/ui_groups.py`

#### `discord_bot/core/engines/`
**Pure domain logic - NO Discord dependencies**
- **Pattern**: `{domain}_engine.py`
- **Examples**: `translation_orchestrator.py`, `event_reminder_engine.py`, `ranking_storage_engine.py`
- **Rules**:
  - Never import `discord.*` or cogs
  - Use event bus for inter-engine communication
  - Register via `EngineRegistry` with dependency injection
  - Async methods preferred

#### `discord_bot/core/engines/base/`
**Engine infrastructure**
- `engine_registry.py` - Engine lifecycle management
- `logging_utils.py` - Logging utilities

#### `discord_bot/integrations/`
**Dependency wiring - SINGLE source of truth**
- `integration_loader.py` - Wire engines to cogs
- **Rule**: Only this file imports both engines AND cogs

#### `discord_bot/language_context/`
**Translation and language detection**
- `translators/` - External service adapters (DeepL, MyMemory, etc.)
- `detectors/` - Language detection logic
- `context/` - Language context management

#### `discord_bot/games/`
**Game-specific features**
- `storage/` - Game data persistence
- Pokemon, battles, cookies, etc.

---

### **Configuration** (`config/`)
- `env.py` - Environment variable loading
- `config.example.json` - Example configuration
- `project/` - IDE project files (gitignored)

---

### **Data Storage** (`data/`)
**Persistent data files**
- `game_data.db` - SQLite database
- `pokemon_base_stats_cache.json` - Static game data
- `language_map.json` - Language code mappings
- **Rule**: All `.db` and large JSON files go here

---

### **Scripts** (`scripts/`)

#### `scripts/deployment/`
**EC2 and production deployment**
- `deploy-ec2.sh`, `deploy_to_ec2.ps1`
- `check_ec2_status.ps1`, `view_ec2_logs.ps1`
- `sync_commands_ec2.py`

#### `scripts/diagnostics/`
**Development and debugging tools**
- `diagnose_*.py` - System diagnostic scripts
- `validate_*.py` - Validation tools
- `check_*.py` - Health check scripts
- `migrate_*.py` - Database migration scripts

#### `scripts/utilities/`
**General utility scripts**
- One-off tools and helpers

---

### **Tests** (`tests/`)
**Pytest test suite**
- Mirror structure of `discord_bot/`
- **Pattern**: `test_{module_name}.py`
- **Examples**: `test_translation_engine.py`, `tests_r8_validation.py`
- Use `conftest.py` for shared fixtures

---

### **Logs** (`logs/`)

#### `logs/diagnostics/`
**System diagnostic reports**
- Event system diagnostics
- Error reports
- Investigation logs

#### `logs/screenshots/`
**Reference screenshots**
- UI examples
- Test cases
- Bug reports

#### `logs/security/`
**Security audit logs** (gitignored by default)

#### Root log files:
- `CURRENT_ACTIVE_ISSUES.txt` - Known issues tracker

---

### **Workflow Documentation** (`worfklow/`)

#### `worfklow/architecture/`
**System architecture and implementation docs**
- Component designs
- Feature implementations (R8, R10, R11 series)
- Integration notes (`wiring_notes.md`)
- Technical specifications

#### `worfklow/deployment/`
**Deployment guides and checklists**
- EC2 deployment procedures
- Phase migration guides
- Deployment checklists

#### `worfklow/instructions/`
**AI assistant instructions** (gitignored)
- `copilot-instructions.md`
- `master_bot.instructions.md`
- Session-specific prompts

#### `worfklow/md/`
**Temporary markdown files** (gitignored)
- Draft documentation
- Work-in-progress notes

---

## 🔧 Import Rules & Dependency Flow

### **Critical Dependency Chain**
```
config/env → logging → core engines → event bus → integration loader → cogs → discord runtime
```

### **Strict Import Rules**

#### ✅ **ALLOWED**
```python
# Cogs can import engines (injected)
from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine

# Engines can import other engines (via registry)
from discord_bot.core.engines.base.engine_registry import EngineRegistry

# Engines use event bus for communication
from discord_bot.core.event_bus import EventBus
from discord_bot.core.event_topics import TRANSLATION_REQUESTED
```

#### ❌ **FORBIDDEN**
```python
# NEVER import discord.* in engines
import discord  # ❌ in any file under core/engines/

# NEVER import cogs from engines
from discord_bot.cogs.translation_cog import ...  # ❌

# NEVER import engines from other engines directly
from discord_bot.core.engines.processing_engine import ...  # ❌ Use registry
```

### **Import Pattern by Layer**

#### **Cogs** (`discord_bot/cogs/`)
```python
import discord
from discord import app_commands
from discord.ext import commands
from discord_bot.core.engines.{feature}_engine import FeatureEngine  # Injected
from discord_bot.core.utils import is_admin_or_helper  # Shared utilities
```

#### **Engines** (`discord_bot/core/engines/`)
```python
import asyncio
import logging
from typing import Any, Dict, Optional
from discord_bot.core.event_bus import EventBus
from discord_bot.core.event_topics import EVENT_TOPIC
# NO discord imports allowed
```

#### **Integration Loader** (`discord_bot/integrations/integration_loader.py`)
```python
# ONLY file that imports both engines AND cogs
from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine
from discord_bot.cogs.translation_cog import TranslationCog
```

---

## 🎯 Coding Standards

### **Engine Development**

#### **Engine Class Pattern**
```python
class FeatureEngine:
    """Domain-pure engine for {feature}."""
    
    def __init__(self, dependency: DependencyEngine) -> None:
        self.dependency = dependency
        self.event_bus: Optional[EventBus] = None
    
    def plugin_name(self) -> str:
        return "feature_engine"
    
    def required_dependencies(self) -> Set[str]:
        return {"dependency_engine"}
    
    async def on_dependencies_ready(self) -> None:
        """Called when all dependencies are injected."""
        # Initialize after dependencies ready
        pass
```

#### **Event-Driven Communication**
```python
# Emit events
self.event_bus.emit(
    FEATURE_EVENT_TOPIC,
    {"data": "value"}
)

# Subscribe to events
self.event_bus.on(OTHER_EVENT_TOPIC, self._handle_event)
```

### **Cog Development**

#### **Cog Class Pattern**
```python
class FeatureCog(commands.Cog):
    """Discord interface for {feature}."""
    
    def __init__(self, bot: commands.Bot, feature_engine: Optional[FeatureEngine] = None):
        self.bot = bot
        self.feature_engine = feature_engine or getattr(bot, "feature_engine", None)
    
    @app_commands.command(name="feature_action")
    async def feature_action(self, interaction: discord.Interaction, param: str):
        """Command description."""
        # Parse Discord input
        # Call engine
        result = await self.feature_engine.process(param)
        # Send Discord response
        await interaction.response.send_message(result)

async def setup(bot: commands.Bot):
    """Cog setup with dependency injection."""
    feature_engine = getattr(bot, "feature_engine", None)
    await bot.add_cog(FeatureCog(bot, feature_engine))
```

### **Database Operations**

#### **Storage Engine Pattern**
```python
class FeatureStorageEngine:
    """SQLite storage for {feature}."""
    
    def __init__(self, db_path: str = "data/feature_data.db"):
        # Resolve absolute path
        path_obj = Path(db_path)
        if not path_obj.is_absolute():
            path_obj = Path.cwd() / path_obj
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(path_obj))
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        """Create tables with explicit defaults."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
```

#### **Insert/Update Rules**
```python
# ✅ ALWAYS explicitly set timestamp columns
from datetime import datetime, timezone

created_at = datetime.now(timezone.utc).isoformat()

cursor.execute("""
    INSERT INTO table (col1, col2, created_at)
    VALUES (?, ?, ?)
""", (val1, val2, created_at))

# ❌ NEVER rely on DEFAULT CURRENT_TIMESTAMP in explicit column lists
```

---

## 📝 Documentation Standards

### **When to Create Documentation**

#### **Architecture Docs** (`worfklow/architecture/`)
- New engine implementations
- System redesigns
- Integration patterns
- **Pattern**: `{FEATURE}_IMPLEMENTATION.md`, `R{version}_{TOPIC}.md`

#### **Deployment Docs** (`worfklow/deployment/`)
- Deployment procedures
- Migration guides
- Configuration checklists
- **Pattern**: `{FEATURE}_DEPLOYMENT_CHECKLIST.md`, `CANONICAL_{PROCESS}.md`

#### **Diagnostic Reports** (`logs/diagnostics/`)
- Bug investigation results
- System analysis
- Root cause reports
- **Pattern**: `{FEATURE}_DIAGNOSTIC_REPORT.md`, `{FEATURE}_FIX_SUMMARY.md`

### **Documentation Template**
```markdown
# {Feature Name} - {Purpose}

## Overview
Brief description of feature/issue

## Implementation/Analysis
Detailed technical content

## Key Components
- Component 1: Description
- Component 2: Description

## Usage/Resolution
How to use or what was fixed

## References
- Related files
- Dependencies
```

---

## 🚫 Anti-Patterns to Avoid

### **File Placement**
- ❌ Scripts in root directory
- ❌ Database files in root
- ❌ Documentation in root (except README.md)
- ❌ IDE project files tracked in git

### **Code Structure**
- ❌ Business logic in cogs
- ❌ Discord dependencies in engines
- ❌ Circular imports between engines
- ❌ Direct engine-to-engine imports (use registry)

### **Database**
- ❌ Multiple SQLite connections per engine
- ❌ Relying on DEFAULT when using explicit column lists
- ❌ Missing UTC timezone on timestamps
- ❌ Storing lists as comma-separated strings (use JSON)

### **Git**
- ❌ Committing .env files
- ❌ Committing IDE project files
- ❌ Committing logs and diagnostics
- ❌ Committing unorganized WIP docs

---

## 🔄 Session Workflow

### **Starting a New Session**
1. Read this file to understand structure
2. Check `logs/CURRENT_ACTIVE_ISSUES.txt` for context
3. Review recent commits for changes
4. Check `worfklow/architecture/` for system docs

### **Adding New Features**
1. **Create engine** in `discord_bot/core/engines/`
2. **Register engine** in `integration_loader.py`
3. **Create cog** in `discord_bot/cogs/`
4. **Wire dependencies** in `integration_loader.py`
5. **Add tests** in `tests/`
6. **Document** in `worfklow/architecture/`

### **Before Committing**
1. Ensure files in correct directories
2. Update .gitignore if needed
3. Move WIP docs to proper folders
4. Clear root of stray files
5. Write descriptive commit messages

### **Commit Message Format**
```
{Type}: {Brief description}

{Detailed explanation of changes}

Files Modified:
- path/to/file: Description

{Additional context or references}
```

**Types**: `Fix`, `Feature`, `Refactor`, `Docs`, `Test`, `Chore`

---

## 📋 Quick Reference Checklist

### ✅ New Engine Checklist
- [ ] File in `discord_bot/core/engines/{feature}_engine.py`
- [ ] No `discord.*` imports
- [ ] Implements `plugin_name()` and `required_dependencies()`
- [ ] Uses event bus for communication
- [ ] Registered in `integration_loader.py`
- [ ] Tests in `tests/test_{feature}_engine.py`

### ✅ New Cog Checklist
- [ ] File in `discord_bot/cogs/{feature}_cog.py`
- [ ] Thin adapter pattern (no business logic)
- [ ] Engines injected via `setup()` function
- [ ] Uses shared command groups from `ui_groups.py`
- [ ] Wired in `integration_loader.py`
- [ ] Tests in `tests/cogs/test_{feature}_cog.py`

### ✅ Database Change Checklist
- [ ] Schema in `create_tables()` method
- [ ] Explicit timestamps (no DEFAULT reliance)
- [ ] JSON for structured data (not CSV)
- [ ] UTC timezone for all timestamps
- [ ] Migration script if altering existing tables

### ✅ Pre-Commit Checklist
- [ ] Root directory clean (only essential files)
- [ ] Scripts in `scripts/{category}/`
- [ ] Docs in `worfklow/{category}/`
- [ ] Logs in `logs/{category}/`
- [ ] No stray .md files in root
- [ ] .gitignore updated if needed
- [ ] Tests pass
- [ ] Descriptive commit message

---

## 🆘 Common Issues & Solutions

### Issue: "Module not found" error
**Solution**: Check import path matches directory structure. Ensure `__init__.py` exists in package directories.

### Issue: Circular import between engines
**Solution**: Use event bus for communication. Never directly import engines from each other.

### Issue: Engine can't access Discord objects
**Solution**: Engines should never access Discord directly. Pass needed data from cog as parameters.

### Issue: Database constraint failure
**Solution**: Check if all required columns are in INSERT. Explicitly set timestamps.

### Issue: Files accumulating in root
**Solution**: Follow file placement rules. Move to appropriate `scripts/`, `logs/`, or `worfklow/` subdirectories.

---

**Last Updated**: 2025-11-05  
**Version**: 1.0  
**Maintainer**: Project Structure Standards
