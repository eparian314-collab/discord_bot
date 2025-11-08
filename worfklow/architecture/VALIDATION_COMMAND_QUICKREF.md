# `/kvk ranking validate` — Quick Reference

**Command:** `/kvk ranking validate`  
**Permission:** Administrator only  
**Location:** Under `/kvk ranking` command group

────────────────────────────────────────

## Usage

### Basic Usage (Current Event)
```
/kvk ranking validate
```
Validates the currently active KVK event or current week.

### Specific Event Week
```
/kvk ranking validate event_week:2025-45
```
Validates a specific event week.

────────────────────────────────────────

## What It Checks

### 1. Prep Score Progression ✓
**Rule:** Prep day scores should increase or stay flat (days 1→2→3→4→5)

**Valid:**
- Day 1: 10,000 → Day 2: 15,000 → Day 3: 20,000 ✅
- Day 1: 10,000 → Day 2: 10,000 → Day 3: 12,000 ✅ (flat is OK)

**Invalid:**
- Day 1: 15,000 → Day 2: 10,000 → Day 3: 20,000 ❌

**Flag Message:**
> User [TAO] Mars: PREP scores decrease or out of order (15000, 10000, 20000)

────────────────────────────────────────

### 2. Duplicate War Submissions ✓
**Rule:** Each user should submit war score only ONCE

**Valid:**
- User submits 1 war screenshot ✅

**Invalid:**
- User submits 3 war screenshots ❌

**Flag Message:**
> User [TAO] Mars: Multiple WAR submissions detected (3 found)

────────────────────────────────────────

### 3. Missing Power Data ✓
**Rule:** Users must submit their power for peer comparison

**Valid:**
- User submitted power via `/kvk ranking set_power 985000` ✅

**Invalid:**
- User submitted rankings but no power ❌

**Flag Message:**
> User [TAO] Mars: Missing POWER data (use `/kvk ranking set_power`)

────────────────────────────────────────

### 4. Score Sanity Checks ✓

#### Negative Scores
**Rule:** Scores cannot be negative

**Flag Message:**
> User [TAO] Mars: Negative score detected (-5000)

#### Unusually High Scores
**Rule:** Scores above 1 billion are flagged for review

**Flag Message:**
> User [TAO] Mars: Unusually high score (2,000,000,000)

#### Invalid Ranks
**Rule:** Rank must be ≥ 1

**Flag Message:**
> User [TAO] Mars: Invalid rank #0

────────────────────────────────────────

## Output Examples

### ✅ All Valid
```
┌──────────────────────────────────────┐
│ ✅ Validation Passed                 │
├──────────────────────────────────────┤
│ All submissions for 2025-45 appear   │
│ valid and consistent.                │
│                                      │
│ Checks Performed:                    │
│ ✓ Prep score progression             │
│ ✓ Duplicate war submissions          │
│ ✓ Missing power data                 │
│ ✓ Data consistency                   │
└──────────────────────────────────────┘
```

### ⚠️ Issues Found
```
┌──────────────────────────────────────┐
│ ⚠️ Validation Issues Found           │
├──────────────────────────────────────┤
│ Found 5 potential issues in 2025-45: │
│                                      │
│ 📊 Prep Stage Issues                 │
│ • User [TAO] Mars: PREP scores       │
│   decrease (15000, 10000, 20000)     │
│                                      │
│ ⚔️ War Stage Issues                  │
│ • User [TAO] Zeus: Multiple WAR      │
│   submissions detected (2 found)     │
│                                      │
│ ⚡ Power Data Issues                 │
│ • User [TAO] Apollo: Missing POWER   │
│ • User [TAO] Diana: Missing POWER    │
│ • User [TAO] Hermes: Missing POWER   │
└──────────────────────────────────────┘
```

────────────────────────────────────────

## Common Resolution Steps

### For Prep Score Decreases
1. Check if user submitted wrong screenshot
2. Ask user to resubmit correct day
3. Admin can delete incorrect entry and have user resubmit

### For Duplicate War Submissions
1. Check which submission is correct (latest usually)
2. Admin can manually delete duplicates from database
3. OR: System auto-overwrites (already implemented)

### For Missing Power
1. Ask user to submit power: `/kvk ranking set_power <number>`
2. User can find their power in game profile
3. Power is used for peer comparison in `/kvk ranking my_performance`

────────────────────────────────────────

## Admin Workflow

### During KVK Event
1. **Daily checks:** Run `/kvk ranking validate` each day
2. **Review flags:** Check for common issues (missing power, duplicates)
3. **Notify users:** DM users with issues to correct them

### Before Leaderboard Publish
1. **Final validation:** Run validation on event week
2. **Clean data:** Resolve all flagged issues
3. **Export results:** Use `/kvk ranking leaderboard` to show final standings

### After Event Close
1. **Archive check:** Ensure all data is consistent before archiving
2. **Power verification:** Confirm all participants submitted power
3. **Historical record:** Keep validation reports for future reference

────────────────────────────────────────

## Technical Details

### Data Source
- Queries: `event_rankings` table
- Filters: `guild_id` + `event_week`
- Groups: By `user_id`

### Performance
- Query time: <100ms for ~100 users
- No external API calls
- Can run repeatedly without load

### Limitations
- Does not check screenshot authenticity
- Cannot detect score manipulation
- Relies on user-submitted data

────────────────────────────────────────

## Related Commands

- `/kvk ranking submit` — Submit ranking screenshot
- `/kvk ranking set_power` — Submit account power
- `/kvk ranking my_performance` — View peer comparison (requires power)
- `/kvk ranking leaderboard` — View guild standings
- `/kvk ranking stats` — Admin submission statistics

────────────────────────────────────────

## Troubleshooting

### Command Not Appearing
- **Check:** Slash commands synced? (may take 1 hour)
- **Check:** User has Administrator permission?
- **Check:** Bot has `applications.commands` scope?

### "No submissions found"
- **Cause:** No one submitted rankings for that event week
- **Fix:** Verify event_week format (YYYY-WW) or use current event

### Validation Always Passes
- **Cause:** No issues detected (good!)
- **OR:** Data is from test/simulation runs
- **Fix:** Check that real submissions exist

────────────────────────────────────────

**Implemented:** R11 — November 5, 2025  
**Status:** ✅ Production Ready
