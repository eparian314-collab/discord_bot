# Top Heroes Ranking System - Setup Checklist

## ✅ Completed Components

### Core Engines
- [x] **ScreenshotProcessor** - OCR processing for Top Heroes screenshots
  - Location: `core/engines/screenshot_processor.py`
  - Features: Guild tag extraction, player name detection, rank/score parsing
  - Event week tracking (YYYY-WW format)
  - Day/category mapping (Construction, Research, Resource/Mob, Hero, Troop)

- [x] **RankingStorageEngine** - Database storage and retrieval
  - Location: `core/engines/ranking_storage_engine.py`
  - Database: `event_rankings.db` with SQLite
  - Duplicate detection and update logic
  - Weekly event tracking with auto-cleanup
  - Submission statistics tracking

- [x] **RankingCog** - Discord interface with commands
  - Location: `cogs/ranking_cog.py`
  - User commands: submit, view, leaderboard
  - Admin commands: report, stats, user lookup
  - Modlog integration for audit trail

---

## 🔧 Setup Requirements

### 1. Install Tesseract OCR Binary

**Windows:**
```powershell
# Download installer from GitHub
# https://github.com/UB-Mannheim/tesseract/wiki

# Or use Chocolatey
choco install tesseract

# Add to PATH
$env:PATH += ";C:\Program Files\Tesseract-OCR"
```

**Verify Installation:**
```powershell
tesseract --version
```

### 2. Configure Environment Variables

Edit `.env` file:
```bash
# Required: Channel where users submit rankings
RANKINGS_CHANNEL_ID=YOUR_RANKINGS_CHANNEL_ID_HERE

# Optional: Modlog channel (defaults to channel named "modlog")
MODLOG_CHANNEL_ID=YOUR_MODLOG_CHANNEL_ID_HERE

# Optional: Bot announcement channel
BOT_CHANNEL_ID=YOUR_BOT_CHANNEL_ID_HERE
```

**How to get Channel IDs:**
1. Enable Developer Mode in Discord: Settings → Advanced → Developer Mode
2. Right-click channel → Copy Channel ID
3. Paste into `.env` file

### 3. Install Python Dependencies

Already in `requirements.txt`:
```
Pillow>=10.0.0
pytesseract>=0.3.10
```

If not installed:
```powershell
pip install Pillow pytesseract
```

### 4. Integrate Ranking Cog

Add to `integrations/integration_loader.py`:

```python
from discord_bot.cogs.ranking_cog import setup as setup_ranking_cog
from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine

# In load_integrations() function, add:
# Initialize ranking engines
screenshot_processor = ScreenshotProcessor()
ranking_storage = RankingStorageEngine("event_rankings.db")

# Load ranking cog
await setup_ranking_cog(bot, screenshot_processor, ranking_storage)
```

---

## 📋 Testing Checklist

### Basic Functionality
- [ ] Bot starts without errors
- [ ] Commands appear in Discord: `/games ranking`
- [ ] Tesseract installed and accessible
- [ ] Database created: `event_rankings.db`

### User Commands
- [ ] `/games ranking submit` - Upload test screenshot
  - [ ] Channel restriction works (only in #rankings)
  - [ ] OCR extracts data correctly
  - [ ] Duplicate detection works
  - [ ] Confirmation message received
  - [ ] Modlog receives notification

- [ ] `/games ranking view` - Check personal history
  - [ ] Shows submitted rankings
  - [ ] Works in any channel

- [ ] `/games ranking leaderboard` - View guild rankings
  - [ ] Shows current week by default
  - [ ] Filters work (day, stage, guild_tag)
  - [ ] Displays correctly formatted

### Admin Commands (Requires Admin Permission)
- [ ] `/games ranking report` - Generate report
  - [ ] Current week report works
  - [ ] Filters work (week, day, stage)
  - [ ] Shows top 10 rankings
  - [ ] Sends copy to modlog

- [ ] `/games ranking stats` - View statistics
  - [ ] Shows submission counts
  - [ ] Success rate calculates correctly
  - [ ] Updates in real-time

- [ ] `/games ranking user @mention` - User lookup
  - [ ] Shows user's history
  - [ ] Displays best performances
  - [ ] Shows recent submissions

### Modlog Integration
- [ ] Modlog channel exists or MODLOG_CHANNEL_ID set
- [ ] Bot has permission to send messages in modlog
- [ ] Submission notifications appear in modlog
- [ ] Admin reports copy to modlog

---

## 🎮 Usage Workflow

### During Top Heroes Event

**Day 1-5 (Prep Stage):**
1. Members take screenshots of rankings
2. Submit in #rankings: `/games ranking submit day:1 guild_tag:TAO`
3. Upload screenshot when prompted
4. Bot processes and confirms

**Admin Monitoring:**
```
# Check daily progress
/games ranking stats

# View full report
/games ranking report

# Check specific member
/games ranking user @MemberName
```

**Before War Day (Day 6):**
```
# Generate final prep report
/games ranking report week:2025-43

# Review by day
/games ranking report day:1
/games ranking report day:2
...
```

---

## 🔍 Troubleshooting

### OCR Not Working
**Problem:** "Tesseract not found" error

**Solutions:**
1. Verify Tesseract installed: `tesseract --version`
2. Check PATH includes Tesseract directory
3. Restart terminal/IDE after installation
4. Try absolute path in code if needed

### Channel Restriction Not Working
**Problem:** Can submit in wrong channels

**Solutions:**
1. Check RANKINGS_CHANNEL_ID in `.env`
2. Verify ID is correct (right-click → Copy ID)
3. Restart bot after .env changes
4. Check bot has READ_MESSAGES permission

### No Modlog Messages
**Problem:** Admin notifications not appearing

**Solutions:**
1. Check channel named "modlog" exists OR
2. Set MODLOG_CHANNEL_ID in `.env`
3. Verify bot has SEND_MESSAGES + EMBED_LINKS permissions
4. Check bot can see modlog channel

### Commands Not Appearing
**Problem:** `/games ranking` not showing

**Solutions:**
1. Verify cog loaded in `integration_loader.py`
2. Check for startup errors: `python -m discord_bot.main`
3. Sync commands: `python sync_commands.py`
4. Wait 1-5 minutes for Discord to update

### Duplicate Detection Issues
**Problem:** Duplicate submissions allowed

**Solutions:**
1. Check database constraints exist
2. Verify event_week calculation correct
3. Check UNIQUE constraint in schema:
   ```sql
   UNIQUE(user_id, guild_id, event_week, stage_type, day_number)
   ```

---

## 📊 Database Management

### View Rankings
```powershell
sqlite3 event_rankings.db
SELECT * FROM event_rankings ORDER BY submitted_at DESC LIMIT 10;
```

### Check Current Week
```sql
SELECT event_week, COUNT(*) as submissions 
FROM event_rankings 
GROUP BY event_week 
ORDER BY event_week DESC;
```

### View Statistics
```sql
SELECT 
    guild_tag,
    COUNT(*) as total_submissions,
    AVG(rank) as avg_rank,
    MAX(score) as highest_score
FROM event_rankings
WHERE event_week = '2025-43'
GROUP BY guild_tag;
```

### Cleanup Old Data
```sql
-- Automatic cleanup in code, or manual:
DELETE FROM event_rankings 
WHERE submitted_at < datetime('now', '-30 days');
```

---

## 🚀 Quick Start Commands

**First Time Setup:**
```powershell
# 1. Install Tesseract
choco install tesseract

# 2. Configure channels
# Edit .env and add RANKINGS_CHANNEL_ID

# 3. Restart bot
python -m discord_bot.main

# 4. Test in Discord
/games ranking stats
```

**Daily Usage:**
```
# Members submit rankings
/games ranking submit day:3 guild_tag:TAO
[Upload screenshot]

# Admins check progress
/games ranking stats
/games ranking report
```

**Weekly Reporting:**
```
# End of week analysis
/games ranking report week:2025-43
/games ranking leaderboard show_all_weeks:True
```

---

## 📝 Event Categories Reference

| Day | Category | Description |
|-----|----------|-------------|
| Day 1 | Construction | Building construction points |
| Day 2 | Research | Research completion points |
| Day 3 | Resource & Mob | Resource gathering + mob kills |
| Day 4 | Hero | Hero development points |
| Day 5 | Troop Training | Troop training points |
| Day 6 | War | Fighting day (no regular submissions) |

---

## 🎯 Success Criteria

Your ranking system is working correctly when:

✅ Users can submit screenshots in #rankings channel
✅ Bot extracts guild tag, player name, rank, score
✅ Duplicate submissions update existing data
✅ Modlog receives all submission notifications
✅ Admins can generate reports anytime
✅ Statistics show accurate submission counts
✅ Leaderboards display correctly with filters
✅ Event week tracking works automatically
✅ Database stores all required information

---

## 🆘 Need Help?

### Common Issues

1. **Import Errors** - Check all files exist in correct locations
2. **Permission Errors** - Verify bot has admin access to channels
3. **OCR Errors** - Install Tesseract binary (not just Python package)
4. **Database Errors** - Check file permissions for event_rankings.db
5. **Command Sync Issues** - Try manual sync with `sync_commands.py`

### Debug Mode

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Files to Check

- `cogs/ranking_cog.py` - Discord commands
- `core/engines/screenshot_processor.py` - OCR logic
- `core/engines/ranking_storage_engine.py` - Database operations
- `integrations/integration_loader.py` - Cog registration
- `.env` - Configuration variables
- `event_rankings.db` - Data storage

---

## 📞 Contact

If issues persist:
1. Check logs in `logs/` directory
2. Review error messages in console
3. Verify all dependencies installed
4. Test with simple screenshot first
5. Check Discord bot permissions

---

**System Ready to Deploy! 🎉**

Follow the checklist above to complete setup and start tracking Top Heroes event rankings.
