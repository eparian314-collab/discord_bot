# Canonical Phase/Day Migration Summary

## Overview

Migrated the ranking system from legacy `StageType` enum + `day_number` integer to a canonical model using:
- **phase**: `"prep"` or `"war"` (string)
- **day**: `1-5` (int), `"overall"` (string), or `None`

## Migration Rules

### Phase Conversion
- `StageType.PREP` → `"prep"`
- `StageType.WAR` → `"war"`

### Day Conversion
**Prep Phase:**
- Day 1-5 → integer 1-5
- Day -1 (legacy "overall") → string `"overall"`
- Day 6 (legacy war marker in prep context) → `None` with phase=`"war"`

**War Phase:**
- Always `None` (war has no daily subdivisions)

## Database Schema Changes

### Added Columns
```sql
ALTER TABLE event_rankings ADD COLUMN phase TEXT;
ALTER TABLE event_rankings ADD COLUMN day TEXT;
```

### Data Migration
```sql
-- Migrate phase
UPDATE event_rankings 
SET phase = CASE 
    WHEN stage_type = 'War Stage' THEN 'war'
    WHEN stage_type = 'Prep Stage' THEN 'prep'
    ELSE 'war'
END;

-- Migrate day
UPDATE event_rankings 
SET day = CASE 
    WHEN day_number IS NULL OR day_number = 6 THEN NULL
    WHEN day_number = -1 THEN 'overall'
    ELSE CAST(day_number AS TEXT)
END;
```

### Unique Constraint (Pending Update)
**Current:** `(user_id, guild_id, event_week, stage_type, day_number)`
**Target:** `(user_id, guild_id, event_week, phase, day)`

## Code Changes

### ✅ Completed

#### 1. `screenshot_processor.py`
- **RankingData dataclass**: Added `phase: str` and `day: Optional[int | str]`
- **Legacy fields**: Kept `stage_type` and `day_number` for backward compatibility
- **_determine_phase_and_day()**: New method that detects phase/day from OCR text
  - Detects day selector UI → phase="prep"
  - No day selector → phase="war"
  - Parses highlighted day (1-5 or "overall")

#### 2. `ranking_storage_engine.py`
- **_ensure_event_ranking_columns()**: Adds phase/day columns with migration logic
- **save_ranking()**: Stores both canonical (phase, day) and legacy (stage_type, day_number)
  - Converts day to string for storage: `day_str = str(ranking.day) if ranking.day else None`
  - Computes legacy values for backward compatibility
- **check_duplicate_submission()**: Updated signature to accept `phase: str, day: Optional[int|str]`
  - Queries: `WHERE phase = ? AND day IS ?`
- **get_guild_leaderboard()**: Updated to use canonical `phase` and `day` parameters
  - Queries canonical columns with string day comparison

#### 3. `ranking_cog.py`
- **submit_ranking command**: Added optional day parameter with choices (1-5, Overall)
- **Validation logic**: Enforces canonical rules
  - Prep requires day (1-5 or -1 for "overall")
  - War rejects day input (must be None)
- **Duplicate check call**: Updated to pass `phase` and `normalized_day`
- **Leaderboard commands**: Updated to use canonical `phase` and `day` parameters

### ⏳ Pending

#### 1. `ranking_cog.py` - Internal Methods
- **_normalize_day()**: Still uses `StageType` parameter
- **_format_day_label()**: Still uses `StageType` parameter
- **_resolve_entry_stage()**: Still returns `StageType` enum
- **_aggregate_entries()**: Still uses `StageType.PREP` and `StageType.WAR`
- **SubmissionValidationResult.stage_type**: Still uses `StageType` field

#### 2. Database Schema
- **UNIQUE constraint**: Needs update from `(stage_type, day_number)` to `(phase, day)`

#### 3. Query Methods
- **get_user_rankings()**: No filtering by phase/day yet (returns all)
- **get_ranking_history()**: May need canonical column support
- **get_submission_stats()**: May need canonical column support

## Validation Rules

### Command Input
```python
if phase == "prep":
    if day is None:
        raise Error("Prep requires day selection")
    if day == -1:
        normalized_day = "overall"
    elif 1 <= day <= 5:
        normalized_day = day
    else:
        raise Error("Invalid day")
else:  # war
    if day is not None:
        raise Error("War does not use day subdivisions")
    normalized_day = None
```

### Storage Format
```python
# Canonical storage
phase = "prep" | "war"
day_str = str(ranking.day) if ranking.day else None  # "1"-"5", "overall", or NULL

# Legacy compatibility
stage_type_str = "Prep Stage" if phase == "prep" else "War Stage"
day_number = -1 if day == "overall" else day if isinstance(day, int) else None
```

## Testing Checklist

### Manual Test Cases
- [ ] Submit prep day 1 → verify phase="prep", day="1"
- [ ] Submit prep day 5 → verify phase="prep", day="5"
- [ ] Submit prep overall → verify phase="prep", day="overall"
- [ ] Submit war → verify phase="war", day=NULL
- [ ] Duplicate detection for prep day 1
- [ ] Duplicate detection for prep overall
- [ ] Duplicate detection for war
- [ ] Leaderboard filtering by phase="prep"
- [ ] Leaderboard filtering by day=3
- [ ] View user rankings showing canonical fields

### Migration Validation
- [ ] Run `_ensure_event_ranking_columns()` on existing database
- [ ] Verify all existing prep entries have phase="prep"
- [ ] Verify all existing war entries have phase="war"
- [ ] Verify day conversion: -1 → "overall", 1-5 → "1"-"5", NULL/6 → NULL
- [ ] Check for any NULL phase values (should be zero)

## Backward Compatibility

### Database
- **Dual storage**: Both canonical and legacy columns populated
- **Legacy queries**: Can still query by `stage_type` and `day_number` if needed
- **Gradual migration**: Old data migrated on first `_ensure_event_ranking_columns()` call

### Code
- **RankingData**: Includes both canonical and legacy fields
- **StageType enum**: Still exists for internal formatting methods
- **API surface**: Commands now use string "prep"/"war" but internal code can use both

## Rollout Plan

1. ✅ **Phase 1**: Update storage layer with dual format
2. ✅ **Phase 2**: Update command layer to use canonical input/output
3. ⏳ **Phase 3**: Update internal helper methods
4. ⏳ **Phase 4**: Update UNIQUE constraint (requires table rebuild)
5. ⏳ **Phase 5**: Remove legacy columns after validation period
6. ⏳ **Phase 6**: Remove StageType enum after all code updated

## Notes

- **String day storage**: Day stored as TEXT to handle "overall" string
- **NULL vs "None"**: War entries have `day=NULL` in SQL, `day=None` in Python
- **Type union**: `day: Optional[int | str]` supports 1-5 (int) and "overall" (str)
- **Query comparison**: Use `IS` operator for NULL: `WHERE day IS NULL`
- **Migration idempotency**: `_ensure_event_ranking_columns()` safe to call multiple times
