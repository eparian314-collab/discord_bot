# HippoBot Slash Command Sync System - Complete Documentation

## Overview

HippoBot uses a sophisticated command sync system that prevents unnecessary Discord API calls and avoids command signature mismatches through hash-based change detection.

## Problem Statement

### Issues Resolved
1. **Duplicate Commands**: Commands appearing in both GLOBAL and GUILD scopes
2. **CommandSignatureMismatch**: Stale global registrations conflicting with updated code
3. **Excessive Syncing**: Commands re-synced on every bot restart
4. **Confusion**: `/kvk ranking submit` executing wrong version due to duplicates

## Architecture

### Command Sync Modes

#### Development Mode (Guild-Only Sync)
- **Configuration**: Set `TEST_GUILDS` in environment/config
- **Behavior**: Commands sync ONLY to specified test guilds
- **Advantages**:
  - Instant command updates (no 1-hour global propagation delay)
  - Safe testing environment
  - No impact on production servers

#### Production Mode (Global Sync)
- **Configuration**: Set `SYNC_GLOBAL_COMMANDS=1` or `PRIMARY_GUILD_NAME=<unset>`
- **Behavior**: Commands sync globally to ALL servers
- **Advantages**:
  - Single source of truth
  - Commands available in all servers immediately after 1-hour propagation

### Hash-Based Sync System

Commands are only synced when the schema changes, detected via SHA256 hash comparison.

**Schema Hash Includes**:
- Command names
- Command descriptions
- Parameter names, types, and requirements
- Choice values
- Permission settings
- Subcommand structure

**What Triggers a Sync**:
- First run (no previous hash exists)
- Command added/removed
- Parameter type changed
- Description modified
- Choices added/removed/changed
- Manual force with `FORCE_COMMAND_SYNC=1`

**What Does NOT Trigger a Sync**:
- Bot restart with unchanged code
- Code comments changed
- Non-command code modified
- Log messages changed

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DISCORD_TOKEN` | Bot token (**required**) | - | `MTIzNDU2Nzg5MDEyMzQ1Njc4.GaBcDe...` |
| `TEST_GUILDS` | Guild IDs for development sync | - | `1234567890,9876543210` |
| `PRIMARY_GUILD_NAME` | Guild name for single-guild sync | - | `"My Test Server"` |
| `SYNC_GLOBAL_COMMANDS` | Enable global sync | `1` (true) | `0` (false for dev) |
| `FORCE_COMMAND_SYNC` | Force sync regardless of hash | `0` (false) | `1` (true) |
| `OWNER_IDS` | User IDs to receive sync alerts | - | `123456789012345678` |

### Configuration Files

#### config.json (optional)
```json
{
  "LOG_LEVEL": "INFO",
  "TEST_GUILDS": "1234567890,9876543210",
  "OWNER_IDS": "123456789012345678",
  "SYNC_GLOBAL_COMMANDS": "0"
}
```

### Sync Policy Matrix

| Scenario | `SYNC_GLOBAL_COMMANDS` | `TEST_GUILDS` | `PRIMARY_GUILD_NAME` | Result |
|----------|------------------------|---------------|----------------------|--------|
| **Development** | `0` or unset | Set | Unset | Guild-only sync to TEST_GUILDS |
| **Single Server** | Auto `0` | Ignored | Set | Guild-only sync to named guild |
| **Production** | `1` | Ignored | Unset | Global sync to all servers |
| **Hybrid** | `1` | Set | Unset | Global + guild sync (not recommended) |

## Operations

### Phase 1: Initial Setup (First Time)

1. **Set Environment Variables**
   ```powershell
   $env:DISCORD_TOKEN="your_bot_token_here"
   $env:TEST_GUILDS="1234567890"
   $env:SYNC_GLOBAL_COMMANDS="0"  # Development mode
   ```

2. **Verify Configuration**
   ```powershell
   python -c "import os; print('Token:', os.getenv('DISCORD_TOKEN')[:20], '...'); print('Guilds:', os.getenv('TEST_GUILDS'))"
   ```

### Phase 2: Diagnostic (Check Current State)

Run the diagnostic to see what commands are registered where:

```powershell
python scripts/diagnostics/command_sync_diagnostic.py
```

**Output**: `logs/diagnostics/command_scope_inventory.json`

This shows:
- All global commands
- All guild commands
- Duplicate commands (in both scopes)
- Command IDs and signatures

### Phase 3: Cleanup (Remove Stale Global Commands)

**⚠️ WARNING**: This deletes ALL global commands. Only run if you intend guild-only sync.

```powershell
# Interactive (requires typing "DELETE" to confirm)
python scripts/diagnostics/command_cleanup.py

# Non-interactive (auto-confirm)
python scripts/diagnostics/command_cleanup.py --force
```

**Output**: `logs/diagnostics/command_cleanup_report.json`

This will:
1. Delete all global commands
2. Re-sync to TEST_GUILDS
3. Verify cleanup success

### Phase 4: Normal Operation

Start the bot normally:

```powershell
python -m discord_bot.main
```

**First Run**: Commands sync to Discord (schema hash doesn't exist)
**Subsequent Runs**: Commands skip sync if schema unchanged (uses cached hash)

### Phase 5: Force Sync (When Needed)

If commands seem out of sync or you want to force a refresh:

```powershell
$env:FORCE_COMMAND_SYNC="1"
python -m discord_bot.main
```

Or clear the hash cache:

```powershell
Remove-Item data/command_schema_hashes.json
python -m discord_bot.main
```

## Command Organization

### UI Groups (Hierarchical Structure)

```
/language
  ├── translate
  ├── assign
  ├── remove
  └── sos
      ├── add
      ├── remove
      └── list

/games
  ├── pokemon
  │   ├── catch
  │   └── battle
  └── cookies
      └── check

/kvk
  └── ranking
      ├── submit      ← Main submission command
      ├── view
      ├── leaderboard
      └── stats

/rankings              ← Historic analysis (separate root command)
/ranking_compare_me    ← Player self-comparison
/ranking_compare_others ← Player peer comparison

/admin
  ├── help
  └── sync
```

### Command Tree Structure

**Defined in**: `discord_bot/core/ui_groups.py`

**Why Separate File**:
- Avoids circular imports between cogs
- Provides single source of truth for command hierarchy
- Allows shared group registration

**Registration**:
```python
# In integration_loader.py build() method:
ui_groups.register_command_groups(self.bot)
```

## Troubleshooting

### Issue: Commands Not Appearing in Discord

**Symptoms**:
- Slash commands don't show up when typing `/`
- Commands worked before, now missing

**Diagnosis**:
```powershell
python scripts/diagnostics/command_sync_diagnostic.py
```

**Solutions**:
1. **Hash out of sync**: Force sync with `FORCE_COMMAND_SYNC=1`
2. **Wrong scope**: Check `SYNC_GLOBAL_COMMANDS` and `TEST_GUILDS` config
3. **Guild not connected**: Verify bot is in the guild specified in `TEST_GUILDS`
4. **Permissions**: Bot needs `applications.commands` scope

### Issue: CommandSignatureMismatch Error

**Symptoms**:
- Error in logs: `CommandSignatureMismatch: ...`
- Commands execute but show error message
- `/kvk ranking submit` runs wrong version

**Root Cause**: Global and guild commands have different signatures

**Solution**:
```powershell
# Remove all global commands
python scripts/diagnostics/command_cleanup.py --force

# Restart bot
python -m discord_bot.main
```

### Issue: Duplicate Commands

**Symptoms**:
- Command appears twice in autocomplete
- Different versions execute randomly

**Diagnosis**:
```powershell
python scripts/diagnostics/command_sync_diagnostic.py
# Check "duplicates" section in output
```

**Solution**: Run cleanup script (Phase 3 above)

### Issue: Commands Sync Every Restart

**Symptoms**:
- "Syncing commands..." message on every bot start
- Slow startup

**Diagnosis**:
```powershell
# Check if hash file exists
Test-Path data/command_schema_hashes.json
```

**Solutions**:
1. **Hash file missing**: Normal for first run, will be created
2. **Permissions issue**: Verify bot can write to `data/` directory
3. **Schema changing**: Check if you're modifying command code between restarts

### Issue: Global Sync Takes Too Long

**Symptom**: Commands don't appear in servers after sync

**Explanation**: Global command propagation takes up to 1 hour per Discord's design

**Solution**: Use guild-only sync for development/testing

## Schema Hash System

### File Location
`data/command_schema_hashes.json`

### Format
```json
{
  "global": "a1b2c3d4e5f6...",
  "guild:1234567890": "f6e5d4c3b2a1...",
  "guild:9876543210": "9876abcdef01..."
}
```

### Manual Operations

**View Current Hashes**:
```powershell
Get-Content data/command_schema_hashes.json | ConvertFrom-Json
```

**Force Sync All Scopes**:
```powershell
Remove-Item data/command_schema_hashes.json
```

**Force Sync Specific Scope** (requires Python):
```python
import json
from pathlib import Path

hash_file = Path("data/command_schema_hashes.json")
hashes = json.loads(hash_file.read_text())
del hashes["guild:1234567890"]  # Remove specific scope
hash_file.write_text(json.dumps(hashes, indent=2))
```

## Sync Lifecycle Flowchart

```
Bot Start
    ↓
on_ready() triggered
    ↓
Resolve target guilds (TEST_GUILDS / PRIMARY_GUILD_NAME)
    ↓
For each scope (global / guild:ID):
    ↓
    Compute current schema hash (SHA256 of command tree)
    ↓
    Load previous hash from data/command_schema_hashes.json
    ↓
    Compare hashes
    ↓
    ┌─────────────┬─────────────┐
    │ Unchanged   │ Changed     │
    ↓             ↓
 Skip sync    Perform sync
    ↓             ↓
 Log info    await tree.sync()
                  ↓
              Save new hash
                  ↓
              Mark synced
    ↓             ↓
    └─────────────┘
    ↓
Verify remote schema (compare local vs Discord)
    ↓
Report mismatches to OWNER_IDS
    ↓
Send startup message to bot channels
    ↓
Bot ready for use
```

## Best Practices

### Development Workflow
1. Set `TEST_GUILDS` to your development server
2. Set `SYNC_GLOBAL_COMMANDS=0`
3. Make command changes
4. Bot auto-detects changes and syncs to test guild only
5. Test commands immediately (no 1-hour wait)

### Production Deployment
1. Test all commands in development
2. Set `SYNC_GLOBAL_COMMANDS=1`
3. Remove `TEST_GUILDS` or set to empty
4. Deploy bot
5. Wait 1 hour for global propagation
6. Verify commands in production servers

### Emergency Rollback
If commands break in production:
1. Revert code to previous version
2. Set `FORCE_COMMAND_SYNC=1`
3. Restart bot
4. Commands will re-sync with old signatures

## API Reference

### Core Functions

#### `compute_command_schema_hash(bot, scope="global") -> str`
Computes SHA256 hash of command tree schema.

**Parameters**:
- `bot`: Discord bot instance
- `scope`: Scope identifier (`"global"` or `"guild:123456"`)

**Returns**: Hex string of hash

#### `should_sync_commands(bot, scope="global", force=False) -> bool`
Determines if sync is needed based on hash comparison.

**Parameters**:
- `bot`: Discord bot instance
- `scope`: Scope identifier
- `force`: Skip hash check and always return True

**Returns**: `True` if sync needed, `False` otherwise

#### `mark_synced(bot, scope="global") -> bool`
Saves current schema hash after successful sync.

**Parameters**:
- `bot`: Discord bot instance
- `scope`: Scope identifier

**Returns**: `True` if save succeeded

#### `clear_schema_hashes() -> bool`
Clears all saved hashes (forces sync on next run).

**Returns**: `True` if clear succeeded

## Migration Guide

### From Manual Sync to Hash-Based

**Before**:
```python
# Always synced on every restart
await bot.tree.sync()
```

**After**:
```python
# Only syncs when schema changes
# (Built into HippoBot.on_ready())
```

No code changes needed - hash system is automatic.

### From Global to Guild-Only

1. **Run cleanup**:
   ```powershell
   python scripts/diagnostics/command_cleanup.py --force
   ```

2. **Update config**:
   ```powershell
   $env:SYNC_GLOBAL_COMMANDS="0"
   $env:TEST_GUILDS="your_guild_id"
   ```

3. **Restart bot**:
   ```powershell
   python -m discord_bot.main
   ```

### From Guild-Only to Global

1. **Update config**:
   ```powershell
   $env:SYNC_GLOBAL_COMMANDS="1"
   Remove-Item Env:TEST_GUILDS  # Or set to empty
   ```

2. **Clear hashes** (force sync):
   ```powershell
   Remove-Item data/command_schema_hashes.json
   ```

3. **Restart bot**:
   ```powershell
   python -m discord_bot.main
   ```

4. **Wait 1 hour** for global propagation

## Support & Debugging

### Enable Debug Logging

```powershell
$env:LOG_LEVEL="DEBUG"
python -m discord_bot.main
```

Look for these log messages:
- `"Computed schema hash for <scope>: <hash>..."`
- `"Schema hash unchanged for <scope>, skipping sync"`
- `"Schema hash changed for <scope>, sync needed"`

### Diagnostic Outputs

All diagnostics save to `logs/diagnostics/`:
- `command_scope_inventory.json` - Current command registrations
- `command_cleanup_report.json` - Cleanup operation results

### Getting Help

If you encounter issues:
1. Run diagnostic: `python scripts/diagnostics/command_sync_diagnostic.py`
2. Check logs: `logs/hippobot.log`
3. Verify config: Check environment variables
4. Review this document's Troubleshooting section

## Appendix: Discord Command Sync Behavior

### Global Commands
- Synced to ALL servers the bot is in
- Propagation takes up to 1 hour
- Stored in Discord's global command registry
- Single definition shared across all guilds

### Guild Commands
- Synced to specific guild only
- Appear immediately (within seconds)
- Stored in guild-specific command registry
- Can have different definitions per guild

### Precedence
If a command exists in both global and guild scope:
- **Guild command takes precedence** in that guild
- Other guilds see the global command
- This causes confusion and should be avoided

### Rate Limits
- Global sync: 200 commands per day
- Guild sync: 200 commands per day per guild
- Hash-based system minimizes syncs to stay within limits
