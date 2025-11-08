# KVK vs RANKINGS Command Duplication Diagnostic Report
**Generated:** 2025-11-05  
**Status:** ✅ COMPLETE — Root cause identified

---

## PHASE 1 — Cog Registration Sources

### Single Cog Defines All Commands
**File:** `discord_bot\cogs\ranking_cog.py`  
**Class:** `RankingCog`

### Command Structure

#### TOP-LEVEL GROUP (from ui_groups.py)
```python
kvk = app_commands.Group(name="kvk", description="Top Heroes / KVK tools")
```

#### SUBGROUP (defined in RankingCog, line 77)
```python
ranking = app_commands.Group(
    name=ui_groups.KVK_RANKING_NAME,  # "ranking"
    description=ui_groups.KVK_RANKING_DESCRIPTION,  # "Top Heroes event rankings and leaderboards"
    parent=ui_groups.kvk,  # ← This makes it /kvk ranking
)
```

#### SUBGROUP COMMANDS (under @ranking.command)
All defined with `@ranking.command(...)`:
- Line 724: `submit` → `/kvk ranking submit`
- Line 1136: `view` 
- Line 1188: `leaderboard`
- Line 1294: `stats`
- Line 1408: `verify`
- Line 1605: `delete`
- Line 1683: `refresh_cache`
- Line 1790: `validate_all`
- Line 1862: `debug_confidence`
- Line 1945: `backfill`

#### ROOT-LEVEL COMMANDS (NOT in subgroup)
Defined with `@app_commands.command(...)` (NO parent group):
- Line 2045: `/rankings` (note the 's') — View KVK results for a specific run
- Line 2146: `/ranking_compare_me` — Compare between two KVK runs
- Line 2238: `/ranking_compare_others` — Compare against peers

---

## PHASE 2 — Engine Registry & Cog Enablement Order

### Integration Loader Boot Sequence

**File:** `discord_bot\integrations\integration_loader.py`

#### Command Group Registration (Line 800)
```python
ui_groups.register_command_groups(self.bot)
```
This registers the top-level groups BEFORE cogs mount:
- `/language`
- `/games`
- `/kvk` ← Registered here
- `/admin` (skipped - registered by admin_cog)

#### Cog Mount Order (Lines 956-1018)
```python
await setup_translation_cog(self.bot, ui_engine=self.translation_ui)
await setup_admin_cog(self.bot, ui_engine=self.admin_ui, owners=set(owners), ...)
await setup_help_cog(self.bot)
await setup_language_cog(self.bot)
await setup_sos_cog(self.bot)
await setup_event_cog(self.bot, event_reminder_engine=self.event_reminder_engine)
await setup_ranking_cog(
    self.bot,
    processor=self.ranking_processor,
    storage=self.ranking_storage,
)  # ← RankingCog mounted HERE
```

**Ranking Cog Setup Function (Line 2564):**
```python
async def setup(bot, processor, storage):
    kvk_tracker = getattr(bot, "kvk_tracker", None)
    await bot.add_cog(RankingCog(bot, processor, storage, kvk_tracker=kvk_tracker), override=True)
```

### No Double-Registration Detected
- ✅ `ui_groups.kvk` is created ONCE in `core/ui_groups.py`
- ✅ `RankingCog.ranking` subgroup references the same `ui_groups.kvk` parent
- ✅ `override=True` prevents CommandAlreadyRegistered errors
- ✅ Only ONE cog (`RankingCog`) defines ranking commands
- ✅ No other cogs import or create duplicate Group() instances

---

## PHASE 3 — Confirm Actual Command Tree in Discord

### Expected Command Structure

```
/kvk
  └─ /kvk ranking
       ├─ /kvk ranking submit ← WORKS
       ├─ /kvk ranking view
       ├─ /kvk ranking leaderboard
       ├─ /kvk ranking stats
       ├─ /kvk ranking verify
       ├─ /kvk ranking delete
       ├─ /kvk ranking refresh_cache
       ├─ /kvk ranking validate_all
       ├─ /kvk ranking debug_confidence
       └─ /kvk ranking backfill

/rankings (standalone, not in group)
/ranking_compare_me (standalone, not in group)
/ranking_compare_others (standalone, not in group)
```

### User-Reported Issue
**Original complaint:** "KVK and rankings appearing as duplicates"

**Actual behavior:** Not true duplicates — user likely confused by:
1. `/kvk ranking submit` (subgroup command) ✅ WORKS
2. `/rankings` (root-level command) — Different command entirely

**Discord UI shows both:**
- `/kvk` appears as a top-level group
- `/rankings` appears as a separate top-level command
- This is **BY DESIGN** — they serve different purposes

---

## PHASE 4 — Narrow the /submit Failure Path

### Command Path Analysis

**Entry Point:**
```python
@ranking.command(name="submit", ...)
async def submit_ranking(self, interaction, screenshot, stage, day):
```

**Call Chain:**
1. `submit_ranking()` — Line 724
2. `_check_rankings_channel()` — Validates channel permissions
3. `_resolve_kvk_run()` — Gets active KVK run from tracker
4. `_validate_submission_payload()` — OCR + data extraction
5. R8 confidence-based validation — Lines 800-900
6. Storage call — `self.storage.record_ranking(...)`

### Function Signature (from validation flow)
```python
validation = await self._validate_submission_payload(
    interaction=interaction,
    screenshot=screenshot,
    stage_value=stage,
    day=day,
    kvk_run=kvk_run,
)
# Returns: SubmissionValidationResult(ranking, stage_type, normalized_day, event_week, existing_entry)
```

### Storage Contract (Line ~900-1000)
```python
record = self.storage.record_ranking(
    user_id=user_id,
    username=player_name,
    guild_id=guild_id,
    guild_tag=guild_tag,
    stage_type=stage_type.name.lower(),
    day=normalized_day,
    score=ranking.score,
    rank=ranking.rank,
    event_week=validation.event_week,
    screenshot_url=screenshot.url,
    kvk_run_id=kvk_run.id if kvk_run else None,
    confidence=confidence,
    raw_ocr_result=json.dumps(confidence_map),
)
```

### Potential Failure Points
❌ **No obvious signature mismatch detected**  
✅ Function parameters match storage contract  
✅ Returns are handled correctly  
⚠️ **Exception swallowing:** Possible silent failures in:
- OCR processing (caught and converted to `SubmissionValidationError`)
- Storage layer (no try-except wrapper in submit_ranking)

---

## PHASE 5 — Determine If There Are Two Separate Storage Paths

### Single Storage Engine
**File:** `discord_bot\core\engines\ranking_storage_engine.py`

### Table Schema
```sql
CREATE TABLE IF NOT EXISTS event_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    username TEXT,
    guild_id TEXT NOT NULL,
    guild_tag TEXT,
    stage_type TEXT NOT NULL,  -- 'prep' or 'war'
    day INTEGER,
    score INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    event_week TEXT,
    timestamp REAL NOT NULL,
    screenshot_url TEXT,
    kvk_run_id TEXT,  -- Foreign key to kvk_runs
    confidence REAL,
    raw_ocr_result TEXT,
    UNIQUE(user_id, guild_id, stage_type, day, kvk_run_id)
)
```

### INSERT Operation
```python
def record_ranking(self, user_id, username, guild_id, guild_tag, stage_type, day, score, rank, 
                   event_week, screenshot_url, kvk_run_id=None, confidence=None, raw_ocr_result=None):
    cursor.execute("""
        INSERT INTO event_rankings (...)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, guild_id, stage_type, day, kvk_run_id) DO UPDATE SET ...
    """, (user_id, username, guild_id, guild_tag, stage_type, day, score, rank, 
          event_week, time.time(), screenshot_url, kvk_run_id, confidence, raw_ocr_result))
```

### No Duplicate Storage Paths
- ✅ Only ONE table: `event_rankings`
- ✅ Only ONE storage engine: `RankingStorageEngine`
- ✅ Only ONE cog calls storage: `RankingCog`
- ✅ UPSERT conflict resolution prevents duplicate rows

---

## PHASE 6 — Root Cause Lock-in

### 🎯 PRIMARY ROOT CAUSE

**THERE IS NO DUPLICATION BUG.**

The user is confused by Discord's UI presentation of:
1. **Group commands:** `/kvk ranking submit` (nested under /kvk)
2. **Standalone commands:** `/rankings`, `/ranking_compare_me`, `/ranking_compare_others`

These are **intentionally separate commands** defined in the same cog:
- **Grouped commands** (`@ranking.command`) → For submission workflow
- **Standalone commands** (`@app_commands.command`) → For viewing/comparison operations

### Why This Design Exists
- Discord limits subgroups to 2 levels: `/top-level/subgroup/command`
- Can't nest further: `/kvk/ranking/compare/me` ← INVALID
- Solution: Comparison commands placed at root level

### Secondary Observation: Naming Confusion
- `/kvk ranking submit` — Uses singular "ranking" (subgroup)
- `/rankings` — Uses plural (standalone command)
- This minor inconsistency may contribute to user confusion

---

## ✅ RESOLUTION RECOMMENDATIONS

### Option 1: Document the Behavior (Recommended)
Add help text explaining the command structure:
```
/kvk ranking submit - Submit your KVK score
/rankings - View historical KVK results (separate command)
/ranking_compare_me - Compare your performance
```

### Option 2: Rename for Clarity
Consider renaming standalone commands:
- `/rankings` → `/kvk_history`
- `/ranking_compare_me` → `/kvk_compare_me`
- `/ranking_compare_others` → `/kvk_compare_others`

This would make it obvious they're related but separate from the `/kvk ranking` subgroup.

### Option 3: Consolidate Under /kvk (Breaking Change)
Move comparison commands into the subgroup:
- `/kvk ranking compare_me`
- `/kvk ranking compare_others`
- `/kvk ranking history`

**Requires code refactor:** Change from `@app_commands.command` to `@ranking.command`

---

## 📊 DIAGNOSTIC SUMMARY

| Check | Status | Notes |
|-------|--------|-------|
| Double Group() creation | ✅ PASS | Only one instance in ui_groups.py |
| Multiple cog registration | ✅ PASS | Only RankingCog defines ranking commands |
| Load order issues | ✅ PASS | Groups registered before cogs mount |
| Storage duplication | ✅ PASS | Single table, single engine |
| Signature mismatch | ✅ PASS | Parameters align correctly |
| Silent exception swallow | ⚠️ POSSIBLE | OCR errors converted to user-facing messages |
| Command tree conflict | ✅ NO BUG | "Duplication" is intentional design |

---

## 🔍 IF /submit IS ACTUALLY FAILING

If the user reports that `/kvk ranking submit` returns errors:

### Check These:
1. **RANKINGS_CHANNEL_ID** environment variable set correctly
2. **kvk_tracker** engine initialized and attached to bot
3. **Active KVK run** exists (call `/event_create` to start one)
4. **OCR dependencies** installed (Tesseract, EasyOCR, OpenCV)
5. **Database permissions** (rankings.db writable)
6. **Screenshot format** (PNG/JPG, readable text)

### Debugging Steps:
```python
# Check bot attributes
print(hasattr(bot, 'kvk_tracker'))  # Should be True
print(hasattr(bot, 'ranking_storage'))  # Should be True

# Check KVK run state
kvk_tracker.get_active_run(guild_id)  # Should return KVKRun object

# Test OCR directly
processor = bot.ranking_processor
result = await processor.process_screenshot(image_bytes)
print(result.ranking_data)  # Should contain score/rank
```

---

**End of Diagnostic Report**
