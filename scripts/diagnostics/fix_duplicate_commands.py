"""
Fix Duplicate Slash Commands

This script clears ALL Discord slash commands and forces a fresh sync.
Use this when you see duplicate commands in Discord.
"""
import os
import sys
import asyncio

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("❌ DISCORD_TOKEN not found in environment")
    sys.exit(1)

async def clear_and_resync():
    """Clear all commands and force a fresh sync."""
    
    # Create minimal bot instance
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Logged in as {bot.user}")
        print(f"📊 Connected to {len(bot.guilds)} guilds")
        print()
        
        try:
            # Step 1: Clear global commands
            print("🗑️  Clearing global commands...")
            bot.tree.clear_commands(guild=None)
            synced_global = await bot.tree.sync()
            print(f"✅ Global commands cleared ({len(synced_global)} remaining)")
            print()
            
            # Step 2: Clear guild-specific commands
            for guild in bot.guilds:
                print(f"🗑️  Clearing commands for guild: {guild.name} ({guild.id})")
                bot.tree.clear_commands(guild=guild)
                try:
                    synced_guild = await bot.tree.sync(guild=guild)
                    print(f"   ✅ Cleared ({len(synced_guild)} remaining)")
                except Exception as e:
                    print(f"   ⚠️  Error: {e}")
            
            print()
            print("=" * 80)
            print("✅ ALL COMMANDS CLEARED")
            print("=" * 80)
            print()
            print("Next steps:")
            print("1. Close this script (Ctrl+C)")
            print("2. Restart your main bot")
            print("3. Bot will re-sync commands on startup")
            print("4. Wait 5-10 minutes for Discord to update")
            print()
            print("If you still see duplicates after 10 minutes:")
            print("- Try /hippo (or any command) to force Discord to refresh")
            print("- Restart your Discord client")
            print("- Clear Discord cache: %AppData%\\discord\\Cache")
            print()
            
        except Exception as e:
            print(f"❌ Error during sync: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await bot.close()
    
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    print("=" * 80)
    print("DUPLICATE COMMAND FIXER")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This will delete ALL slash commands!")
    print("You'll need to restart your bot to re-register them.")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response != "yes":
        print("❌ Cancelled")
        sys.exit(0)
    
    print()
    print("🚀 Starting command clear...")
    print()
    
    try:
        asyncio.run(clear_and_resync())
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
