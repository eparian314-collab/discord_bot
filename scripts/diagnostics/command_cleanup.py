"""
PHASE 4 - One-Time Cleanup Script

This script safely:
1. Deletes ALL global slash commands (removing stale signatures)
2. Re-syncs commands ONLY to configured TEST_GUILDS
3. Verifies cleanup success
4. Generates a cleanup report

⚠️ WARNING: This will remove all global commands. Only run this if:
   - You intend to use guild-only sync for development
   - You have TEST_GUILDS properly configured
   - You understand this affects ALL servers the bot is in

Usage:
    python scripts/diagnostics/command_cleanup.py
    
    Or with confirmation skip:
    python scripts/diagnostics/command_cleanup.py --force

Prerequisites:
    - DISCORD_TOKEN must be set
    - TEST_GUILDS must be set to at least one guild ID
    - Bot must have proper permissions in the test guild
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

# Ensure parent directory is in path
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import discord
from discord_bot.integrations import load_config


async def cleanup_global_commands(client: discord.Client) -> List[str]:
    """Delete all global commands and return list of deleted command names."""
    print("\n[PHASE 4.1] Fetching global commands...")
    try:
        commands = await client.application.fetch_global_commands()
        print(f"Found {len(commands)} global commands")
        
        if not commands:
            print("✅ No global commands to clean up")
            return []
        
        deleted = []
        for cmd in commands:
            try:
                await cmd.delete()
                print(f"  ✅ Deleted: /{cmd.name} (ID: {cmd.id})")
                deleted.append(cmd.name)
            except Exception as e:
                print(f"  ❌ Failed to delete /{cmd.name}: {e}")
        
        print(f"\n✅ Deleted {len(deleted)} of {len(commands)} global commands")
        return deleted
        
    except Exception as e:
        print(f"❌ Error during global command cleanup: {e}")
        return []


async def sync_guild_commands(client: discord.Client, guild_id: int) -> int:
    """Sync commands to a specific guild and return count of synced commands."""
    print(f"\n[PHASE 4.2] Syncing commands to guild {guild_id}...")
    try:
        guild = discord.Object(id=guild_id)
        synced = await client.application.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {guild_id}")
        for cmd in synced:
            print(f"  - /{cmd.name}")
        return len(synced)
    except Exception as e:
        print(f"❌ Error syncing to guild {guild_id}: {e}")
        return 0


async def verify_cleanup(client: discord.Client, guild_ids: List[int]) -> Dict[str, Any]:
    """Verify that global commands are gone and guild commands are present."""
    print("\n[PHASE 4.3] Verifying cleanup...")
    
    # Check global commands
    try:
        global_cmds = await client.application.fetch_global_commands()
        global_count = len(global_cmds)
        if global_count == 0:
            print("✅ No global commands remaining (expected)")
        else:
            print(f"⚠️  WARNING: {global_count} global commands still exist!")
            for cmd in global_cmds:
                print(f"  - /{cmd.name} (ID: {cmd.id})")
    except Exception as e:
        print(f"❌ Error checking global commands: {e}")
        global_count = -1
    
    # Check guild commands
    guild_results = {}
    for guild_id in guild_ids:
        try:
            guild = discord.Object(id=guild_id)
            guild_cmds = await client.application.fetch_guild_commands(guild=guild)
            guild_count = len(guild_cmds)
            guild_results[guild_id] = guild_count
            print(f"✅ Guild {guild_id}: {guild_count} commands")
        except Exception as e:
            print(f"❌ Error checking guild {guild_id}: {e}")
            guild_results[guild_id] = -1
    
    return {
        "global_commands": global_count,
        "guild_commands": guild_results,
    }


async def run_cleanup(force: bool = False):
    """Main cleanup runner."""
    print("="*80)
    print("PHASE 4 - ONE-TIME COMMAND CLEANUP")
    print("="*80)
    
    # Load config
    try:
        load_config()
    except Exception as e:
        print(f"Warning: load_config() failed: {e}")
    
    # Get token and test guilds
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!")
        return
    
    test_guilds_raw = os.getenv("TEST_GUILDS", "")
    if not test_guilds_raw:
        print("❌ TEST_GUILDS not set!")
        return
    
    try:
        # Parse all test guild IDs
        guild_ids = [int(gid.strip()) for gid in test_guilds_raw.split(",") if gid.strip()]
    except ValueError:
        print(f"❌ Invalid TEST_GUILDS value: {test_guilds_raw}")
        return
    
    if not guild_ids:
        print("❌ No valid guild IDs found in TEST_GUILDS")
        return
    
    print("\n📋 Configuration:")
    print(f"   - Test Guild IDs: {guild_ids}")
    
    # Confirmation prompt
    if not force:
        print("\n⚠️  WARNING: This will DELETE ALL GLOBAL commands!")
        print("   Commands will be re-synced to test guilds only.")
        print("   This operation cannot be undone.")
        response = input("\nType 'DELETE' to confirm: ")
        if response != "DELETE":
            print("❌ Cleanup cancelled")
            return
    
    # Create client
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    
    cleanup_results = {}
    
    @client.event
    async def on_ready():
        nonlocal cleanup_results
        
        print(f"\n✅ Logged in as {client.user}")
        
        try:
            # Step 1: Delete global commands
            deleted_commands = await cleanup_global_commands(client)
            
            # Step 2: Sync to guild(s)
            synced_counts = {}
            for guild_id in guild_ids:
                count = await sync_guild_commands(client, guild_id)
                synced_counts[guild_id] = count
            
            # Step 3: Verify
            verification = await verify_cleanup(client, guild_ids)
            
            # Compile results
            cleanup_results = {
                "timestamp": datetime.utcnow().isoformat(),
                "deleted_global_commands": deleted_commands,
                "synced_guild_commands": synced_counts,
                "verification": verification,
                "success": verification["global_commands"] == 0 and all(v > 0 for v in verification["guild_commands"].values()),
            }
            
            # Save report
            output_file = Path(_project_root) / "logs" / "diagnostics" / "command_cleanup_report.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(cleanup_results, f, indent=2)
            
            print(f"\n💾 Cleanup report saved to: {output_file}")
            
            if cleanup_results["success"]:
                print("\n✅ ✅ ✅ CLEANUP SUCCESSFUL ✅ ✅ ✅")
                print("   - All global commands removed")
                print("   - Guild commands synced")
                print("   - Bot is now in guild-only sync mode")
                print("\nNext steps:")
                print("   1. Restart the bot to ensure clean state")
                print("   2. Test commands in Discord")
                print("   3. Verify no CommandSignatureMismatch errors")
            else:
                print("\n⚠️  CLEANUP INCOMPLETE")
                print("   Check the report for details")
            
        except Exception as e:
            print(f"\n❌ Cleanup failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await client.close()
    
    # Run client
    try:
        await client.start(token)
    except KeyboardInterrupt:
        print("\n⏹️  Cleanup interrupted by user")


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(run_cleanup(force))
