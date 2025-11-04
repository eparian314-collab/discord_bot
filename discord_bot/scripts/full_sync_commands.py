"""
Proper command sync that loads all cogs before syncing.

This script:
1. Builds the full application stack (including all cogs)
2. Waits for setup_hook to complete (cogs are loaded)
3. Syncs commands to Discord
4. Verifies the sync was successful
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
from discord_bot.integrations import build_application


async def full_command_sync():
    """Perform a complete command sync with all cogs loaded."""
    print("🚀 Starting Full Command Sync")
    print("=" * 60)
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found in environment!")
        return
    
    # Build the full application stack
    print("\n🔧 Building application stack...")
    try:
        bot, registry = build_application()
        print("✅ Application stack built successfully")
    except Exception as e:
        print(f"❌ Failed to build application: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Override on_ready to perform sync and exit
    original_on_ready = bot.on_ready
    sync_complete = asyncio.Event()
    
    async def sync_on_ready():
        """Custom on_ready that syncs and reports."""
        try:
            # Call original on_ready first (which also syncs)
            await original_on_ready()
            
            # Give it a moment
            await asyncio.sleep(2)
            
            # Verify command tree
            print("\n📊 Verifying Command Tree:")
            print("=" * 60)
            
            commands = bot.tree.get_commands()
            print(f"\n🎯 Total top-level commands: {len(commands)}")
            
            for cmd in commands:
                if hasattr(cmd, '_children'):  # It's a group
                    print(f"\n📁 /{cmd.name} ({len(cmd._children)} children)")
                    for child_name, child in cmd._children.items():
                        if hasattr(child, '_children'):  # Subgroup
                            print(f"   └─ 📁 {child_name} ({len(child._children)} commands)")
                            for subchild_name in child._children.keys():
                                print(f"      └─ ⚡ /{cmd.name} {child_name} {subchild_name}")
                        else:
                            print(f"   └─ ⚡ /{cmd.name} {child_name}")
                else:
                    print(f"\n⚡ /{cmd.name}")
            
            # Check for KVK ranking specifically
            print("\n\n🎯 Checking KVK Ranking Commands:")
            print("=" * 60)
            kvk_cmd = discord.utils.get(commands, name="kvk")
            if kvk_cmd and hasattr(kvk_cmd, '_children'):
                if 'ranking' in kvk_cmd._children:
                    ranking_group = kvk_cmd._children['ranking']
                    if hasattr(ranking_group, '_children'):
                        print(f"✅ /kvk ranking subgroup found with {len(ranking_group._children)} commands:")
                        for cmd_name in ranking_group._children.keys():
                            print(f"   ✅ /kvk ranking {cmd_name}")
                    else:
                        print("⚠️  /kvk ranking subgroup exists but has no commands")
                else:
                    print("❌ /kvk ranking subgroup NOT FOUND in kvk children")
                    print(f"   Available: {list(kvk_cmd._children.keys())}")
            else:
                print("❌ /kvk group not found or has no children")
            
            # Check loaded cogs
            print("\n\n🔧 Loaded Cogs:")
            print("=" * 60)
            for cog_name in sorted(bot.cogs.keys()):
                print(f"✅ {cog_name}")
            
            print("\n\n✅ Command sync and verification complete!")
            print("\n💡 Next steps:")
            print("   1. Commands should appear in Discord within 1-10 minutes")
            print("   2. Try typing / in Discord to see if commands appear")
            print("   3. If not appearing, try restarting Discord client")
            print("   4. Check bot has application.commands scope in OAuth2")
            
        except Exception as e:
            print(f"\n❌ Error during sync verification: {e}")
            import traceback
            traceback.print_exc()
        finally:
            sync_complete.set()
    
    bot.on_ready = sync_on_ready
    
    # Start the bot
    try:
        print("\n🔌 Connecting to Discord...")
        async with asyncio.timeout(30):  # 30 second timeout
            task = asyncio.create_task(bot.start(token))
            await sync_complete.wait()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except asyncio.TimeoutError:
        print("\n❌ Timeout waiting for connection")
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if not bot.is_closed():
            await bot.close()
            print("\n🛑 Bot disconnected")


if __name__ == "__main__":
    asyncio.run(full_command_sync())
