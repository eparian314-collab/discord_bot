# ✅ Command Sanitizer Suite - Complete Implementation

**Date:** 2025-11-05  
**Status:** Ready for Execution  
**Purpose:** Resolve duplicate commands and "Unknown Interaction" errors

---

## 🎯 Problem Summary

**Current State:**
- ✅ Detected: 26 global commands + 3 guild commands
- ⚠️ Issue: 3 commands exist in BOTH scopes (`/language`, `/games`, `/kvk`)
- ⚠️ Stale: `/Translate` (capitalized) with no description
- ✅ Verified: Command signatures match between code and Discord

**Root Cause:**
- Previous nuclear sync registered commands in BOTH global AND guild scope
- Discord shows both copies, causing confusion
- Guild version takes precedence, but duplicates appear in command list

---

## 🛠️ Tools Created

### 1. One-Time Sanitizer (PRIMARY TOOL)
**File:** `scripts/one_time_sanitizer.py`

**Purpose:** Clean slate - delete all commands and prepare for resync

**Usage:**
```powershell
python scripts\one_time_sanitizer.py
# Type: YES when prompted
```

**What it does:**
1. Deletes ALL 26 global commands
2. Deletes ALL 3 guild commands
3. Verifies clean state (0 global, 0 guild)
4. Provides next steps

**⚠️ DELETE AFTER SUCCESSFUL RUN** (one-time use)

---

### 2. Diagnostic Tools

#### PROMPT 1: Scope Inspector
**File:** `scripts/diagnostics/prompt1_scope_inspector.py`

**Purpose:** Show which commands are in global vs guild scope

**Usage:**
```powershell
python scripts\diagnostics\prompt1_scope_inspector.py
```

**Output:**
- Lists all global commands with IDs
- Lists all guild commands per guild
- Identifies duplicates between scopes
- Explains why duplicates cause issues

**Current Output:**
```
Global commands: 26
Guild 1423768684572184700: 3 commands
⚠️ Duplicates: /games, /kvk, /language
```

---

#### PROMPT 2: Signature Diff
**File:** `scripts/diagnostics/prompt2_signature_diff.py`

**Purpose:** Compare local code signature with live Discord

**Usage:**
```powershell
python scripts\diagnostics\prompt2_signature_diff.py
```

**Output:**
- Side-by-side comparison of `/kvk ranking submit`
- Parameter names, types, required flags
- Identifies mismatches

**Current Output:**
```
✅ Signatures match
   - screenshot: discord.Attachment (required)
   - stage: Optional[str] (optional, 2 choices)
   - day: Optional[int] (optional, 6 choices)
```

---

#### PROMPT 3: Republish Planner
**File:** `scripts/diagnostics/prompt3_republish_planner.py`

**Purpose:** Show complete republish procedure

**Usage:**
```powershell
python scripts\diagnostics\prompt3_republish_planner.py
```

**Output:**
- 7-step procedure
- Rate limit warnings
- Safety notes
- Production migration guide

---

## 📋 Documentation Files

### 1. Sanitizer README
**File:** `scripts/SANITIZER_README.md`

**Contents:**
- Quick fix guide
- Tool descriptions
- Workflow diagrams
- Troubleshooting
- Best practices

---

### 2. Final Action Plan
**File:** `FINAL_ACTION_PLAN.md`

**Contents:**
- Current state summary
- Step-by-step execution
- Success criteria
- Troubleshooting guide
- Post-resolution tasks

---

### 3. Diagnostic Complete Report
**File:** `DIAGNOSTIC_COMPLETE.md`

**Contents:**
- Phase 8-12 results
- Root cause analysis
- Resolution summary
- Verification checklist

---

### 4. Command Registry Diagnostic
**File:** `COMMAND_REGISTRY_DIAGNOSTIC.md`

**Contents:**
- Initial diagnostic findings
- Command tree hierarchy
- Sync recommendations
- Minimal safe procedure

---

### 5. Phases 8-12 Resolution
**File:** `PHASES_8-12_SYNC_RESOLUTION.md`

**Contents:**
- Detailed phase analysis
- Signature verification
- Group collision detection
- Sync strategy determination

---

## 🚀 Quick Start Execution

### Step 1: Run Sanitizer
```powershell
cd c:\discord_bot
python scripts\one_time_sanitizer.py
```

When prompted, type: `YES`

### Step 2: Wait for Completion
Expected output:
```
✅ SANITIZE COMPLETE!
   Global commands deleted: 26
   Guild commands deleted: 3
   After state: 0 global, 0 guild
```

### Step 3: Delete Sanitizer
```powershell
Remove-Item scripts\one_time_sanitizer.py
```

### Step 4: Restart Bot
```powershell
python main.py
```

Bot will automatically sync commands on startup.

### Step 5: Verify in Discord
1. Close Discord completely
2. Wait 30 seconds
3. Reopen Discord
4. Type `/kvk ranking submit`
5. Should see ONE command (not two)
6. Execute should work cleanly

---

## 📊 Current State (Before Sanitizer)

**Global Scope (26 commands):**
```
/language, /games, /kvk          # Main groups (DUPLICATES)
/translate, /keyword, /admin     # Standalone
/help, /language_assign, etc.    # More standalone
/Translate                       # STALE (capitalized)
... and 17 more
```

**Guild Scope (3 commands):**
```
/language, /games, /kvk          # Main groups (DUPLICATES)
```

**Issue:**
- 3 commands appear twice (global + guild)
- `/Translate` is stale and broken
- Discord uses guild version but shows both

---

## 📊 Expected State (After Sanitizer + Bot Restart)

**Option A: Guild-Scoped (Recommended for Development)**
```
Global: 0 commands
Guild 1423768684572184700: 3 commands (/language, /games, /kvk)
```

**Benefits:**
- ✅ Instant sync (no propagation)
- ✅ Isolated to test guild
- ✅ Easy to test changes

---

**Option B: Global-Scoped (Production)**
```
Global: 26 commands (all commands)
Guild 1423768684572184700: 0 commands
```

**Benefits:**
- ✅ Available in all guilds
- ⚠️ 1-hour propagation delay

---

## ✅ Success Criteria

After execution:

| Check | Command | Expected Result |
|-------|---------|-----------------|
| No duplicates | Type `/kvk` in Discord | See ONE command |
| Global cleared | Run `prompt1_scope_inspector.py` | Global: 0 or 3 |
| Guild populated | Run `prompt1_scope_inspector.py` | Guild: 3 |
| Submit works | `/kvk ranking submit` | Executes cleanly |
| No stale commands | Type `/Translate` | Not found |
| Signatures match | Run `prompt2_signature_diff.py` | No mismatches |

---

## 🆘 Troubleshooting

### Issue: Commands still duplicate after sanitizer
**Cause:** Discord client cache  
**Fix:**
```
1. Close Discord (including system tray)
2. Clear cache: %AppData%\Discord\Cache
3. Reopen Discord
4. Wait 60 seconds
```

---

### Issue: "Unknown Interaction" persists
**Cause:** Multiple bot instances  
**Fix:**
```
1. Open Task Manager
2. Kill ALL python.exe processes
3. Wait 30 seconds
4. Start bot once: python main.py
```

---

### Issue: Commands don't appear
**Cause:** Sync didn't run  
**Fix:**
```
1. Check bot logs for "Command sync complete"
2. If missing, manually sync:
   python scripts/sync_commands.py --guild 1423768684572184700
```

---

## 📁 File Structure

```
c:\discord_bot\
├── FINAL_ACTION_PLAN.md                    # This execution guide
├── DIAGNOSTIC_COMPLETE.md                  # Phase 8-12 summary
├── COMMAND_REGISTRY_DIAGNOSTIC.md          # Initial findings
├── PHASES_8-12_SYNC_RESOLUTION.md         # Detailed analysis
├── COMMAND_SANITIZER_IMPLEMENTATION.md     # This file
│
├── scripts\
│   ├── one_time_sanitizer.py              # PRIMARY TOOL ⭐
│   ├── SANITIZER_README.md                 # Tool documentation
│   │
│   └── diagnostics\
│       ├── prompt1_scope_inspector.py      # Show global vs guild
│       ├── prompt2_signature_diff.py       # Compare signatures
│       └── prompt3_republish_planner.py    # Show republish steps
│
├── command_tree_code.json                  # Extracted from source
├── command_tree_live.json                  # Fetched from Discord
└── phase8_signature_analysis.json          # Detailed comparison
```

---

## 🎊 Post-Resolution

### Update Your Workflow

**Development:**
```powershell
# Always use guild sync
python scripts/sync_commands.py --guild 1423768684572184700
```

**Production:**
```powershell
# Clear guild overrides first
python scripts/sync_commands.py --guild 1423768684572184700 --clear

# Then sync globally
python scripts/sync_commands.py

# Wait 1 hour, then verify
```

---

### Add to Deployment Checklist

```markdown
## Command Sync Verification

Before deploying:
1. Run: python scripts/diagnostics/prompt2_signature_diff.py
2. Verify no mismatches
3. Choose sync strategy (guild vs global)
4. Execute sync
5. Verify with: python scripts/diagnostics/prompt1_scope_inspector.py
6. Test in Discord
```

---

## 📞 Quick Reference

**Problem:** Duplicate commands  
**Tool:** `python scripts/one_time_sanitizer.py`

**Problem:** Unknown Interaction error  
**Tool:** `python scripts/diagnostics/prompt2_signature_diff.py`

**Problem:** Need to see command scope  
**Tool:** `python scripts/diagnostics/prompt1_scope_inspector.py`

**Problem:** Need republish steps  
**Tool:** `python scripts/diagnostics/prompt3_republish_planner.py`

---

## ✅ Ready to Execute

**Your next command:**
```powershell
python scripts\one_time_sanitizer.py
```

**Then:** Follow steps in `FINAL_ACTION_PLAN.md`

---

**Created:** 2025-11-05  
**Tools:** 4 scripts + 5 documentation files  
**Status:** ✅ Complete and ready  
**Execution Time:** ~2 minutes total  
**Risk:** ⭕ None (fully reversible)
