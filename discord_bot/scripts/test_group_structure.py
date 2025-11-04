"""
Test if command groups are properly nested.
"""
import sys
from pathlib import Path

# Ensure parent directory is in path
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from discord import app_commands
from discord_bot.core import ui_groups

print("🔍 Testing Command Group Structure")
print("=" * 60)

# Check kvk group
print(f"\n📁 KVK Group:")
print(f"   Name: {ui_groups.kvk.name}")
print(f"   Description: {ui_groups.kvk.description}")
print(f"   Has parent: {ui_groups.kvk.parent is not None}")
print(f"   Children: {list(ui_groups.kvk._children.keys()) if hasattr(ui_groups.kvk, '_children') else 'No _children attribute'}")

# Now create a ranking subgroup like in ranking_cog.py
test_ranking = app_commands.Group(
    name=ui_groups.KVK_RANKING_NAME,
    description=ui_groups.KVK_RANKING_DESCRIPTION,
    parent=ui_groups.kvk,
)

print(f"\n📁 Test Ranking Subgroup:")
print(f"   Name: {test_ranking.name}")
print(f"   Description: {test_ranking.description}")
print(f"   Parent: {test_ranking.parent}")
print(f"   Parent name: {test_ranking.parent.name if test_ranking.parent else 'None'}")

# Check if it's in the kvk children
print(f"\n🔗 After creating subgroup, KVK children:")
print(f"   {list(ui_groups.kvk._children.keys()) if hasattr(ui_groups.kvk, '_children') else 'No _children attribute'}")

# Try importing the actual ranking cog
try:
    from discord_bot.cogs.ranking_cog import RankingCog
    print(f"\n📁 RankingCog.ranking:")
    print(f"   Name: {RankingCog.ranking.name}")
    print(f"   Parent: {RankingCog.ranking.parent}")
    print(f"   Parent name: {RankingCog.ranking.parent.name if RankingCog.ranking.parent else 'None'}")
    print(f"   Same parent as ui_groups.kvk: {RankingCog.ranking.parent is ui_groups.kvk}")
    
    # Check kvk children again
    print(f"\n🔗 After importing RankingCog, KVK children:")
    print(f"   {list(ui_groups.kvk._children.keys()) if hasattr(ui_groups.kvk, '_children') else 'No _children attribute'}")
    
except Exception as e:
    print(f"\n❌ Error importing RankingCog: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ Test complete!")


