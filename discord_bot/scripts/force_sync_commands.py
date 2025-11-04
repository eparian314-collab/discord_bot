"""
Force sync Discord slash commands immediately.

This script will:
1. Clear all global commands
2. Sync commands to your test guild for instant updates
3. List all registered commands

Run this when slash commands aren't showing up in Discord.
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

from discord_bot.integrations import load_config


async def main():
    # Load config
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
    print("DISCORD SLASH COMMAND SYNC")
    print("=" * 80)
    print(f"Test Guild IDs: {test_guild_ids}")
    print()
    
    # Create bot
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Logged in as {bot.user}")
        print()
        
        # Import all cogs to register commands
        print("📦 Loading cogs to register commands...")
        try:
            # Create a fresh IntegrationLoader and build the bot WITH cogs mounted
            from discord_bot.integrations.integration_loader import IntegrationLoader
            loader = IntegrationLoader()
            temp_bot, registry = loader.build()
            
            # Wait for cogs to mount
            await asyncio.sleep(2)
            
            # Copy the command tree from the fully configured bot
            bot.tree._guild_commands = temp_bot.tree._guild_commands
            bot.tree._global_commands = temp_bot.tree._global_commands
            
            print(f"   ✅ Loaded commands from fully configured bot")
            
            # Close the temp bot
            await temp_bot.close()
        except Exception as e:
            print(f"   ❌ Error loading application: {e}")
            import traceback
            traceback.print_exc()
            print(f"   Will sync empty command tree to clear old commands")
        
        print()
        print("=" * 80)
        print("STEP 1: Clear Global Commands")
        print("=" * 80)
        try:
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            print("✅ Cleared all global commands")
        except Exception as e:
            print(f"❌ Failed to clear global commands: {e}")
        
        print()
        
        if test_guild_ids:
            print("=" * 80)
            print("STEP 2: Sync to Test Guilds (Instant)")
            print("=" * 80)
            for guild_id in test_guild_ids:
                try:
                    guild = discord.Object(id=guild_id)
                    synced = await bot.tree.sync(guild=guild)
                    print(f"✅ Synced {len(synced)} commands to guild {guild_id}")
                    
                    # List commands
                    if synced:
                        print(f"   Commands:")
                        for cmd in synced:
                            print(f"      • /{cmd.name} - {cmd.description}")
                except Exception as e:
                    print(f"❌ Failed to sync guild {guild_id}: {e}")
        else:
            print("=" * 80)
            print("STEP 2: Sync Globally (May take up to 1 hour)")
            print("=" * 80)
            print("⚠️  No TEST_GUILDS set - syncing globally")
            print("    This can take up to 1 hour for Discord to propagate!")
            try:
                synced = await bot.tree.sync()
                print(f"✅ Synced {len(synced)} commands globally")
            except Exception as e:
                print(f"❌ Failed to sync globally: {e}")
        
        print()
        print("=" * 80)
        print("STEP 3: List All Registered Commands")
        print("=" * 80)
        
        # List global commands
        global_cmds = bot.tree.get_commands()
        if global_cmds:
            print(f"\n📌 Global Commands ({len(global_cmds)}):")
            for cmd in global_cmds:
                if isinstance(cmd, discord.app_commands.Group):
                    print(f"   📁 /{cmd.name} (Group)")
                    for subcmd in cmd.commands:
                        if isinstance(subcmd, discord.app_commands.Group):
                            print(f"      📁 {subcmd.name} (Subgroup)")
                            for subsubcmd in subcmd.commands:
                                print(f"         • {subsubcmd.name} - {subsubcmd.description}")
                        else:
                            print(f"      • {subcmd.name} - {subcmd.description}")
                else:
                    print(f"   • /{cmd.name} - {cmd.description}")
        else:
            print("   (No global commands)")
        
        # List guild-specific commands
        if test_guild_ids:
            for guild_id in test_guild_ids:
                guild = discord.Object(id=guild_id)
                guild_cmds = bot.tree.get_commands(guild=guild)
                if guild_cmds:
                    print(f"\n📌 Guild {guild_id} Commands ({len(guild_cmds)}):")
                    for cmd in guild_cmds:
                        if isinstance(cmd, discord.app_commands.Group):
                            print(f"   📁 /{cmd.name} (Group)")
                            for subcmd in cmd.commands:
                                if isinstance(subcmd, discord.app_commands.Group):
                                    print(f"      📁 {subcmd.name} (Subgroup)")
                                    for subsubcmd in subcmd.commands:
                                        print(f"         • {subsubcmd.name} - {subsubcmd.description}")
                                else:
                                    print(f"      • {subcmd.name} - {subcmd.description}")
                        else:
                            print(f"   • /{cmd.name} - {cmd.description}")
        
        print()
        print("=" * 80)
        print("✅ SYNC COMPLETE!")
        print("=" * 80)
        print()
        if test_guild_ids:
            print("Commands should appear IMMEDIATELY in your test guild(s).")
        else:
            print("Commands synced globally - may take up to 1 hour to appear.")
        print("Try typing '/' in Discord to see the command list.")
        print()
        
        await bot.close()
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
