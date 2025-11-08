# REAL ROOT CAUSE: Duplicate /kvk in Discord

## You Were Right - I Was Wrong

The screenshot clearly shows TWO `/kvk` entries in Discord's command list. The diagnostics confirm the code structure is correct (single Group object, proper parent references), so the issue is:

### Most Likely Cause: Discord Command Cache

Discord caches slash commands and the cache doesn't always clear immediately. If you:
1. Synced commands when `/kvk` was structured differently
2. Then changed the code
3. Synced again

Discord might be showing BOTH the old and new versions.

### Solution: Nuclear Command Sync

```bash
# Clear ALL commands and re-sync
python scripts/nuclear_sync.py
```

This will:
1. Delete ALL global commands
2. Delete ALL guild commands  
3. Re-register from scratch
4. Force Discord to forget the old structure

### Alternative Causes:

#### 1. Integration Loader Called Twice
Check if `IntegrationLoader.build()` is being called multiple times in your startup sequence.

**File to check:** `main.py` or wherever you initialize the bot

#### 2. Manual bot.tree.add_command() Somewhere
Search for any place that manually calls:
```python
bot.tree.add_command(ui_groups.kvk, override=True)
```

**Already found in:** `ui_groups.register_command_groups()` line 52

**Check if it's called elsewhere:**
```bash
grep -r "bot.tree.add_command" --include="*.py"
```

## Immediate Fix

Run this:

```python
# In Python console or as a script
import asyncio
from discord_bot.integrations.integration_loader import build_application

async def clear_commands():
    bot, registry = build_application()
    await bot.login(os.getenv('DISCORD_TOKEN'))
    
    # Clear global
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    
    # Clear all guilds
    for guild in bot.guilds:
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
    
    print("All commands cleared. Restart bot to re-sync.")
    await bot.close()

asyncio.run(clear_commands())
```

Then restart your bot normally.

## Prevention

Add this check to `integration_loader.py` to prevent double registration:

```python
# In IntegrationLoader.build() or register_command_groups()
if hasattr(bot, '_command_groups_registered'):
    logger.warning("Command groups already registered - skipping")
    return

ui_groups.register_command_groups(bot)
bot._command_groups_registered = True
```
