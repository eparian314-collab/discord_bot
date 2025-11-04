"""
Force sync Discord slash commands.

This script will:
1. Clear the global command tree
2. Resync commands globally
3. Resync commands to test guilds if configured

Run this if you see "This command is outdated" errors.
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

# Load environment variables from .env file
from dotenv import load_dotenv
dotenv_path = _project_root / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    print("✅ Loaded .env file")
else:
    print("⚠️ .env file not found, relying on system environment variables.")


import discord
from discord.ext import commands
from core.bot_base import HippoBot


async def sync_commands():
    """Force sync all commands to Discord."""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found in environment!")
        return
    
    # Parse test guild IDs
    test_guilds_raw = os.getenv("TEST_GUILDS", "")
    test_guild_ids = []
    if test_guilds_raw:
        for chunk in test_guilds_raw.replace(";", ",").split(","):
            token_id = chunk.strip()
            if token_id:
                try:
                    test_guild_ids.append(int(token_id))
                except ValueError:
                    pass
    
    # Create minimal bot
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Logged in as {bot.user}")
        
        try:
            # Clear global commands first
            print("🧹 Clearing global commands...")
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            print("✅ Global commands cleared")
            
            # Sync to test guilds if configured
            if test_guild_ids:
                print(f"🔄 Syncing to {len(test_guild_ids)} test guild(s)...")
                for guild_id in test_guild_ids:
                    guild_obj = discord.Object(id=guild_id)
                    bot.tree.clear_commands(guild=guild_obj)
                    synced = await bot.tree.sync(guild=guild_obj)
                    print(f"✅ Synced {len(synced)} commands to guild {guild_id}")
            else:
                # Sync globally
                print("🔄 Syncing commands globally...")
                synced = await bot.tree.sync()
                print(f"✅ Synced {len(synced)} commands globally")
            
            print("\n✨ Command sync complete!")
            print("⏳ Wait 5-10 minutes for Discord to propagate the changes.")
            print("💡 If commands still show as outdated, try:\n")
            print("   1. Restart Discord completely")
            print("   2. Clear Discord cache (Settings > Advanced > Clear Cache)")
            print("   3. Right-click the server icon > 'Reload Server'")
            
        except Exception as e:
            print(f"❌ Error during sync: {e}")
        finally:
            await bot.close()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    print("🚀 Discord Command Sync Tool")
    print("=" * 50)
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(sync_commands())
