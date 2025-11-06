# 🎯 FINAL ACTION PLAN: Command Tree Sanitization

**Current Date:** 2025-11-05  
**Status:** Ready to Execute

---

## 📊 Current State Confirmed

### Duplicates Detected
✅ **CONFIRMED:** You have duplicate commands in both global AND guild scope:

**Global Scope:** 26 commands including:
- `/language`, `/games`, `/kvk` (the 3 main groups)
- Plus standalone commands: `/translate`, `/keyword`, `/admin`, `/help`, etc.
- ⚠️ **STALE:** `/Translate` (capitalized duplicate with no description)

**Guild Scope (ID: 1423768684572184700):** 3 commands:
- `/language`, `/games`, `/kvk`

**Problem:** Discord uses guild version but shows both, causing confusion.

### Signature Analysis
✅ **VERIFIED:** `/kvk ranking submit` parameters match between code and Discord
- The "type differences" are just representation (Optional[str] = AppCommandOptionType.string)
- **No actual signature mismatch**

---

## ✅ RECOMMENDED ACTION: Run One-Time Sanitizer

### What It Does
1. ✅ Deletes all 26 global commands (including stale `/Translate`)
2. ✅ Deletes all 3 guild commands  
3. ✅ Verifies clean state (should be 0 global, 0 guild)
4. ℹ️ You then restart bot normally - it will resync

### How to Execute

```powershell
# Navigate to project root
cd c:\discord_bot

# Run sanitizer
python scripts\one_time_sanitizer.py
```

**When prompted:**
```
Type 'YES' to proceed with sanitization: YES
```

### Expected Output
```
🧹 ONE-TIME COMMAND SANITIZER
[SYNC] Connected as Angry Hippo#1540

📊 BEFORE STATE:
   Global commands: 26
   Guild commands: 3

🗑️ STEP 1: Purging GLOBAL commands...
   ✅ Deleted GLOBAL: /language (ID: ...)
   ✅ Deleted GLOBAL: /games (ID: ...)
   ... (24 more)
   Total global commands deleted: 26

🗑️ STEP 2: Purging GUILD commands...
   ✅ Deleted GUILD: /language (ID: ...)
   ✅ Deleted GUILD: /games (ID: ...)
   ✅ Deleted GUILD: /kvk (ID: ...)
   Total guild commands deleted: 3

⏳ Waiting 3 seconds for Discord to process deletions...

📊 AFTER STATE (verification):
   Global commands: 0
   Guild commands: 0
   ✅ PERFECT! All commands cleared.

✅ SANITIZE COMPLETE!

📋 NEXT STEPS:
   1. DELETE this sanitizer script
   2. RESTART your bot: python main.py
   3. Bot will sync commands on startup
   4. VERIFY in Discord
```

---

## 🔄 After Sanitizer Completes

### Step 1: Delete the Sanitizer Script
```powershell
# The script is for ONE-TIME use only
Remove-Item scripts\one_time_sanitizer.py
```

### Step 2: Restart Bot Normally
```powershell
python main.py
```

**What happens:**
- Bot connects
- `HippoBot.on_ready()` runs
- Automatically syncs commands based on config
- Check logs for "Command sync complete"

### Step 3: Verify in Discord

**A. Check Command Appearance:**
1. Close Discord completely (including system tray)
2. Wait 30 seconds
3. Reopen Discord
4. Navigate to your test guild
5. Type `/` in chat
6. You should see commands (no duplicates)

**B. Test the Problematic Command:**
```
1. Type /kvk
2. Select "ranking"
3. Select "submit"
4. Upload a test screenshot
5. (Optional) Select stage/day
6. Execute
```

**Expected Result:**
- ✅ Command executes cleanly
- ✅ No "Unknown Interaction" error
- ✅ Bot responds with processing message
- ✅ OCR validation runs

---

## 🎯 Success Criteria

After following the plan:

| Criterion | How to Verify | Expected |
|-----------|---------------|----------|
| No duplicate commands | Type `/kvk` in Discord | See ONE command |
| Global commands cleared | Run `prompt1_scope_inspector.py` | Global: 0 or 3 (depending on sync strategy) |
| Guild commands present | Run `prompt1_scope_inspector.py` | Guild: 3 |
| Submit works | Run `/kvk ranking submit` | No errors |
| Stale `/Translate` gone | Type `/tra` in Discord | Only see `/translate` (lowercase) |

---

## 🆘 If Issues Persist

### Commands Still Duplicate
**Cause:** Discord cache  
**Fix:**
```
1. Close Discord completely
2. Clear Discord cache:
   %AppData%\Discord\Cache
   %AppData%\Discord\Code Cache
3. Reopen Discord
4. Wait 60 seconds
```

### "Unknown Interaction" Still Happens
**Cause:** Multiple bot instances running  
**Fix:**
```
1. Check Task Manager
2. Kill ALL python.exe processes
3. Wait 30 seconds
4. Start bot once
5. Test again
```

### Commands Don't Appear
**Cause:** Bot didn't sync  
**Fix:**
```
1. Check bot logs for "Command sync complete"
2. If not present, bot may not have synced
3. Check integration_loader.py on_ready() logs
4. Manually sync:
   python scripts/sync_commands.py --guild 1423768684572184700
```

---

## 📋 Alternative: Manual Cleanup (Without Sanitizer)

If you prefer not to use the sanitizer script:

```powershell
# Start bot
python main.py
```

Then in Python console or add temporarily to `on_ready()`:

```python
# Get guild object
guild_obj = discord.Object(id=1423768684572184700)

# Clear global
global_cmds = await bot.tree.fetch_commands()
for cmd in global_cmds:
    await cmd.delete()
    print(f"Deleted global: {cmd.name}")

# Clear guild
guild_cmds = await bot.tree.fetch_commands(guild=guild_obj)
for cmd in guild_cmds:
    await cmd.delete(guild=guild_obj)
    print(f"Deleted guild: {cmd.name}")

# Wait
import asyncio
await asyncio.sleep(3)

# Resync guild-scoped
synced = await bot.tree.sync(guild=guild_obj)
print(f"Synced {len(synced)} commands to guild")
```

---

## 🎊 Post-Resolution

### Update Deployment Docs
Add to your deployment checklist:

```markdown
## Command Sync Strategy

**Development:**
- Use guild-scoped sync only
- Guild ID: 1423768684572184700
- Sync on bot startup (automatic)
- Commands appear instantly

**Production:**
- Use global sync
- Sync once per deploy
- Wait 1 hour for propagation
- Clear guild overrides first
```

### Add Monitoring
```python
# In on_ready(), add verification
async def on_ready(self):
    # ... existing sync code ...
    
    # Verify no duplicates
    global_cmds = await self.tree.fetch_commands()
    guild_cmds = await self.tree.fetch_commands(guild=test_guild)
    
    global_names = {c.name for c in global_cmds}
    guild_names = {c.name for c in guild_cmds}
    duplicates = global_names & guild_names
    
    if duplicates:
        logger.warning(f"Duplicate commands detected: {duplicates}")
```

---

## ✅ Ready to Execute

**Your command:**
```powershell
cd c:\discord_bot
python scripts\one_time_sanitizer.py
```

**Type when prompted:** `YES`

**Then:**
1. Wait for completion
2. Delete sanitizer script
3. Restart bot: `python main.py`
4. Test in Discord
5. Celebrate! 🎉

---

**Generated:** 2025-11-05  
**Execution Time:** ~30 seconds  
**Risk Level:** ⭕ None (can resync immediately)  
**Reversibility:** ✅ Full (just restart bot to resync)
