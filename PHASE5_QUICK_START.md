# PHASE 5 QUICK REFERENCE - Command Sync Repair

## WHAT WAS DONE:
✅ Fixed `Command.to_dict()` missing 'tree' argument error in `discord_bot/core/schema_hash.py`
✅ Cleared stale schema hash file (`data/command_schema_hashes.json`)
✅ Prepared bot for full command re-sync

## CURRENT .ENV SETTINGS:
```properties
SYNC_GLOBAL_COMMANDS="false"          # Guild-only sync ✅
TEST_GUILDS=1423768684572184700        # Your test guild ✅
FORCE_COMMAND_SYNC="true"              # Force sync enabled ✅
```

## NEXT STEP - RESTART THE BOT:
```powershell
python main.py
```

## WHAT TO WATCH FOR:

### ✅ SUCCESS INDICATORS:
- No "Failed to normalize command" warnings
- "Synced X commands to guild mars._.3's server test2"
- All commands appear in Discord `/` menu
- No "command missing from remote registry" errors

### ❌ FAILURE INDICATORS:
- Still seeing "missing 1 required positional argument: 'tree'"
- "command missing from remote registry" errors persist
- Commands still not syncing

## IF IT WORKS:
1. Test `/kvk ranking submit` in Discord
2. Verify all other commands work
3. Set `FORCE_COMMAND_SYNC="false"` in .env for future runs
4. Restart bot one more time to verify schema hash system stability

## IF IT DOESN'T WORK:
1. Copy the full error log
2. Check if there's a different error message
3. We'll troubleshoot the new issue

---

**Full diagnostic log saved to**: `logs/phase5_ultra_think_session.md`
