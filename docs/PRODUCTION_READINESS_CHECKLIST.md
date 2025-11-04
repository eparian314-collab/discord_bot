# HippoBot Production Readiness Checklist

**Last Updated:** November 3, 2025  
**Status:** ✅ All critical issues resolved

## Recent Fixes Applied

### ✅ Command Group Architecture (Nov 3, 2025)
- **Issue:** Circular imports causing `AttributeError` and duplicate command registration
- **Status:** RESOLVED
- **Details:** See `docs/COMMAND_GROUP_FIX_SUMMARY.md`
- **Impact:** All 22 slash commands now register and function properly

## Pre-Deployment Checklist

### 1. Environment Configuration
- [ ] `.env` file configured with all required keys:
  - `DISCORD_TOKEN` (required)
  - `DEEPL_API_KEY` (required for translation)
  - `MY_MEMORY_API_KEY` (optional, fallback translator)
  - `OPENAI_API_KEY` (optional, personality features)
  - `RANKINGS_CHANNEL_ID` (required if using ranking system)
  - `ALLOWED_CHANNELS` (comma-separated list of bot channel IDs)
  - `OWNER_IDS` (comma-separated list of bot owner Discord IDs)

### 2. Database Setup
- [ ] `data/` directory exists and is writable
- [ ] SQLite databases auto-created on first run:
  - `data/event_rankings.db` (ranking system)
  - `data/game_data.db` (Pokemon game, cookies, relationships)
- [ ] No manual schema setup required (auto-migration on startup)

### 3. Dependencies
- [ ] Python 3.10+ installed
- [ ] All requirements installed: `pip install -r requirements.txt`
- [ ] Tesseract OCR installed (if using ranking screenshot system)
  - Windows: Download from GitHub or use `choco install tesseract`
  - Verify: `tesseract --version`

### 4. Preflight Validation
Run the preflight check script before starting:
```powershell
python scripts/preflight_check.py
```

Expected output:
- ✅ All directories exist
- ✅ .env is complete
- ✅ Channel IDs are valid
- ✅ Databases are accessible

### 5. Bot Startup
Start the bot:
```powershell
python main.py
```

Expected startup sequence:
```
[OK] Sanitized 236 Python files
INFO 🚀 Starting HippoBot
INFO 🛠️ Preparing engines and integrations
INFO ⚙️ Mounted cogs: translation, admin, help, language, sos, events, ranking, easteregg, game
INFO HippoBot logged in as Baby Hippo#XXXX
INFO Command sync complete (schema_version=1, global: 22)
INFO Sent startup message to guild...
```

### 6. Command Verification
After startup, verify commands are visible in Discord:

**Top-Level Command Groups:**
- `/language` - Translation and language management
- `/games` - Pokemon, cookies, fun commands
- `/kvk` - Top Heroes ranking (if configured)
- `/admin` - Administrative commands (owner only)

**Games Subcommands:**
- `/games pokemon catch|fish|explore|train|evolve|collection|details`
- `/games cookies balance|stats|leaderboard`
- `/games fun rps|joke|catfact|trivia|riddle|8ball|weather`

**Expected Count:** 22 global commands

### 7. Feature Testing
Test critical features:

**Translation System:**
```
/language translate text:"Hello" target_language:"Spanish"
Expected: "Hola" (or similar)
```

**Cookie Economy:**
```
/games cookies balance
Expected: Shows cookie balance, relationship status, game unlock status
```

**Rock-Paper-Scissors (Recently Fixed):**
```
/games fun rps choice:"rock"
Expected: Baby Hippo plays against you, no AttributeError
```

**Pokemon Game:**
```
/games pokemon catch
Expected: Prompts to feed 5 cookies to Baby Hippo if game not unlocked
```

## Common Issues & Solutions

### Issue: Bot doesn't respond to commands
**Diagnostic:**
```powershell
# Check bot permissions in server settings
# Verify bot has "application.commands" scope
# Check ALLOWED_CHANNELS includes the channel ID
```

**Solution:**
1. Ensure bot was invited with correct scopes: `applications.commands` + `bot`
2. Add channel ID to `ALLOWED_CHANNELS` in `.env`
3. Verify bot role has "Use Application Commands" permission

### Issue: Commands not syncing
**Diagnostic:**
```powershell
python scripts/sync_commands.py
```

**Solution:**
- Global commands take up to 1 hour to sync
- Guild-specific commands sync immediately
- Force sync: `python scripts/force_sync_commands.py`

### Issue: Translation not working
**Diagnostic:**
Check logs for provider errors:
```
ERROR Failed to translate via DeepL
WARNING Falling back to MyMemory
```

**Solution:**
1. Verify `DEEPL_API_KEY` is valid (check DeepL dashboard)
2. Ensure API key has remaining quota
3. MyMemory fallback should work without API key (rate-limited)

### Issue: Database errors
**Diagnostic:**
```powershell
python scripts/check_schema.py
```

**Solution:**
1. Ensure `data/` directory exists and is writable
2. Check file permissions on `.db` files
3. Delete corrupted DB files (will be recreated on restart)

### Issue: Cog loading errors
**Diagnostic:**
Check logs for:
```
ERROR Failed to mount cogs
```

**Solution:**
1. Verify all dependencies injected in `integration_loader.py`
2. Check for circular imports (see `docs/COMMAND_GROUP_FIX_SUMMARY.md`)
3. Ensure all `__init__` parameters match what's passed in `_mount_cogs`

## Monitoring & Maintenance

### Daily Checks
- [ ] Bot online and responding in Discord
- [ ] No error spikes in logs (`logs/` directory)
- [ ] Database backups exist (`data/storage_backup.json`)

### Weekly Tasks
- [ ] Review error logs for patterns
- [ ] Check API quota usage (DeepL, OpenAI)
- [ ] Verify database integrity: `python scripts/check_schema.py`
- [ ] Update dependencies: `pip install -r requirements.txt --upgrade`

### Monthly Tasks
- [ ] Full preflight validation: `python scripts/preflight_check.py`
- [ ] Backup databases: Copy `data/*.db` to safe location
- [ ] Review and prune old ranking data (if applicable)
- [ ] Test all major features end-to-end

## Emergency Procedures

### Bot Crashed or Unresponsive
```powershell
# 1. Stop bot process
Stop-Process -Name python -Force

# 2. Check logs for root cause
Get-Content logs/hippo_bot.log -Tail 100

# 3. Run preflight check
python scripts/preflight_check.py

# 4. Restart bot
python main.py
```

### Database Corruption
```powershell
# 1. Stop bot
Stop-Process -Name python -Force

# 2. Backup current DB
Copy-Item data/game_data.db data/game_data.db.backup

# 3. Restore from backup (if available)
Copy-Item data/storage_backup.json data/game_data.db

# 4. Or delete and start fresh (loses data)
Remove-Item data/game_data.db
python main.py  # Will recreate DB
```

### Command Sync Issues
```powershell
# Nuclear option: Full rebuild
python scripts/nuclear_sync.py
```
**Warning:** This rebuilds everything and can take time to propagate.

## Performance Baselines

**Startup Time:** 3-5 seconds  
**Command Response:** <1 second (except translation: 1-3 seconds)  
**Memory Usage:** ~100-200 MB baseline  
**Database Size:** Varies by activity, typically <50 MB

## Security Notes

- **Never commit `.env`** - Contains sensitive API keys
- **Owner IDs** should be restricted to trusted admins only
- **Admin commands** are protected by `is_owner()` check
- **Rate limiting** built-in for easter egg cookies (5/day)
- **Spam protection** auto-mutes users who exceed limits

## Support Resources

- **Architecture Docs:** `docs_archive/ARCHITECTURE.md`
- **Command Sync:** `COMMAND_SYNC_RESOLUTION_COMPLETE.md`
- **Ranking System:** `docs_archive/RANKING_SYSTEM.md`
- **Translation Setup:** `docs_archive/THREE_TIER_TRANSLATION_SUMMARY.md`
- **Game System:** `docs_archive/POKEMON_STAT_SYSTEM.md`

## Version Info

**Bot Version:** HippoBot v2 (Hippo-Bot-v2 branch)  
**Discord.py Version:** 2.x  
**Command Schema Version:** 1  
**Last Major Update:** Nov 3, 2025 (Command group architecture fix)

---

**Production Status:** ✅ **READY FOR DEPLOYMENT**

All known critical issues have been resolved. Bot is stable and fully functional with 22 working slash commands across translation, games, admin, and event management systems.
