# Unified Ranking System

## Overview

The Unified Ranking System combines classic manual ranking submission with advanced visual parsing for automatic stage/day detection. This system works for **any in-game event** with day-based formats (KVK, tournaments, seasonal events, etc.).

## Key Features

### 1. **Automatic Visual Detection** ✨
- Detects prep vs. war stage from screenshot visual cues
- Identifies prep days (1-5) or war stage automatically
- Extracts self-score from leaderboard screenshots
- Falls back to manual input if auto-detection fails

### 2. **Power Band Comparisons** ⚔️
- Track your performance against peers within ±10% power level
- Automatic peer grouping based on configured power levels
- Real-time comparison updates with each submission

### 3. **Multi-Event Support** 🎯
- Flexible system works for any event type (KVK, tournaments, battles)
- Day-based tracking (Construction, Research, Resource, Hero, Troop)
- War stage tracking (day 6)
- Week-based event windows with admin control

### 4. **Admin Tools** 🔧
- Test run creation for validation
- Comprehensive reports by week/day/stage
- User lookup and statistics
- Modlog notifications for all submissions

## Commands

All commands are under `/games ranking`:

### User Commands

#### `/games ranking submit`
Submit a ranking screenshot with optional visual parsing.

**Parameters:**
- `screenshot` (required): Upload your ranking screenshot
- `day` (optional): Which day (1-5 for prep)? Leave blank for auto-detection
- `stage` (optional): Which stage (Prep/War)? Leave blank for auto-detection

**How it works:**
1. If you don't specify stage/day, the system attempts visual parsing
2. Visual parsing detects stage type, prep day, and your score row
3. If successful, shows "✨ Visual parsing successful!" 
4. If visual parsing fails, prompts you to manually specify stage/day
5. Validates screenshot and saves to database
6. Updates power band comparison tracking

**Examples:**
```
/games ranking submit screenshot:<upload> 
  → Auto-detects everything

/games ranking submit screenshot:<upload> day:3 stage:Prep
  → Manual specification, skips auto-detection

/games ranking submit screenshot:<upload> stage:War
  → Specifies war stage, auto-detects other info
```

#### `/games ranking view`
View your ranking submission history.

**Parameters:**
- `limit` (optional): Number of recent submissions to show (default: 5, max: 20)

#### `/games ranking leaderboard`
View guild leaderboard for event rankings.

**Parameters:**
- `day` (optional): Filter by day (1-5)
- `stage` (optional): Filter by stage (Prep/War)
- `guild_tag` (optional): Filter by guild tag (default: TAO)
- `show_all_weeks` (optional): Show all-time instead of current week

#### `/games ranking status`
Check your current comparison status with power band peers.

**Shows:**
- Your score, rank, and power level
- Number of peers in your power band
- How many peers you're ahead of
- Separate stats for prep and war stages

**Note:** Requires visual parsing system to be active.

#### `/games ranking power`
Set your power level for comparison tracking.

**Parameters:**
- `power_level` (required): Your current power (1M - 1B)

**Example:**
```
/games ranking power power_level:25000000
  → Sets your power to 25M
  → System will track peers with 22.5M - 27.5M power (±10%)
```

### Admin Commands

#### `/games ranking start_test_run`
**Admin only** - Create a temporary event test window.

**Parameters:**
- `duration_minutes` (optional): How long window stays open (5-720 min, default: 60)

**Use case:** Testing OCR and storage without affecting live event data.

#### `/games ranking report`
**Admin only** - Generate comprehensive rankings report.

**Parameters:**
- `week` (optional): Event week (YYYY-WW format, default: current)
- `day` (optional): Filter by specific day (1-5)
- `stage` (optional): Filter by stage (Prep/War)

**Shows:**
- Total submission count
- Submissions by day breakdown
- Top 10 rankings
- Also posts to modlog channel

#### `/games ranking stats`
**Admin only** - View submission statistics.

**Shows:**
- Total submissions (last 7 days)
- Success/failure counts
- Unique user count
- Success rate percentage

#### `/games ranking user`
**Admin only** - Look up specific user's submission history.

**Parameters:**
- `user` (required): Discord user to look up

**Shows:**
- Total submissions
- Current week submissions
- Best performances (rank/score)
- Recent submission history

## Visual Parsing System

### How It Works

1. **Stage Detection**
   - Analyzes screenshot layout and visual cues
   - Identifies prep stage headers vs. war stage layout
   - Confidence threshold: 80%

2. **Day Detection (Prep Stage)**
   - OCR on day header text
   - Pattern matching for day names:
     - Day 1: Construction
     - Day 2: Research
     - Day 3: Resource & Mob
     - Day 4: Hero
     - Day 5: Troop Training
   - Highlights and visual position analysis

3. **Self-Score Identification**
   - Parses all leaderboard rows (rank, player name, guild tag, score)
   - Matches submitting user's Discord name against player names
   - Fuzzy matching with 80% confidence threshold
   - Returns your specific row data

4. **Comparison Engine**
   - Stores all parsed leaderboard entries
   - Groups users by power level (±10% bands)
   - Calculates peer rankings and deltas
   - Tracks progress over time

### System Status

Check visual parsing health with:
```
/games ranking system  # Admin only
```

Shows:
- ✅/❌ System health
- ✅/❌ Dependencies (Tesseract OCR, OpenCV, Pillow)
- ✅/❌ Directory readiness
- 📂 Cache file status
- 📁 Configured paths

## Architecture

### Components

**UnifiedRankingCog** (`cogs/unified_ranking_cog.py`)
- Main command handler
- Combines manual + visual workflows
- Event window validation
- Permission checks

**KVKVisualManager** (`core/engines/kvk_visual_manager.py`)
- Orchestrates visual parsing workflow
- Validates screenshot requirements
- Coordinates parser and comparison engines

**KVKImageParser** (`core/engines/kvk_image_parser.py`)
- Low-level OCR and computer vision
- Stage/day detection logic
- Leaderboard parsing
- Self-score identification

**KVKComparisonEngine** (`core/engines/kvk_comparison_engine.py`)
- Power band peer tracking
- Delta calculations
- Comparison status queries

**RankingStorageEngine** (`core/engines/ranking_storage_engine.py`)
- SQLite persistence
- Duplicate detection
- Leaderboard queries
- Statistics generation

### Data Flow

```
Screenshot Upload
    ↓
Visual Parsing Attempt (if stage/day not specified)
    ↓
Manual Fallback (if visual parsing fails)
    ↓
Classic OCR Validation (ScreenshotProcessor)
    ↓
Duplicate Check
    ↓
Database Storage (RankingStorageEngine)
    ↓
KVK Tracker Recording
    ↓
Comparison Update (KVKComparisonEngine)
    ↓
Modlog Notification
    ↓
Success Response with Embed
```

## Configuration

### Environment Variables

**Required:**
- `DISCORD_TOKEN` - Bot authentication token
- `RANKINGS_CHANNEL_ID` - Dedicated channel for submissions

**Optional:**
- `MODLOG_CHANNEL_ID` - Channel for admin notifications
- `DEEPL_API_KEY` - For translation features
- `MY_MEMORY_API_KEY` - Translation fallback
- `OPEN_AI_API_KEY` - AI enhancement features

### Channel Setup

1. Create a dedicated rankings channel in your Discord server
2. Get the channel ID (Enable Developer Mode → Right-click channel → Copy ID)
3. Add to `.env`:
   ```
   RANKINGS_CHANNEL_ID=1234567890123456789
   ```
4. Bot will auto-post guidance message on startup
5. Non-command messages auto-deleted to keep channel clean

### Dependencies

**Core:**
- Python 3.10+
- discord.py 2.6+
- SQLite3

**Visual Parsing:**
- Tesseract OCR 5.0+ (binary installation required)
- pytesseract 0.3+
- Pillow 12.0+
- opencv-python 4.5+
- numpy

**Installation:**
```bash
# Python packages
pip install -r requirements.txt

# Tesseract (Ubuntu/Debian)
sudo apt-get install tesseract-ocr

# Tesseract (Windows)
choco install tesseract

# Tesseract (macOS)
brew install tesseract
```

## Migration from Old System

If upgrading from separate RankingCog + EnhancedKVKRankingCog:

1. **Backup database:**
   ```bash
   cp data/event_rankings.db data/event_rankings.db.backup
   ```

2. **Update integration loader:**
   ```python
   # Replace old import
   from discord_bot.cogs.ranking_cog import setup as setup_ranking_cog
   
   # With new import
   from discord_bot.cogs.unified_ranking_cog import setup as setup_unified_ranking_cog
   ```

3. **Update setup call:**
   ```python
   # Replace old setup
   await setup_ranking_cog(bot, processor, storage)
   
   # With new setup
   await setup_unified_ranking_cog(bot, processor, storage)
   ```

4. **Remove old cog files (optional):**
   ```bash
   mv cogs/ranking_cog.py cogs/ranking_cog.py.backup
   mv cogs/kvk_visual_cog.py cogs/kvk_visual_cog.py.backup
   ```

5. **Restart bot:**
   ```bash
   python main.py
   ```

6. **Verify:**
   - Check logs for "✅ Visual parsing system initialized successfully"
   - Test `/games ranking submit` with auto-detection
   - Verify power band comparisons with `/games ranking status`

## Troubleshooting

### Visual Parsing Not Working

**Symptom:** Always prompts for manual stage/day input

**Possible causes:**
1. Tesseract not installed or not in PATH
2. Screenshot quality too low
3. Screenshot format not supported
4. Dependencies missing

**Fix:**
```bash
# Verify Tesseract
tesseract --version

# Reinstall Python packages
pip install --force-reinstall pytesseract pillow opencv-python

# Check system status
# Use /games ranking system command (admin only)
```

### Commands Not Appearing

**Symptom:** Slash commands don't show up in Discord

**Possible causes:**
1. Commands not synced
2. Bot missing permissions
3. Cache issues

**Fix:**
```bash
# Force command sync
python scripts/sync_commands.py

# Or nuclear option
python scripts/nuclear_sync.py

# Wait up to 1 hour for global sync
```

### Database Errors

**Symptom:** Submission fails with database error

**Possible causes:**
1. Database file locked
2. Schema out of date
3. Disk space issues

**Fix:**
```bash
# Check schema
python scripts/check_schema.py

# Run migrations if needed
# (Future: Auto-migration on startup)

# Check disk space
df -h
```

## Best Practices

### For Users

1. **Submit high-quality screenshots**
   - Full screen or clear crop
   - Readable text
   - Highlighted row visible
   - Stage/day indicators visible

2. **Set power level early**
   - Use `/games ranking power` before first submission
   - Update when power changes significantly
   - Enables accurate peer comparisons

3. **Submit consistently**
   - Daily submissions recommended
   - Helps track progress over time
   - Builds comparison history

### For Admins

1. **Create test runs before events**
   - Use `/games ranking start_test_run` to validate
   - Test OCR with sample screenshots
   - Verify modlog notifications

2. **Monitor submission stats**
   - Check `/games ranking stats` regularly
   - Look for low success rates (may indicate screenshot issues)
   - Encourage users to improve screenshot quality

3. **Use reports for strategy**
   - Generate weekly reports after events
   - Identify top performers
   - Track guild participation

4. **Keep modlog clean**
   - Configure `MODLOG_CHANNEL_ID` to separate channel
   - Review failed submissions to help users
   - Celebrate achievements!

## Future Enhancements

Planned features:
- [ ] Multi-language OCR support
- [ ] Screenshot quality scoring
- [ ] Automated event window detection
- [ ] Historical trend charts
- [ ] Export to CSV/Excel
- [ ] Integration with other game APIs
- [ ] Machine learning for better self-score ID
- [ ] Mobile-optimized screenshot support

## Support

**Issues or questions?**
- Check bot logs: `logs/` directory
- Run diagnostics: `/games ranking system` (admin)
- Review documentation: `docs/` directory
- Contact bot administrator

**Contributing:**
- Report bugs via GitHub issues
- Submit PR for enhancements
- Follow architectural guidelines in `ARCHITECTURE.md`

---

**Last Updated:** 2025-11-03  
**System Version:** 2.0 (Unified)  
**Maintained by:** HippoBot Development Team
