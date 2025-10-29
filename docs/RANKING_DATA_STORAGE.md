# Top Heroes Ranking - Data Storage

## What Gets Stored

From each screenshot submission, the system stores:

### 📊 Core Data Fields

1. **Guild Tag** - 3-letter tag extracted from player name (e.g., "TAO")
2. **Username** - Discord username (e.g., "mars._.3")
3. **Player Name** - In-game name extracted from screenshot (e.g., "Mars")
4. **Category** - Which day (1-5) or War day (6)
   - Day 1 = Construction Day
   - Day 2 = Research Day
   - Day 3 = Resource and Mob Day
   - Day 4 = Hero Day
   - Day 5 = Troop Training Day
   - Day 6 = War Day
5. **Rank** - Overall rank position (e.g., #10435)
6. **Score** - Points/score (e.g., 28,200,103)
7. **Week** - Event week in YYYY-WW format (e.g., "2025-43")
8. **Stage** - Prep Stage or War Stage
9. **Screenshot URL** - Discord CDN link to original screenshot

### 🗄️ Database Structure

```
event_rankings table:
├── id (auto-increment)
├── user_id (Discord user ID)
├── username (Discord username)
├── guild_id (Discord server ID)
├── guild_tag ("TAO", "AOW", etc.)
├── player_name (in-game name)
├── event_week ("2025-43")
├── stage_type ("Prep Stage" or "War Stage")
├── day_number (1-5)
├── category ("Construction Day", "Research Day", etc.)
├── rank (10435)
├── score (28200103)
├── submitted_at (timestamp)
├── screenshot_url (Discord CDN link)
└── created_at (auto-timestamp)
```

## What Happens on Submission

### First Time Submission
```
1. User uploads screenshot
2. Bot extracts: guild tag, player name, rank, score
3. Bot stores with: week, day, stage
4. Success message shows all stored data
```

### Duplicate Submission (Same Week/Day/Stage)
```
1. User uploads screenshot
2. Bot detects: "Already submitted Day 1 Prep this week"
3. Bot shows: Current stored rank/score
4. Bot warns: "This will REPLACE your previous submission"
5. Bot processes new screenshot
6. Bot REPLACES old data with new data
7. Success message shows updated stored data
```

## Example Data Flow

### Screenshot Content
```
[Image shows:]
- Prep Stage button highlighted
- Day 1 button highlighted
- Player: #10435 [TAO] Mars
- Points: 28,200,103
```

### Extracted & Stored
```
✅ Guild Tag: TAO
✅ Username: mars._.3 (Discord)
✅ Player Name: Mars (in-game)
✅ Category: Day 1 - Construction Day
✅ Rank: 10435
✅ Score: 28200103
✅ Week: 2025-43
✅ Stage: Prep Stage
```

### Confirmation Message
```
✅ Ranking Submitted!
Event Week: 2025-43

📊 Data Stored
Guild Tag: TAO
Player: Mars
Category: Day 1 - Construction Day
Rank: #10,435
Score: 28,200,103 points
Week: 2025-43
```

## No Improvement Tracking

The system **DOES NOT**:
- ❌ Compare ranks between days
- ❌ Track score improvements
- ❌ Show day-to-day progress
- ❌ Calculate rank changes

The system **ONLY**:
- ✅ Stores raw data from each screenshot
- ✅ Replaces data if resubmitted for same week/day/stage
- ✅ Keeps historical data by week

## Querying Data

### View Your Submissions
```bash
/games ranking view
# Shows your recent submissions with:
# - Day, Stage, Rank, Score for each
```

### View Guild Leaderboard
```bash
/games ranking leaderboard
# Shows all members' data for current week
# Sorted by best rank
```

### Filter by Day
```bash
/games ranking leaderboard day:1
# Shows only Day 1 submissions
```

### Filter by Stage
```bash
/games ranking leaderboard stage:Prep
# Shows only Prep Stage submissions
```

## Data Lifecycle

### Weekly Reset
- New event week starts every Monday
- Previous week's data remains in database
- Can view old weeks with filters

### Automatic Cleanup
- System keeps last 4 weeks by default
- Older data automatically deleted
- Prevents database bloat

### Manual Cleanup
```python
# Delete data older than 4 weeks
storage.delete_old_event_weeks(weeks_to_keep=4)
```

## Unique Constraints

The database enforces uniqueness on:
```
user_id + guild_id + event_week + stage_type + day_number
```

This means:
- ✅ User can submit Day 1 Prep (stored)
- ✅ User can submit Day 2 Prep (stored - different day)
- ✅ User can submit Day 1 War (stored - different stage)
- ❌ User submits Day 1 Prep again (replaces first submission)

## Summary

**Simple data storage system:**
1. User submits screenshot
2. Bot extracts: guild tag, username, day, rank, score
3. Bot stores with current week
4. Done! No comparisons, just clean data storage.

**Perfect for:**
- Guild leaders tracking member participation
- Weekly event performance records
- Historical data by week
- Leaderboards per day/stage/week
