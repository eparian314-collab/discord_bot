# Ranking System - Admin Commands

## Overview
Admin commands for server masters to monitor and manage the Top Heroes event ranking system.

## Commands Added

### 1. `/games ranking report`
**Purpose:** Generate comprehensive rankings report for the guild

**Parameters:**
- `week` (optional): Event week in YYYY-WW format (defaults to current week)
- `day` (optional): Filter by specific day (1-5)
- `stage` (optional): Filter by stage ('Prep' or 'War')

**Features:**
- Shows total submissions count
- Displays breakdown by day (if not filtered)
- Shows top 10 rankings with guild tag, player name, rank, and score
- Sends copy to modlog channel for audit trail
- Ephemeral response (only admin sees it)

**Example Usage:**
```
/games ranking report
/games ranking report week:2025-43 day:3
/games ranking report stage:War
```

**Output:**
```
📊 Rankings Report - Week 2025-43
Total Submissions: 25 members

📅 Submissions by Day
Day 1: 8 members
Day 2: 6 members
Day 3: 11 members

🏆 Top 10 Rankings
1. [TAO] PlayerOne - Rank #1,234 (28,200,103 pts)
2. [TAO] PlayerTwo - Rank #2,456 (24,500,000 pts)
...
```

---

### 2. `/games ranking stats`
**Purpose:** View submission statistics and success metrics

**Parameters:** None

**Features:**
- Total submissions in last 7 days
- Successful vs failed submissions count
- Unique users who submitted
- Success rate percentage
- Current event week display
- Ephemeral response

**Example Usage:**
```
/games ranking stats
```

**Output:**
```
📊 Ranking Submission Statistics
Current Event Week: 2025-43
Last 7 days

Total Submissions: 45 submissions
Successful: ✅ 42
Failed: ❌ 3
Unique Users: 👥 28 members
Success Rate: 📈 93.3%
```

---

### 3. `/games ranking user`
**Purpose:** View specific user's ranking submission history

**Parameters:**
- `user` (required): Discord user to look up

**Features:**
- Total submissions count
- Current week submissions (last 5)
- Best performance (best rank + highest score)
- Recent submission history
- User avatar thumbnail
- Ephemeral response

**Example Usage:**
```
/games ranking user @PlayerName
```

**Output:**
```
👤 Ranking History - PlayerName
Total Submissions: 12

📅 Current Week (2025-43)
Day 3 - [TAO] InGameName
  Rank #10,435 | Score: 28,200,103 pts

🏆 Best Performance
Best Rank: #1,234
Highest Score: 35,600,000 pts

🕐 Recent Submissions
Week 2025-43 - Day 3
Week 2025-42 - Day 5
Week 2025-42 - Day 3
```

---

## Access Control

All admin commands require:
- **Administrator permission** in Discord server
- Commands are ephemeral (only requester sees response)
- Audit logs sent to modlog channel

**Permission Check:**
```python
@app_commands.checks.has_permissions(administrator=True)
```

---

## Integration with Modlog

All admin report requests are logged to the modlog channel:
- Report command sends copy of generated report
- Includes which admin requested the report
- Timestamp and week information

**Modlog Message Format:**
```
📋 Admin Report Requested - AdminName
[Same content as report embed]
```

---

## Configuration Required

### 1. Set Rankings Channel ID
Edit `.env` file:
```bash
RANKINGS_CHANNEL_ID=1234567890123456789
```

To get channel ID:
1. Enable Developer Mode in Discord
2. Right-click #rankings channel
3. Click "Copy Channel ID"
4. Paste into .env

### 2. Configure Modlog Channel
The bot looks for a channel named "modlog" or uses `MODLOG_CHANNEL_ID` from `.env`:
```bash
MODLOG_CHANNEL_ID=9876543210987654321
```

---

## Database Schema

Admin commands query the `event_rankings` table:
```sql
CREATE TABLE event_rankings (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    guild_id TEXT,
    guild_tag TEXT,
    player_name TEXT,
    event_week TEXT NOT NULL,
    stage_type TEXT NOT NULL,
    day_number INTEGER,
    category TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    screenshot_url TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, guild_id, event_week, stage_type, day_number)
)
```

And `event_submissions` table for statistics:
```sql
CREATE TABLE event_submissions (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    guild_id TEXT,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    ranking_id INTEGER
)
```

---

## Testing Commands

1. **Test Report Command:**
   ```
   /games ranking report
   ```
   Should show current week's submissions

2. **Test Stats Command:**
   ```
   /games ranking stats
   ```
   Should show statistics (may be 0 if no submissions yet)

3. **Test User Lookup:**
   ```
   /games ranking user @yourself
   ```
   Should show your submission history (or empty if none)

---

## Error Handling

### No Data Found
- Report: "📭 No rankings found for week {week}!"
- User lookup: "📭 {user} has not submitted any rankings yet!"

### Non-Guild Context
- All commands: "❌ This command can only be used in a server!"

### Permission Denied
- Discord automatically shows: "You don't have permission to use this command"

---

## Workflow Example

1. **Daily Check** (Server Master):
   ```
   /games ranking stats
   ```
   → See how many members have submitted today

2. **Weekly Report** (Before War Day):
   ```
   /games ranking report
   ```
   → Review all submissions for strategy planning

3. **Individual Check** (For verification):
   ```
   /games ranking user @SuspiciousPlayer
   ```
   → Verify specific member's submission history

4. **Past Week Review**:
   ```
   /games ranking report week:2025-42
   ```
   → Analyze previous week's performance

---

## Next Steps

1. **Configure .env** - Add RANKINGS_CHANNEL_ID
2. **Test commands** - Try each admin command
3. **Verify modlog** - Check messages appear in modlog channel
4. **Train admins** - Show server masters how to use commands
5. **Monitor usage** - Check stats regularly during events

---

## Troubleshooting

### Command not showing up
- Check if cog is loaded in `integration_loader.py`
- Verify bot has been restarted after code changes
- Check if TEST_GUILDS is set (commands sync per-guild)

### Permission errors
- Verify admin role has "Administrator" permission
- Check bot has access to modlog channel
- Ensure bot can send embeds in modlog

### No data in reports
- Check if RANKINGS_CHANNEL_ID is set correctly
- Verify users are submitting in correct channel
- Check event_rankings.db exists and has data

### Stats showing 0
- Normal if no submissions yet
- Check event_submissions table is being populated
- Verify 7-day window includes submission dates

---

## Security Notes

- All admin commands are ephemeral (private responses)
- Only administrators can access commands
- All admin actions logged to modlog
- No sensitive data exposed in public channels
- User lookups respect privacy (admin-only visibility)

---

## Future Enhancements

Potential additions:
- Export report to CSV/Excel
- Automated weekly reports sent to modlog
- Rank change tracking and alerts
- Performance trends over multiple weeks
- Comparison between guild members
- Integration with announcement system for top performers
