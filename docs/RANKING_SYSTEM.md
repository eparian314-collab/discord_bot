# Top Heroes Event Ranking System

## Overview
Track and display Top Heroes event rankings submitted by guild members through screenshot submissions with OCR processing.

## Features

### ✅ Screenshot Processing
- **OCR Technology**: Automatically extracts data from ranking screenshots
- **Smart Detection**: Identifies stage type, day number, rank, score, and player info
- **Guild Tag Recognition**: Extracts 3-letter guild tags (e.g., [TAO])
- **Player Name Extraction**: Identifies in-game player names

### ✅ Event Categories
Based on day number (1-5):
1. **Day 1**: Construction Day
2. **Day 2**: Research Day
3. **Day 3**: Resource and Mob Day
4. **Day 4**: Hero Day
5. **Day 5**: Troop Training Day

### ✅ Stage Types
- **Prep Stage**: Preparation phase rankings
- **War Stage**: War phase rankings

### ✅ Database Storage
- Comprehensive ranking history
- Player tracking with Discord and in-game names
- Guild tag filtering
- Submission logging for analytics

## Commands

### `/games ranking submit <screenshot> <day> <stage>`
Submit your event ranking screenshot.

**Parameters:**
- `screenshot` - Upload your ranking screenshot (PNG/JPG, max 10MB)
- `day` - Which day is this for? (1-5)
- `stage` - Which stage? (Prep or War)

**Example:**
```
/games ranking submit screenshot:image.png day:1 stage:Prep
```

**What the bot extracts:**
- ✅ Stage type (Prep/War)
- ✅ Day number (1-5)
- ✅ Category (Construction/Research/Resource/Hero/Troop)
- ✅ Overall rank (e.g., #10435)
- ✅ Score/points (e.g., 28,200,103)
- ✅ Guild tag (e.g., [TAO])
- ✅ Player name (e.g., Mars)

### `/games ranking view [limit]`
View your ranking submission history.

**Parameters:**
- `limit` - How many recent submissions to show (default: 5, max: 20)

**Shows:**
- Your recent submissions
- Day, stage, and category
- Rank and score for each submission

### `/games ranking leaderboard [day] [stage] [guild_tag]`
View guild leaderboard for event rankings.

**Parameters:**
- `day` - Filter by specific day (1-5) [optional]
- `stage` - Filter by stage (Prep or War) [optional]
- `guild_tag` - Filter by guild (default: TAO) [optional]

**Displays:**
- Top 20 players based on filters
- Best rank achieved
- Highest score
- Player names with guild tags
- Medal emojis for top 3 (🥇🥈🥉)

## Installation

### 1. Install Dependencies

```bash
pip install Pillow pytesseract
```

### 2. Install Tesseract OCR

**Windows:**
1. Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location: `C:\Program Files\Tesseract-OCR`
3. Add to PATH or pytesseract will find it automatically

**Mac:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

### 3. Verify Installation

```bash
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

## Integration

### Add to `integration_loader.py`:

```python
from discord_bot.cogs.ranking_cog import setup as setup_ranking_cog
from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine

# In __init__ or setup:
self.ranking_processor = ScreenshotProcessor()
self.ranking_storage = RankingStorageEngine("event_rankings.db")

# In _mount_cogs:
await setup_ranking_cog(
    self.bot,
    processor=self.ranking_processor,
    storage=self.ranking_storage
)
```

## Database Schema

### `event_rankings` Table
```sql
CREATE TABLE event_rankings (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,           -- Discord user ID
    username TEXT NOT NULL,           -- Discord username
    guild_id TEXT,                    -- Discord guild ID
    guild_tag TEXT,                   -- In-game guild tag (e.g., "TAO")
    player_name TEXT,                 -- In-game player name
    
    stage_type TEXT NOT NULL,         -- "Prep Stage" or "War Stage"
    day_number INTEGER,               -- 1-5
    category TEXT NOT NULL,           -- "Construction Day", "Research Day", etc.
    
    rank INTEGER NOT NULL,            -- Overall rank (#10435)
    score INTEGER NOT NULL,           -- Points (28,200,103)
    
    submitted_at TEXT NOT NULL,       -- UTC timestamp
    screenshot_url TEXT,              -- Discord CDN URL
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### `event_submissions` Table
```sql
CREATE TABLE event_submissions (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    guild_id TEXT,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL,             -- "success" or "failed"
    error_message TEXT,
    ranking_id INTEGER,               -- Foreign key to event_rankings
    FOREIGN KEY(ranking_id) REFERENCES event_rankings(id)
);
```

## Usage Examples

### Submitting a Ranking

1. Take screenshot of your Top Heroes ranking (must show stage, day buttons, rank, score, player name)
2. Use `/games ranking submit`
3. Upload screenshot
4. Select day number (1-5)
5. Select stage (Prep or War)
6. Bot processes and confirms

### Viewing Leaderboard

**All TAO members, all days:**
```
/games ranking leaderboard
```

**Day 1 Construction only:**
```
/games ranking leaderboard day:1
```

**War Stage only:**
```
/games ranking leaderboard stage:War
```

**Day 3 War Stage TAO members:**
```
/games ranking leaderboard day:3 stage:War guild_tag:TAO
```

## Screenshot Requirements

For best OCR results, screenshots should:
- ✅ Be clear and not blurry
- ✅ Show the stage type button (Prep Stage / War Stage)
- ✅ Show day number buttons (1-5 with one highlighted)
- ✅ Show your overall rank (e.g., #10435)
- ✅ Show your score (e.g., 28,200,103 points)
- ✅ Show your player name with guild tag (e.g., #10435 [TAO] Mars)
- ✅ Be in good lighting (not too dark)
- ✅ Have text that is readable

## Guild Tag Filtering

The system is designed to work with multiple guilds:
- **Current Focus**: TAO guild members
- **Future-Ready**: Can filter by any guild tag (e.g., AoW, ToO, etc.)
- **Default Filter**: Leaderboard defaults to showing TAO members only
- **Flexible**: Users can remove guild_tag filter to see all submissions

## Data Management

### Automatic Cleanup
```python
# Delete rankings older than 30 days
storage.delete_old_rankings(days=30)
```

### Submission Statistics
```python
# Get submission stats for last 7 days
stats = storage.get_submission_stats(guild_id="123...", days=7)
# Returns: total_submissions, successful, failed, unique_users
```

### Ranking History
```python
# Get user's ranking progression over time
history = storage.get_ranking_history(user_id="123...", days=7)
```

## Troubleshooting

### OCR Not Working
1. Verify Tesseract is installed: `tesseract --version`
2. Check Python can find it: `python -c "import pytesseract"`
3. Try setting path manually in code:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

### Can't Extract Data
- Screenshot may be too blurry
- Text may be too small
- Try taking screenshot on higher resolution
- Ensure good contrast between text and background

### Wrong Data Extracted
- OCR may misread similar characters (0/O, 1/I, 5/S)
- Bot validates rank and score are numbers
- Manual correction not currently supported (resubmit with clearer screenshot)

## Future Enhancements

### Planned Features
- [ ] Manual data entry option (for when OCR fails)
- [ ] Edit submitted rankings
- [ ] Delete rankings
- [ ] Ranking change notifications (daily progress tracking)
- [ ] Automated reminders to submit rankings
- [ ] Weekly/monthly ranking reports
- [ ] Compare rankings between guild members
- [ ] Achievement badges for top performers
- [ ] Export rankings to CSV/Excel

### Advanced Analytics
- [ ] Track improvement over time
- [ ] Average rank per day/category
- [ ] Most improved player awards
- [ ] Consistency tracking (submissions per event)
- [ ] Guild-wide statistics dashboard

## Technical Details

### OCR Extraction Methods

**Stage Type Detection:**
- Searches for "Prep Stage" or "War Stage" keywords

**Day Number Detection:**
- Looks for buttons labeled 1-5
- Maps day to category automatically

**Guild Tag Extraction:**
- Pattern: `[TAO]`, `(TAO)`, or `#10435 TAO Mars`
- Extracts 3-letter uppercase tags

**Player Name Extraction:**
- Pattern: `#10435 [TAO] Mars`
- Extracts name after guild tag

**Rank Extraction:**
- Pattern: `#10435` or `Rank: 10435`
- Removes commas and converts to integer

**Score Extraction:**
- Pattern: Large numbers with commas (e.g., `28,200,103`)
- Takes largest number found (filters out small numbers)

### Performance
- Screenshot processing: ~2-5 seconds
- Database queries: <100ms
- Leaderboard generation: <500ms
- Concurrent submissions: Supported via SQLite

## Files Created

1. `core/engines/screenshot_processor.py` - OCR and data extraction
2. `core/engines/ranking_storage_engine.py` - Database operations
3. `cogs/ranking_cog.py` - Discord commands
4. `core/ui_groups.py` - Updated with `games_ranking` group
5. `event_rankings.db` - SQLite database (auto-created)

## Support

For issues or questions:
1. Check screenshot meets requirements
2. Verify Tesseract is installed correctly
3. Check bot logs for detailed error messages
4. Use `/ranking view` to see if data was extracted (even if incorrectly)
