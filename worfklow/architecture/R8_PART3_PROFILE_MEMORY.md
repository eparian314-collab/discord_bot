# ✅ R8-PART3: Player Profile Memory Layer - COMPLETE

## Implementation Summary

**File Modified**: `discord_bot/core/engines/ranking_storage_engine.py`  
**Lines Changed**: +53 lines added  
**Status**: ✅ Compiled successfully, no errors

## Changes Made

### 1. Database Schema: `player_profile` Table

**Location**: `_ensure_tables()` method (after event_rankings indexes, before event_submissions)

```sql
CREATE TABLE IF NOT EXISTS player_profile (
    user_id INTEGER PRIMARY KEY,
    player_name TEXT,
    guild TEXT
)
```

**Purpose**: Persistent memory of user's guild + player name for intelligent auto-correction

---

### 2. Profile Helper Methods

**Location**: Added before `save_or_update_ranking()` method

#### `_get_profile(user_id: int) -> Optional[Dict]`
- Fetches cached profile from `player_profile` table
- Returns: `{"player_name": str, "guild": str}` or `None`
- Uses connection pooling pattern (get → query → maybe_close)

#### `_update_profile(user_id: int, player_name: str, guild: str)`
- Upserts profile using `INSERT ... ON CONFLICT ... DO UPDATE`
- Updates both `player_name` and `guild` on conflict
- Commits immediately after update

---

### 3. Smart Correction Logic in `save_or_update_ranking()`

**Location**: Inserted at method start (after docstring, before duplicate check)

#### Guild Correction (Auto-Fix)
```python
guild_confidence = getattr(ranking, 'confidence_map', {}).get('guild', 1.0)
if guild_confidence < 0.95:
    if user_profile and user_profile.get('guild'):
        ranking.guild_tag = user_profile['guild']  # Use cached guild
```

**Trigger**: Guild OCR confidence < 0.95  
**Action**: Replace OCR guild with cached guild from profile

#### Player Name Correction (Smart Rename Detection)

**Case 1: Low Confidence OCR (< 0.98)**
```python
if ranking.player_name != user_profile['player_name']:
    if name_confidence < 0.98:
        ranking.player_name = user_profile['player_name']  # Keep old name
```
**Trigger**: Name differs from cache AND confidence < 0.98  
**Action**: Use cached name (treat as OCR error)

**Case 2: High Confidence OCR (≥ 0.98)**
```python
else:  # name_confidence >= 0.98
    # Accept rename and update stored profile
    self._update_profile(
        int(ranking.user_id),
        ranking.player_name,
        ranking.guild_tag or ""
    )
```
**Trigger**: Name differs from cache AND confidence ≥ 0.98  
**Action**: Accept as intentional rename, update profile

**Case 3: First-Time Submission**
```python
else:  # No existing profile
    self._update_profile(
        int(ranking.user_id),
        ranking.player_name,
        ranking.guild_tag or ""
    )
```
**Trigger**: No cached profile exists  
**Action**: Create new profile entry

---

## Behavior Matrix

| Scenario | Guild Conf. | Name Conf. | Cached Guild | Cached Name | Result |
|----------|-------------|------------|--------------|-------------|--------|
| First submission | Any | Any | None | None | **Create profile** |
| Messy guild OCR | < 0.95 | Any | "ABC" | "Player1" | **Use cached guild "ABC"** |
| Messy name OCR | Any | < 0.98 | "ABC" | "Player1" | **Use cached name "Player1"** |
| Intentional rename | Any | ≥ 0.98 | "ABC" | "OldName" | **Accept new name, update profile** |
| Perfect OCR | ≥ 0.95 | ≥ 0.98 | "ABC" | "Player1" | **Use OCR values, update profile if changed** |

---

## Integration Points

### Upstream Dependency: ScreenshotProcessor
**Required**: `RankingData` must have `confidence_map` attribute

```python
class RankingData:
    ...
    confidence: float = 1.0
    confidence_map: Dict[str, float] = field(default_factory=dict)
```

**Fields in confidence_map**:
- `"guild"`: 0.0-1.0 confidence for guild tag extraction
- `"player_name"`: 0.0-1.0 confidence for player name extraction

### Downstream Effect: ranking_cog.py
**No changes required** - profile memory operates transparently within storage layer

---

## Database Migration

### For Existing Databases
```sql
-- Run once on production DB
CREATE TABLE IF NOT EXISTS player_profile (
    user_id INTEGER PRIMARY KEY,
    player_name TEXT,
    guild TEXT
);
```

**Migration Strategy**: Table creation happens automatically in `_ensure_tables()`, so:
- New installations: Created on first run
- Existing installations: Created on next bot startup
- No data loss: Existing `event_rankings` table unchanged

---

## Testing Checklist

- [ ] **Profile Creation**: First-time submission creates profile entry
- [ ] **Guild Auto-Fix**: Low guild confidence uses cached value
- [ ] **Name Stability**: Low name confidence preserves cached name
- [ ] **Intentional Rename**: High confidence name change updates profile
- [ ] **No Regression**: Existing submissions without confidence_map still work (defaults to 1.0)
- [ ] **Connection Safety**: Standalone mode closes connections properly
- [ ] **GameStorageEngine Mode**: Shared connection mode works correctly

---

## Code Quality

✅ **Compilation**: No syntax errors  
✅ **Type Safety**: Uses `Optional[Dict]` return types  
✅ **Error Handling**: Try-finally ensures connection cleanup  
✅ **SQL Injection**: Parameterized queries used throughout  
✅ **Idempotency**: `ON CONFLICT DO UPDATE` ensures safe retries  
✅ **Defaults**: Uses `getattr(..., default)` to handle missing confidence attributes

---

## Performance Impact

**Minimal**: 
- Profile lookup: Single indexed SELECT (O(1) with PRIMARY KEY)
- Profile update: Single UPSERT (O(1) with PRIMARY KEY)
- No additional loops or O(n) operations
- Executes only once per submission

**Estimated Overhead**: < 5ms per submission

---

## Future Enhancements

### Possible Additions (Not in Scope)
1. **Name Lock Cooldown**: Prevent rename for 24h after change
2. **Guild Transfer Detection**: Detect when user joins new guild
3. **Profile History**: Track name/guild change history
4. **Multi-Server Profiles**: Separate profiles per Discord server
5. **Confidence Tuning**: Log correction frequency to optimize thresholds

---

## Deployment Checklist

- [x] Code implemented
- [x] Syntax validated (py_compile)
- [x] No linting errors
- [ ] Unit tests written
- [ ] Integration test with mock RankingData
- [ ] Integration test with ScreenshotProcessor
- [ ] Manual test with Discord bot
- [ ] Monitor profile table growth
- [ ] Validate correction accuracy

---

## Related Files

**Modified**:
- `discord_bot/core/engines/ranking_storage_engine.py` (✅ this implementation)

**Requires Updates**:
- `discord_bot/core/engines/screenshot_processor.py` (add `confidence_map` to RankingData)

**Unchanged**:
- `discord_bot/cogs/ranking_cog.py` (profile memory is transparent to cog layer)
- `R8_CONFIDENCE_UI_IMPLEMENTATION.md` (UI layer unchanged)

---

## Success Criteria

✅ **No new files created**  
✅ **No new directories created**  
✅ **No architecture changes**  
✅ **No new commands added**  
✅ **No UI interactions added**  
✅ **Integrates cleanly with R8-PART2 (confidence UI)**  
✅ **Works with missing confidence_map (defaults to 1.0)**  
✅ **Compiles without errors**

**Status**: ✅ **READY FOR TESTING**
