# R8 Deployment Checklist

## ✅ Phase 1: Implementation (COMPLETE)

### Core Components
- [x] **validators.py** - Confidence scoring functions (336 lines)
- [x] **profile_cache.py** - Player profile caching helpers (164 lines)
- [x] **confirm_flow.py** - UI payload builders (282 lines)
- [x] **validation_constants.py** - Tunable thresholds (138 lines)
- [x] **tests_r8_validation.py** - Unit test suite (410 lines)
- [x] **wiring_notes.md** - Integration documentation

### Integration Patches
- [x] **ranking_cog.py** - UI branching logic (+220 lines)
  - Three-tier confidence flow (auto/confirm/modal)
  - ConfirmView with buttons
  - CorrectionModal with text inputs
- [x] **ranking_storage_engine.py** - Profile memory (+53 lines)
  - player_profile table creation
  - _get_profile() and _update_profile() helpers
  - Smart guild/name correction in save_or_update_ranking()

### Verification
- [x] All files compile without syntax errors
- [x] No linting errors detected
- [x] Architecture preserved (no circular dependencies)
- [x] Existing commands unchanged

---

## ⏳ Phase 2: Integration (PENDING)

### ScreenshotProcessor Updates
- [ ] Add `confidence: float = 1.0` to RankingData dataclass
- [ ] Add `confidence_map: Dict[str, float] = field(default_factory=dict)` to RankingData
- [ ] Implement confidence calculation in process_screenshot()
  - [ ] Call validators.score_confidence() for numeric fields
  - [ ] Call validators.guild_confidence() for guild extraction
  - [ ] Call validators.name_confidence() for player name
  - [ ] Call validators.overall_confidence() with weights
  - [ ] Store results in RankingData.confidence and .confidence_map

### Database Migration
- [ ] Start bot once to trigger player_profile table creation
- [ ] Verify table exists: `sqlite3 data/event_rankings.db ".schema player_profile"`
- [ ] Verify indexes created: `sqlite3 data/event_rankings.db ".indexes"`

---

## ⏳ Phase 3: Testing (PENDING)

### Unit Tests
- [ ] Run pytest on tests_r8_validation.py
  - [ ] TestValidators (18 tests)
  - [ ] TestProfileCache (7 tests)
  - [ ] TestConfirmFlow (3 tests)
  - [ ] TestIntegration (3 tests)

### Integration Tests
- [ ] Test auto-accept flow (confidence ≥ 0.99)
  - Submit screenshot with perfect OCR
  - Verify instant success embed
  - Verify no UI prompts shown
  
- [ ] Test soft confirm flow (0.95 ≤ confidence < 0.99)
  - Submit screenshot with medium confidence
  - Verify preview embed appears
  - Click ✅ Confirm button
  - Verify success embed
  
- [ ] Test correction modal flow (confidence < 0.95)
  - Submit screenshot with low confidence
  - Verify warning embed + modal
  - Edit values in modal
  - Submit modal
  - Verify success embed with "(Corrected)" suffix

### Profile Memory Tests
- [ ] Test first-time submission
  - Submit screenshot as new user
  - Verify profile created in player_profile table
  
- [ ] Test guild correction
  - Submit with messy guild OCR (confidence < 0.95)
  - Verify cached guild used instead
  - Check database has correct guild
  
- [ ] Test name stability
  - Submit with messy name OCR (confidence < 0.98)
  - Verify cached name used instead
  - Check profile unchanged
  
- [ ] Test intentional rename
  - Submit with different name (confidence ≥ 0.98)
  - Verify new name accepted
  - Check profile updated in database

---

## ⏳ Phase 4: Monitoring (PENDING)

### Metrics to Track
- [ ] Confidence score distribution
  - % auto-accept (≥0.99)
  - % soft confirm (0.95-0.989)
  - % correction modal (<0.95)

- [ ] User interaction patterns
  - % confirm button clicks
  - % cancel button clicks
  - % modal submissions vs cancellations

- [ ] Correction frequency
  - % submissions with guild correction applied
  - % submissions with name correction applied
  - % submissions requiring manual modal input

- [ ] Profile accuracy
  - % returning users with existing profiles
  - % name changes detected
  - % guild changes detected

### Logs to Add
```python
logger.info(f"R8: Confidence score: {confidence:.2f}")
logger.info(f"R8: Guild corrected: {old_guild} → {new_guild}")
logger.info(f"R8: Name corrected: {old_name} → {new_name}")
logger.info(f"R8: Profile created for user {user_id}")
logger.info(f"R8: Intentional rename detected: {old_name} → {new_name}")
```

---

## ⏳ Phase 5: Tuning (PENDING)

### Threshold Adjustments
Based on real-world data, may need to adjust:

**validation_constants.py**:
```python
# Current values:
AUTO_ACCEPT_THRESHOLD = 0.99      # May be too strict?
SOFT_CONFIRM_MIN = 0.95           # May be too lenient?
GUILD_CORRECTION_THRESHOLD = 0.95  # May need lowering?
NAME_CORRECTION_THRESHOLD = 0.98   # May need lowering?

# Confidence weights:
CONFIDENCE_WEIGHTS = {
    "score": 0.35,       # Most important
    "phase": 0.20,       # High importance
    "day": 0.15,         # Medium importance
    "server_id": 0.10,   # Low importance
    "guild": 0.10,       # Low importance
    "player_name": 0.10  # Low importance
}
```

**Tuning Strategy**:
1. Collect 100+ submissions with confidence scores
2. Analyze false positives (auto-accept with errors)
3. Analyze false negatives (correction modal for perfect OCR)
4. Adjust thresholds to minimize both
5. Re-test and iterate

---

## Command Reference

### Database Inspection
```powershell
# View player_profile table
sqlite3 data/event_rankings.db "SELECT * FROM player_profile LIMIT 10;"

# Count profiles
sqlite3 data/event_rankings.db "SELECT COUNT(*) FROM player_profile;"

# Check for profiles with mismatched data
sqlite3 data/event_rankings.db "
  SELECT pp.user_id, pp.player_name, er.player_name AS latest_name
  FROM player_profile pp
  JOIN event_rankings er ON pp.user_id = er.user_id
  WHERE pp.player_name != er.player_name
  ORDER BY er.submitted_at DESC
  LIMIT 20;
"
```

### Testing Commands
```powershell
# Run all R8 tests
pytest tests/test_r8_validation.py -v

# Run specific test class
pytest tests/test_r8_validation.py::TestValidators -v

# Run with coverage
pytest tests/test_r8_validation.py --cov=discord_bot.core.engines --cov-report=term-missing

# Run integration tests only
pytest tests/test_r8_validation.py::TestIntegration -v
```

### Syntax Validation
```powershell
# Compile all R8 files
python -m py_compile `
  discord_bot\cogs\ranking_cog.py `
  discord_bot\core\engines\ranking_storage_engine.py `
  discord_bot\core\engines\screenshot_processor.py

# Check for import errors
python -c "from discord_bot.cogs.ranking_cog import RankingCog; print('✅ RankingCog OK')"
python -c "from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine; print('✅ Storage OK')"
```

---

## Rollback Plan

If critical issues discovered:

### Quick Rollback (UI Only)
Remove confidence branching from ranking_cog.py:
1. Keep imports: `from discord import app_commands, ui, Interaction`
2. Remove entire confidence branching block (lines ~733-933)
3. Replace with original logic:
   ```python
   ranking_id, was_updated, score_changed = self._persist_validated_submission(...)
   embed = self._build_submission_embed(...)
   await interaction.followup.send(embed=embed)
   ```
4. Result: System reverts to auto-accept all submissions

### Full Rollback (All Layers)
1. Restore ranking_cog.py to pre-R8 version
2. Restore ranking_storage_engine.py to pre-R8 version
3. player_profile table can remain (harmless)
4. R8 validator files can remain (unused)

### Partial Rollback (Keep Profile Memory)
1. Rollback UI layer (ranking_cog.py)
2. Keep profile memory layer (ranking_storage_engine.py)
3. System will use cached values silently (no user interaction)

---

## Success Metrics

### Week 1 Goals
- [ ] Zero crashes from R8 code
- [ ] < 5% user complaints about UI flow
- [ ] > 80% confidence scores ≥ 0.95
- [ ] < 10% manual corrections needed

### Week 4 Goals
- [ ] Profile coverage > 90% of active users
- [ ] Guild correction accuracy > 95%
- [ ] Name correction accuracy > 95%
- [ ] Average submission time < 30 seconds (including UI)

### Long-term Goals
- [ ] Confidence thresholds optimized
- [ ] False positive rate < 2%
- [ ] False negative rate < 5%
- [ ] User satisfaction score > 8/10

---

## Known Limitations

1. **No rename confirmation UI** - High confidence renames are silent
2. **No name lock cooldown** - Users can change names rapidly
3. **No guild transfer detection** - Guild changes are treated as OCR errors or renames
4. **No multi-server profiles** - Profile is global across all servers
5. **No confidence logging** - Need to add instrumentation for tuning

---

## Documentation Files

- [x] `R8_CONFIDENCE_UI_IMPLEMENTATION.md` - UI branching details
- [x] `R8_PART3_PROFILE_MEMORY.md` - Profile memory implementation
- [x] `R8_COMPLETE_ARCHITECTURE.md` - System architecture diagram
- [x] `R8_DEPLOYMENT_CHECKLIST.md` - This file

---

## Status Summary

**✅ PHASE 1 COMPLETE**: All code implemented and compiles  
**⏳ PHASE 2 PENDING**: ScreenshotProcessor integration  
**⏳ PHASE 3 PENDING**: Testing  
**⏳ PHASE 4 PENDING**: Monitoring  
**⏳ PHASE 5 PENDING**: Tuning  

**Current Blocker**: ScreenshotProcessor needs confidence_map attribute

**Next Action**: Update `screenshot_processor.py` to compute and attach confidence scores
