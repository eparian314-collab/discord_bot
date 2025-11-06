# Command Sanitizer & Diagnostic Suite

**Purpose:** Resolve duplicate commands and signature mismatches in Discord slash command tree.

---

## 🚨 Quick Fix: One-Time Sanitizer

If you have duplicate commands (e.g., `/kvk` appears twice), run this once:

```powershell
cd c:\discord_bot
python scripts\one_time_sanitizer.py
```

**What it does:**
1. Deletes ALL global commands
2. Deletes ALL guild commands
3. Verifies clean state
4. You then restart bot normally to resync

**⚠️ DELETE THIS SCRIPT AFTER SUCCESSFUL RUN** (one-time use only)

---

## 📊 Diagnostic Tools

### PROMPT 1: Scope Inspector
**Purpose:** See which commands are global vs guild-scoped

```powershell
python scripts\diagnostics\prompt1_scope_inspector.py
```

**Output:**
- List of all global commands
- List of all guild commands (per guild)
- Identifies duplicates between scopes
- Explains why duplicates cause issues

---

### PROMPT 2: Signature Diff
**Purpose:** Compare local code signature with live Discord API

```powershell
python scripts\diagnostics\prompt2_signature_diff.py
```

**Output:**
- Side-by-side comparison of `/kvk ranking submit`
- Parameter names, types, required flags
- Identifies mismatches (name, type, required/optional)
- Explains if signatures match

---

### PROMPT 3: Republish Planner
**Purpose:** Show exact steps to safely republish commands

```powershell
python scripts\diagnostics\prompt3_republish_planner.py
```

**Output:**
- Complete step-by-step plan
- Delete global commands
- Delete guild commands
- Resync guild-scoped from code
- Rate limit warnings
- Production migration guide

---

## 🔄 Workflow

### Problem: Duplicate Commands or "Unknown Interaction" Errors

**Diagnosis:**
1. Run `prompt1_scope_inspector.py` - Check for duplicates
2. Run `prompt2_signature_diff.py` - Check for mismatches

**Resolution:**
1. Run `one_time_sanitizer.py` - Clean slate
2. Restart bot normally - Resync from code
3. Test `/kvk ranking submit` - Verify working

**Verification:**
1. Close/reopen Discord client
2. Type `/kvk ranking submit`
3. Should see ONE command (not two)
4. Execute should work cleanly

---

## 📋 Understanding Command Scopes

### Global Commands
- **Scope:** All guilds the bot is in
- **Propagation:** Up to 1 hour
- **Use case:** Production release
- **Sync:** `await bot.tree.sync()`

### Guild Commands
- **Scope:** Single specified guild
- **Propagation:** Instant
- **Use case:** Development/testing
- **Sync:** `await bot.tree.sync(guild=discord.Object(id=GUILD_ID))`

### Why Duplicates Happen
If you sync BOTH global and guild, Discord stores BOTH copies:
- Global: `/kvk ranking submit` (parameters from old code)
- Guild: `/kvk ranking submit` (parameters from new code)

Discord uses the **guild version** but this causes:
- Confusion (two identical commands)
- Signature mismatches (if global is stale)
- "Unknown Interaction" errors

**Solution:** Keep commands in ONE scope only.

---

## 🔧 Manual Cleanup (Alternative to Sanitizer)

If you prefer manual control:

```python
import discord
from discord.ext import commands

DEV_GUILD_ID = 1423768684572184700

@bot.event
async def on_ready():
    # Delete global
    global_cmds = await bot.tree.fetch_commands()
    for cmd in global_cmds:
        await cmd.delete()
    
    # Delete guild
    guild_obj = discord.Object(id=DEV_GUILD_ID)
    guild_cmds = await bot.tree.fetch_commands(guild=guild_obj)
    for cmd in guild_cmds:
        await cmd.delete(guild=guild_obj)
    
    # Wait
    await asyncio.sleep(3)
    
    # Resync guild-scoped
    synced = await bot.tree.sync(guild=guild_obj)
    print(f"Synced {len(synced)} commands")
```

---

## 📝 Files in This Suite

```
scripts/
├── one_time_sanitizer.py          # Main cleanup tool (DELETE AFTER USE)
└── diagnostics/
    ├── prompt1_scope_inspector.py   # Show global vs guild commands
    ├── prompt2_signature_diff.py    # Compare local vs live signatures
    └── prompt3_republish_planner.py # Show republish steps
```

---

## ⚠️ Important Notes

### Rate Limits
- **Global sync:** 200/day (per bot)
- **Guild sync:** 200/day (per guild)
- **Deletions:** No limit

### Propagation Times
- **Global sync:** Up to 1 hour
- **Guild sync:** Instant
- **Deletions:** 3-30 seconds

### Best Practices
1. **Development:** Use guild-scoped sync
2. **Testing:** Sync to single test guild
3. **Production:** Sync globally when stable
4. **Never:** Sync on every bot restart
5. **Never:** Sync in loops

### Cache Issues
If commands still duplicate after cleanup:
1. Close Discord completely (including system tray)
2. Wait 30 seconds
3. Reopen Discord
4. Try again

---

## 🎯 Current Configuration

**Your test guild:** `1423768684572184700` (mars._.3's server test2)

**Current state (from diagnostic):**
- Global: 3 commands (`language`, `games`, `kvk`)
- Guild: 3 commands (`language`, `games`, `kvk`)
- **Issue:** Duplicates causing confusion

**Resolution:**
```powershell
python scripts\one_time_sanitizer.py
# Answer "YES" when prompted
# Wait for completion
# Restart bot: python main.py
```

---

## 🆘 Troubleshooting

### "Unknown Interaction" Error
**Cause:** Signature mismatch or stale commands  
**Fix:** Run sanitizer, restart bot

### Commands Appear Twice
**Cause:** Both global and guild scope populated  
**Fix:** Run sanitizer to clear one scope

### Commands Don't Appear
**Cause:** Not synced or Discord cache  
**Fix:** Restart Discord client, wait 30 seconds

### "Command Already Exists" Error
**Cause:** Trying to add duplicate  
**Fix:** Clear existing commands first

---

## ✅ Success Criteria

After running sanitizer and restarting bot:
- ✅ `/kvk ranking submit` appears once (not twice)
- ✅ Command executes without errors
- ✅ `prompt1_scope_inspector.py` shows no duplicates
- ✅ `prompt2_signature_diff.py` shows no mismatches

---

## 🔄 Future Prevention

Add to your deployment checklist:

1. **Before deploying:**
   ```powershell
   python scripts/diagnostics/prompt2_signature_diff.py
   ```
   Ensure no mismatches

2. **Development:**
   - Always use guild sync
   - Never sync both global + guild

3. **Production:**
   - Clear guild overrides
   - Sync globally
   - Wait 1 hour
   - Verify in multiple guilds

---

**Created:** 2025-11-05  
**For:** HippoBot Command Tree Diagnostic  
**Status:** Ready to use
