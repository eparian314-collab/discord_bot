"""
Real-time Discord command tree diagnostic.
This connects to the actual bot process to see what Discord sees.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# This requires the bot to be running - let's check the tree structure without running
from discord_bot.core import ui_groups
from discord_bot.cogs.ranking_cog import RankingCog
from discord_bot.cogs.event_management_cog import EventManagementCog
from discord import app_commands

print("=" * 80)
print("DUPLICATE /KVK INVESTIGATION")
print("=" * 80)
print()

# Check ui_groups.kvk
print("1. UI_GROUPS.KVK GROUP:")
print(f"   Name: {ui_groups.kvk.name}")
print(f"   ID: {id(ui_groups.kvk)}")
print(f"   Parent: {ui_groups.kvk.parent}")
print()

# Check RankingCog.ranking
print("2. RANKINGCOG.RANKING SUBGROUP:")
print(f"   Name: {RankingCog.ranking.name}")
print(f"   ID: {id(RankingCog.ranking)}")
print(f"   Parent: {RankingCog.ranking.parent}")
print(f"   Parent Name: {RankingCog.ranking.parent.name if RankingCog.ranking.parent else None}")
print(f"   Parent ID: {id(RankingCog.ranking.parent) if RankingCog.ranking.parent else None}")
print(f"   Same as ui_groups.kvk? {RankingCog.ranking.parent is ui_groups.kvk}")
print()

# Check EventManagementCog
print("3. EVENT_MANAGEMENT_COG:")
event_cog_attrs = []
for attr_name in dir(EventManagementCog):
    if attr_name.startswith('_'):
        continue
    attr = getattr(EventManagementCog, attr_name)
    if isinstance(attr, app_commands.Command):
        event_cog_attrs.append(f"   @app_commands.command: {attr.name}")
    elif isinstance(attr, app_commands.Group):
        event_cog_attrs.append(f"   Group: {attr.name} (parent: {attr.parent.name if attr.parent else 'None'})")

if event_cog_attrs:
    print("\n".join(event_cog_attrs))
else:
    print("   No command groups found")
print()

# Check all cogs for Groups
print("4. SCANNING ALL COGS FOR app_commands.Group:")
import discord_bot.cogs as cogs_module
import inspect
import importlib
import pkgutil

cog_classes = []
for importer, modname, ispkg in pkgutil.iter_modules(cogs_module.__path__):
    try:
        module = importlib.import_module(f"discord_bot.cogs.{modname}")
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.endswith('Cog'):
                cog_classes.append((modname, name, obj))
    except Exception as e:
        print(f"   Error loading {modname}: {e}")

found_groups = []
for modname, cogname, cogclass in cog_classes:
    for attr_name in dir(cogclass):
        if attr_name.startswith('_'):
            continue
        try:
            attr = getattr(cogclass, attr_name)
            if isinstance(attr, app_commands.Group):
                parent_name = attr.parent.name if attr.parent else "None"
                parent_id = id(attr.parent) if attr.parent else "N/A"
                found_groups.append({
                    'cog': cogname,
                    'group_name': attr.name,
                    'parent': parent_name,
                    'parent_id': parent_id,
                    'group_id': id(attr)
                })
        except:
            pass

if found_groups:
    for g in found_groups:
        print(f"   {g['cog']}.{g['group_name']}")
        print(f"      Parent: {g['parent']} (ID: {g['parent_id']})")
        print(f"      Group ID: {g['group_id']}")
else:
    print("   No Groups found in cogs")

print()
print("5. HYPOTHESIS:")
print("   If you see TWO /kvk entries in Discord:")
print("   A. Bot.tree.add_command(kvk) is being called TWICE")
print("   B. OR a cog is manually adding kvk again")
print("   C. OR Discord is caching an old sync")
print()
print("   Check integration_loader.py line 800 - is it called multiple times?")
print("   Check if any cog's setup() function calls bot.tree.add_command(ui_groups.kvk)")
print()
print("=" * 80)
