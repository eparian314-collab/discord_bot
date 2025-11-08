"""
PHASE 2 - Command Scope Inventory Diagnostic

This script fetches and compares:
- GLOBAL commands
- GUILD commands (for configured test guild)
- Identifies duplicates appearing in both scopes
- Marks global copies as stale
- Generates a comprehensive report for schema analysis

Usage:
    python scripts/diagnostics/command_sync_diagnostic.py

Prerequisites:
    - DISCORD_TOKEN must be set in environment or config.json
    - TEST_GUILDS must be set to at least one guild ID
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure parent directory is in path
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import discord
from discord import app_commands

from discord_bot.integrations import load_config


def serialize_command(cmd: app_commands.AppCommand) -> Dict[str, Any]:
    """Serialize a command to a JSON-friendly format."""
    payload = cmd.to_dict()
    return {
        "id": str(cmd.id),
        "name": cmd.name,
        "type": cmd.type.value if hasattr(cmd.type, 'value') else cmd.type,
        "description": cmd.description,
        "options": payload.get("options", []),
        "default_member_permissions": payload.get("default_member_permissions"),
        "dm_permission": payload.get("dm_permission", True),
    }


def command_signature(cmd_dict: Dict[str, Any]) -> str:
    """Generate a signature for a command for comparison."""
    # Use name and type for matching
    return f"{cmd_dict['name']}::{cmd_dict['type']}"


async def fetch_global_commands(client: discord.Client) -> List[Dict[str, Any]]:
    """Fetch all global commands."""
    print("\n[PHASE 2.1] Fetching GLOBAL commands...")
    try:
        commands = await client.application.fetch_global_commands()
        serialized = [serialize_command(cmd) for cmd in commands]
        print(f"✅ Found {len(serialized)} global commands")
        return serialized
    except Exception as e:
        print(f"❌ Error fetching global commands: {e}")
        return []


async def fetch_guild_commands(client: discord.Client, guild_id: int) -> List[Dict[str, Any]]:
    """Fetch all guild-specific commands."""
    print(f"\n[PHASE 2.2] Fetching GUILD commands for guild {guild_id}...")
    try:
        guild = discord.Object(id=guild_id)
        commands = await client.application.fetch_guild_commands(guild=guild)
        serialized = [serialize_command(cmd) for cmd in commands]
        print(f"✅ Found {len(serialized)} guild commands")
        return serialized
    except Exception as e:
        print(f"❌ Error fetching guild commands: {e}")
        return []


def compare_command_lists(
    global_cmds: List[Dict[str, Any]],
    guild_cmds: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compare global and guild commands to identify duplicates."""
    print("\n[PHASE 2.3] Comparing command scopes...")
    
    global_sigs = {command_signature(cmd): cmd for cmd in global_cmds}
    guild_sigs = {command_signature(cmd): cmd for cmd in guild_cmds}
    
    # Find duplicates (commands in both global and guild)
    duplicate_sigs = set(global_sigs.keys()) & set(guild_sigs.keys())
    
    # Commands only in global
    global_only_sigs = set(global_sigs.keys()) - set(guild_sigs.keys())
    
    # Commands only in guild
    guild_only_sigs = set(guild_sigs.keys()) - set(global_sigs.keys())
    
    results = {
        "duplicates": [
            {
                "signature": sig,
                "global": global_sigs[sig],
                "guild": guild_sigs[sig],
            }
            for sig in sorted(duplicate_sigs)
        ],
        "global_only": [global_sigs[sig] for sig in sorted(global_only_sigs)],
        "guild_only": [guild_sigs[sig] for sig in sorted(guild_only_sigs)],
    }
    
    print("📊 Analysis complete:")
    print(f"   - Duplicates (in both scopes): {len(results['duplicates'])}")
    print(f"   - Global only: {len(results['global_only'])}")
    print(f"   - Guild only: {len(results['guild_only'])}")
    
    return results


def print_detailed_report(comparison: Dict[str, Any]) -> None:
    """Print a detailed report of the comparison."""
    print("\n" + "="*80)
    print("DETAILED COMPARISON REPORT")
    print("="*80)
    
    if comparison["duplicates"]:
        print("\n⚠️  DUPLICATE COMMANDS (present in both GLOBAL and GUILD):")
        print("   These are STALE global commands that should be removed!")
        for dup in comparison["duplicates"]:
            print(f"\n   - {dup['signature']}")
            print(f"     Global ID: {dup['global']['id']}")
            print(f"     Guild ID:  {dup['guild']['id']}")
    
    if comparison["global_only"]:
        print("\n🌐 GLOBAL-ONLY commands:")
        for cmd in comparison["global_only"]:
            print(f"   - {cmd['name']} (ID: {cmd['id']})")
    
    if comparison["guild_only"]:
        print("\n🏠 GUILD-ONLY commands:")
        for cmd in comparison["guild_only"]:
            print(f"   - {cmd['name']} (ID: {cmd['id']})")


async def run_diagnostic():
    """Main diagnostic runner."""
    print("="*80)
    print("PHASE 2 - COMMAND SCOPE INVENTORY DIAGNOSTIC")
    print("="*80)
    
    # Load config
    try:
        load_config()
    except Exception as e:
        print(f"Warning: load_config() failed: {e}")
    
    # Get token and test guild
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!")
        return
    
    test_guilds_raw = os.getenv("TEST_GUILDS", "")
    if not test_guilds_raw:
        print("❌ TEST_GUILDS not set!")
        return
    
    try:
        # Parse first test guild ID
        test_guild_id = int(test_guilds_raw.split(",")[0].strip())
    except ValueError:
        print(f"❌ Invalid TEST_GUILDS value: {test_guilds_raw}")
        return
    
    print("\n📋 Configuration:")
    print(f"   - Test Guild ID: {test_guild_id}")
    
    # Create client
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"\n✅ Logged in as {client.user}")
        
        try:
            # Fetch commands
            global_cmds = await fetch_global_commands(client)
            guild_cmds = await fetch_guild_commands(client, test_guild_id)
            
            # Compare
            comparison = compare_command_lists(global_cmds, guild_cmds)
            
            # Print report
            print_detailed_report(comparison)
            
            # Save to file
            output_file = Path(_project_root) / "logs" / "diagnostics" / "command_scope_inventory.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "global_commands": global_cmds,
                    "guild_commands": guild_cmds,
                    "comparison": comparison,
                    "test_guild_id": test_guild_id,
                }, f, indent=2)
            
            print(f"\n💾 Full report saved to: {output_file}")
            
        except Exception as e:
            print(f"\n❌ Diagnostic failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await client.close()
    
    # Run client
    await client.start(token)


if __name__ == "__main__":
    asyncio.run(run_diagnostic())
