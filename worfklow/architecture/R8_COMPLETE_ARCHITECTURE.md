# R8 Complete System Architecture

## Three-Layer Validation System

```
┌────────────────────────────────────────────────────────────────────┐
│                    USER SUBMITS SCREENSHOT                         │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│  R8-PART1: Confidence Scoring (validators.py)                     │
│  ─────────────────────────────────────────────────────────────────│
│  • OCR text → confidence scores per field                          │
│  • score_confidence(text, parsed_int, bounds)                      │
│  • guild_confidence(text, cached_guild)                            │
│  • name_confidence(text, cached_name)                              │
│  • overall_confidence(field_scores, weights)                       │
│                                                                     │
│  OUTPUT: RankingData with .confidence and .confidence_map          │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│  R8-PART2: UI Branching (ranking_cog.py)                          │
│  ─────────────────────────────────────────────────────────────────│
│  confidence = ranking.confidence                                   │
│                                                                     │
│  ┌─────────────────┐                                              │
│  │ confidence ≥0.99│──→ Auto-Accept → save_or_update_ranking()   │
│  └─────────────────┘                                              │
│                                                                     │
│  ┌─────────────────────┐                                          │
│  │ 0.95 ≤ conf < 0.99  │──→ ConfirmView (✅/❌ buttons)           │
│  └─────────────────────┘    │                                     │
│                              └──→ On confirm → save_or_update...   │
│                                                                     │
│  ┌─────────────────┐                                              │
│  │ confidence <0.95│──→ CorrectionModal (text inputs)             │
│  └─────────────────┘    │                                         │
│                         └──→ On submit → save_or_update...        │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│  R8-PART3: Profile Memory (ranking_storage_engine.py)             │
│  ─────────────────────────────────────────────────────────────────│
│  user_profile = _get_profile(user_id)                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────┐          │
│  │ GUILD CORRECTION                                     │          │
│  │ If confidence_map['guild'] < 0.95:                  │          │
│  │   ranking.guild_tag = cached_guild                   │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────┐          │
│  │ NAME CORRECTION                                      │          │
│  │ If name differs from cache:                          │          │
│  │   If confidence_map['player_name'] < 0.98:          │          │
│  │     ranking.player_name = cached_name (OCR error)    │          │
│  │   Else:                                              │          │
│  │     Accept rename + update_profile() (intentional)   │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                     │
│  If no profile: _update_profile() (first-time submission)          │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │ SAVE TO DB    │
                        │ ✅ CLEAN DATA  │
                        └───────────────┘
```

## Data Flow Example

### Scenario: Messy OCR + Existing Profile

```python
# STEP 1: ScreenshotProcessor (with R8-PART1 validators)
ranking = RankingData(
    user_id="123456789",
    player_name="P1ayer",           # OCR misread "Player"
    guild_tag="4BC",                # OCR misread "ABC"
    score=1234567,
    confidence=0.87,                 # Overall low confidence
    confidence_map={
        "player_name": 0.85,         # Low name confidence
        "guild": 0.82,               # Low guild confidence
        "score": 0.95                # Score is OK
    }
)

# STEP 2: RankingCog (R8-PART2 UI branching)
if confidence < 0.95:  # 0.87 < 0.95 ✓
    # Show CorrectionModal with pre-filled values:
    # - Player Name: "P1ayer"
    # - Guild: "4BC"
    # - Score: "1234567"
    
# User sees messy values and can correct OR...
# User clicks Submit without editing

# STEP 3: RankingStorageEngine (R8-PART3 profile memory)
user_profile = _get_profile(123456789)
# Returns: {"player_name": "Player", "guild": "ABC"}

# Guild correction (0.82 < 0.95):
ranking.guild_tag = "ABC"  # ✅ Corrected from "4BC"

# Name correction (0.85 < 0.98):
ranking.player_name = "Player"  # ✅ Corrected from "P1ayer"

# Save to DB with clean values:
# user_id=123456789, player_name="Player", guild="ABC", score=1234567
```

## Confidence Threshold Reference

| Field | Auto-Accept | Soft Confirm | Correction | Cache Fallback |
|-------|-------------|--------------|------------|----------------|
| **Overall** | ≥ 0.99 | 0.95-0.989 | < 0.95 | N/A |
| **Guild** | ≥ 0.95 | - | - | < 0.95 |
| **Player Name** | ≥ 0.98 | - | - | < 0.98 (name differs) |
| **Score** | N/A | N/A | Manual entry | N/A |

## Integration Status

| Component | File | Status | Lines |
|-----------|------|--------|-------|
| **Confidence Scoring** | `validators.py` | ✅ Created | 336 |
| **Profile Cache Helpers** | `profile_cache.py` | ✅ Created | 164 |
| **UI Payload Builders** | `confirm_flow.py` | ✅ Created | 282 |
| **Test Suite** | `tests_r8_validation.py` | ✅ Created | 410 |
| **Configuration** | `validation_constants.py` | ✅ Created | 138 |
| **UI Branching** | `ranking_cog.py` | ✅ Patched | +220 |
| **Profile Memory** | `ranking_storage_engine.py` | ✅ Patched | +53 |

**Total LOC**: ~1,603 lines  
**Compilation Status**: ✅ All files compile without errors  
**Architecture Impact**: ✅ Zero - layered middleware approach

## Testing Priority

### High Priority (Blocks Production)
1. ✅ Syntax validation (py_compile) - DONE
2. ⏳ ScreenshotProcessor integration (add confidence_map attribute)
3. ⏳ Manual Discord test (submit real screenshot)

### Medium Priority (Quality Assurance)
4. ⏳ Unit tests for validators.py
5. ⏳ Unit tests for profile memory logic
6. ⏳ Integration test (mock full pipeline)

### Low Priority (Nice to Have)
7. ⏳ Performance benchmarking
8. ⏳ Confidence score tuning (collect real-world data)
9. ⏳ UI timeout behavior testing

## Next Steps

**Immediate**:
1. Update `ScreenshotProcessor.process_screenshot()` to compute and attach `confidence` + `confidence_map`
2. Test profile table creation (run bot once to trigger `_ensure_tables()`)
3. Submit test screenshot with various confidence levels

**Short-term**:
1. Monitor profile table growth
2. Log correction frequency (guild vs name vs none)
3. Tune confidence thresholds based on user feedback

**Long-term**:
1. Add name lock cooldown (prevent accidental renames within 24h)
2. Add guild transfer detection
3. Add confidence score analytics dashboard
