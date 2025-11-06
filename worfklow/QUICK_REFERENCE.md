# 🚀 HippoBot Quick Reference Card

> **Read this FIRST every session** - Then consult PROJECT_STRUCTURE_RULES.md for details

---

## 📁 Where Does This File Go?

| File Type | Location | Examples |
|-----------|----------|----------|
| **Discord commands** | `discord_bot/cogs/` | `translation_cog.py`, `ranking_cog.py` |
| **Business logic** | `discord_bot/core/engines/` | `translation_orchestrator.py`, `event_reminder_engine.py` |
| **Deployment scripts** | `scripts/deployment/` | `deploy_to_ec2.ps1`, `sync_commands_ec2.py` |
| **Dev/debug tools** | `scripts/diagnostics/` | `diagnose_*.py`, `validate_*.py` |
| **Test files** | `tests/` | `test_translation_engine.py` |
| **Architecture docs** | `worfklow/architecture/` | `KVK_RANKING_IMPLEMENTATION.md` |
| **Deployment docs** | `worfklow/deployment/` | `CANONICAL_DEPLOYMENT_CHECKLIST.md` |
| **Diagnostic reports** | `logs/diagnostics/` | `EVENT_REMINDER_DIAGNOSTIC_REPORT.md` |
| **Screenshots** | `logs/screenshots/` | `Screenshot*.png` |
| **Database files** | `data/` | `game_data.db`, `*.json` |

**❌ NEVER in root!** Only: `main.py`, `__main__.py`, `README.md`, `requirements.txt`, `pytest.ini`, `.env*`, `.git*`

---

## 🔒 Critical Import Rules

### ✅ ALLOWED
```python
# Cogs import engines (via injection)
from discord_bot.core.engines.feature_engine import FeatureEngine

# Engines use event bus
from discord_bot.core.event_bus import EventBus

# Engines registered via registry
from discord_bot.core.engines.base.engine_registry import EngineRegistry
```

### ❌ FORBIDDEN
```python
import discord  # ❌ NEVER in core/engines/
from discord_bot.cogs.* import ...  # ❌ NEVER in engines
from discord_bot.core.engines.other_engine import ...  # ❌ Use registry
```

---

## 🎯 Quick Architecture Rules

1. **Cogs** = Thin Discord UI layer → Call engines only
2. **Engines** = Pure business logic → NO discord imports
3. **Event Bus** = Inter-engine communication → Use topics
4. **Integration Loader** = Only file importing both cogs AND engines
5. **Database** = Always in `data/`, explicit timestamps, use JSON not CSV

---

## 📝 Before Every Commit

```bash
# 1. Clean root (only essential files)
ls -File  # Check root

# 2. Organize files
# Scripts → scripts/{deployment|diagnostics|utilities}/
# Docs → worfklow/{architecture|deployment}/
# Logs → logs/{diagnostics|screenshots}/

# 3. Update .gitignore if needed

# 4. Check what's staged
git status --short

# 5. Commit with clear message
git commit -m "Type: Brief description

Detailed changes...

Files Modified:
- path/to/file: What changed"
```

---

## 🆘 Emergency Quick Fixes

**Circular Import?**
→ Use event bus instead of direct import

**Engine can't access Discord?**
→ Pass data from cog as parameters, never import discord in engines

**Database constraint error?**
→ Add timestamp explicitly: `datetime.now(timezone.utc).isoformat()`

**Files in wrong place?**
→ Check table above, move to correct folder

**Root directory messy?**
→ Run: `Get-ChildItem -File` and move non-essential files

---

## 🎓 Adding New Features - 5 Steps

1. **Create Engine** → `discord_bot/core/engines/{feature}_engine.py`
2. **Register Engine** → Add to `integration_loader.py` 
3. **Create Cog** → `discord_bot/cogs/{feature}_cog.py`
4. **Wire Dependencies** → Inject engine into cog in `integration_loader.py`
5. **Document** → Add to `worfklow/architecture/`

---

## 📚 Full Details

See `worfklow/PROJECT_STRUCTURE_RULES.md` for:
- Complete directory structure
- Detailed coding standards
- Documentation templates
- Comprehensive checklists
- Common issues & solutions

---

**Keep this file open while coding!**
