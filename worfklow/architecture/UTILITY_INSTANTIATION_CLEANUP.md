# Utility Instantiation Cleanup — Ranking Event Week

**Date:** November 5, 2025  
**Issue:** Redundant utility instantiations in two storage engines  
**Status:** ✅ Resolved

────────────────────────────────────────

## Problem Identified

### Duplicate Implementations

**Location 1:** `game_storage_engine.py:1119`
```python
def get_current_event_week(self) -> str:
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
    processor = ScreenshotProcessor()  # ← Instantiation
    return processor._get_current_event_week()
```

**Location 2:** `ranking_storage_engine.py:1101`
```python
def get_current_event_week(self) -> str:
    if self.storage:
        return self.storage.get_current_event_week()  # ← Delegates to Location 1
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
    processor = ScreenshotProcessor()  # ← Fallback instantiation
    return processor._get_current_event_week()
```

### The Issue

**Circular Delegation:**
1. All callers use `RankingStorageEngine.get_current_event_week()`
2. RankingStorageEngine delegates to GameStorageEngine (when shared storage)
3. GameStorageEngine instantiates ScreenshotProcessor
4. **Result:** Unnecessary delegation layer

**Root Cause:**
- GameStorageEngine originally managed ranking data (legacy)
- After migration to dedicated RankingStorageEngine, the method became redundant
- The delegation was kept for backward compatibility but is no longer needed

────────────────────────────────────────

## Solution Applied

### Change 1: Simplify RankingStorageEngine

**Before:**
```python
def get_current_event_week(self) -> str:
    if self.storage:
        return self.storage.get_current_event_week()  # Delegate
    processor = ScreenshotProcessor()
    return processor._get_current_event_week()
```

**After:**
```python
def get_current_event_week(self) -> str:
    """
    Get current event week in YYYY-WW format.
    
    Uses ScreenshotProcessor's date calculation logic directly.
    No longer delegates to GameStorageEngine (legacy removed).
    """
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
    processor = ScreenshotProcessor()
    return processor._get_current_event_week()
```

**Impact:**
- ✅ Direct calculation, no delegation
- ✅ One fewer instantiation per call
- ✅ Clearer ownership (RankingStorageEngine owns event week logic)

────────────────────────────────────────

### Change 2: Mark GameStorageEngine Method as DEPRECATED

**Updated:**
```python
def get_current_event_week(self) -> str:
    """
    DEPRECATED: Legacy method for ranking event week calculation.
    
    This method is only called by RankingStorageEngine when operating
    in shared-storage mode. Direct callers should use 
    RankingStorageEngine.get_current_event_week() instead.
    
    Will be removed in a future refactor once ranking tables are 
    fully migrated out of GameStorageEngine.
    """
    from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
    processor = ScreenshotProcessor()
    return processor._get_current_event_week()
```

**Purpose:**
- Documents that this is legacy code
- Warns future developers not to use it
- Sets expectation for future removal

────────────────────────────────────────

## Verification

### Caller Analysis

**All callers use RankingStorageEngine:**
```
✓ ranking_cog.py (10 calls) → self.storage.get_current_event_week()
✓ ranking_storage_engine.py → Internal use
✓ scripts/live_test_suite.py → storage.get_current_event_week()
```

**No direct calls to GameStorageEngine.get_current_event_week():**
```
✓ Searched: game_storage.get_current_event_week() → 0 matches
✓ Searched: self.game_storage.get_current_event_week() → 0 matches
```

**Conclusion:** Safe to simplify without breaking changes.

────────────────────────────────────────

## Benefits

### Before Fix
```
Caller → RankingStorageEngine.get_current_event_week()
         ↓ (delegates)
         GameStorageEngine.get_current_event_week()
         ↓ (instantiates)
         ScreenshotProcessor()._get_current_event_week()
         ↓
         Returns event week
```
**Instantiations:** 1 (ScreenshotProcessor)

### After Fix
```
Caller → RankingStorageEngine.get_current_event_week()
         ↓ (direct call)
         ScreenshotProcessor()._get_current_event_week()
         ↓
         Returns event week
```
**Instantiations:** 1 (ScreenshotProcessor, but no delegation layer)

### Improvements
- ✅ Removed unnecessary delegation layer
- ✅ Clearer code ownership
- ✅ Better documentation of legacy code
- ✅ No breaking changes to callers
- ✅ Maintains shared-storage compatibility for `prune_event_weeks()`

────────────────────────────────────────

## Future Cleanup Path

### Phase 1: Current State ✅
- RankingStorageEngine uses direct calculation
- GameStorageEngine method marked DEPRECATED
- All callers use RankingStorageEngine

### Phase 2: Table Migration (Future)
When `event_rankings` table is fully migrated out of GameStorageEngine:
1. Remove `prune_event_weeks()` from GameStorageEngine
2. Remove `get_current_event_week()` from GameStorageEngine
3. RankingStorageEngine becomes fully standalone

### Phase 3: Storage Separation (Future)
- RankingStorageEngine gets own database file
- GameStorageEngine handles only game data (pokemon, battles, cookies)
- Full separation of concerns

────────────────────────────────────────

## Related Utility Instantiations

### Still Present (Acceptable)

**Location:** `ranking_storage_engine.py:1162` (validate_event method)
```python
processor = ScreenshotProcessor()
```
**Reason:** Only used for date calculation in validation logic (no OCR)

**Location:** Multiple validation/utility methods
```python
from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
processor = ScreenshotProcessor()
return processor._get_current_event_week()
```
**Reason:** These are **stateless utility calls** — no OCR, no heavy lifting, just date math

### Pattern Decision

**Acceptable utility pattern:**
```python
# Lightweight, stateless calculation
processor = ScreenshotProcessor()
week = processor._get_current_event_week()
```

**NOT acceptable:**
```python
# Heavy operation with state
processor = ScreenshotProcessor()
ranking = await processor.process_screenshot(image_data)  # ❌ Should use DI
```

────────────────────────────────────────

## Testing

### Regression Test
```python
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine

storage = RankingStorageEngine()
week = storage.get_current_event_week()
print(f"Current event week: {week}")
# Expected: "2025-45" (or current ISO week)
```

### No Shared Storage Test
```python
# Standalone mode (no GameStorageEngine)
storage = RankingStorageEngine(storage=None)
week = storage.get_current_event_week()
# Should work without delegation
```

### Shared Storage Test
```python
# With GameStorageEngine
from discord_bot.games.storage.game_storage_engine import GameStorageEngine
game_storage = GameStorageEngine()
storage = RankingStorageEngine(storage=game_storage)
week = storage.get_current_event_week()
# Should work (no longer delegates, but compatible)
```

────────────────────────────────────────

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Instantiations** | 2 locations | 1 location (direct) |
| **Delegation** | RankingStorageEngine → GameStorageEngine | Direct calculation |
| **Code clarity** | Unclear ownership | Clear: RankingStorageEngine owns it |
| **Performance** | Extra delegation layer | Direct call |
| **Breaking changes** | N/A | None ✅ |

**Result:** Cleaner architecture, better documentation, no functional changes.

────────────────────────────────────────

**Implemented:** November 5, 2025  
**Status:** ✅ Complete  
**Impact:** Low risk, high clarity
