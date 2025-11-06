"""
ONE-TIME COMMAND SANITIZER
Run this once to clean up duplicate commands (global + guild).
After successful run, DELETE THIS FILE.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import discord
from discord.ext import commands

# ========== CONFIGURATION ==========
DEV_GUILD_ID = 1423768684572184700  # mars._.3's server test2
# ===================================


async def sanitize_commands():
    """
    One-time command sanitizer:
    1. Deletes ALL global commands (usually the stale ones)
    2. Deletes ALL guild commands in dev guild
    3. Re-syncs ONLY guild-scoped commands from current code
    4. Verifies clean state
    """
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("❌ DISCORD_TOKEN not found in environment")
        return
    
    # Create bot instance
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print("=" * 80)
        print("🧹 ONE-TIME COMMAND SANITIZER")
        print("=" * 80)
        print(f"[SYNC] Connected as {bot.user}")
        print()
        
        guild_obj = discord.Object(id=DEV_GUILD_ID)
        
        # Step 0: Dump before-state
        print("📊 BEFORE STATE:")
        try:
            global_cmds = await bot.tree.fetch_commands()
            guild_cmds = await bot.tree.fetch_commands(guild=guild_obj)
            print(f"   Global commands: {len(global_cmds)}")
            print(f"   Guild commands: {len(guild_cmds)}")
            print()
            
            if global_cmds:
                print("   Global command list:")
                for cmd in global_cmds:
                    print(f"      - /{cmd.name} (ID: {cmd.id})")
            
            if guild_cmds:
                print(f"   Guild {DEV_GUILD_ID} command list:")
                for cmd in guild_cmds:
                    print(f"      - /{cmd.name} (ID: {cmd.id})")
            print()
        except Exception as e:
            print(f"⚠️ Error fetching current state: {e}")
            print()
        
        # Step 1: PURGE GLOBAL COMMANDS
        print("-" * 80)
        print("🗑️ STEP 1: Purging GLOBAL commands...")
        print("-" * 80)
        deleted_global = 0
        for cmd in global_cmds:
            try:
                await cmd.delete()
                print(f"   ✅ Deleted GLOBAL: /{cmd.name} (ID: {cmd.id})")
                deleted_global += 1
            except Exception as e:
                print(f"   ❌ Failed to delete GLOBAL {cmd.name}: {e}")
        
        print(f"\n   Total global commands deleted: {deleted_global}")
        print()
        
        # Step 2: PURGE GUILD COMMANDS
        print("-" * 80)
        print(f"🗑️ STEP 2: Purging GUILD commands (Guild {DEV_GUILD_ID})...")
        print("-" * 80)
        deleted_guild = 0
        for cmd in guild_cmds:
            try:
                await cmd.delete(guild=guild_obj)
                print(f"   ✅ Deleted GUILD: /{cmd.name} (ID: {cmd.id})")
                deleted_guild += 1
            except Exception as e:
                print(f"   ❌ Failed to delete GUILD {cmd.name}: {e}")
        
        print(f"\n   Total guild commands deleted: {deleted_guild}")
        print()
        
        # Wait for Discord to process deletions
        print("⏳ Waiting 3 seconds for Discord to process deletions...")
        await asyncio.sleep(3)
        print()
        
        # Step 3: REBUILD GUILD-SCOPED COMMANDS
        print("-" * 80)
        print(f"🔄 STEP 3: Rebuilding GUILD commands from current code...")
        print("-" * 80)
        
        # Load the bot's command tree structure
        # This requires importing the integration loader to set up groups
        try:
            from discord_bot.integrations.integration_loader import build_application
            
            # We need to rebuild the bot with proper structure
            print("   ⚠️ Note: This sanitizer doesn't load cogs.")
            print("   ⚠️ You need to restart the bot normally after this completes.")
            print()
            print("   Skipping sync - manual bot restart required.")
            print()
            
        except Exception as e:
            print(f"   ⚠️ Could not load integration loader: {e}")
            print("   This is expected - restart your bot normally to complete sync.")
            print()
        
        # Step 4: Verify clean state
        print("-" * 80)
        print("📊 AFTER STATE (verification):")
        print("-" * 80)
        try:
            global_after = await bot.tree.fetch_commands()
            guild_after = await bot.tree.fetch_commands(guild=guild_obj)
            
            print(f"   Global commands: {len(global_after)}")
            print(f"   Guild commands: {len(guild_after)}")
            
            if len(global_after) == 0 and len(guild_after) == 0:
                print()
                print("   ✅ PERFECT! All commands cleared.")
            else:
                print()
                print("   ⚠️ Some commands remain:")
                if global_after:
                    for cmd in global_after:
                        print(f"      Global: /{cmd.name}")
                if guild_after:
                    for cmd in guild_after:
                        print(f"      Guild: /{cmd.name}")
        except Exception as e:
            print(f"   ⚠️ Error checking after-state: {e}")
        
        print()
        print("=" * 80)
        print("✅ SANITIZE COMPLETE!")
        print("=" * 80)
        print()
        print("📋 NEXT STEPS:")
        print("   1. DELETE this sanitizer script (one-time use only)")
        print("   2. RESTART your bot normally:")
        print("      python main.py")
        print("   3. Bot will sync commands on startup")
        print("   4. VERIFY in Discord:")
        print("      - Type /kvk ranking submit")
        print("      - Should see NO duplicates")
        print("      - Command should execute cleanly")
        print()
        print("   5. If you still see duplicates:")
        print("      - Close and reopen Discord client (cache refresh)")
        print("      - Wait 30 seconds")
        print("      - Try again")
        print()
        
        await bot.close()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n⏹️ Sanitizer cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    print()
    print("⚠️" * 40)
    print("⚠️  ONE-TIME COMMAND SANITIZER")
    print("⚠️  This will DELETE all global and guild commands")
    print("⚠️  Then you must restart your bot normally to resync")
    print("⚠️" * 40)
    print()
    
    response = input("Type 'YES' to proceed with sanitization: ")
    
    if response.strip().upper() == "YES":
        print("\n🚀 Starting sanitization...")
        asyncio.run(sanitize_commands())
    else:
        print("\n❌ Sanitization cancelled")
