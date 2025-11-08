# ✅ PHASE/DAY LOGIC IMPLEMENTATION

## Authoritative Rules Applied

### Phase Detection & Day Logic

```
IF PHASE == PREP:
    day ∈ {1, 2, 3, 4, 5, -1 (Overall)}
    War-day inputs are invalid.
    Storage key = (user, event_id, phase="prep", day)

IF PHASE == WAR:
    day = None (no subdivisions)
    War score overwrites previous war submissions.
    Storage key = (user, event_id, phase="war", day=NULL)
```

## Implementation Changes

### 1. ScreenshotProcessor (`screenshot_processor.py`)

**Added:**
- `RankingCategory.PREP_OVERALL` - For overall prep aggregation
- `RankingCategory.WAR_TOTAL` - For war stage combined score

**Enhanced `_extract_stage_type()`:**
- Detects prep/war from keywords ('prep', 'preparation', 'war')
- Detects prep from day selector UI presence
- Returns StageType.PREP, StageType.WAR, or StageType.UNKNOWN

**Enhanced `_extract_day_number()`:**
- Returns 1-5 for specific prep days
- Returns -1 for "Overall" prep aggregation
- Returns None for war stage (no day component)
- Looks for highlight markers and day selector UI

### 2. RankingCog (`ranking_cog.py`)

**Updated `/kvk ranking submit` Command:**
```python
@app_commands.describe(
    screenshot="Upload your ranking screenshot",
    stage="Which stage is this submission for?",
    day="[PREP ONLY] Event day (1-5) or Overall. Leave blank for War stage.",
)
async def submit_ranking(
    screenshot: discord.Attachment,
    stage: str,
    day: Optional[int] = None  # NOW OPTIONAL
)
```

**Day Choices Added:**
- Day 1 - Construction (value=1)
- Day 2 - Research (value=2)
- Day 3 - Resource & Mob (value=3)
- Day 4 - Hero (value=4)
- Day 5 - Troop Training (value=5)
- Overall Prep (value=-1)

**Validation Logic (`_validate_submission_payload`):**
```python
if stage_type == StageType.PREP:
    # PREP REQUIRES day
    if day is None:
        raise Error("Prep stage requires day selection")
    if day == -1:
        normalized_day = -1  # Overall
    elif 1 <= day <= 5:
        normalized_day = day
    else:
        raise Error("Invalid day")
else:  # WAR
    # WAR REJECTS day input
    if day is not None:
        raise Error("War stage does not use day subdivisions")
    normalized_day = None
```

**Display Functions Updated:**

`_format_day_label()`:
- `day=None` or `StageType.WAR` → "War Stage Total"
- `day=-1` → "Prep Stage Overall"
- `day=1-5` → "Day X - [Category Name]"

`_normalize_day()`:
- WAR → None (no day component)
- PREP → keeps day value (1-5 or -1)

`_resolve_entry_stage()`:
- `day_number=None` → WAR
- `day_number=1-5 or -1` → PREP
- Legacy `day_number=6` → WAR (backward compatibility)

### 3. Database Schema

**Existing Schema (No Changes Needed):**
```sql
CREATE TABLE event_rankings (
    ...
    stage_type TEXT NOT NULL,
    day_number INTEGER,  -- NULL for WAR, -1 for Overall Prep, 1-5 for Prep days
    ...
    UNIQUE(user_id, guild_id, event_week, stage_type, day_number)
)
```

**Storage Keys:**
- PREP Day 1: `(user, guild, event_week, "Prep Stage", 1)`
- PREP Overall: `(user, guild, event_week, "Prep Stage", -1)`
- WAR: `(user, guild, event_week, "War Stage", NULL)`

## User Experience Flow

### Submitting Prep Day Ranking
1. User: `/kvk ranking submit stage:prep day:3 screenshot:[file]`
2. Bot validates: stage=prep, day required, day=3 is valid
3. OCR processes screenshot
4. Stores with key: `(user, event, "prep", 3)`
5. Response: "✅ Submitted Day 3 - Resource & Mob ranking"

### Submitting Overall Prep Ranking
1. User: `/kvk ranking submit stage:prep day:-1 screenshot:[file]`
2. Bot validates: stage=prep, day=-1 is valid
3. Stores with key: `(user, event, "prep", -1)`
4. Response: "✅ Submitted Prep Stage Overall ranking"

### Submitting War Ranking
1. User: `/kvk ranking submit stage:war screenshot:[file]`
2. Bot validates: stage=war, day must be blank
3. If day provided → Error: "War stage does not use day subdivisions"
4. Stores with key: `(user, event, "war", NULL)`
5. Response: "✅ Submitted War Stage Total ranking"

## OCR Parsing Rules

### Step 1 — Detect Phase
- UI tab highlighted = "Preparation" → PREP
- UI tab highlighted = "War" → WAR
- Day selector visible → PREP
- No day selector → WAR

### Step 2 — Extract Day (PREP only)
- Find highlighted day in horizontal menu: [Day 1][Day 2][Day 3][Day 4][Day 5][Overall]
- "Overall" highlighted → day = -1
- Day X highlighted → day = X

### Step 3 — Store Clean Data
```python
RankingEntry(
    user_id,
    player_name,
    player_guild,
    player_server,
    rank_position,      # e.g. 94
    score_value,        # e.g. 794885
    phase="prep" or "war",
    day=1..5 or -1 or None  # None for WAR
)
```

## Migration & Backward Compatibility

**Legacy Support:**
- Old entries with `day_number=6` are interpreted as WAR
- `_format_day_label()` handles day=6 → "War Stage Total"
- `_resolve_entry_stage()` treats day=6 as WAR

**No Database Migration Required:**
- Schema already allows NULL day_number
- UNIQUE constraint handles NULL correctly (multiple NULL values allowed in SQLite)

## Testing Checklist

- [ ] Submit prep day 1-5 (should succeed)
- [ ] Submit prep overall with day=-1 (should succeed)
- [ ] Submit war with day=None (should succeed)
- [ ] Submit war with day=1 (should fail with clear error)
- [ ] Submit prep without day (should fail with clear error)
- [ ] View leaderboard filtered by prep day
- [ ] View leaderboard filtered by war stage
- [ ] Verify duplicate detection works for all combinations
- [ ] Verify legacy day=6 entries display correctly

## Files Modified

1. `discord_bot/core/engines/screenshot_processor.py`
   - Enhanced phase/day detection
   - Added PREP_OVERALL and WAR_TOTAL categories

2. `discord_bot/cogs/ranking_cog.py`
   - Made `day` parameter optional
   - Added day choices dropdown
   - Implemented authoritative validation logic
   - Updated display formatting

## Status

✅ Phase/day logic implemented according to authoritative rules
✅ Database schema compatible (no migration needed)
✅ Backward compatibility maintained (legacy day=6 supported)
✅ User-facing command updated with clear guidance
⏳ Ready for testing and validation

---

**Next Steps:**
1. Test all submission scenarios
2. Verify OCR accuracy for phase/day detection
3. Monitor for edge cases in production
4. Enhance OCR patterns if needed based on real screenshot data
