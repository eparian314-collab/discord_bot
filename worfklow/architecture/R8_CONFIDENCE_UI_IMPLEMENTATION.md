# R8 Confidence-Based Validation Implementation Summary

## ✅ COMPLETED: Confidence-Based UI Branching in RankingCog

### Implementation Location
**File**: `discord_bot/cogs/ranking_cog.py`  
**Function**: `submit_ranking()` command  
**Lines**: Inserted after validation, before persistence

### Changes Made

#### 1. Import Additions
```python
from discord import app_commands, ui, Interaction
```

#### 2. Confidence Branching Logic

The system now branches based on confidence scores returned from the OCR processor:

```
┌─────────────────────────────────────────────────────┐
│ User submits screenshot                             │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ Parse & Validate (existing logic)                   │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
         Extract confidence
               │
    ┌──────────┴──────────┐
    │                     │
    ▼                     ▼
confidence >= 0.99    0.95 ≤ confidence < 0.99
    │                     │
    │                     ▼
    │          ┌────────────────────┐
    │          │ Soft Confirm View  │
    │          │ - Show preview     │
    │          │ - ✅ Confirm button│
    │          │ - ❌ Cancel button │
    │          └────────────────────┘
    │                     │
    ▼                     ▼
┌─────────────┐    Wait for button
│ Auto-Accept │    interaction
└──────┬──────┘           │
       │                  │
       └──────────┬───────┘
                  │
                  ▼
            Save to DB
                  │
                  ▼
           Success Embed
```

```
    confidence < 0.95
           │
           ▼
┌────────────────────┐
│ Correction Modal   │
│ - Player Name      │
│ - Guild Tag        │
│ - Score            │
│ (pre-filled)       │
└────────────────────┘
           │
           ▼
    User corrects
           │
           ▼
      Save to DB
           │
           ▼
    Success Embed
```

### Behavior by Confidence Level

| Confidence | User Experience | Actions |
|------------|----------------|---------|
| ≥ 0.99 | **Auto-Accept** | Instant "✅ Submission recorded" |
| 0.95-0.989 | **Soft Confirm** | Preview embed with "Confirm" / "Cancel" buttons |
| < 0.95 | **Manual Correction** | Modal form with pre-filled values for editing |

### UI Components

#### Soft Confirm View (0.95-0.989)
- **Embed**: Orange preview showing detected values
- **Buttons**: 
  - ✅ Confirm Submission (green)
  - ❌ Cancel (red)
- **Timeout**: 120 seconds
- **Shows**: Player name, guild tag, score, phase, day
- **Footer**: "Click 'Confirm' to proceed or 'Cancel' to abort"

#### Correction Modal (< 0.95)
- **Warning Embed**: Red alert showing low confidence
- **Modal Fields**:
  - Player Name (pre-filled, max 30 chars)
  - Guild Tag (pre-filled, max 6 chars)
  - Score (pre-filled, numbers only, max 15 chars)
- **Validation**: Checks score format before saving
- **Result**: Success embed with "(Corrected)" suffix

### Code Structure

```python
# Extract confidence from ranking
confidence = getattr(ranking, 'confidence', 1.0)
confidence_map = getattr(ranking, 'confidence_map', {})

if confidence >= 0.99:
    # Auto-accept path (existing logic)
    _persist_validated_submission(...)
    # Continue to success embed

elif confidence >= 0.95:
    # Soft confirm path
    class ConfirmView(ui.View):
        @ui.button(label="✅ Confirm Submission")
        async def confirm_btn(...):
            # Persist and send success
        
        @ui.button(label="❌ Cancel")
        async def cancel_btn(...):
            # Cancel submission
    
    await interaction.followup.send(embed=preview, view=ConfirmView(self))
    return  # Exit, wait for button

else:  # confidence < 0.95
    # Correction modal path
    class CorrectionModal(ui.Modal):
        player_name = ui.TextInput(...)
        guild = ui.TextInput(...)
        score = ui.TextInput(...)
        
        async def on_submit(...):
            # Apply corrections
            # Persist and send success
    
    await interaction.followup.send(embed=warning)
    await interaction.followup.send_modal(CorrectionModal(self))
    return  # Exit, wait for modal
```

### Integration with Existing Systems

#### Unchanged Components
- ✅ Command signature
- ✅ Permission checks
- ✅ KVK run validation
- ✅ Duplicate detection
- ✅ Phase/day validation
- ✅ Storage layer
- ✅ Success embed builder

#### New Requirements for ScreenshotProcessor
The processor must now return `RankingData` with:
- `ranking.confidence` (float 0.0-1.0)
- `ranking.confidence_map` (dict with field-level scores)

If these attributes are missing, system defaults to `confidence=1.0` (auto-accept).

### Error Handling

1. **Invalid score in modal**: Shows error message "❌ Invalid score format"
2. **Timeout**: Discord automatically times out views/modals after 120s
3. **Cancel button**: Gracefully exits with "❌ Submission cancelled"
4. **Missing confidence**: Defaults to 1.0 (high confidence)

### Testing Checklist

- [ ] High confidence (0.99+) auto-accepts
- [ ] Medium confidence (0.95-0.989) shows confirm button
- [ ] Low confidence (<0.95) shows correction modal
- [ ] Confirm button saves correctly
- [ ] Cancel button exits gracefully
- [ ] Modal validation rejects invalid scores
- [ ] Modal corrections apply correctly
- [ ] Success embeds show proper action ("Submitted" vs "Updated" vs "Corrected")
- [ ] Duplicate detection still works
- [ ] KVK run tracking still works
- [ ] Existing entries get replaced properly

### Deployment Notes

#### Prerequisites
1. Update `ScreenshotProcessor` to compute and attach confidence scores
2. Implement validators.py confidence calculation functions
3. Test in isolated environment first

#### Rollback Plan
If issues occur:
1. Remove confidence branching logic (lines added in this patch)
2. Keep just the auto-accept path: `_persist_validated_submission(...)` immediately
3. System reverts to original behavior (no confirmation step)

#### Monitoring
Log confidence scores to track:
- Distribution of confidence levels
- Frequency of manual corrections
- Success rate after correction
- Modal submission rates

### Future Enhancements

1. **Profile caching**: Remember user's guild/name for auto-fill
2. **Name locking**: Prevent accidental name changes
3. **Smart defaults**: Use previous submission values in modal
4. **Candidate suggestions**: Show multiple OCR candidates for ambiguous fields
5. **Confidence tuning**: Adjust thresholds based on user feedback

### Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `ranking_cog.py` | Added ui imports | 1 line |
| `ranking_cog.py` | Added confidence branching | ~200 lines |

### Files Created (R8 Complete System)

| File | Purpose | Status |
|------|---------|--------|
| `validators.py` | Confidence scoring functions | ✅ Created |
| `profile_cache.py` | Player profile caching | ✅ Created |
| `confirm_flow.py` | UI payload builders | ✅ Created |
| `validation_constants.py` | Tunable thresholds | ✅ Created |
| `tests_r8_validation.py` | Unit tests | ✅ Created |
| `wiring_notes.md` | Integration guide | ✅ Created |

### Status

**✅ PHASE COMPLETE**: Confidence-based UI branching fully implemented in RankingCog.

**Next Steps**:
1. Update ScreenshotProcessor to compute confidence scores
2. Run unit tests
3. Deploy to test environment
4. Collect user feedback
5. Tune thresholds based on real-world data
