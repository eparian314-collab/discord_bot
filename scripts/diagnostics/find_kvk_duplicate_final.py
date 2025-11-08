"""
Final diagnostic to identify the duplicate /kvk registration.
"""
import sys
sys.path.insert(0, 'c:/discord_bot')

from discord_bot.core import ui_groups
from discord import app_commands

print("=" * 80)
print("FINAL DUPLICATE /KVK DIAGNOSTIC")
print("=" * 80)
print()

# Check if ui_groups.kvk is being modified or if there's a second Group object

print("1. UI_GROUPS.KVK OBJECT:")
print(f"   ID: {id(ui_groups.kvk)}")
print(f"   Name: {ui_groups.kvk.name}")
print(f"   Parent: {ui_groups.kvk.parent}")
print()

# Import all cogs and check for kvk-related attributes
from discord_bot.cogs.ranking_cog import RankingCog
from discord_bot.cogs.event_management_cog import EventManagementCog
from discord_bot.cogs.admin_cog import AdminCog

print("2. RANKINGCOG:")
print(f"   ranking.name: {RankingCog.ranking.name}")
print(f"   ranking.parent: {RankingCog.ranking.parent}")
print(f"   ranking.parent ID: {id(RankingCog.ranking.parent) if RankingCog.ranking.parent else 'None'}")
print(f"   parent is ui_groups.kvk? {RankingCog.ranking.parent is ui_groups.kvk}")
print()

print("3. EVENT_MANAGEMENT_COG:")
# Check if EventManagementCog has any kvk-related attributes
has_kvk_attr = hasattr(EventManagementCog, 'kvk')
if has_kvk_attr:
    kvk_attr = getattr(EventManagementCog, 'kvk')
    print("   HAS KVK ATTRIBUTE!")
    print(f"   kvk ID: {id(kvk_attr)}")
    print(f"   kvk name: {kvk_attr.name if hasattr(kvk_attr, 'name') else 'N/A'}")
    print(f"   Same as ui_groups.kvk? {kvk_attr is ui_groups.kvk}")
else:
    print("   No kvk attribute")
print()

print("4. ADMIN_COG:")
print(f"   admin.name: {AdminCog.admin.name}")
print(f"   admin ID: {id(AdminCog.admin)}")
print(f"   Same as ui_groups.admin? {AdminCog.admin is ui_groups.admin}")
print()

# The smoking gun: check if there's a second 'kvk' Group being created
print("5. THEORY:")
print("   If Discord shows TWO /kvk entries, one of these is true:")
print("   A. register_command_groups() is called TWICE")
print("   B. A cog creates its own 'kvk' Group (not referencing ui_groups.kvk)")
print("   C. A cog has 'kvk = ui_groups.kvk' as class attr AND it gets auto-registered")
print()

# Check if RankingCog or EventManagementCog have kvk as a class attribute
print("6. CHECKING FOR DUPLICATE GROUP REFERENCES:")
for cog_name, cog_class in [("RankingCog", RankingCog), ("EventManagementCog", EventManagementCog)]:
    for attr_name in ['kvk', 'ranking']:
        if hasattr(cog_class, attr_name):
            attr = getattr(cog_class, attr_name)
            if isinstance(attr, app_commands.Group):
                print(f"   {cog_name}.{attr_name}:")
                print(f"      Name: {attr.name}")
                print(f"      ID: {id(attr)}")
                if attr.parent:
                    print(f"      Parent: {attr.parent.name} (ID: {id(attr.parent)})")
                    print(f"      Parent is ui_groups.kvk? {attr.parent is ui_groups.kvk}")
                else:
                    print("      Parent: None")
                    print(f"      IS THIS A DUPLICATE TOP-LEVEL /KVK? {attr.name == 'kvk'}")
print()

print("=" * 80)
print("DIAGNOSIS:")
print("If a cog has a Group named 'kvk' with parent=None, that's your duplicate!")
print("=" * 80)
