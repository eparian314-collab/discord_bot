# Guardian Error Engine Enhancement - Ranking System Integration

**Version**: 1.0  
**Date**: November 6, 2025  
**Status**: ✅ Complete

---

## Overview

Enhanced the `GuardianErrorEngine` to provide comprehensive error tracking, categorization, and diagnostics specifically for the ranking system. This enables admins to identify failure patterns, track OCR issues, and monitor system health in real-time.

---

## What Was Changed

### 1. **Event Topics** (`core/event_topics.py`)

Added ranking-specific error topics and payload contracts:

```python
# New Topics
RANKING_SUBMISSION_ERROR = "ranking.submission.error"
RANKING_OCR_ERROR = "ranking.ocr.error"
RANKING_VALIDATION_ERROR = "ranking.validation.error"
RANKING_DB_ERROR = "ranking.db.error"
RANKING_PERMISSION_ERROR = "ranking.permission.error"

# New Payload Type
class RankingError(TypedDict):
    category: str           # submission|ocr|validation|db|permission
    user_id: str
    guild_id: Optional[str]
    kvk_run_id: Optional[int]
    stage: Optional[str]    # prep|war
    day: Optional[int]
    error_message: str
    confidence: Optional[float]
    screenshot_url: Optional[str]
    context: Optional[dict[str, Any]]
```

### 2. **GuardianErrorEngine** (`core/engines/error_engine.py`)

#### New Features

**Category-Based Error Tracking**
- Errors are now categorized (e.g., `"ranking.submission"`, `"ranking.ocr"`)
- Separate deques for category-specific errors (max 50 per category)
- Dedicated ranking error deque (max 100)
- Error rate counters for pattern detection

**Enhanced log_error() Method**
```python
await guardian.log_error(
    error=exception,
    context="Human-readable context",
    severity="error|warning|critical",
    category="ranking.submission",  # NEW: Optional category
    **metadata  # Additional context
)
```

**Specialized log_ranking_error() Method**
```python
await guardian.log_ranking_error(
    error=exception,
    category="submission",  # submission|ocr|validation|db|permission
    user_id=str(interaction.user.id),
    guild_id=str(interaction.guild_id),
    kvk_run_id=kvk_run.id,
    stage="prep",  # prep|war
    day=3,  # 1-5 for prep, None for war
    confidence=0.85,  # OCR confidence if applicable
    screenshot_url=screenshot.url,
    context="KVK submission processing failed",
    **extra_metadata
)
```

**New Diagnostic Methods**
- `get_errors_by_category(category, limit)` - Get recent errors for specific category
- `get_ranking_errors(limit)` - Get recent ranking-specific errors
- `get_error_summary()` - Overall error statistics by category
- `get_ranking_error_report(hours)` - Detailed ranking error report with:
  - Total ranking errors in time window
  - Breakdown by category
  - Affected user count
  - Affected KVK run count
  - Low confidence OCR error count
  - Most common error type

### 3. **EnhancedKVKRankingCog** (`cogs/kvk_visual_cog.py`)

#### Dependency Injection
Added `guardian` parameter to `setup_dependencies()`:
```python
async def setup_dependencies(self, 
                            kvk_tracker=None,
                            storage=None,
                            guardian=None,  # NEW
                            rankings_channel_id=None,
                            modlog_channel_id=None):
```

#### Error Tracking Integration

**Validation Errors**
```python
if not validation["valid"]:
    if self.guardian:
        await self.guardian.log_ranking_error(
            error=ValueError(f"Screenshot validation failed: {validation_error}"),
            category="validation",
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            kvk_run_id=kvk_run.id,
            screenshot_url=screenshot.url,
            context="KVK screenshot validation failed",
            validation_reason=validation_error,
        )
```

**OCR/Parsing Errors**
```python
if not result["success"]:
    if self.guardian:
        await self.guardian.log_ranking_error(
            error=RuntimeError(f"Visual parsing failed: {parsing_error}"),
            category="ocr",
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            kvk_run_id=kvk_run.id,
            screenshot_url=screenshot.url,
            context="KVK visual parsing failed",
            parsing_details=result,
        )
```

**General Submission Errors**
```python
except Exception as e:
    if self.guardian:
        await self.guardian.log_ranking_error(
            error=e,
            category="submission",
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            kvk_run_id=kvk_run.id,
            screenshot_url=screenshot.url,
            context="KVK submission processing failed",
        )
```

#### New Admin Command: `/kvk errors`

View comprehensive ranking error diagnostics:

```python
@kvk.command(name="errors", description="🔍 View ranking system error diagnostics (Admin only)")
async def view_errors(self, interaction, hours: int = 24):
```

**Features:**
- Time-windowed error analysis (1-168 hours)
- Overall health metrics:
  - Total ranking errors
  - Affected users
  - Affected KVK runs
  - Low confidence OCR errors
- Error breakdown by category
- Most common error type
- Recent error samples (last 3) with:
  - Timestamp
  - Category
  - User mention
  - Error message
  - Confidence score (if applicable)
- Safe mode alert if system is in safe mode

### 4. **Integration Loader** (`discord_bot/integrations/integration_loader.py`)

Added EnhancedKVKRankingCog mounting with guardian injection:

```python
# Mount enhanced KVK visual ranking cog
try:
    from discord_bot.cogs.kvk_visual_cog import EnhancedKVKRankingCog
    
    kvk_visual_cog = EnhancedKVKRankingCog(self.bot)
    await kvk_visual_cog.setup_dependencies(
        kvk_tracker=self.kvk_tracker,
        storage=self.ranking_storage,
        guardian=self.error_engine,  # Inject guardian
        rankings_channel_id=int(os.getenv("RANKINGS_CHANNEL_ID", "0")) or None,
        modlog_channel_id=int(os.getenv("MODLOG_CHANNEL_ID", "0")) or None,
    )
    await self.bot.add_cog(kvk_visual_cog, override=True)
    logger.info("✅ Mounted EnhancedKVKRankingCog with guardian error tracking")
except Exception as e:
    logger.error(f"❌ Failed to mount EnhancedKVKRankingCog: {e}")
```

---

## Usage Examples

### Admin: View Error Diagnostics

```
/kvk errors hours:24
```

**Output:**
```
🔍 Ranking System Error Diagnostics
Error analysis for the past 24 hours

📊 Overall Health
Total ranking errors: 12
Affected users: 5
Affected KVK runs: 2
Low confidence OCR: 8

🏷️ By Category
Ocr: 8 errors
Validation: 3 errors
Submission: 1 errors

⚠️ Most Common
Ocr

🔴 Recent Errors (Last 3)
15:23:45 ocr (conf: 78%)
User: @Mars • Visual parsing failed: Could not detect guild tag

14:52:11 validation (conf: N/A)
User: @Jupiter • Screenshot validation failed: Image too small

13:41:33 ocr (conf: 82%)
User: @Venus • Visual parsing failed: Could not extract score
```

### Developer: Log Custom Ranking Error

```python
# In any cog with guardian access
if self.guardian:
    await self.guardian.log_ranking_error(
        error=ValueError("Custom error"),
        category="db",  # submission|ocr|validation|db|permission
        user_id="123456789",
        guild_id="987654321",
        kvk_run_id=42,
        stage="prep",
        day=3,
        confidence=0.85,
        screenshot_url="https://...",
        context="Database save failed",
        custom_field="additional context",
    )
```

### Query Error Data Programmatically

```python
# Get recent ranking errors
recent_errors = guardian.get_ranking_errors(limit=10)

# Get errors by specific category
ocr_errors = guardian.get_errors_by_category("ranking.ocr", limit=20)

# Get comprehensive report
report = guardian.get_ranking_error_report(hours=48)
print(f"Total errors: {report['total_ranking_errors']}")
print(f"Most common: {report['most_common_error']}")
print(f"Low confidence OCR: {report['low_confidence_ocr_errors']}")

# Get overall summary
summary = guardian.get_error_summary()
print(f"Safe mode: {summary['safe_mode']}")
print(f"By category: {summary['by_category']}")
```

---

## Error Categories

| Category | When to Use | Example Scenarios |
|----------|-------------|-------------------|
| `ranking.submission` | Top-level submission failures | Network errors, Discord API failures, unexpected exceptions |
| `ranking.ocr` | OCR/parsing failures | EasyOCR errors, text extraction failures, pattern matching failures |
| `ranking.validation` | Screenshot/input validation | Image too small, wrong format, missing game UI elements |
| `ranking.db` | Database operations | SQLite errors, connection failures, constraint violations |
| `ranking.permission` | Authorization/permission issues | Non-admin late submissions, channel restrictions, role checks |

---

## Integration Points

### Where Errors Are Logged

1. **KVK Visual Submission** (`kvk_visual_cog.py`)
   - Screenshot validation failures → `ranking.validation`
   - Visual parsing failures → `ranking.ocr`
   - General submission errors → `ranking.submission`

2. **Future Integration Points** (Ready to Use)
   - Database save failures → `ranking.db`
   - Permission checks → `ranking.permission`
   - Any cog with guardian access can log ranking errors

### Event Bus Topics

All ranking errors are emitted to the event bus with appropriate topics:
- `RANKING_SUBMISSION_ERROR`
- `RANKING_OCR_ERROR`
- `RANKING_VALIDATION_ERROR`
- `RANKING_DB_ERROR`
- `RANKING_PERMISSION_ERROR`

Subscribers can listen for these topics to:
- Send admin alerts
- Trigger automated responses
- Log to external monitoring systems
- Generate reports

---

## Benefits

### For Admins
✅ **Real-time visibility** into ranking system health  
✅ **Pattern detection** - identify recurring issues  
✅ **User impact analysis** - see who's affected  
✅ **Data-driven decisions** - prioritize fixes based on error frequency  
✅ **Historical tracking** - view errors over time windows  

### For Developers
✅ **Centralized error handling** - consistent logging pattern  
✅ **Rich context capture** - full error details with metadata  
✅ **Easy integration** - simple API for logging errors  
✅ **Event-driven architecture** - errors emitted to event bus  
✅ **Safe mode protection** - automatic detection of repeated failures  

### For Users
✅ **Better support** - admins can diagnose issues faster  
✅ **Improved reliability** - patterns lead to targeted fixes  
✅ **Transparency** - clear error messages with tracking  

---

## Testing Checklist

- [x] GuardianErrorEngine initialization with event bus
- [x] Error categorization and storage
- [x] Ranking-specific error logging
- [x] Event bus emission for each category
- [x] Error aggregation and counting
- [x] Time-windowed report generation
- [x] Admin command `/kvk errors` functionality
- [x] Guardian injection in EnhancedKVKRankingCog
- [x] Integration with kvk visual submission flow
- [x] Error tracking for validation failures
- [x] Error tracking for OCR failures
- [x] Error tracking for general submission failures

---

## Future Enhancements

1. **Automated Alerting**
   - Send Discord DM to admins when error rate exceeds threshold
   - Post to modlog channel for critical errors

2. **Error Trend Analysis**
   - Track error rates over days/weeks
   - Identify degradation patterns
   - Predict potential failures

3. **User-Specific Error History**
   - View errors for a specific user
   - Identify problematic screenshot patterns
   - Provide personalized guidance

4. **OCR Training Integration**
   - Automatically flag low-confidence errors for training
   - Feed error data into OCR improvement pipeline

5. **External Monitoring**
   - Export error data to monitoring platforms
   - Integration with logging services (e.g., Sentry, LogRocket)

---

## Architecture Compliance

✅ **No upward imports** - GuardianErrorEngine uses event bus for communication  
✅ **Dependency injection** - Guardian passed to cogs via setup_dependencies  
✅ **Event-driven** - All errors emitted to appropriate topics  
✅ **Layered architecture** - Clear separation between engines and cogs  
✅ **Domain-pure** - No Discord dependencies in error engine  

---

## Conclusion

The Guardian Error Engine enhancement provides comprehensive, production-ready error tracking for the ranking system. Admins now have full visibility into system health, failure patterns, and user impact. The modular design makes it easy to extend error tracking to other subsystems.

**Status**: ✅ Ready for production deployment
