# 🎯 Top Heroes Ranking System - Enhanced with Weekly Tracking

## Major Updates

### ✅ Event Week Tracking
- **Automatic weekly reset**: System tracks events by ISO week (Monday-Sunday)
- **Format**: `YYYY-WW` (e.g., "2025-43")
- **New event detection**: After 2+ weeks, automatically creates new event week
- **Historical data**: Keeps last 4 weeks of rankings by default

### ✅ Dedicated Rankings Channel
- **Channel restriction**: Submissions ONLY allowed in configured rankings channel
- **Environment variable**: `RANKINGS_CHANNEL_ID` in `.env`
- **Clear error messages**: Users redirected to correct channel if they try elsewhere
- **Keeps rankings organized**: All event data in one dedicated channel

### ✅ Duplicate Detection & Updates
- **Smart duplicate checking**: Detects if user already submitted for that day/stage/week
- **Auto-update**: Allows users to resubmit improved rankings
- **Shows improvements**: Displays rank/score changes when updating
- **Prevents confusion**: Clear warnings about replacing existing data

### ✅ Enhanced Validation
- **Data matching**: Verifies screenshot data matches user's selected day/stage
- **Detailed error messages**: Tells users exactly what's wrong
- **Visual guides**: Shows what screenshot needs to include
- **Smart fallbacks**: Helpful tips for better screenshots

## How Event Weeks Work

### Event Schedule
```
Week Structure (7 days):
- Monday-Friday: Days 1-5 (Event days)
- Saturday: Day 6 (War/Fighting day)
- Sunday: Rest/preparation for next week
```

### Week Tracking
- **Start of week**: Monday at 00:00 UTC
- **Current week**: Auto-detected from submission date
- **Week boundaries**: ISO 8601 standard (Monday = week start)
- **Automatic rollover**: New submissions after Sunday create new event week

### Example Timeline
```
Week 2025-43 (Oct 21-27):
  Mon Oct 21 - Day 1 submissions
  Tue Oct 22 - Day 2 submissions
  Wed Oct 23 - Day 3 submissions
  Thu Oct 24 - Day 4 submissions
  Fri Oct 25 - Day 5 submissions
  Sat Oct 26 - War day (Day 6)
  Sun Oct 27 - Rest day

Week 2025-44 (Oct 28 - Nov 3):
  Mon Oct 28 - NEW EVENT WEEK starts
  [Process repeats]
```

## Duplicate Handling

### When User Submits Duplicate
1. ✅ System checks: User ID + Guild + Week + Stage + Day
2. ⚠️ If found: Shows existing submission with rank/score
3. 📊 Compares: Old vs new data
4. 🔄 Updates: Replaces old with new submission
5. 📈 Shows improvement: Rank gained/lost, score difference

### Example Flow
```
User submits Day 1 Prep:
  First time: ✅ Saved as new ranking
  
User submits Day 1 Prep again (same week):
  System: "⚠️ You already submitted Day 1 Prep!"
  Shows: "Your current: Rank #10435, Score 28M"
  Action: Processes new screenshot
  Result: "📈 Improvement: +50 ranks, +2M points"
  Updates: Replaces old data
```

## Channel Configuration

### Setup Requirements

1. **Create dedicated channel** in Discord (e.g., `#event-rankings`)
2. **Get channel ID** (right-click → Copy ID, dev mode must be on)
3. **Add to `.env`**:
   ```env
   RANKINGS_CHANNEL_ID=1234567890123456789
   ```

### User Experience

#### Correct Channel
```
User in #event-rankings:
/games ranking submit → ✅ Works!
```

#### Wrong Channel
```
User in #general:
/games ranking submit → ❌ Blocked

Bot responds:
"📊 Rankings submissions can only be done in #event-rankings!

This keeps all event rankings organized in one place.
Please go to #event-rankings to submit your screenshot."
```

#### No Channel Configured
```
User anywhere:
/games ranking submit → ❌ Blocked

Bot responds:
"❌ Rankings channel not configured!
Please ask a server admin to set RANKINGS_CHANNEL_ID in the bot's .env file."
```

## Error Handling

### Invalid Screenshot
```
❌ Screenshot validation failed:
Could not read text from image. Please provide a clearer screenshot.

Please make sure your screenshot shows:
• Stage type (Prep/War Stage button)
• Day number (1-5 buttons with one highlighted)
• Your rank (e.g., #10435)
• Your score (e.g., 28,200,103 points)
• Your player name with guild tag (e.g., [TAO] Mars)
```

### Data Mismatch
```
User selects: Day 1, Prep Stage
Screenshot shows: Day 2, Prep Stage

⚠️ Data mismatch!
You selected Day 1, but the screenshot appears to show Day 2.
Please check your screenshot and try again.
```

### Wrong File Type
```
User uploads PDF:

❌ Please upload an image file (PNG, JPG, etc.)!
```

### File Too Large
```
User uploads 15MB image:

❌ Image too large! Please upload a screenshot under 10MB.
```

## Database Changes

### Updated Schema
```sql
CREATE TABLE event_rankings (
    ...existing columns...
    event_week TEXT NOT NULL,  -- NEW: "YYYY-WW" format
    ...
    UNIQUE(user_id, guild_id, event_week, stage_type, day_number)
);

CREATE INDEX idx_rankings_event_week 
ON event_rankings(event_week, guild_id);
```

### New Methods
- `check_duplicate_submission()` - Check if already submitted
- `update_ranking()` - Update existing ranking
- `get_current_event_week()` - Get current week identifier
- `delete_old_event_weeks()` - Clean up old data

## Command Updates

### `/games ranking submit`
**Changes:**
- ✅ Now checks for rankings channel
- ✅ Detects duplicate submissions
- ✅ Shows improvement metrics
- ✅ Validates data matches screenshot
- ✅ Better error messages

**New flow:**
1. Check if in rankings channel → Deny if wrong channel
2. Validate inputs (day, stage, file)
3. Check for duplicate → Warn if found
4. Process screenshot with OCR
5. Validate extracted data matches inputs
6. Save or update ranking
7. Show success with improvements
8. Post to bot channel

### `/games ranking leaderboard`
**Changes:**
- ✅ Defaults to current week only
- ✅ New `show_all_weeks` parameter for all-time rankings
- ✅ Shows which week in title
- ✅ Footer displays current event week

**Usage:**
```
/games ranking leaderboard
  → Shows current week's rankings

/games ranking leaderboard show_all_weeks:True
  → Shows all-time rankings

/games ranking leaderboard day:1 stage:Prep
  → Shows current week Day 1 Prep rankings
```

### `/games ranking view`
**No changes** - Still shows user's personal history

## Configuration File (.env)

### Updated Template
```env
# Channel Configuration
# BOT_CHANNEL_ID: Where announcements are posted (catches, battles, leaderboard)
BOT_CHANNEL_ID=1426291882438426715

# RANKINGS_CHANNEL_ID: Dedicated channel for Top Heroes ranking submissions (required!)
# Users can ONLY submit rankings in this channel
RANKINGS_CHANNEL_ID=

# ALLOWED_CHANNELS: Channels where users can interact with the bot (comma-separated)
# Add more channel IDs here: 123456789,987654321,etc
ALLOWED_CHANNELS=1423024480799817881,1426291734996062440
```

## Data Lifecycle

### Automatic Cleanup
```python
# Delete old event weeks (keeps last 4 weeks = ~1 month)
storage.delete_old_event_weeks(weeks_to_keep=4)
```

### Manual Cleanup
```python
# Delete specific old weeks
storage.delete_old_rankings(days=30)
```

### Week Boundaries
- **Week starts**: Monday 00:00 UTC
- **Week ends**: Sunday 23:59 UTC
- **New week**: Detected automatically on first submission

## Migration Notes

### Existing Database
If you already have ranking data without `event_week`:
1. System will recreate table with new schema
2. Old data will be lost (or backup first)
3. Fresh start for new event tracking

### Backup Command
```bash
# Before upgrading
cp data/event_rankings.db data/event_rankings.db.backup
```

## Testing Checklist

### ✅ Channel Restrictions
- [ ] Submit in rankings channel → Works
- [ ] Submit in other channel → Blocked with redirect
- [ ] Submit without channel configured → Error message

### ✅ Duplicate Detection
- [ ] Submit Day 1 Prep → Success
- [ ] Submit Day 1 Prep again → Duplicate warning
- [ ] Check shows old rank/score
- [ ] New submission updates data
- [ ] Shows improvement metrics

### ✅ Data Validation
- [ ] Select Day 1, screenshot shows Day 1 → Success
- [ ] Select Day 1, screenshot shows Day 2 → Mismatch error
- [ ] Select Prep, screenshot shows War → Mismatch error

### ✅ Week Tracking
- [ ] Submit today → Uses current week
- [ ] View leaderboard → Shows current week by default
- [ ] Use show_all_weeks:True → Shows all data
- [ ] After Sunday → New week starts Monday

### ✅ Error Messages
- [ ] Wrong file type → Clear error
- [ ] File too large → Size limit message
- [ ] OCR fails → Helpful guide
- [ ] Wrong channel → Redirect message

## Files Modified

1. ✅ `.env` - Added `RANKINGS_CHANNEL_ID`
2. ✅ `core/engines/screenshot_processor.py` - Added event week tracking
3. ✅ `core/engines/ranking_storage_engine.py` - Added duplicate detection, update, cleanup
4. ✅ `cogs/ranking_cog.py` - Complete rewrite with all new features

## Summary of Benefits

### For Users
✅ Know exactly where to submit rankings  
✅ Can update rankings if they improve  
✅ See their progress week-over-week  
✅ Clear error messages when something goes wrong  
✅ Can view current week or all-time leaderboards

### For Admins
✅ All rankings in one dedicated channel  
✅ Automatic weekly organization  
✅ Duplicate prevention  
✅ Historical data tracking  
✅ Automatic cleanup of old data

### For Guild
✅ Clean, organized ranking submissions  
✅ Week-by-week competition tracking  
✅ Easy comparison between events  
✅ No confusion about which week's data  
✅ Public leaderboards in bot channel

## Next Steps

1. **Set RANKINGS_CHANNEL_ID** in `.env`
2. **Test with screenshot** in rankings channel
3. **Try duplicate submission** to see update flow
4. **Check leaderboard** for current week
5. **Post announcement** to guild about new channel requirement

## Quick Setup
```bash
# 1. Create #event-rankings channel in Discord
# 2. Get channel ID (enable Developer Mode, right-click channel)
# 3. Add to .env:
echo "RANKINGS_CHANNEL_ID=your_channel_id_here" >> .env

# 4. Restart bot
python main.py

# 5. Test in #event-rankings channel:
/games ranking submit
```

🎉 **Your ranking system is now production-ready with weekly tracking and channel restrictions!**
