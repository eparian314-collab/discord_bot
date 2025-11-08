# Canonical Model Deployment Checklist

## Pre-Deployment Verification

### Code Review
- [x] `screenshot_processor.py` updated with canonical RankingData model
- [x] `ranking_storage_engine.py` migration logic implemented
- [x] `ranking_cog.py` validation logic enforces canonical rules
- [x] No compilation errors in modified files
- [x] Duplicate detection uses canonical phase/day

### Database Safety
- [x] Migration adds columns without dropping existing data
- [x] Both canonical AND legacy columns populated (dual storage)
- [x] Migration is idempotent (safe to run multiple times)
- [ ] Database backup created before deployment

## Deployment Steps

### 1. Backup Current Database
```powershell
# On EC2 or local
cp game_data.db game_data.db.backup-$(date +%Y%m%d-%H%M%S)
```

### 2. Deploy Code
```powershell
# Use existing deploy script
.\deploy_to_ec2.ps1
```

### 3. Bot Restart
The bot will automatically:
- Call `_ensure_event_ranking_columns()` on first ranking operation
- Migrate existing data to canonical format
- Continue populating legacy columns for compatibility

### 4. Post-Deployment Validation

#### Test Prep Submissions
```
/kvk ranking submit <prep-screenshot> stage:Prep day:1
/kvk ranking submit <prep-screenshot> stage:Prep day:Overall
```
Expected: Success, no duplicate warnings, proper validation

#### Test War Submissions
```
/kvk ranking submit <war-screenshot> stage:War
/kvk ranking submit <war-screenshot> stage:War day:3  # Should FAIL
```
Expected: First succeeds, second fails with "War does not use day subdivisions"

#### Test Duplicate Detection
```
# Submit same prep day 1 twice
/kvk ranking submit <screenshot> stage:Prep day:1
/kvk ranking submit <screenshot> stage:Prep day:1
```
Expected: Second submission blocked with duplicate message

#### Test Leaderboard Filtering
```
/kvk ranking leaderboard stage:Prep day:1
/kvk ranking leaderboard stage:War
```
Expected: Filtered results, no errors

### 5. Database Validation

#### Check Migration Status
```sql
-- All entries should have phase
SELECT COUNT(*) FROM event_rankings WHERE phase IS NULL;
-- Expected: 0

-- Verify phase distribution
SELECT phase, COUNT(*) FROM event_rankings GROUP BY phase;
-- Expected: "prep" and "war" counts

-- Verify day distribution
SELECT day, COUNT(*) FROM event_rankings GROUP BY day;
-- Expected: "1"-"5", "overall", NULL

-- Check dual storage consistency
SELECT 
    COUNT(*) as inconsistent_count
FROM event_rankings 
WHERE (phase = 'prep' AND stage_type != 'Prep Stage')
   OR (phase = 'war' AND stage_type != 'War Stage');
-- Expected: 0
```

#### Verify Legacy Compatibility
```sql
-- Old queries should still work
SELECT * FROM event_rankings 
WHERE stage_type = 'Prep Stage' AND day_number = 1;

-- Canonical queries should work
SELECT * FROM event_rankings 
WHERE phase = 'prep' AND day = '1';
```

## Rollback Plan

### If Critical Issues Found

#### Option 1: Code Rollback (Preserve Data)
```powershell
# Revert to previous bot version
git checkout <previous-commit>
.\deploy_to_ec2.ps1
```
**Safe because**: Legacy columns still populated, old code still works

#### Option 2: Database Rollback (Nuclear)
```powershell
# Restore backup
cp game_data.db.backup-<timestamp> game_data.db
```
**WARNING**: Loses all submissions since deployment

## Monitoring

### Log Patterns to Watch

#### Success Indicators
```
[RankingStorageEngine] Migration completed: phase and day columns added
[RankingCog] Prep submission validated: phase=prep, day=3
[RankingCog] War submission validated: phase=war, day=None
[RankingStorageEngine] Duplicate detected: phase=prep, day=1
```

#### Error Indicators
```
[RankingStorageEngine] Failed to add phase column
[RankingCog] Validation error: <message>
[ScreenshotProcessor] Failed to determine phase/day
```

### Metrics to Track
- Total submissions per phase (prep vs war)
- Day distribution for prep submissions (1-5 vs overall)
- Duplicate detection rate
- Leaderboard query errors

## Known Limitations

### Current State
- ✅ Submission validation enforces canonical rules
- ✅ Duplicate detection uses canonical keys
- ✅ Leaderboard filtering uses canonical columns
- ⏳ UNIQUE constraint still uses legacy columns
- ⏳ Internal helper methods still use StageType enum

### Won't Break
- View commands still work (read from both formats)
- Historical data accessible via legacy or canonical queries
- Old submissions preserved in both formats

### Future Work
1. Update UNIQUE constraint to canonical columns
2. Migrate internal helper methods
3. Remove legacy columns after validation period
4. Remove StageType enum completely

## Emergency Contacts

- Bot Owner: Check `OWNER_IDS` in .env
- Database Location: `game_data.db` in bot root directory
- Logs Location: `logs/` directory
- Backup Location: Same directory as database

## Success Criteria

Deployment considered successful when:
- [x] Code deployed without errors
- [ ] Database migration completed
- [ ] Test submissions work for all scenarios
- [ ] Duplicate detection works correctly
- [ ] Leaderboard filtering works correctly
- [ ] No NULL phase values in database
- [ ] Legacy queries still functional
- [ ] Bot running stable for 24 hours

## Timeline

- **Code Complete**: ✅ Done
- **Testing Phase**: ⏳ Pending manual testing
- **Deployment**: ⏳ Waiting for user approval
- **Monitoring**: ⏳ 24-48 hours after deployment
- **Validation**: ⏳ Review after first KVK cycle
