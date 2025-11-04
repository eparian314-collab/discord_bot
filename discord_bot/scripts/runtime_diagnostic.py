"""
Runtime diagnostic - run the bot briefly to check for errors.
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

from discord_bot.integrations import build_application, load_config


async def runtime_diagnostic():
    """Run bot briefly and check for errors."""
    print("🔍 Runtime Diagnostic")
    print("=" * 60)
    
    # Load configuration first
    print("\n📋 Loading configuration...")
    try:
        injected = load_config()
        print(f"✅ Config loaded ({len(injected)} JSON keys injected)")
    except Exception as e:
        print(f"⚠️  Config load warning: {e}")
        injected = {}
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found!")
        return
    
    print("\n🔧 Building application...")
    try:
        bot, registry = build_application()
        print("✅ Application built")
    except Exception as e:
        print(f"❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check environment
    print("\n🌍 Environment Check:")
    print(f"   RANKINGS_CHANNEL_ID: {os.getenv('RANKINGS_CHANNEL_ID', 'NOT SET')}")
    print(f"   OCR_PROVIDER: {os.getenv('OCR_PROVIDER', 'NOT SET')}")
    print(f"   DB_PATH: {os.getenv('DB_PATH', 'NOT SET')}")
    print(f"   TIMEZONE: {os.getenv('TIMEZONE', 'NOT SET')}")
    print(f"   LOG_LEVEL: {os.getenv('LOG_LEVEL', 'NOT SET')}")
    
    # Check bot attributes
    print("\n🤖 Bot Attributes:")
    print(f"   kvk_tracker: {hasattr(bot, 'kvk_tracker') and bot.kvk_tracker is not None}")
    print(f"   ranking_storage: {hasattr(bot, 'ranking_storage') and bot.ranking_storage is not None}")
    print(f"   ranking_processor: {hasattr(bot, 'ranking_processor') and bot.ranking_processor is not None}")
    
    # Check cog
    print("\n📦 Checking RankingCog:")
    ranking_cog = bot.get_cog("RankingCog")
    if ranking_cog:
        print(f"   ✅ RankingCog loaded")
        print(f"   Rankings channel ID: {ranking_cog._rankings_channel_id}")
        print(f"   Has processor: {ranking_cog.processor is not None}")
        print(f"   Has storage: {ranking_cog.storage is not None}")
        print(f"   Has kvk_tracker: {ranking_cog.kvk_tracker is not None}")
        
        # Check ranking group
        if hasattr(ranking_cog, 'ranking'):
            print(f"   ✅ Ranking group exists")
            print(f"   Parent: {ranking_cog.ranking.parent.name if ranking_cog.ranking.parent else 'None'}")
            print(f"   Commands: {list(ranking_cog.ranking._children.keys()) if hasattr(ranking_cog.ranking, '_children') else []}")
        else:
            print(f"   ❌ Ranking group missing!")
    else:
        print(f"   ❌ RankingCog NOT loaded!")
    
    # Check registry
    print("\n📊 Engine Registry:")
    status = registry.status()
    for name, info in sorted(status.items()):
        ready = "✅" if info.get("ready") else "⏳"
        waiting_for = info.get("waiting_for", [])
        if waiting_for:
            print(f"   {ready} {name} (waiting: {', '.join(waiting_for)})")
        else:
            print(f"   {ready} {name}")
    
    print("\n✅ Diagnostic complete!")
    print("\n💡 If everything looks good, the bot should work.")
    print("   Commands are synced and will appear in Discord within 1-10 minutes.")
    

if __name__ == "__main__":
    asyncio.run(runtime_diagnostic())
