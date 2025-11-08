# Slash Command Diagnosis Report
**Date**: November 6, 2025  
**Issue**: `/kvk ranking submit` and other commands showing `CommandSignatureMismatch` errors

## Root Cause Analysis

### Problem Summary
Users were unable to use `/kvk ranking submit` and several other commands, receiving `CommandSignatureMismatch` errors even though the bot reported successful command syncs.

### Commands Affected
From log analysis (`logs/hippo_bot.log`), the following commands had signature mismatches:
- `/kvk ranking submit`
- `/kvk ranking leaderboard`
- `/kvk ranking stats`
- `/kvk ranking view`
- `/ranking_compare_me`
- `/ranking_results`

### Why Commands Weren't Syncing

#### Issue 1: Hash-Based Sync Detection
The bot uses a schema hash system (`discord_bot/core/schema_hash.py`) to avoid unnecessary syncs:
```
2025-11-06T12:17:46 INFO Schema hash unchanged for guild:1423768684572184700, skipping sync
2025-11-06T12:17:46 INFO Skipping guild command sync (schema unchanged)
```

**Problem**: While the local command tree was correct (26 commands), the hash system thought nothing changed, so it skipped the sync. Meanwhile, Discord's server-side cache still held **old, broken command signatures**.

#### Issue 2: Discord Server-Side Cache
Discord caches command schemas on their servers. Even when we did sync commands previously, the cache wasn't properly invalidated, causing the mismatch to persist.

## Solution Implemented

### Step 1: Force Command Sync
Set environment variable:
```powershell
$env:FORCE_COMMAND_SYNC="true"
```

### Step 2: Three-Phase Sync Sequence
Modified `integration_loader.py` to perform a full cache-clearing sync:

```python
# PHASE 1: Clear stale cached commands
guild_obj_clear = discord.Object(id=guild_id)
self.tree.clear_commands(guild=guild_obj_clear)
logger.info(f"🧹 Cleared stale guild commands for {name} ({guild_id})")

# PHASE 2: Copy global command tree to guild
guild_obj_copy = discord.Object(id=guild_id)
self.tree.copy_global_to(guild=guild_obj_copy)
logger.info(f"🔧 Copied global command tree to guild {name} ({guild_id})")

# PHASE 3: Sync to Discord API
guild_obj_sync = discord.Object(id=guild_id)
synced_guild = await self.tree.sync(guild=guild_obj_sync)
logger.info(f"🔍 DIAGNOSTIC: Discord API returned {len(synced_guild)} commands synced")
```

### Step 3: Verification
After forced sync:
```
2025-11-06T12:19:27 INFO 🧹 Cleared stale guild commands for mars._.3's server test2
2025-11-06T12:19:27 INFO 🔧 Copied global command tree to guild mars._.3's server test2
2025-11-06T12:19:27 INFO 🔍 DIAGNOSTIC: Discord API returned 26 commands synced
2025-11-06T12:19:27 INFO Command sync complete (schema_version=1, mars._.3's server test2: 26)
```

## Technical Details

### Discord.py v2.x API Requirements
For guild-specific syncs, discord.py v2.x requires:
1. `tree.clear_commands(guild=...)` - Clear Discord's cache
2. `tree.copy_global_to(guild=...)` - Copy global tree to guild scope
3. `tree.sync(guild=...)` - Push to Discord API

**Critical**: Steps 1 & 2 are required but were missing in earlier implementations.

### Hash System Bypass
When `FORCE_COMMAND_SYNC="true"`, the schema hash check is bypassed:
```python
env_force = os.getenv("FORCE_COMMAND_SYNC", "").lower() in {"1", "true", "yes"}
force_sync = force or env_force

if should_sync_commands(self, scope=scope, force=force_sync):
    # Perform full sync sequence
```

## Prevention Strategy

### Short-Term
1. Keep `FORCE_COMMAND_SYNC="true"` in `.env` for next few bot restarts
2. Monitor logs for any new `CommandSignatureMismatch` errors
3. Test all `/kvk ranking *` commands in Discord

### Long-Term
1. **Implement self-healing sync**: Add `on_app_command_error` handler to detect `CommandSignatureMismatch` and automatically trigger forced resync
2. **Improve hash detection**: Consider adding a fallback verification step that compares remote vs local schemas
3. **Add sync metrics**: Track sync success/failure rates and command usage

## Testing Checklist

- [ ] Test `/kvk ranking submit` with a screenshot
- [ ] Test `/kvk ranking leaderboard`
- [ ] Test `/kvk ranking view`
- [ ] Test `/kvk ranking stats`
- [ ] Test `/ranking_compare_me`
- [ ] Test `/ranking_results`
- [ ] Check logs for any `CommandSignatureMismatch` errors
- [ ] Verify all 26 commands appear in Discord's slash command menu

## References

- **Bot Logs**: `logs/hippo_bot.log`
- **Integration Loader**: `discord_bot/integrations/integration_loader.py`
- **Schema Hash System**: `discord_bot/core/schema_hash.py`
- **Ranking Cog**: `discord_bot/cogs/ranking_cog.py`

## Next Steps

1. **User Testing**: Ask users to test `/kvk ranking submit` and report results
2. **Log Monitoring**: Watch for any CommandSignatureMismatch in real-time logs
3. **Documentation**: Update the main repair documentation with this diagnosis
4. **Implement Auto-Heal**: Add the `on_app_command_error` handler for future-proofing
