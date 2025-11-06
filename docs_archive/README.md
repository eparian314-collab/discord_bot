# Documentation Archive

Historical documentation for HippoBot organized by relevance and status.

---

## 📁 Folder Structure

### `current/` - Active Documentation
Documentation that accurately reflects the current system state and is still relevant for understanding or using the bot.

**Core Architecture:**
- `ARCHITECTURE.md` - Overall system architecture and dependency flow
- `OPERATIONS.md` - Startup checklist and event topics
- `TOP_HEROES_EVENT_SYSTEM.md` - Event reminder system

**Translation System:**
- `AUTO_TRANSLATE_SYSTEM.md` - Auto-translation features
- `THREE_TIER_TRANSLATION_SUMMARY.md` - Translation provider hierarchy
- `LANGUAGE_CODES.md` - Language code mappings
- `LANGUAGE_NORMALIZATION.md` - Language detection and normalization

**Game Features:**
- `BATTLE_SYSTEM.md` - Pokemon battle mechanics
- `EVOLUTION_SYSTEM.md` - Pokemon evolution system
- `POKEMON_STAT_SYSTEM.md` - Pokemon stats and IVs
- `COOKIE_TRACKING_IMPLEMENTATION.md` - Cookie/relationship system
- `EASTER_EGG_LIMITS_GUIDE.md` - Daily easter egg mechanics

**Ranking System:**
- `RANKING_SYSTEM.md` - Event ranking submission and leaderboards
- `RANKING_IMPLEMENTATION.md` - Technical implementation details
- `RANKING_DATA_STORAGE.md` - Database schema and storage

**SOS System:**
- `SOS_IMPLEMENTATION.md` - Emergency translation system
- `SOS_TRANSLATION.md` - SOS phrase detection
- `SOS_QUICKSTART.md` - Quick reference for SOS features

**Security:**
- `SECURITY_GUIDE.md` - Security best practices
- `SECURITY_IMPLEMENTATION.md` - Security features

---

### `reference/` - Setup & How-To Guides
Guides for setup, configuration, and usage. May need minor updates but still useful as reference material.

**Setup Guides:**
- `QUICK_START_GUIDE.md` - Getting started with the bot
- `HELPER_ROLE_GUIDE.md` - Helper role configuration
- `OPENAI_SETUP_GUIDE.md` - OpenAI integration setup
- `GOOGLE_TRANSLATE_QUICKSTART.md` - Google Translate adapter
- `SIMULATION_TEST_GUIDE.md` - Testing guide

**Localization:**
- `LOCALIZATION_GUIDE.md` - Localization system overview
- `LOCALIZATION_IMPLEMENTATION.md` - Implementation details
- `LOCALIZATION_QUICK_REF.md` - Quick reference
- `LANGUAGE_ROLE_REACTIONS.md` - Language role reactions
- `CHANNEL_ROUTING_SETUP.md` - Channel routing

**SOS Reference:**
- `SOS_VISUAL_FLOW.md` - SOS system flow diagram
- `TEST_SOS_SYSTEM.md` - SOS testing procedures

**Ideas:**
- `OPENAI_ENHANCEMENT_IDEAS.md` - Future OpenAI features

---

### `outdated/` - Historical/Superseded Documentation
Documentation that is no longer accurate or has been superseded by newer implementations. Kept for historical reference only.

**Old IDE Instructions:**
- `MASTER_IDE_INSTRUCTIONS.md` - Superseded by `worfklow/PROJECT_STRUCTURE_RULES.md`

**Implementation Summaries:**
- `FEATURE_IMPLEMENTATION_PLAN.md` - Old planning doc
- `IMPLEMENTATION_SUMMARY.md` - Historical implementation notes
- `TEST_IMPLEMENTATION_SUMMARY.md` - Old test summaries

**Refactoring Notes:**
- `POKEMON_DATA_MANAGER_REFACTOR.md` - Completed refactoring
- `POKEMON_DETAILS_IMPLEMENTATION.md` - Old implementation

**Old Ranking Docs:**
- `RANKING_SETUP.md` - Superseded by current ranking system
- `RANKING_SETUP_CHECKLIST.md` - Old setup checklist
- `RANKING_ADMIN_COMMANDS.md` - Old command structure
- `RANKING_WEEKLY_SYSTEM.md` - Weekly system (now phase-based)

**Fix Summaries:**
- `SECURITY_FIXES_SUMMARY.md` - Completed security fixes
- `TRANSLATION_FIX_SUMMARY.md` - Historical translation fixes
- `TRANSLATION_LOGIC_FIX.md` - Old bug fixes

---

## 🔍 Finding Documentation

### Looking for current system info?
→ Start with `current/ARCHITECTURE.md` and `current/OPERATIONS.md`

### Need setup instructions?
→ Check `reference/QUICK_START_GUIDE.md`

### Understanding a specific feature?
→ Check `current/` for feature-specific docs

### Researching historical decisions?
→ Check `outdated/` for old implementation notes

---

## 📝 Maintenance Notes

**Last Organized**: 2025-11-05

**Next Review**: When major system changes occur, review and update:
1. Move outdated docs from `current/` to `outdated/`
2. Update docs in `current/` to reflect new changes
3. Add new documentation to appropriate folder
4. Delete truly obsolete docs that have no historical value

**Superseded By**: 
- `worfklow/PROJECT_STRUCTURE_RULES.md` - Current project structure and coding standards
- `worfklow/QUICK_REFERENCE.md` - Quick lookup guide
- `worfklow/architecture/` - Latest architecture and implementation docs
- `worfklow/deployment/` - Current deployment guides

---

## ⚠️ Important Notes

1. **Always check current codebase** - Documentation may lag behind code changes
2. **Reference newer docs first** - Check `worfklow/` folders before `docs_archive/`
3. **Outdated ≠ Useless** - Historical docs help understand evolution of the system
4. **When in doubt** - Check git history and current code as source of truth

---

**Documentation Status Key:**
- ✅ **Current** - Accurate and actively maintained
- 📚 **Reference** - Useful but may need minor updates
- 🕰️ **Outdated** - Historical reference only
- 🗑️ **Deprecated** - Should be deleted in future cleanup
