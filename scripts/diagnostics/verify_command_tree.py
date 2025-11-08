"""
Command Tree Verification Script
Prints the actual command structure as Discord will see it.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from discord_bot.core import ui_groups
from discord_bot.cogs.ranking_cog import RankingCog
from discord import app_commands

def print_command_tree():
    """Display the command tree structure."""
    
    print("=" * 80)
    print("COMMAND TREE STRUCTURE ANALYSIS")
    print("=" * 80)
    print()
    
    # Top-level groups
    print("📦 TOP-LEVEL GROUPS (from ui_groups.py)")
    print("-" * 80)
    for group_name in ['language', 'games', 'kvk', 'admin']:
        group = getattr(ui_groups, group_name, None)
        if group:
            print(f"  /{group.name:<20} - {group.description}")
    print()
    
    # KVK subgroup structure
    print("📦 KVK SUBGROUP STRUCTURE (from RankingCog)")
    print("-" * 80)
    
    # Get the ranking subgroup from RankingCog class definition
    ranking_group = None
    for attr_name in dir(RankingCog):
        attr = getattr(RankingCog, attr_name)
        if isinstance(attr, app_commands.Group) and attr.name == "ranking":
            ranking_group = attr
            break
    
    if ranking_group:
        parent_name = getattr(ranking_group.parent, 'name', None) if ranking_group.parent else None
        if parent_name:
            print(f"  /{parent_name} {ranking_group.name:<15} - {ranking_group.description}")
            print(f"    Parent: /{parent_name}")
            print()
            print("    Subcommands under /kvk ranking:")
            
            # Get all commands decorated with @ranking.command
            for attr_name in dir(RankingCog):
                attr = getattr(RankingCog, attr_name)
                if isinstance(attr, app_commands.Command):
                    # Check if it's bound to the ranking group
                    if hasattr(attr, 'parent') and attr.parent == ranking_group:
                        print(f"      /{parent_name} {ranking_group.name} {attr.name:<20} - {attr.description}")
        else:
            print("  (No parent - this would be a root-level group)")
    else:
        print("  ⚠️ Could not find 'ranking' subgroup")
    
    print()
    
    # Root-level commands from RankingCog
    print("📦 ROOT-LEVEL COMMANDS (from RankingCog)")
    print("-" * 80)
    
    root_commands = []
    for attr_name in dir(RankingCog):
        attr = getattr(RankingCog, attr_name)
        if isinstance(attr, app_commands.Command):
            # Root commands have no parent or their parent is not a Group
            if not hasattr(attr, 'parent') or attr.parent is None:
                root_commands.append((attr.name, attr.description))
    
    if root_commands:
        for cmd_name, cmd_desc in sorted(root_commands):
            print(f"  /{cmd_name:<30} - {cmd_desc}")
    else:
        print("  (None found)")
    
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print("Expected Discord UI:")
    print("  - /kvk (group)")
    print("    - /kvk ranking (subgroup)")
    print("      - /kvk ranking submit")
    print("      - /kvk ranking view")
    print("      - /kvk ranking leaderboard")
    print("      - ... (other ranking subcommands)")
    print("  - /rankings (standalone command)")
    print("  - /ranking_compare_me (standalone command)")
    print("  - /ranking_compare_others (standalone command)")
    print()

if __name__ == "__main__":
    print_command_tree()
