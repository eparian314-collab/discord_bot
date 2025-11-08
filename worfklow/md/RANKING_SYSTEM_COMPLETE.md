# Top Heroes KVK Ranking System - Complete Documentation

**Version**: 2.2  
**Last Updated**: November 2025  
**Status**: Production Ready ✅

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [KVK Cycle Management](#kvk-cycle-management)
4. [Ranking Submission Flow](#ranking-submission-flow)
5. [OCR Processing](#ocr-processing)
6. [Confidence-Based Validation](#confidence-based-validation)
7. [Database Schema](#database-schema)
8. [Commands Reference](#commands-reference)
9. [Event Management Integration](#event-management-integration)
10. [Testing & Debugging](#testing--debugging)

---

## System Overview

### What It Does

The KVK Ranking System tracks Top Heroes Kingdom vs Kingdom (KVK) event performance across:
- **14-day event cycles** with automatic lifecycle management
- **6-day event model**: 5 prep days + 1 war day
- **Screenshot-based submissions** with EasyOCR extraction
- **Confidence-based validation** (R8 system)
- **Player profile memory** for OCR correction
- **Historical tracking** per run number
- **Guild leaderboards** and analytics

### Key Features

✅ **Automatic KVK Cycle Detection** - Creates tracking window when event is scheduled  
✅ **Smart OCR Extraction** - EasyOCR with confidence scoring (lazy-loaded)  
✅ **Phase/Day Validation** - Canonical model (prep/war, 1-5/overall/None)  
✅ **Duplicate Prevention** - Detects and handles re-submissions  
✅ **Profile Correction** - Remembers player guild/name for OCR fixes  
✅ **Test Mode** - Isolated test KVK runs for debugging  
✅ **Auto-Closure** - 14-day window with automatic cleanup  

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    RANKING SYSTEM FLOW                       │
└─────────────────────────────────────────────────────────────┘

1. EVENT CREATION (Admin)
   └─> /event_create title:"Test KVK" ...
       └─> EventManagementCog detects "kvk" in title
           └─> KVKTracker.ensure_run() creates cycle
               └─> 14-day window opened

2. RANKING SUBMISSION (User)
   └─> /kvk ranking submit <screenshot>
       └─> RankingCog validates channel/permissions
           └─> ScreenshotProcessor (EasyOCR + confidence)
               └─> Confidence branching (R8):
                   ├─> ≥0.99: Auto-accept
                   ├─> 0.95-0.989: Confirm button
                   └─> <0.95: Correction modal
                       └─> RankingStorageEngine
                           ├─> Profile memory correction
                           ├─> save_or_update_ranking()
                           └─> KVKTracker.record_submission()

3. LEADERBOARD QUERY
   └─> /kvk ranking leaderboard
       └─> KVKTracker.fetch_leaderboard()
           └─> Returns top 25 ranked by score
```

### File Structure

```
discord_bot/
├─ cogs/
│  ├─ ranking_cog.py              # Discord commands (/kvk ranking *)
│  └─ event_management_cog.py     # Event scheduling + KVK trigger
│
├─ core/engines/
│  ├─ screenshot_processor.py     # EasyOCR extraction + confidence
│  ├─ ranking_storage_engine.py   # Database + profile memory
│  └─ kvk_tracker.py              # Run lifecycle management
│
└─ games/storage/
   └─ game_storage_engine.py      # SQLite connection pool
```

---

## KVK Cycle Management

### How KVK Cycles Start

**Trigger**: Admin creates event with "kvk" in title

```python
# File: event_management_cog.py
async def create_event(interaction, title, time_utc, ...):
    title_lower = title.strip().lower()
    is_kvk_event = "kvk" in title_lower
    is_test_kvk = "test kvk" in title_lower
    
    if is_kvk_event and self.kvk_tracker:
        kvk_run, created = await self.kvk_tracker.ensure_run(
            guild_id=interaction.guild.id,
            title=title,
            is_test=is_test_kvk,
            ...
        )
```

### KVK Run Lifecycle

| State | Description | Duration |
|-------|-------------|----------|
| **Active** | Submissions accepted | 14 days (default) |
| **Closed** | Read-only, no new submissions | Permanent |

### Run Types

#### Regular KVK Run
- **Trigger**: Event title contains "kvk" (e.g., "Guild KVK Offensive")
- **Run Number**: Auto-incremented (KVK-01, KVK-02, ...)
- **Permission**: Admin or Helper role
- **Label**: "KVK Run #05"

#### Test KVK Run
- **Trigger**: Event title contains "test kvk" (e.g., "Test KVK Warmup")
- **Run Number**: None (doesn't count toward sequence)
- **Permission**: Bot owner only
- **Label**: "Test KVK"
- **Isolation**: Separate tracking, no interference with production

### Phase/Day Calculation

**6-Day Event Model** (calculated from `kvk_run.started_at`):

```python
# File: ranking_cog.py._calculate_event_day()
elapsed_days = (now - kvk_run.started_at).days + 1

if elapsed_days <= 5:
    return "prep", elapsed_days  # Days 1-5: PREP
else:
    return "war", None           # Day 6+: WAR
```

**Phase Behavior**:

| Day | Phase | Day Value | User Action |
|-----|-------|-----------|-------------|
| 1 | `prep` | `1` | Submit Day 1 screenshot |
| 2 | `prep` | `2` | Submit Day 2 screenshot |
| 3 | `prep` | `3` | Submit Day 3 screenshot |
| 4 | `prep` | `4` | Submit Day 4 screenshot |
| 5 | `prep` | `5` | Submit Day 5 screenshot |
| 1-5 | `prep` | `"overall"` | Submit cumulative prep total |
| 6+ | `war` | `None` | Submit war screenshot (no days) |

---

## Ranking Submission Flow

### Command Structure

```
/kvk ranking submit
  screenshot: <image file>
  stage: "Prep" | "War" (optional, auto-calculated if omitted)
  day: 1-5 | "Overall" (required for Prep, must be blank for War)
```

### Validation Rules

#### Prep Phase
✅ **Day required** (1-5 or Overall)  
✅ **Multiple submissions allowed** (different days)  
✅ **Overwrites** if same day re-submitted  
✅ **Backfill allowed** (can submit old days)  

#### War Phase
✅ **Day must be blank** (no subdivisions)  
✅ **Overwrites** previous war submission  
❌ **Cannot specify day** (validation error)  

### Duplicate Handling

**Primary Key**: `(user_id, event_week, phase, day)`

**Overwrite Scenarios**:

| Existing | New Submission | Result |
|----------|----------------|--------|
| Prep Day 3 | Prep Day 3 | ✅ **Overwrites** |
| Prep Day 3 | Prep Day 4 | ✅ **Coexists** |
| Prep Overall | Prep Overall | ✅ **Overwrites** |
| Prep Day 3 | Prep Overall | ✅ **Coexists** |
| War | War | ✅ **Overwrites** |

---

## OCR Processing

### EasyOCR Implementation

**Lazy Loading** (prevents startup memory spike):

```python
# File: screenshot_processor.py
class ScreenshotProcessor:
    def __init__(self):
        self.reader = None  # Not loaded at startup
    
    def _ensure_reader(self):
        if self.reader is None:
            self.reader = easyocr.Reader(['en'], gpu=False)
    
    async def process_screenshot(self, image_data, ...):
        self._ensure_reader()  # Load on first use
```

### Preprocessing Pipeline

```python
# OpenCV preprocessing for game UI clarity
1. Convert to grayscale
2. Histogram equalization (improve contrast)
3. Adaptive thresholding (clarify text)
4. EasyOCR extraction with confidence
```

### Data Extraction

**Screenshot Format Detection**:

```
Expected Game UI Elements:
┌────────────────────────────────┐
│ [Prep Stage] [War Stage]  ← Phase detection
│ [Day 1][Day 2][Day 3][Day 4][Day 5][Overall] ← Day tabs
│                                 │
│ #10435  [TAO]  Mars            │ ← Player entry
│ Points: 25,200,103             │ ← Score
└────────────────────────────────┘
```

**Extracted Fields**:
- `phase`: "prep" or "war" (from highlighted stage)
- `day`: 1-5, "overall", or None (from highlighted tab)
- `guild_tag`: 3-letter code in brackets (e.g., [TAO])
- `player_name`: Text after guild tag
- `rank`: Number after # symbol
- `score`: Large number (commas removed)

---

## Confidence-Based Validation

### R8 System Overview

**Three-layer validation**:

1. **Confidence Scoring** (validators.py)
2. **UI Branching** (ranking_cog.py)
3. **Profile Memory** (ranking_storage_engine.py)

### Confidence Thresholds

| Confidence | User Experience | Logic |
|------------|-----------------|-------|
| **≥ 0.99** | ✅ Auto-accept | Instant save, green embed |
| **0.95-0.989** | ⚠️ Soft confirm | Preview + Confirm/Cancel buttons |
| **< 0.95** | 📝 Manual correction | Modal form with pre-filled fields |

### Field-Level Confidence

```python
confidence_map = {
    'guild': 0.82,        # Low confidence
    'player_name': 0.85,  # Low confidence
    'score': 0.95,        # High confidence
    'rank': 0.97          # High confidence
}

overall_confidence = sum(values) / len(values)  # 0.8975
```

### Profile Memory Correction

**Automatic OCR fixes** using cached player profiles:

```python
# File: ranking_storage_engine.py
profile = _get_profile(user_id)
# Returns: {"player_name": "Mars", "guild": "TAO"}

# Guild correction (if confidence < 0.95)
if confidence_map['guild'] < 0.95:
    ranking.guild_tag = profile['guild']  # "TAO" (corrected)

# Name correction (if differs + confidence < 0.98)
if ranking.player_name != profile['player_name']:
    if confidence_map['player_name'] < 0.98:
        ranking.player_name = profile['player_name']  # "Mars" (corrected)
    else:
        # High confidence + different = intentional rename
        _update_profile(user_id, ranking.player_name, ranking.guild_tag)
```

---

## Database Schema

### Tables

#### `kvk_runs`
Tracks KVK event cycles.

```sql
CREATE TABLE kvk_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    title TEXT NOT NULL,
    run_number INTEGER,              -- NULL for test runs
    is_test INTEGER DEFAULT 0,
    started_at TEXT NOT NULL,        -- ISO 8601 UTC
    ends_at TEXT NOT NULL,           -- ISO 8601 UTC
    closed_at TEXT,                  -- ISO 8601 UTC
    status TEXT DEFAULT 'active',    -- 'active' or 'closed'
    channel_id INTEGER,
    initiated_by TEXT,
    event_id TEXT
);
```

#### `event_rankings`
Stores individual ranking submissions.

```sql
CREATE TABLE event_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    username TEXT,
    guild_tag TEXT,
    event_week TEXT NOT NULL,        -- 'KVK-05' or 'KVK-TEST-123'
    phase TEXT NOT NULL,             -- 'prep' or 'war'
    day TEXT,                        -- '1'-'5', 'overall', or NULL
    rank INTEGER NOT NULL,
    score INTEGER NOT NULL,
    player_name TEXT,
    submitted_at TEXT NOT NULL,
    screenshot_url TEXT,
    guild_id TEXT,
    kvk_run_id INTEGER,
    is_test_run INTEGER DEFAULT 0,
    
    -- Legacy fields (backward compatibility)
    stage_type TEXT,                 -- 'Prep Stage' or 'War Stage'
    day_number INTEGER,              -- -1, 1-5, or NULL
    
    UNIQUE(user_id, guild_id, event_week, phase, day)
);
```

#### `kvk_submissions`
Links rankings to KVK runs.

```sql
CREATE TABLE kvk_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kvk_run_id INTEGER NOT NULL,
    ranking_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    day_number INTEGER,
    stage_type TEXT,
    submitted_at TEXT NOT NULL,
    is_test INTEGER DEFAULT 0,
    
    UNIQUE(kvk_run_id, user_id, day_number, stage_type),
    FOREIGN KEY(kvk_run_id) REFERENCES kvk_runs(id),
    FOREIGN KEY(ranking_id) REFERENCES event_rankings(id)
);
```

#### `player_profile`
Caches player info for OCR correction (R8 Part 3).

```sql
CREATE TABLE player_profile (
    user_id TEXT PRIMARY KEY,
    player_name TEXT,
    guild TEXT,
    updated_at TEXT
);
```

---

## Commands Reference

### User Commands

#### `/kvk ranking submit`
Submit your event ranking screenshot.

**Parameters**:
- `screenshot` (required): PNG/JPG image, max 10MB
- `stage` (optional): "Prep" or "War" (auto-calculated if omitted)
- `day` (conditional): 1-5 or "Overall" (required for Prep, blank for War)

**Examples**:
```
/kvk ranking submit screenshot:prep_day3.png stage:Prep day:3
/kvk ranking submit screenshot:prep_total.png stage:Prep day:Overall
/kvk ranking submit screenshot:war.png stage:War
/kvk ranking submit screenshot:current.png  # Auto-calculates from event day
```

**Response**: Embed showing extracted data + KVK run info

---

#### `/kvk ranking view`
View your submission history for current KVK run.

**Parameters**: None

**Shows**:
- Your submissions for active run
- Phase, day, rank, score
- Submit timestamps
- Screenshot thumbnails

---

#### `/kvk ranking leaderboard`
View guild leaderboard.

**Parameters**:
- `stage` (optional): Filter by "Prep" or "War"
- `day` (optional): Filter by specific day (1-5)

**Examples**:
```
/kvk ranking leaderboard               # All submissions
/kvk ranking leaderboard stage:Prep    # All prep days
/kvk ranking leaderboard stage:Prep day:3  # Prep Day 3 only
/kvk ranking leaderboard stage:War     # War phase only
```

**Shows**:
- Top 25 players by score
- Rank, score, player name, guild
- Medal emojis for top 3 (🥇🥈🥉)

---

### Admin Commands

#### `/event_create`
Create event and optionally start KVK cycle.

**To Start KVK**:
- Include "kvk" in title (case-insensitive)
- Example: `title:"Guild KVK Offensive"`

**To Start Test KVK** (bot owner only):
- Include "test kvk" in title
- Example: `title:"Test KVK Warmup"`

**Result**: Automatically creates 14-day KVK tracking window

---

#### `/kvk ranking report`
Admin analytics and reports.

**Parameters**:
- `run_number` (optional): Specific run to analyze

**Shows**:
- Submission statistics
- Participation rates
- Score distributions

---

#### `/kvk ranking user`
View specific user's rankings.

**Parameters**:
- `user` (required): Discord user mention

**Shows**:
- All submissions for specified user
- Historical performance across runs

---

## Event Management Integration

### Event Creation Workflow

```python
# Admin creates event
/event_create 
  title: "Kingdom KVK War"
  time_utc: "2025-11-10 12:00"
  category: "raid"
  
# System detects "kvk" in title
is_kvk_event = "kvk" in title.lower()  # True

# Automatically creates KVK cycle
if is_kvk_event:
    kvk_run, created = await kvk_tracker.ensure_run(
        guild_id=guild.id,
        title="Kingdom KVK War",
        is_test=False,
        ...
    )
    # KVK Run #6 created (if run #5 was last)
    # Window: 2025-11-10 to 2025-11-24 (14 days)
```

### Automatic Phase Detection

```python
# User submits screenshot on Day 3 of event
/kvk ranking submit screenshot:image.png

# System auto-calculates phase and day
event_day = (now - kvk_run.started_at).days + 1  # 3
phase = "prep"  # Day 3 is prep phase
day = 3

# Validates screenshot matches expected phase
# Stores with canonical values
```

---

## Testing & Debugging

### Test KVK Setup

**Create test run** (bot owner only):

```
/event_create
  title: "Test KVK Validation"
  time_utc: "2025-11-05 18:00"
  category: "raid"
```

**Verify**:
- ✅ Event created in database
- ✅ KVK run created with `is_test=1`
- ✅ Label shows "Test KVK" (not "KVK Run #X")
- ✅ Submissions accepted normally
- ✅ Doesn't increment production run counter

### Manual Testing Checklist

**Prep Phase Tests**:
- [ ] Submit Day 1 → Verify `phase="prep", day="1"`
- [ ] Submit Day 5 → Verify `phase="prep", day="5"`
- [ ] Submit Overall → Verify `phase="prep", day="overall"`
- [ ] Re-submit Day 3 → Verify overwrite behavior
- [ ] Submit Day 2 then Day 4 → Verify coexistence

**War Phase Tests**:
- [ ] Submit War → Verify `phase="war", day=NULL`
- [ ] Re-submit War → Verify overwrite
- [ ] Try submit War with day specified → Verify error

**Validation Tests**:
- [ ] Submit wrong phase → Verify rejection
- [ ] Submit image too large → Verify size error
- [ ] Submit non-image file → Verify type error

**Confidence Tests**:
- [ ] Good quality screenshot → Auto-accept (≥0.99)
- [ ] Medium quality → Soft confirm button (0.95-0.989)
- [ ] Poor quality → Correction modal (<0.95)

### Database Queries

**Check active runs**:
```sql
SELECT * FROM kvk_runs WHERE status = 'active' ORDER BY started_at DESC;
```

**Check submissions for run**:
```sql
SELECT er.*, ks.day_number 
FROM event_rankings er
JOIN kvk_submissions ks ON ks.ranking_id = er.id
WHERE ks.kvk_run_id = 5
ORDER BY er.score DESC;
```

**Check player profile cache**:
```sql
SELECT * FROM player_profile WHERE user_id = '123456789';
```

---

## Troubleshooting

### Common Issues

**"No active KVK run found"**
- Admin hasn't created event with "kvk" in title
- Current run expired (14 days passed)
- Solution: Create new event with `/event_create`

**"Screenshot validation failed"**
- Image quality too low for OCR
- Required UI elements not visible
- Solution: Take clearer screenshot showing all elements

**"Phase mismatch detected"**
- User selected Prep but screenshot shows War (or vice versa)
- Solution: Verify screenshot matches selected stage

**"Day required for Prep phase"**
- User didn't specify which prep day
- Solution: Add `day:1` through `day:5` or `day:Overall`

**EasyOCR not loading**
- First submission takes 10-15 seconds (model loading)
- This is normal - subsequent submissions are fast
- Model lazy-loaded to prevent startup memory spike

---

## Performance Notes

### Optimization Features

✅ **Lazy OCR Loading** - EasyOCR loads only on first screenshot (saves 400MB at startup)  
✅ **Profile Caching** - Reduces repeated OCR errors via memory  
✅ **Connection Pooling** - SQLite connections reused  
✅ **Indexed Queries** - Fast leaderboard lookups via composite indexes  

### Expected Performance

- **First submission**: 10-15 seconds (EasyOCR model load)
- **Subsequent submissions**: 3-5 seconds (OCR only)
- **Leaderboard query**: <500ms (indexed)
- **Profile lookup**: <50ms (primary key)

---

## Migration Notes

### From Old System

**Changes**:
- ✅ Commands moved from `/games ranking` → `/kvk ranking`
- ✅ OCR changed from pytesseract → EasyOCR
- ✅ Data model: `stage_type`+`day_number` → `phase`+`day`
- ✅ Added confidence-based validation (R8)
- ✅ Added profile memory (R8 Part 3)
- ✅ Added KVK cycle management

**Backward Compatibility**:
- ✅ Legacy columns still populated (`stage_type`, `day_number`)
- ✅ Old queries still work
- ✅ Gradual migration (dual storage)

---

## Related Documentation

- `KVK_RANKING_PIPELINE_IMPLEMENTATION.md` - Implementation details
- `CANONICAL_PHASE_DAY_MIGRATION.md` - Phase/day migration guide
- `R8_COMPLETE_ARCHITECTURE.md` - Confidence validation system
- `R8_PART3_SUMMARY.md` - Profile memory implementation
- `.github/copilot-instructions.md` - Developer guide

---

**System Status**: ✅ Production Ready  
**Last Tested**: November 2025  
**Maintainer**: HippoBot Development Team
