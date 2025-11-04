"""
Diagnostic script to check command tree structure and identify sync issues.
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

from discord_bot.integrations import build_application


async def diagnose():
    """Diagnose command tree structure."""
    print("🔍 Building application stack...")
    try:
        bot, registry = build_application()
        print(f"✅ Bot initialized: {bot.user if hasattr(bot, 'user') else 'not logged in yet'}")
        
        # Check command tree
        print("\n📊 Command Tree Analysis:")
        print("=" * 60)
        
        # Get all commands from the tree
        commands = bot.tree.get_commands()
        print(f"\n🎯 Total top-level commands: {len(commands)}")
        
        for cmd in commands:
            if isinstance(cmd, type(bot.tree._get_all_commands()[0])):  # Group
                print(f"\n📁 Group: /{cmd.name}")
                print(f"   Description: {cmd.description}")
                
                # Check for subcommands/subgroups
                if hasattr(cmd, '_children'):
                    children = cmd._children
                    print(f"   Children: {len(children)}")
                    for child_name, child in children.items():
                        if hasattr(child, '_children'):  # It's a subgroup
                            print(f"   └─ 📁 Subgroup: {child_name} ({len(child._children)} commands)")
                            for subchild_name in child._children.keys():
                                print(f"      └─ ⚡ /{cmd.name} {child_name} {subchild_name}")
                        else:
                            print(f"   └─ ⚡ /{cmd.name} {child_name}")
            else:
                print(f"\n⚡ Command: /{cmd.name}")
                print(f"   Description: {cmd.description}")
        
        # Check specific groups
        print("\n\n🎯 Checking Specific Groups:")
        print("=" * 60)
        
        # Check kvk group
        kvk_cmd = discord.utils.get(commands, name="kvk")
        if kvk_cmd:
            print("\n✅ /kvk group found")
            if hasattr(kvk_cmd, '_children'):
                print(f"   Subgroups/commands: {list(kvk_cmd._children.keys())}")
                
                # Check ranking subgroup
                if 'ranking' in kvk_cmd._children:
                    ranking_group = kvk_cmd._children['ranking']
                    print(f"\n✅ /kvk ranking subgroup found")
                    if hasattr(ranking_group, '_children'):
                        print(f"   Commands: {list(ranking_group._children.keys())}")
                else:
                    print("\n❌ /kvk ranking subgroup NOT FOUND")
        else:
            print("\n❌ /kvk group NOT FOUND")
        
        # Check games group
        games_cmd = discord.utils.get(commands, name="games")
        if games_cmd:
            print("\n✅ /games group found")
            if hasattr(games_cmd, '_children'):
                print(f"   Subgroups/commands: {list(games_cmd._children.keys())}")
        else:
            print("\n❌ /games group NOT FOUND")
        
        # Check language group
        language_cmd = discord.utils.get(commands, name="language")
        if language_cmd:
            print("\n✅ /language group found")
            if hasattr(language_cmd, '_children'):
                print(f"   Subgroups/commands: {list(language_cmd._children.keys())}")
        else:
            print("\n❌ /language group NOT FOUND")
        
        # Check for standalone ranking commands
        print("\n\n🔍 Checking for Standalone Ranking Commands:")
        print("=" * 60)
        standalone_ranking = [c for c in commands if 'ranking' in c.name.lower()]
        if standalone_ranking:
            for cmd in standalone_ranking:
                print(f"⚠️  Found standalone: /{cmd.name}")
        else:
            print("✅ No standalone ranking commands found")
        
        # Check cogs
        print("\n\n🔧 Loaded Cogs:")
        print("=" * 60)
        for cog_name, cog in bot.cogs.items():
            print(f"✅ {cog_name}")
            # Check if cog has commands
            cog_commands = [cmd for cmd in bot.tree.walk_commands() if hasattr(cmd, 'binding') and cmd.binding == cog]
            if cog_commands:
                print(f"   Commands: {len(cog_commands)}")
        
        print("\n\n💡 Recommendations:")
        print("=" * 60)
        
        if not kvk_cmd:
            print("❌ KVK group missing - check ui_groups.py registration")
        if kvk_cmd and 'ranking' not in getattr(kvk_cmd, '_children', {}):
            print("❌ Ranking subgroup not in KVK - check ranking_cog.py parent assignment")
        if standalone_ranking:
            print("⚠️  Standalone ranking commands found - these should be in /kvk ranking")
        
        print("\n✅ Diagnostic complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import discord
    asyncio.run(diagnose())


