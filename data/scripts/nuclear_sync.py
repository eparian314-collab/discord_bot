"""
Nuclear option: Completely clear ALL commands (global + guild) and force fresh sync.

Use this when Discord has cached old command signatures that cause mismatches.
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure parent directory is in path
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import discord
from discord.ext import commands

from discord_bot.integrations import load_config, build_application


async def main():
    try:
        load_config()
    except Exception as exc:
        print(f"Warning: load_config() failed: {exc}")
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN not set!")
        return
    
    test_guilds_str = os.getenv("TEST_GUILDS", "")
    test_guild_ids = []
    if test_guilds_str:
        test_guild_ids = [int(gid.strip()) for gid in test_guilds_str.split(",") if gid.strip()]
    
    print("=" * 80)
    print("🚨 NUCLEAR COMMAND SYNC - CLEARING EVERYTHING")
    print("=" * 80)
    print(f"Test Guild IDs: {test_guild_ids}")
    print()
    
    # Build bot with all cogs loaded
    bot, registry = build_application()
    
    async with bot:
        await bot.login(token)
        print(f"✅ Logged in as {bot.user}")
        print()
        
        # STEP 1: Clear ALL global commands
        print("=" * 80)
        print("STEP 1: Nuclear Clear - Global Commands")
        print("=" * 80)
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print("✅ Cleared all global commands")
        print()
        
        # STEP 2: Clear ALL guild commands
        print("=" * 80)
        print("STEP 2: Nuclear Clear - Guild Commands")
        print("=" * 80)
        for guild_id in test_guild_ids:
            guild_obj = discord.Object(id=guild_id)
            bot.tree.clear_commands(guild=guild_obj)
            await bot.tree.sync(guild=guild_obj)
            print(f"✅ Cleared all commands for guild {guild_id}")
        print()
        
        # STEP 3: Wait 2 seconds for Discord to process
        print("⏳ Waiting 2 seconds for Discord cache to clear...")
        await asyncio.sleep(2)
        print()
        
        # STEP 4: Fresh sync to guilds
        print("=" * 80)
        print("STEP 3: Fresh Sync - Guild Commands")
        print("=" * 80)
        for guild_id in test_guild_ids:
            guild_obj = discord.Object(id=guild_id)
            # Copy global commands to guild
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"✅ Synced {len(synced)} commands to guild {guild_id}")
            for cmd in synced:
                print(f"   • {cmd.name}")
        print()
        
        print("=" * 80)
        print("✅ NUCLEAR SYNC COMPLETE!")
        print("=" * 80)
        print()
        print("🔄 Now restart your Discord client (close and reopen)")
        print("⏱️  Wait 30 seconds, then try your commands")
    
    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())


