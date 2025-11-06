#!/usr/bin/env python3
"""
Slash Command Sync Script for EC2 Ubuntu Environment
Forces a complete sync of all slash commands to Discord.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def sync_commands():
    """Sync all slash commands to Discord."""
    
    # Get bot token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Error: DISCORD_TOKEN not found in environment variables")
        sys.exit(1)
    
    # Get optional guild configuration
    test_guilds = os.getenv("TEST_GUILDS", "")
    primary_guild_name = os.getenv("PRIMARY_GUILD_NAME", "").strip()
    sync_global = os.getenv("SYNC_GLOBAL_COMMANDS", "1").lower() not in {"0", "false", "no"}
    
    # Create bot instance with minimal setup
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
        print(f"📊 Connected to {len(bot.guilds)} guild(s)")
        
        # Determine sync targets
        targets = []
        should_sync_global = sync_global  # Copy to local scope to avoid UnboundLocalError
        
        if primary_guild_name:
            guild = discord.utils.find(lambda g: g.name.lower() == primary_guild_name.lower(), bot.guilds)
            if guild:
                targets.append((guild.id, guild.name))
                should_sync_global = False
                print(f"🎯 Target: Primary guild '{guild.name}' (ID: {guild.id})")
            else:
                print(f"⚠️  Warning: PRIMARY_GUILD_NAME '{primary_guild_name}' not found")
        elif test_guilds:
            for guild_id_str in test_guilds.replace(";", ",").split(","):
                guild_id_str = guild_id_str.strip()
                if guild_id_str:
                    try:
                        guild_id = int(guild_id_str)
                        guild = bot.get_guild(guild_id)
                        if guild:
                            targets.append((guild_id, guild.name))
                            print(f"🎯 Target: Test guild '{guild.name}' (ID: {guild_id})")
                        else:
                            print(f"⚠️  Warning: Test guild {guild_id} not accessible")
                    except ValueError:
                        print(f"⚠️  Warning: Invalid guild ID '{guild_id_str}'")
        
        # Perform sync
        synced_count = 0
        
        try:
            if should_sync_global:
                print("\n🌍 Syncing commands globally...")
                synced = await bot.tree.sync()
                synced_count += len(synced)
                print(f"✅ Synced {len(synced)} global command(s)")
                print("⏳ Note: Global commands may take up to 1 hour to propagate")
            
            if targets:
                print(f"\n🏢 Syncing commands to {len(targets)} guild(s)...")
                for guild_id, guild_name in targets:
                    try:
                        synced = await bot.tree.sync(guild=discord.Object(id=guild_id))
                        synced_count += len(synced)
                        print(f"✅ Synced {len(synced)} command(s) to '{guild_name}' (ID: {guild_id})")
                    except Exception as e:
                        print(f"❌ Failed to sync to '{guild_name}' (ID: {guild_id}): {e}")
            
            if not sync_global and not targets:
                print("⚠️  No sync targets configured. Set SYNC_GLOBAL_COMMANDS=1 or configure TEST_GUILDS/PRIMARY_GUILD_NAME")
            
            print(f"\n✅ Sync complete! Total commands synced: {synced_count}")
            
        except Exception as e:
            print(f"\n❌ Sync failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await bot.close()
    
    # Run bot
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n⚠️  Sync interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("🦛 HippoBot Slash Command Sync Script")
    print("=" * 60)
    
    try:
        asyncio.run(sync_commands())
    except KeyboardInterrupt:
        print("\n⚠️  Sync cancelled by user")
        sys.exit(1)
